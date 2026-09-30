param([Parameter(Mandatory=$true)][long]$WindowHandle,[Parameter(Mandatory=$true)][string]$Output,[ValidateRange(0,16)][int]$Padding=10)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
$evidenceRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../artifacts/test-results/M19'))
$evidencePath=[IO.Path]::GetFullPath($Output)
if(-not $evidencePath.StartsWith($evidenceRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw '截图只能保存至本轮M19结果目录' }
# 仅测试侧读取自身Electron HWND边界与DWM属性；按实际桌面像素裁切，不用renderer截图冒充外轮廓。
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class M19Capture {
 [StructLayout(LayoutKind.Sequential)] public struct Rect { public int Left,Top,Right,Bottom; }
 [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd,out Rect rect);
 [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr hwnd);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("dwmapi.dll",EntryPoint="DwmGetWindowAttribute")] public static extern int DwmRect(IntPtr hwnd,int attr,out Rect rect,int size);
 [DllImport("dwmapi.dll",EntryPoint="DwmGetWindowAttribute")] public static extern int DwmInt(IntPtr hwnd,int attr,out int value,int size);
}
'@
Add-Type -AssemblyName System.Drawing
[void][M19Capture]::SetProcessDPIAware()
$handleValue=[IntPtr]$WindowHandle
if([M19Capture]::GetForegroundWindow() -ne $handleValue){throw '产品窗口并非前台，拒绝保存可能受遮挡的桌面截图'}
$nativeRect=New-Object M19Capture+Rect
if(-not [M19Capture]::GetWindowRect($handleValue,[ref]$nativeRect)){throw '本轮窗口句柄不可读'}
$frameRect=New-Object M19Capture+Rect
$dwmResult=[M19Capture]::DwmRect($handleValue,9,[ref]$frameRect,16)
if($dwmResult -ne 0){$frameRect=$nativeRect}
$cornerPreference=0
$cornerResult=[M19Capture]::DwmInt($handleValue,33,[ref]$cornerPreference,4)
$capturePadding=$Padding
$captureWidth=$frameRect.Right-$frameRect.Left+2*$capturePadding
$captureHeight=$frameRect.Bottom-$frameRect.Top+2*$capturePadding
if($captureWidth -lt 20 -or $captureHeight -lt 20 -or $captureWidth -gt 6000 -or $captureHeight -gt 6000){throw '本轮窗口边界超出截图预算'}
$bitmap=New-Object Drawing.Bitmap($captureWidth,$captureHeight)
$graphics=[Drawing.Graphics]::FromImage($bitmap)
try {
 $graphics.CopyFromScreen($frameRect.Left-$capturePadding,$frameRect.Top-$capturePadding,0,0,$bitmap.Size)
 $bitmap.Save($evidencePath,[Drawing.Imaging.ImageFormat]::Png)
} finally { $graphics.Dispose();$bitmap.Dispose() }
@{ scope='本轮已核对前台HWND的原生桌面裁切；是否产品由调用测试记录'; dpi=[M19Capture]::GetDpiForWindow($handleValue); dwmCornerResult=$cornerResult; dwmCornerPreference=$cornerPreference; nativeRect=$nativeRect; extendedFrame=$frameRect; image=[IO.Path]::GetFileName($evidencePath) } | ConvertTo-Json -Depth 4
