param([ValidateSet('Preflight','InstallBaseline','Install','Upgrade','VerifyPending','Uninstall')][string]$Stage='Preflight')
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$projectRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$resultRoot=[IO.Path]::GetFullPath((Join-Path $projectRoot 'artifacts/test-results/M20'))
$installRoot=[IO.Path]::GetFullPath((Join-Path $resultRoot 'install-smoke'))
$recordPath=Join-Path $resultRoot 'installation.json'
$executable=Join-Path $installRoot 'Orvia M20 Full Test.exe'
$uninstaller=Join-Path $installRoot 'Uninstall Orvia M20 Full Test.exe'
$shortcut=Join-Path ([Environment]::GetFolderPath('Programs')) 'Orvia M20 Full Test.lnk'
$testProfile=Join-Path $resultRoot 'upgrade-profile'
$appId='cn.orvia.m20.fulltest'
if(-not $installRoot.StartsWith($resultRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw '安装目标越界'}

function Assert-NoReparse([string]$Target){
    # 固定本仓库测试路径及已有祖先不能通过junction转向正常安装或个人配置。
    for($cursor=$Target;$cursor;$cursor=[IO.Path]::GetDirectoryName($cursor)){
        if((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw '验收路径含重解析点'}
    }
}
function Get-TestInstallations{
    foreach($hive in @('HKCU','HKLM')){
        foreach($branch in @('Software/Microsoft/Windows/CurrentVersion/Uninstall','Software/WOW6432Node/Microsoft/Windows/CurrentVersion/Uninstall')){
            $registryRoot=$hive+':\'+$branch.Replace('/','\')
            if(Test-Path -LiteralPath $registryRoot){Get-ChildItem -LiteralPath $registryRoot|ForEach-Object{
                $entry=Get-ItemProperty -LiteralPath $_.PSPath
                if($entry.PSObject.Properties['DisplayName'] -and $entry.DisplayName -in @('Orvia M20 Full Test','Orvia M20 Full Test 0.2.0-rc.1','Orvia M20 Full Test 0.3.0-rc.1')){$entry}
            }}
        }
    }
}
function Assert-Identity([string]$Version,[string]$ExpectedKey=''){
    $entries=@(Get-TestInstallations)
    if($entries.Count -ne 1){throw '独立M20测试注册身份不唯一'}
    $entry=$entries[0]
    if(-not $entry.PSObject.Properties['UninstallString'] -or -not $entry.PSObject.Properties['DisplayVersion']){throw '测试注册信息缺项'}
    if($entry.PSPath -notmatch 'HKEY_CURRENT_USER' -or $entry.UninstallString -ne ('"'+$uninstaller+'" /currentuser') -or $entry.DisplayVersion -ne $Version){throw '测试注册路径、当前用户范围或版本不符'}
    if($ExpectedKey -and $entry.PSPath -ne $ExpectedKey){throw '同身份版本升级改变了注册身份'}
    if($entry.PSObject.Properties['InstallLocation'] -and [IO.Path]::GetFullPath(([string]$entry.InstallLocation).TrimEnd('\','/')) -ne $installRoot){throw '注册安装目录越界'}
    return $entry
}
function Package-For([string]$RequestedStage){
    if($RequestedStage -eq 'InstallBaseline'){
        return @{version='0.2.0-rc.1';installer=(Join-Path $resultRoot 'baseline/release/Orvia-M20-baseline-test-0.2.0-rc.1-win-x64-setup.exe');directory=(Join-Path $resultRoot 'baseline/release/win-unpacked')}
    }
    if($RequestedStage -notin @('Install','Upgrade')){throw '待核验阶段无效'}
    return @{version='0.3.0-rc.1';installer=(Join-Path $resultRoot 'release/Orvia-M20-full-test-0.3.0-rc.1-win-x64-setup.exe');directory=(Join-Path $resultRoot 'release/win-unpacked')}
}
function Resource-Fact([string]$Directory){
    Assert-NoReparse $Directory
    if(-not(Test-Path -LiteralPath $Directory -PathType Container)){throw '安装资源目录缺失'}
    $queue=New-Object 'System.Collections.Generic.Stack[string]';$queue.Push($Directory)
    $lines=New-Object 'System.Collections.Generic.List[string]';$bytes=[int64]0;$visited=0
    while($queue.Count){$directory=$queue.Pop();foreach($file in Get-ChildItem -LiteralPath $directory -Force){
        if(++$visited -gt 12000){throw '安装资源目录项超过预算'}
        Assert-NoReparse $file.FullName
        if($file.PSIsContainer){$queue.Push($file.FullName);continue}
        $bytes+=$file.Length
        if($bytes -gt 2GB -or $lines.Count -ge 10000){throw '安装资源体积或文件数超过预算'}
        $relative=$file.FullName.Substring($Directory.Length+1).Replace('\','/')
        $lines.Add($relative+' '+$file.Length+' '+(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash)
    }}
    $content=[Text.Encoding]::UTF8.GetBytes((($lines|Sort-Object)-join "`n"))
    $algorithm=[Security.Cryptography.SHA256]::Create()
    try{$digest=[BitConverter]::ToString($algorithm.ComputeHash($content)).Replace('-','')}finally{$algorithm.Dispose()}
    return @{sha256=$digest;files=$lines.Count;bytes=$bytes}
}
function Write-Record($Record){Assert-NoReparse $recordPath;$Record|ConvertTo-Json -Depth 12|Set-Content -LiteralPath $recordPath -Encoding utf8}
function Read-Record([string]$ExpectedStatus){
    Assert-NoReparse $recordPath
    $record=Get-Content -Raw -LiteralPath $recordPath|ConvertFrom-Json
    $parsed=[Guid]::Empty
    if($record.module -ne 'M20' -or $record.appId -ne $appId -or $record.projectRoot -ne $projectRoot -or $record.installRoot -ne $installRoot -or $record.status -ne $ExpectedStatus -or -not[Guid]::TryParse([string]$record.runId,[ref]$parsed)){throw '安装记录不属于本轮独立验收'}
    return $record
}
function Verify-Owned($Record){
    $null=Assert-Identity $Record.version $Record.registryKey
    foreach($target in @($executable,$uninstaller,$shortcut)){Assert-NoReparse $target;if(-not(Test-Path -LiteralPath $target -PathType Leaf)){throw '本轮安装文件或快捷方式缺失'}}
    if((Get-FileHash -LiteralPath $executable).Hash -ne $Record.executableSha256 -or (Get-FileHash -LiteralPath $uninstaller).Hash -ne $Record.uninstallerSha256 -or (Resource-Fact (Join-Path $installRoot 'resources')).sha256 -ne $Record.resources.sha256){throw '本轮安装字节已改变，拒绝操作'}
}
function Verify-Installed($Record,$Package){
    $expectedKey=if($Record.previousInstallation){$Record.previousInstallation.registryKey}else{''}
    $entry=Assert-Identity $Package.version $expectedKey
    foreach($target in @($executable,$uninstaller,$shortcut)){Assert-NoReparse $target;if(-not(Test-Path -LiteralPath $target -PathType Leaf)){throw '安装文件或快捷方式缺失'}}
    $directoryExe=Join-Path $Package.directory 'Orvia M20 Full Test.exe'
    Assert-NoReparse $directoryExe
    if((Get-FileHash -LiteralPath $executable).Hash -ne (Get-FileHash -LiteralPath $directoryExe).Hash){throw '安装EXE与同轮目录包不符'}
    $expected=Resource-Fact (Join-Path $Package.directory 'resources')
    $actual=Resource-Fact (Join-Path $installRoot 'resources')
    if($expected.sha256 -ne $actual.sha256 -or $expected.files -ne $actual.files -or $expected.bytes -ne $actual.bytes){throw '安装版资源与目录包不符'}
    $shell=New-Object -ComObject WScript.Shell;$link=$shell.CreateShortcut($shortcut)
    if($link.TargetPath -ne $executable -or $link.IconLocation -ne ($executable+',0')){throw '独立测试快捷方式身份不符'}
    $Record.status='installed';$Record.registryKey=$entry.PSPath
    $Record.executableSha256=(Get-FileHash -LiteralPath $executable).Hash
    $Record.uninstallerSha256=(Get-FileHash -LiteralPath $uninstaller).Hash
    $Record.resources=$actual;$Record.signature=[string](Get-AuthenticodeSignature -LiteralPath $executable).Status
    $Record.completedAt=[DateTime]::UtcNow.ToString('o');Write-Record $Record
}

foreach($target in @($resultRoot,$installRoot,$recordPath,$shortcut,$testProfile)){Assert-NoReparse $target}
if($Stage -eq 'Preflight'){
    Write-Output ('M20独立测试路径已核对；已有测试注册项 '+@(Get-TestInstallations).Count+'；未执行安装、升级或卸载。')
    exit 0
}
if($Stage -eq 'Uninstall'){
    $record=Read-Record 'installed';Verify-Owned $record
    $hadProfile=Test-Path -LiteralPath $testProfile -PathType Container
    # 只执行经过字节核验的自有卸载器；不执行注册命令、不递归删除、不清个人profile。
    $process=Start-Process -FilePath $uninstaller -ArgumentList '/S' -WindowStyle Hidden -Wait -PassThru
    $until=(Get-Date).AddSeconds(45)
    while(((Test-Path -LiteralPath $executable) -or @(Get-TestInstallations).Count -or (Test-Path -LiteralPath $shortcut)) -and (Get-Date) -lt $until){Start-Sleep -Milliseconds 300}
    $success=$process.ExitCode -eq 0 -and -not(Test-Path -LiteralPath $executable) -and @(Get-TestInstallations).Count -eq 0 -and -not(Test-Path -LiteralPath $shortcut)
    if(-not $success -or ($hadProfile -and -not(Test-Path -LiteralPath $testProfile))){throw '卸载或测试profile保留未通过，保留现场'}
    $record.status='uninstalled';Write-Record $record
    @{module='M20';runId=$record.runId;exitCode=$process.ExitCode;testProfilePreserved=$hadProfile;personalData='not inspected or deleted'}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $resultRoot 'uninstallation.json') -Encoding utf8
    Write-Output 'M20独立测试安装已卸载，合成profile和历史记录保留；个人配置未检查或删除。'
    exit 0
}
if($Stage -eq 'VerifyPending'){
    # 安装退出码未知时只依据当前真实包、资源和注册身份恢复记录，不重新派发安装。
    $record=Read-Record 'pending';$package=Package-For $record.stage
    Assert-NoReparse $package.installer
    if($record.version -ne $package.version -or $record.installer -ne $package.installer -or (Get-FileHash -LiteralPath $package.installer).Hash -ne $record.installerSha256){throw 'pending安装包身份不符'}
    Verify-Installed $record $package
    Write-Output 'M20待核验安装已按当前事实确认；没有重新安装或补写未知退出码。'
    exit 0
}
$package=Package-For $Stage
foreach($target in @($package.installer,$package.directory)){Assert-NoReparse $target}
if(-not(Test-Path -LiteralPath $package.installer -PathType Leaf)){throw '本地测试安装器缺失；本脚本不下载或构建'}
$previous=$null
if($Stage -eq 'Upgrade'){
    $previous=Read-Record 'installed';Verify-Owned $previous
    if($previous.version -ne '0.2.0-rc.1' -or $previous.stage -ne 'InstallBaseline'){throw '仅允许本轮独立0.2基线真正升级0.3候选版'}
    Copy-Item -LiteralPath $recordPath -Destination (Join-Path $resultRoot ('installation-history-'+[Guid]::NewGuid().ToString()+'.json'))
}elseif(@(Get-TestInstallations).Count -or (Test-Path -LiteralPath $installRoot) -or (Test-Path -LiteralPath $recordPath) -or (Test-Path -LiteralPath $shortcut)){throw '已有测试安装、路径、记录或快捷方式，拒绝覆盖'}
$null=New-Item -ItemType Directory -Path $resultRoot -Force
$record=[pscustomobject]@{module='M20';appId=$appId;runId=$(if($previous){$previous.runId}else{[Guid]::NewGuid().ToString()});projectRoot=$projectRoot;installRoot=$installRoot;stage=$Stage;version=$package.version;status='pending';installer=$package.installer;installerSha256=(Get-FileHash -LiteralPath $package.installer).Hash;previousInstallation=$previous;exitCode=$null;registryKey='';executableSha256='';uninstallerSha256='';resources=$null;signature='';completedAt=''}
Write-Record $record
# /D必须最后；当前用户、固定测试AppId和目录，不自动启动应用，不影响生产安装。
$process=Start-Process -FilePath $package.installer -ArgumentList @('/S',('/D='+$installRoot)) -WindowStyle Hidden -Wait -PassThru
$record.exitCode=$process.ExitCode;Write-Record $record
if($process.ExitCode -ne 0){throw '安装/升级失败，保留pending现场，不自动重试'}
Verify-Installed $record $package
Write-Output ('M20 '+$Stage+'实际完成，版本 '+$package.version+'；独立资源、注册身份与快捷方式已核验。')
