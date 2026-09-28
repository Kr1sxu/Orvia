param([ValidateSet('Install','Uninstall')][string]$Stage='Install')
$ErrorActionPreference='Stop'
$projectRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$resultRoot=Join-Path $projectRoot 'artifacts/test-results/M08'
$installRoot=[IO.Path]::GetFullPath((Join-Path $resultRoot 'install-smoke'))
$requiredPrefix=[IO.Path]::GetFullPath($resultRoot)+[IO.Path]::DirectorySeparatorChar
if (-not $installRoot.StartsWith($requiredPrefix,[StringComparison]::OrdinalIgnoreCase)) { throw '安装目标越界' }
if ($Stage -eq 'Install') {
    # 不升级或覆盖用户已有安装；只有本轮隔离目录可用于自动安装验收。
    $existing=Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue | Where-Object DisplayName -eq 'Orvia'
    if ($existing -or (Test-Path -LiteralPath $installRoot)) { throw '已有 Orvia 安装或验收目录，拒绝覆盖' }
    $installer=Join-Path $resultRoot 'release/Orvia-0.1.0-win-x64-setup.exe'
    $process=Start-Process -FilePath $installer -ArgumentList @('/S',('/D='+$installRoot)) -WindowStyle Hidden -PassThru -Wait
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $installRoot 'Orvia.exe'))) { throw '安装验收失败' }
    @{installed=$true; installRoot=$installRoot; exitCode=$process.ExitCode} | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $resultRoot 'installation.json')
} else {
    $evidence=Get-Content -Raw (Join-Path $resultRoot 'installation.json') | ConvertFrom-Json
    if ($evidence.installRoot -ne $installRoot) { throw '安装记录与目标不一致' }
    $uninstaller=Join-Path $installRoot 'Uninstall Orvia.exe'
    if (-not (Test-Path -LiteralPath $uninstaller)) { throw '本轮卸载器不存在' }
    $process=Start-Process -FilePath $uninstaller -ArgumentList '/S' -WindowStyle Hidden -PassThru -Wait
    # NSIS 卸载器会启动临时副本；最多等 30 秒，绝不自行递归删除安装目录。
    $until=(Get-Date).AddSeconds(30)
    while ((Test-Path -LiteralPath (Join-Path $installRoot 'Orvia.exe')) -and (Get-Date) -lt $until) { Start-Sleep -Milliseconds 500 }
    $removed=-not (Test-Path -LiteralPath (Join-Path $installRoot 'Orvia.exe'))
    @{uninstalled=$removed; exitCode=$process.ExitCode} | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $resultRoot 'uninstallation.json')
    if (-not $removed) { throw '卸载未完成，保留现场' }
}
