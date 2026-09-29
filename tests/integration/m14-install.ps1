param([ValidateSet('InstallLegacy','Upgrade','Install','Uninstall','VerifyPending')][string]$Stage='Install')
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$projectRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$resultRoot=[IO.Path]::GetFullPath((Join-Path $projectRoot 'artifacts/test-results/M14'))
$installRoot=[IO.Path]::GetFullPath((Join-Path $resultRoot 'install-smoke'))
$recordPath=Join-Path $resultRoot 'installation.json'
$executable=Join-Path $installRoot 'Orvia.exe'
$uninstaller=Join-Path $installRoot 'Uninstall Orvia.exe'
if (-not $installRoot.StartsWith($resultRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw '安装目标越界' }

function Assert-NoReparse([string]$Target) {
    # 安装路径及其已有祖先不能通过 junction/symlink 指向真实用户安装。
    $cursor=$Target
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw '验收路径包含重解析点，拒绝操作' }
        }
        $cursor=[IO.Path]::GetDirectoryName($cursor)
    }
}
function Get-OrviaInstallations {
    # 同时拒绝用户级、机器级和 32 位注册表中的其他 Orvia 安装。
    foreach ($hive in @('HKCU','HKLM')) {
        foreach ($branch in @('Software/Microsoft/Windows/CurrentVersion/Uninstall','Software/WOW6432Node/Microsoft/Windows/CurrentVersion/Uninstall')) {
            $registryRoot=($hive+':\'+$branch.Replace('/','\'))
            if (Test-Path -LiteralPath $registryRoot) {
                Get-ChildItem -LiteralPath $registryRoot | ForEach-Object {
                    $entry=Get-ItemProperty -LiteralPath $_.PSPath
                    $isOrviaName=$entry.PSObject.Properties['DisplayName'] -and ([string]$entry.DisplayName -match '^Orvia(?:\s+.+)?$')
                    $isOrviaKey=([string] $_.PSChildName).Trim('{','}') -eq '55817df6-2716-5647-9669-c503900a11ff'
                    if ($isOrviaName -or $isOrviaKey) { $entry }
                }
            }
        }
    }
}
function Assert-RegistryIdentity($Entries,[string]$ExpectedVersion,[string]$ExpectedKey='') {
    if ($Entries.Count -ne 1) { throw '需要唯一的本轮 Orvia 注册信息，拒绝操作' }
    $entry=$Entries[0]
    if (-not $entry.PSObject.Properties['UninstallString'] -or -not $entry.PSObject.Properties['DisplayVersion']) { throw '安装注册信息缺少卸载路径或版本' }
    # NSIS 不一定提供 InstallLocation；只接受固定卸载器及固定参数，不解析或执行任意命令。
    $expectedUninstall='"'+$uninstaller+'" /currentuser'
    if ([string]$entry.UninstallString -ne $expectedUninstall -or [string]$entry.DisplayVersion -ne $ExpectedVersion) { throw '注册表卸载路径或版本与本轮验收不一致' }
    if ($entry.PSObject.Properties['InstallLocation']) {
        $registered=[IO.Path]::GetFullPath(([string]$entry.InstallLocation).TrimEnd('\','/'))
        if ($registered -ne $installRoot) { throw '注册表 InstallLocation 与本轮验收不一致' }
    }
    if ($ExpectedKey -and $entry.PSPath -ne $ExpectedKey) { throw '安装注册表身份已改变' }
    return $entry
}
function Read-OwnedRecord {
    Assert-NoReparse $recordPath
    if (-not (Test-Path -LiteralPath $recordPath -PathType Leaf)) { throw '缺少本轮安装记录，拒绝操作' }
    $record=Get-Content -Raw -LiteralPath $recordPath | ConvertFrom-Json
    if ($record.module -ne 'M14' -or $record.installRoot -ne $installRoot -or $record.projectRoot -ne $projectRoot -or $record.status -ne 'installed') { throw '安装记录不属于本轮已验证安装' }
    $parsedGuid=[Guid]::Empty
    if (-not [Guid]::TryParse([string]$record.runId,[ref]$parsedGuid)) { throw '安装记录缺少有效身份' }
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf) -or -not (Test-Path -LiteralPath $uninstaller -PathType Leaf)) { throw '本轮安装文件不完整，保留现场' }
    Assert-NoReparse $executable
    Assert-NoReparse $uninstaller
    if ((Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash -ne $record.executableSha256 -or (Get-FileHash -LiteralPath $uninstaller -Algorithm SHA256).Hash -ne $record.uninstallerSha256) { throw '本轮安装文件身份已改变，拒绝操作' }
    $null=Assert-RegistryIdentity @(Get-OrviaInstallations) $record.version $record.registryKey
    return $record
}
function Write-Record($Record) {
    Assert-NoReparse $recordPath
    $Record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $recordPath -Encoding utf8
}

Assert-NoReparse $installRoot
if ($Stage -eq 'VerifyPending') {
    # 仅恢复本轮安装成功但后续事实校验中断的记录；不启动安装器、不修改安装目录。
    Assert-NoReparse $recordPath
    if (-not (Test-Path -LiteralPath $recordPath -PathType Leaf)) { throw '缺少待核验安装记录' }
    $record=Get-Content -Raw -LiteralPath $recordPath | ConvertFrom-Json
    if ($record.module -ne 'M14' -or $record.installRoot -ne $installRoot -or $record.projectRoot -ne $projectRoot -or $record.status -ne 'pending') { throw '记录不是本轮待核验安装' }
    $parsedGuid=[Guid]::Empty
    if (-not [Guid]::TryParse([string]$record.runId,[ref]$parsedGuid)) { throw '待核验记录身份无效' }
    if ($record.stage -notin @('InstallLegacy','Install','Upgrade')) { throw '待核验阶段无效' }
    $expectedVersion=if ($record.stage -eq 'InstallLegacy') { '0.1.0' } else { '0.2.0-rc.1' }
    $packageModule=if ($record.stage -eq 'InstallLegacy') { 'M08' } else { 'M14' }
    $expectedInstaller=Join-Path $projectRoot "artifacts/test-results/$packageModule/release/Orvia-$expectedVersion-win-x64-setup.exe"
    $packageExecutable=Join-Path $projectRoot "artifacts/test-results/$packageModule/release/win-unpacked/Orvia.exe"
    if ($record.version -ne $expectedVersion -or $record.installer -ne $expectedInstaller) { throw '待核验包路径或版本无效' }
    foreach ($file in @($expectedInstaller,$packageExecutable,$executable,$uninstaller)) {
        Assert-NoReparse $file
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw '核验所需本地安装文件缺失' }
    }
    if ((Get-FileHash -LiteralPath $expectedInstaller -Algorithm SHA256).Hash -ne $record.installerSha256) { throw '待核验安装包已改变' }
    $installedHash=(Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash
    if ($installedHash -ne (Get-FileHash -LiteralPath $packageExecutable -Algorithm SHA256).Hash) { throw '安装程序与本轮对应解包产物不一致' }
    $expectedKey=''
    if ($record.stage -eq 'Upgrade') {
        $previous=$record.previousInstallation
        if ($previous.module -ne 'M14' -or $previous.runId -ne $record.runId -or $previous.installRoot -ne $installRoot -or $previous.projectRoot -ne $projectRoot -or $previous.status -ne 'installed' -or $previous.version -ne '0.1.0' -or $previous.stage -ne 'InstallLegacy') { throw '升级缺少本轮已验证旧版记录' }
        $expectedKey=$previous.registryKey
    }
    $registry=Assert-RegistryIdentity @(Get-OrviaInstallations) $expectedVersion $expectedKey
    $record.status='installed'
    $record | Add-Member -Force -NotePropertyName registryKey -NotePropertyValue $registry.PSPath
    $record | Add-Member -Force -NotePropertyName executableSha256 -NotePropertyValue $installedHash
    $record | Add-Member -Force -NotePropertyName uninstallerSha256 -NotePropertyValue (Get-FileHash -LiteralPath $uninstaller -Algorithm SHA256).Hash
    $record | Add-Member -Force -NotePropertyName verificationMethod -NotePropertyValue 'VerifyPending: package hash, unpacked executable hash and registry identity'
    $record | Add-Member -Force -NotePropertyName completedAt -NotePropertyValue ([DateTime]::UtcNow.ToString('o'))
    # 不补写未知历史退出码；恢复依据为当前安装文件与注册信息事实。
    Write-Record $record
    Write-Output 'M14 pending 记录已通过本地包与注册信息核验；未重新启动安装器。'
    exit 0
}
if ($Stage -eq 'Uninstall') {
    $record=Read-OwnedRecord
    # 只执行记录并校验过的卸载器；不递归删除目录。NSIS 保留 userData 的策略不变，
    # 本脚本不读取/清理真实用户配置，不把安装目录消失视为用户数据已删除。
    $process=Start-Process -FilePath $uninstaller -ArgumentList '/S' -WindowStyle Hidden -PassThru -Wait
    $until=(Get-Date).AddSeconds(45)
    do {
        $remaining=@(Get-OrviaInstallations)
        $removed=(-not (Test-Path -LiteralPath $executable)) -and $remaining.Count -eq 0
        if ($removed -or (Get-Date) -ge $until) { break }
        Start-Sleep -Milliseconds 500
    } while ($true)
    $success=$removed -and $process.ExitCode -eq 0
    $report=@{module='M14'; runId=$record.runId; installRoot=$installRoot; uninstalled=$success; executableRemoved=(-not (Test-Path -LiteralPath $executable)); registryRemoved=($remaining.Count -eq 0); exitCode=$process.ExitCode; userDataPolicy='preserved; not inspected'; completedAt=[DateTime]::UtcNow.ToString('o')}
    $uninstallReport=Join-Path $resultRoot 'uninstallation.json'
    Assert-NoReparse $uninstallReport
    $report | ConvertTo-Json | Set-Content -LiteralPath $uninstallReport -Encoding utf8
    if (-not $success) { throw '卸载未通过，保留现场且不删除任何目录' }
    $record.status='uninstalled'
    Write-Record $record
    Write-Output 'M14 本轮隔离安装已卸载；用户数据未检查或删除。'
    exit 0
}

$version=if ($Stage -eq 'InstallLegacy') { '0.1.0' } else { '0.2.0-rc.1' }
$packageModule=if ($Stage -eq 'InstallLegacy') { 'M08' } else { 'M14' }
$installer=Join-Path $projectRoot "artifacts/test-results/$packageModule/release/Orvia-$version-win-x64-setup.exe"
Assert-NoReparse $installer
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) { throw '本地验收安装包不存在；脚本不下载或构建安装包' }
$previous=$null
if ($Stage -eq 'Upgrade') {
    $previous=Read-OwnedRecord
    if ($previous.version -ne '0.1.0' -or $previous.stage -ne 'InstallLegacy') { throw '升级只允许本轮 InstallLegacy 创建的 M08 安装' }
} else {
    if (@(Get-OrviaInstallations).Count -ne 0 -or (Test-Path -LiteralPath $installRoot) -or (Test-Path -LiteralPath $recordPath)) { throw '已有 Orvia 安装、验收目录或记录，拒绝覆盖；请保留现场' }
}
$null=New-Item -ItemType Directory -Path $resultRoot -Force
$runId=if ($previous) { $previous.runId } else { [Guid]::NewGuid().ToString() }
$record=@{module='M14'; runId=$runId; projectRoot=$projectRoot; installRoot=$installRoot; status='pending'; stage=$Stage; version=$version; installer=$installer; installerSha256=(Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash; previousInstallation=$previous; startedAt=[DateTime]::UtcNow.ToString('o')}
Write-Record $record
# /D 必须是 NSIS 的最后一个参数；即使路径含空格也不添加嵌套引号。
$process=Start-Process -FilePath $installer -ArgumentList @('/S',('/D='+$installRoot)) -WindowStyle Hidden -PassThru -Wait
if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $executable -PathType Leaf) -or -not (Test-Path -LiteralPath $uninstaller -PathType Leaf)) { throw '安装/升级未完成，保留 pending 记录及现场' }
$record.exitCode=$process.ExitCode
Write-Record $record
Assert-NoReparse $executable
Assert-NoReparse $uninstaller
$expectedKey=if ($previous) { $previous.registryKey } else { '' }
$registry=Assert-RegistryIdentity @(Get-OrviaInstallations) $version $expectedKey
$record.status='installed'
$record.registryKey=$registry.PSPath
$record.executableSha256=(Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash
$record.uninstallerSha256=(Get-FileHash -LiteralPath $uninstaller -Algorithm SHA256).Hash
$record.exitCode=$process.ExitCode
$record.completedAt=[DateTime]::UtcNow.ToString('o')
Write-Record $record
Write-Output "M14 $Stage 已验证安装文件及注册表身份，版本 $version。"
