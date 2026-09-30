param([Parameter(Mandatory=$true)][long]$WindowHandle,[Parameter(Mandatory=$true)][int]$OwnerProcess,[ValidateSet('Inspect','Focus','DoubleTitle','SnapLeft','FullScreenKey','EscapeKey','Move','Close')][string]$Action='Inspect')
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
# 测试只操作所属PID已经核对的自有Orvia HWND，不接受通用消息、目标应用或任意命令。
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class M19Native {
 [StructLayout(LayoutKind.Sequential)] public struct Rect { public int Left,Top,Right,Bottom; }
 [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd,out uint process);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd,out Rect rect);
 [DllImport("user32.dll",EntryPoint="GetWindowLongPtrW")] public static extern IntPtr GetStyle(IntPtr hwnd,int index);
 [DllImport("user32.dll")] public static extern IntPtr SendMessageW(IntPtr hwnd,uint message,IntPtr wparam,IntPtr lparam);
 [DllImport("user32.dll")] public static extern bool PostMessageW(IntPtr hwnd,uint message,IntPtr wparam,IntPtr lparam);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
 [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint from,uint to,bool attach);
 [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hwnd);
 [DllImport("user32.dll")] public static extern void keybd_event(byte key,byte scan,uint flags,UIntPtr extra);
 [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hwnd,IntPtr after,int x,int y,int w,int h,uint flags);
 public static long Hit(IntPtr hwnd,int x,int y){return SendMessageW(hwnd,0x84,IntPtr.Zero,new IntPtr((y<<16)|(x&0xffff))).ToInt64();}
}
'@
[void][M19Native]::SetProcessDPIAware()
$targetHandle=[IntPtr]$WindowHandle
$actualOwner=[uint32]0
[void][M19Native]::GetWindowThreadProcessId($targetHandle,[ref]$actualOwner)
if($actualOwner -ne $OwnerProcess){throw '自有窗口身份不匹配'}
$rect=New-Object M19Native+Rect
if(-not [M19Native]::GetWindowRect($targetHandle,[ref]$rect)){throw '自有窗口已退出'}
if($Action -in @('Focus','FullScreenKey','EscapeKey','SnapLeft')){
 # 新测试进程常受Windows前台锁限制；仅临时附接输入队列来激活已校验的自有窗口，立即解除。
 $foreground=[M19Native]::GetForegroundWindow();$foregroundOwner=[uint32]0
 $foregroundThread=[M19Native]::GetWindowThreadProcessId($foreground,[ref]$foregroundOwner)
 $currentThread=[M19Native]::GetCurrentThreadId();$attached=$false
 try{
  if($foregroundThread -ne 0 -and $foregroundThread -ne $currentThread){$attached=[M19Native]::AttachThreadInput($currentThread,$foregroundThread,$true)}
  [void][M19Native]::BringWindowToTop($targetHandle);[void][M19Native]::SetForegroundWindow($targetHandle)
 }finally{if($attached){[void][M19Native]::AttachThreadInput($currentThread,$foregroundThread,$false)}}
 if([M19Native]::GetForegroundWindow() -ne $targetHandle){throw '自有测试窗激活失败，不保存其他窗口截图'}
}
$style=[M19Native]::GetStyle($targetHandle,-16).ToInt64()
if($Action -eq 'DoubleTitle'){[void][M19Native]::SendMessageW($targetHandle,0xA3,[IntPtr]2,[IntPtr]0)}
if($Action -in @('FullScreenKey','EscapeKey')){
 [void][M19Native]::SetForegroundWindow($targetHandle)
 if([M19Native]::GetForegroundWindow() -ne $targetHandle){throw '自有窗口未取得焦点，拒绝发送原生全屏快捷键'}
 # DevTools键盘事件不代表Windows快捷键；只对已核对的自有前台发送固定F11/Escape。
 $key=if($Action -eq 'FullScreenKey'){[byte]0x7a}else{[byte]0x1b}
 [M19Native]::keybd_event($key,0,0,[UIntPtr]::Zero);[M19Native]::keybd_event($key,0,2,[UIntPtr]::Zero)
}
if($Action -eq 'SnapLeft'){
 [void][M19Native]::SetForegroundWindow($targetHandle)
 if([M19Native]::GetForegroundWindow() -ne $targetHandle){throw '未取得自有窗口焦点，拒绝发快捷键'}
 [M19Native]::keybd_event(0x5b,0,0,[UIntPtr]::Zero);[M19Native]::keybd_event(0x25,0,0,[UIntPtr]::Zero)
 [M19Native]::keybd_event(0x25,0,2,[UIntPtr]::Zero);[M19Native]::keybd_event(0x5b,0,2,[UIntPtr]::Zero)
}
if($Action -eq 'Move'){[void][M19Native]::SetWindowPos($targetHandle,[IntPtr]::Zero,$rect.Left+40,$rect.Top+30,0,0,0x15)}
if($Action -eq 'Close'){[void][M19Native]::PostMessageW($targetHandle,0x112,[IntPtr]0xf060,[IntPtr]0)}
@{action=$Action;ownerMatched=$true;thickFrame=($style -band 0x40000)-ne 0;minimizeBox=($style -band 0x20000)-ne 0;maximizeBox=($style -band 0x10000)-ne 0;captionHit=[M19Native]::Hit($targetHandle,$rect.Left+120,$rect.Top+20);leftHit=[M19Native]::Hit($targetHandle,$rect.Left+1,($rect.Top+$rect.Bottom)/2);rightHit=[M19Native]::Hit($targetHandle,$rect.Right-2,($rect.Top+$rect.Bottom)/2);bottomHit=[M19Native]::Hit($targetHandle,($rect.Left+$rect.Right)/2,$rect.Bottom-2)} | ConvertTo-Json
