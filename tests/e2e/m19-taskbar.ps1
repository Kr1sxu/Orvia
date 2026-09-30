param([Parameter(Mandatory=$true)][long]$WindowHandle,[Parameter(Mandatory=$true)][int]$OwnerProcess)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,System.Drawing
Add-Type -TypeDefinition @'
using System;using System.Text;using System.Runtime.InteropServices;
public static class M19Taskbar{
 [DllImport("user32.dll")]public static extern IntPtr FindWindow(string c,string n);
 [DllImport("user32.dll")]public static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);
 [DllImport("user32.dll")]public static extern bool SetProcessDPIAware();
 public delegate bool WindowCallback(IntPtr h,IntPtr p);
 [DllImport("user32.dll")]public static extern bool EnumWindows(WindowCallback c,IntPtr p);
 [DllImport("user32.dll")]public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)]public static extern int GetWindowText(IntPtr h,StringBuilder s,int n);
 public static bool UniqueOwnOrvia(IntPtr expected){int count=0;bool own=false;EnumWindows((h,p)=>{if(IsWindowVisible(h)){var s=new StringBuilder(1024);GetWindowText(h,s,1024);if(s.ToString().Contains("Orvia")){count++;if(h==expected)own=true;}}return true;},IntPtr.Zero);return count==1&&own;}
}
'@
[void][M19Taskbar]::SetProcessDPIAware()
$actualOwner=[uint32]0
[void][M19Taskbar]::GetWindowThreadProcessId([IntPtr]$WindowHandle,[ref]$actualOwner)
if($actualOwner -ne $OwnerProcess){throw '任务栏验收窗口身份不属于本轮'}
$resultRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../artifacts/test-results/M19'))
$expectedExe=Join-Path $resultRoot 'install-smoke/Orvia M19 Visual Test.exe'
if((Get-Process -Id $OwnerProcess).Path -ne $expectedExe -or -not [M19Taskbar]::UniqueOwnOrvia([IntPtr]$WindowHandle)){throw '不是唯一可见的本轮已安装Orvia窗口，拒绝任务栏裁切'}
$taskbar=[M19Taskbar]::FindWindow('Shell_TrayWnd',$null)
if($taskbar -eq [IntPtr]::Zero){throw '没有本机可见任务栏'}
$root=[Windows.Automation.AutomationElement]::FromHandle($taskbar)
$condition=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Button)
$buttons=$root.FindAll([Windows.Automation.TreeScope]::Descendants,$condition)
$matches=@();$preferred=@()
foreach($button in $buttons){
    # Explorer可能使用固定AppId的品牌名；先核对唯一可见自有窗口和安装EXE，才接受Orvia按钮。
    if($button.Current.Name -like '*Orvia*'){$matches+=,$button}
    if($button.Current.Name -like '*Orvia M19 Visual Test*' -or $button.Current.Name -like '*Orvia M19 synthetic icon verification*'){$preferred+=,$button}
}
if($preferred.Count -eq 1){$matches=$preferred}
if($matches.Count -gt 0){$matches|ForEach-Object{@{name=$_.Current.Name;type=$_.Current.ControlType.ProgrammaticName}}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $PSScriptRoot '../../artifacts/test-results/M19/taskbar-own-matches.json') -Encoding utf8}
if($matches.Count -ne 1){throw '本轮任务栏按钮不可唯一识别；不输出其他按钮名称'}
$rect=$matches[0].Current.BoundingRectangle
if($rect.IsEmpty -or $rect.Width -lt 16 -or $rect.Height -lt 16 -or $rect.Width -gt 1000 -or $rect.Height -gt 200){throw '任务栏按钮不可见或尺寸异常'}
$resultRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../artifacts/test-results/M19'))
$bitmap=New-Object Drawing.Bitmap([int]$rect.Width,[int]$rect.Height)
$graphics=[Drawing.Graphics]::FromImage($bitmap)
try{$graphics.CopyFromScreen([int]$rect.X,[int]$rect.Y,0,0,$bitmap.Size);$bitmap.Save((Join-Path $resultRoot 'taskbar.png'),[Drawing.Imaging.ImageFormat]::Png)}finally{$graphics.Dispose();$bitmap.Dispose()}
@{scope='实际任务栏唯一测试按钮的原生桌面裁切，不含其他用户按钮';windowHandle=$WindowHandle;ownerProcess=$actualOwner;name=$matches[0].Current.Name;rectangle=@{x=$rect.X;y=$rect.Y;width=$rect.Width;height=$rect.Height}}|ConvertTo-Json -Depth 4
