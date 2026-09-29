param(
    [Parameter(Mandatory=$true)][string]$InputDirectory,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)
# 只打开 M16 测试目录中已生成的合成 Office 成品，另存 PDF 用于视觉验收。
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path (Get-Location) 'artifacts/test-results/M16'))
$inputRoot = [IO.Path]::GetFullPath($InputDirectory)
$outputRoot = [IO.Path]::GetFullPath($OutputDirectory)
if (-not $inputRoot.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
    -not $outputRoot.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw '仅允许在 M16 测试产物目录内读取和输出'
}
$pptx = Get-ChildItem -LiteralPath $inputRoot -Filter '*.pptx' -File | Select-Object -First 1
if (-not $pptx) { throw '缺少 M16 合成 PPT 文件' }
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
$powerpoint = $null; $presentation = $null
try {
    $powerpoint = New-Object -ComObject PowerPoint.Application
    $presentation = $powerpoint.Presentations.Open($pptx.FullName, -1, 0, 0)
    $presentation.SaveAs((Join-Path $outputRoot 'slides-render.pdf'), 32)
} finally {
    if ($presentation) { $presentation.Close() }
    if ($powerpoint) { $powerpoint.Quit() }
}
Write-Output '本机 PowerPoint 已打开并渲染合成文件'
