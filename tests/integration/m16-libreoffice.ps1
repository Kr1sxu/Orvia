param([Parameter(Mandatory=$true)][string]$InputDirectory,[Parameter(Mandatory=$true)][string]$OutputDirectory)
# 使用本机已有 LibreOffice 的独立 profile 渲染 M16 合成 DOCX；不打开用户资料。
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path (Get-Location) 'artifacts/test-results/M16'))
$inputRoot=[IO.Path]::GetFullPath($InputDirectory)
$outputRoot=[IO.Path]::GetFullPath($OutputDirectory)
if(-not $inputRoot.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or -not $outputRoot.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw '仅允许 M16 测试产物目录'}
$docx=Get-ChildItem -LiteralPath $inputRoot -Filter '*.docx' -File | Select-Object -First 1
if(-not $docx){throw '缺少 M16 合成 DOCX'}
$soffice='C:\Program Files\LibreOffice\program\soffice.exe'
if(-not (Test-Path -LiteralPath $soffice)){throw '本机 LibreOffice 不可用'}
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
$profile=Join-Path $root 'lo-profile'
New-Item -ItemType Directory -Force -Path $profile | Out-Null
$profileUri=([Uri]$profile).AbsoluteUri
& $soffice "-env:UserInstallation=$profileUri" '--headless' '--convert-to' 'pdf:writer_pdf_Export' '--outdir' $outputRoot $docx.FullName
$outputFile=Join-Path $outputRoot ($docx.BaseName+'.pdf')
# Windows launcher 可能先于 soffice.bin 退出；最多等待10秒，仅以实际 PDF 文件判定。
for($attempt=0;$attempt -lt 40 -and -not (Test-Path -LiteralPath $outputFile);$attempt++){Start-Sleep -Milliseconds 250}
if(-not (Test-Path -LiteralPath $outputFile) -or (Get-Item -LiteralPath $outputFile).Length -lt 1000){throw 'LibreOffice 转换失败'}
Write-Output '合成 DOCX 已由本机 LibreOffice 渲染 PDF'
