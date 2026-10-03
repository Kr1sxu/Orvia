param(
  [Parameter(Mandatory=$true)][int]$OwnerProcess,
  [Parameter(Mandatory=$true)][long]$WindowHandle,
  [Parameter(Mandatory=$true)][string]$ProfileDirectory,
  [ValidateSet('Inspect','TypePinyin','CommitSpace')][string]$Action='Inspect'
)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
# 只有固定NIHAO及Space两种测试步骤；每键对都复核自有前台/焦点/HKL，不切布局或读候选窗。
$orviaImeProject=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$orviaImeResults=[IO.Path]::GetFullPath((Join-Path $orviaImeProject 'artifacts/test-results/M20'))
$orviaImeProfile=[IO.Path]::GetFullPath($ProfileDirectory)
if(-not $orviaImeProfile.StartsWith($orviaImeResults+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)-or -not (Test-Path -LiteralPath $orviaImeProfile -PathType Container)){throw 'IME profile不属于本次M20合成树'}
$orviaImeAncestor=$orviaImeProfile
while($orviaImeAncestor.Length-ge $orviaImeResults.Length){
  if(((Get-Item -LiteralPath $orviaImeAncestor).Attributes-band [IO.FileAttributes]::ReparsePoint)-ne 0){throw 'IME profile拒绝reparse路径'}
  if($orviaImeAncestor.Equals($orviaImeResults,[StringComparison]::OrdinalIgnoreCase)){break}
  $orviaImeAncestor=[IO.Path]::GetDirectoryName($orviaImeAncestor)
}
$orviaImeProcess=Get-Process -Id $OwnerProcess
$orviaImeExpected=[IO.Path]::GetFullPath((Join-Path $orviaImeProject 'node_modules/electron/dist/electron.exe'))
if(-not $orviaImeProcess.Path.Equals($orviaImeExpected,[StringComparison]::OrdinalIgnoreCase)){throw 'IME PID不是本项目Electron'}
$orviaImeCommand=(Get-CimInstance Win32_Process -Filter "ProcessId=$OwnerProcess").CommandLine
if(-not $orviaImeCommand.Contains('--user-data-dir='+$orviaImeProfile)){throw 'IME PID未绑定本次隔离profile'}
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class M20ImeInspect {
 [StructLayout(LayoutKind.Sequential)] public struct Rect { public int Left,Top,Right,Bottom; }
 [StructLayout(LayoutKind.Sequential)] public struct GuiInfo { public uint Size,Flags; public IntPtr Active,Focus,Capture,MenuOwner,MoveSize,Caret; public Rect CaretRect; }
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd,out uint pid);
 [DllImport("user32.dll")] public static extern IntPtr GetKeyboardLayout(uint thread);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr hwnd,uint flag);
 [DllImport("user32.dll")] public static extern bool GetGUIThreadInfo(uint thread,ref GuiInfo info);
 [StructLayout(LayoutKind.Sequential)] public struct KeyboardInput { public ushort Vk,Scan; public uint Flags,Time; public UIntPtr Extra; }
 [StructLayout(LayoutKind.Explicit,Size=32)] public struct InputUnion { [FieldOffset(0)] public KeyboardInput Keyboard; }
 [StructLayout(LayoutKind.Sequential)] public struct Input { public uint Type; public InputUnion Data; }
 [DllImport("user32.dll",SetLastError=true)] static extern uint SendInput(uint count,Input[] inputs,int size);
 static void RequireOwnFocus(IntPtr hwnd,uint pid){
  uint actual;uint thread=GetWindowThreadProcessId(hwnd,out actual);
  if(actual!=pid||thread==0||GetForegroundWindow()!=hwnd||(GetKeyboardLayout(thread).ToInt64()&0xffff)!=0x0804)throw new Exception("owned foreground/HKL prerequisite lost; no keys");
  var gui=new GuiInfo();gui.Size=(uint)Marshal.SizeOf(gui);uint focusPid;
  if(!GetGUIThreadInfo(thread,ref gui)||gui.Focus==IntPtr.Zero||GetAncestor(gui.Focus,2)!=hwnd)throw new Exception("owned focus root lost; no keys");
  GetWindowThreadProcessId(gui.Focus,out focusPid);if(focusPid!=pid)throw new Exception("owned focus PID lost; no keys");
 }
 static int Pair(IntPtr hwnd,uint pid,ushort key){
  RequireOwnFocus(hwnd,pid);
  var inputs=new Input[2];inputs[0].Type=1;inputs[0].Data.Keyboard.Vk=key;
  inputs[1].Type=1;inputs[1].Data.Keyboard.Vk=key;inputs[1].Data.Keyboard.Flags=2;
  if(SendInput(2,inputs,Marshal.SizeOf(typeof(Input)))!=2)throw new Exception("fixed VK pair not delivered; no retry");return 2;
 }
 public static int FixedPinyin(long handle,uint pid){
  int count=0;foreach(ushort key in new ushort[]{0x4e,0x49,0x48,0x41,0x4f}){count+=Pair(new IntPtr(handle),pid,key);System.Threading.Thread.Sleep(75);}return count;
 }
 public static int FixedSpace(long handle,uint pid){return Pair(new IntPtr(handle),pid,0x20);}
}
'@
$orviaImeHandle=[IntPtr]$WindowHandle
$orviaImeActualOwner=[uint32]0
$orviaImeThread=[M20ImeInspect]::GetWindowThreadProcessId($orviaImeHandle,[ref]$orviaImeActualOwner)
if($orviaImeActualOwner-ne $OwnerProcess-or $orviaImeThread-eq 0){throw 'IME HWND身份不匹配'}
$orviaImeLayout=[M20ImeInspect]::GetKeyboardLayout($orviaImeThread)
$orviaImeLanguage=[uint32]($orviaImeLayout.ToInt64()-band 0xffff)
$orviaImeInfo=New-Object M20ImeInspect+GuiInfo
$orviaImeInfo.Size=[Runtime.InteropServices.Marshal]::SizeOf($orviaImeInfo)
$orviaImeInfoOk=[M20ImeInspect]::GetGUIThreadInfo($orviaImeThread,[ref]$orviaImeInfo)
$orviaImeFocusOwner=[uint32]0
if($orviaImeInfoOk-and $orviaImeInfo.Focus-ne [IntPtr]::Zero){[void][M20ImeInspect]::GetWindowThreadProcessId($orviaImeInfo.Focus,[ref]$orviaImeFocusOwner)}
$orviaImeKeys=0
if($Action-eq 'TypePinyin'){$orviaImeKeys=[M20ImeInspect]::FixedPinyin($WindowHandle,$OwnerProcess)}
if($Action-eq 'CommitSpace'){$orviaImeKeys=[M20ImeInspect]::FixedSpace($WindowHandle,$OwnerProcess)}
@{action=$Action;ownerMatched=$true;profileMatched=$true;uiThread=$orviaImeThread;hkl=('0x{0:X}'-f $orviaImeLayout.ToInt64());languageId=('0x{0:X4}'-f $orviaImeLanguage);simplifiedChineseLayout=($orviaImeLanguage-eq 0x0804);foregroundOwn=([M20ImeInspect]::GetForegroundWindow()-eq $orviaImeHandle);guiThreadInfoAvailable=$orviaImeInfoOk;focusOwnerMatched=($orviaImeFocusOwner-eq $OwnerProcess);focusRootIsOwn=($orviaImeInfoOk-and [M20ImeInspect]::GetAncestor($orviaImeInfo.Focus,2)-eq $orviaImeHandle);keysSent=$orviaImeKeys;layoutChanged=$false} | ConvertTo-Json -Compress
