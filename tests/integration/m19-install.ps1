param([ValidateSet('Install','Uninstall','VerifyPending','Upgrade')][string]$Stage='Install')
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$projectRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$resultRoot=[IO.Path]::GetFullPath((Join-Path $projectRoot 'artifacts/test-results/M19'))
$installRoot=[IO.Path]::GetFullPath((Join-Path $resultRoot 'install-smoke'))
$installer=Join-Path $resultRoot 'release/Orvia-M19-visual-test-0.2.0-rc.1-win-x64-setup.exe'
$executable=Join-Path $installRoot 'Orvia M19 Visual Test.exe'
$uninstaller=Join-Path $installRoot 'Uninstall Orvia M19 Visual Test.exe'
$recordPath=Join-Path $resultRoot 'installation.json'
$shortcut=Join-Path ([Environment]::GetFolderPath('Programs')) 'Orvia M19 Visual Test.lnk'
if(-not $installRoot.StartsWith($resultRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw '安装路径越界'}

function Assert-NoReparse([string]$Target){
    # 每个已存在祖先均检查；不沿 junction 操作真实用户安装。
    $cursor=$Target
    while($cursor){
        if((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw '路径有重解析点'}
        $cursor=[IO.Path]::GetDirectoryName($cursor)
    }
}
function Get-TestInstallations{
    foreach($hive in @('HKCU','HKLM')){
        foreach($branch in @('Software/Microsoft/Windows/CurrentVersion/Uninstall','Software/WOW6432Node/Microsoft/Windows/CurrentVersion/Uninstall')){
            $registryRoot=$hive+':\'+$branch.Replace('/','\')
            if(Test-Path -LiteralPath $registryRoot){Get-ChildItem -LiteralPath $registryRoot | ForEach-Object{
                $entry=Get-ItemProperty -LiteralPath $_.PSPath
                if($entry.PSObject.Properties['DisplayName'] -and $entry.DisplayName -in @('Orvia M19 Visual Test','Orvia M19 Visual Test 0.2.0-rc.1')){$entry}
            }}
        }
    }
}
function Assert-Identity{
    $entries=@(Get-TestInstallations)
    if($entries.Count -ne 1){throw '本轮安装身份不唯一'}
    if($entries[0].UninstallString -ne ('"'+$uninstaller+'" /currentuser') -or $entries[0].DisplayVersion -ne '0.2.0-rc.1'){throw '注册安装路径或版本不符'}
    return $entries[0]
}
function Write-Record($value){$value|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $recordPath -Encoding utf8}

foreach($target in @($installRoot,$recordPath,$shortcut)){Assert-NoReparse $target}
if($Stage -eq 'Uninstall'){
    $record=Get-Content -Raw -LiteralPath $recordPath|ConvertFrom-Json
    if($record.module -ne 'M19' -or $record.installRoot -ne $installRoot -or $record.status -ne 'installed'){throw '记录不属于本轮已验证安装'}
    $entry=Assert-Identity
    if($entry.PSPath -ne $record.registryKey){throw '注册身份已改变'}
    foreach($target in @($executable,$uninstaller)){Assert-NoReparse $target}
    if((Get-FileHash -LiteralPath $uninstaller).Hash -ne $record.uninstallerSha256 -or (Get-FileHash -LiteralPath $executable).Hash -ne $record.executableSha256){throw '本轮安装字节已改变'}
    # 固定自有卸载器，不执行注册表命令；不递归删除，不读取/删除产品 userData。
    $process=Start-Process -FilePath $uninstaller -ArgumentList '/S' -WindowStyle Hidden -Wait -PassThru
    $until=(Get-Date).AddSeconds(40)
    while(((Test-Path -LiteralPath $executable) -or @(Get-TestInstallations).Count -or (Test-Path -LiteralPath $shortcut)) -and (Get-Date) -lt $until){Start-Sleep -Milliseconds 300}
    if($process.ExitCode -ne 0 -or (Test-Path -LiteralPath $executable) -or @(Get-TestInstallations).Count -or (Test-Path -LiteralPath $shortcut)){throw '卸载未通过，保留现场'}
    $record.status='uninstalled';Write-Record $record
    Write-Output 'M19独立视觉安装已卸载；未检查或删除用户配置。'
    exit 0
}
if($Stage -eq 'VerifyPending'){
    # 只核对刚才自有安装的pending事实，不再启动安装器，不覆盖现场。
    $record=Get-Content -Raw -LiteralPath $recordPath|ConvertFrom-Json
    if($record.module -ne 'M19' -or $record.status -ne 'pending' -or $record.installRoot -ne $installRoot){throw '记录不是本轮pending安装'}
    Assert-NoReparse $installer
    if((Get-FileHash -LiteralPath $installer).Hash -ne $record.installerSha256){throw '本轮安装包已改变'}
}else{
    if($Stage -eq 'Upgrade'){
        $previous=Get-Content -Raw -LiteralPath $recordPath|ConvertFrom-Json
        if($previous.module -ne 'M19' -or $previous.status -ne 'installed' -or $previous.installRoot -ne $installRoot){throw '升级仅允许本轮已验证安装'}
        $previousEntry=Assert-Identity
        if($previousEntry.PSPath -ne $previous.registryKey -or (Get-FileHash -LiteralPath $executable).Hash -ne $previous.executableSha256 -or (Get-FileHash -LiteralPath $uninstaller).Hash -ne $previous.uninstallerSha256){throw '升级前自有安装身份已改变'}
        Copy-Item -LiteralPath $recordPath -Destination (Join-Path $resultRoot ('installation-history-'+[Guid]::NewGuid().ToString()+'.json'))
    }elseif(@(Get-TestInstallations).Count -or (Test-Path -LiteralPath $installRoot) -or (Test-Path -LiteralPath $recordPath) -or (Test-Path -LiteralPath $shortcut)){throw '已有本轮安装/记录/快捷方式，拒绝覆盖'}
    Assert-NoReparse $installer
    $record=@{module='M19';status='pending';installRoot=$installRoot;installerSha256=(Get-FileHash -LiteralPath $installer).Hash;scope='仅窗口/字体/图标；复用旧冻结后端，不代表M20全功能安装版'}
    Write-Record $record
    # /D 必须最后，不启动应用；唯一测试产品标识隔离普通 Orvia 安装。
    $process=Start-Process -FilePath $installer -ArgumentList @('/S',('/D='+$installRoot)) -WindowStyle Hidden -Wait -PassThru
    if($process.ExitCode -ne 0){throw '安装失败，保留pending现场'}
}
$entry=Assert-Identity
foreach($target in @($executable,$uninstaller,$shortcut)){Assert-NoReparse $target;if(-not(Test-Path -LiteralPath $target -PathType Leaf)){throw '安装或快捷方式缺失'}}
$packageExe=Join-Path $resultRoot 'release/win-unpacked/Orvia M19 Visual Test.exe'
if((Get-FileHash -LiteralPath $executable).Hash -ne (Get-FileHash -LiteralPath $packageExe).Hash){throw '安装EXE与解包EXE不符'}
$shell=New-Object -ComObject WScript.Shell
$link=$shell.CreateShortcut($shortcut)
if($link.TargetPath -ne $executable -or $link.IconLocation -ne ($executable+',0')){throw '实际快捷方式目标/图标不符'}
$record.status='installed'
$record|Add-Member -Force -NotePropertyName registryKey -NotePropertyValue $entry.PSPath
$record|Add-Member -Force -NotePropertyName executableSha256 -NotePropertyValue (Get-FileHash -LiteralPath $executable).Hash
$record|Add-Member -Force -NotePropertyName uninstallerSha256 -NotePropertyValue (Get-FileHash -LiteralPath $uninstaller).Hash
$record|Add-Member -Force -NotePropertyName shortcut -NotePropertyValue @{file=$shortcut;target=$link.TargetPath;icon=$link.IconLocation}
$record|Add-Member -Force -NotePropertyName signature -NotePropertyValue ([string](Get-AuthenticodeSignature -LiteralPath $executable).Status)
Write-Record $record
Write-Output 'M19实际安装与快捷方式路径核验通过；可见窗口/任务栏仍须独立验收。'
