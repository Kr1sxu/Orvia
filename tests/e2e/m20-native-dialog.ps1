param(
  [Parameter(Mandatory=$true)][int]$OwnerProcess,
  [Parameter(Mandatory=$true)][string]$ProfileDirectory,
  [Parameter(Mandatory=$true)][ValidateSet('授权此对话访问一个本地目录','添加本地资料（最多3个，每个10 MiB；不上传云端）','确认向固定 Main 模型发送证据片段')][string]$DialogTitle,
  [Parameter(Mandatory=$true)][ValidateSet('File','Folder','Cancel')][string]$Action,
  [string]$SyntheticPath,
  [string]$CapturePath
)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
# 原生框测试只接受本项目M20合成树和本次Electron PID；不读其他窗口名称或桌面截图。
$orviaNativeProject=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$orviaNativeResults=[IO.Path]::GetFullPath((Join-Path $orviaNativeProject 'artifacts/test-results/M20'))
function Test-M20Path([string]$value,[bool]$exists){
  $resolved=[IO.Path]::GetFullPath($value)
  if(-not $resolved.StartsWith($orviaNativeResults+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw '路径不属于M20合成树'}
  $current=if($exists){$resolved}else{[IO.Path]::GetDirectoryName($resolved)}
  while($current.Length -ge $orviaNativeResults.Length){
    if(Test-Path -LiteralPath $current){if(((Get-Item -LiteralPath $current).Attributes -band [IO.FileAttributes]::ReparsePoint)-ne 0){throw '合成树拒绝reparse路径'}}
    if($current.Equals($orviaNativeResults,[StringComparison]::OrdinalIgnoreCase)){break}
    $current=[IO.Path]::GetDirectoryName($current)
  }
  if($exists -and -not (Test-Path -LiteralPath $resolved)){throw '合成路径不存在'}
  return $resolved
}
$orviaNativeProfile=Test-M20Path $ProfileDirectory $true
$orviaNativeOwner=Get-Process -Id $OwnerProcess
$orviaNativeExpected=[IO.Path]::GetFullPath((Join-Path $orviaNativeProject 'node_modules/electron/dist/electron.exe'))
if(-not $orviaNativeOwner.Path.Equals($orviaNativeExpected,[StringComparison]::OrdinalIgnoreCase)){throw ('PID不是本项目实际Electron；仅本次PID映像='+$orviaNativeOwner.Path+'；预期='+$orviaNativeExpected)}
$orviaNativeCommand=(Get-CimInstance Win32_Process -Filter "ProcessId=$OwnerProcess").CommandLine
if(-not $orviaNativeCommand.Contains('--user-data-dir='+$orviaNativeProfile)){throw 'PID未绑定本次隔离profile'}
if($Action-ne 'Cancel'){$SyntheticPath=Test-M20Path $SyntheticPath $true}
if($CapturePath){$CapturePath=Test-M20Path $CapturePath $false}
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,System.Drawing
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Drawing;
using System.Drawing.Imaging;
public static class M20DialogNative {
 public delegate bool Callback(IntPtr hwnd,IntPtr data);
 public class OwnedButton { public long Handle; public int Id; public string Text; }
 [StructLayout(LayoutKind.Sequential)] public struct Rect { public int Left,Top,Right,Bottom; }
 [DllImport("user32.dll")] public static extern bool EnumWindows(Callback callback,IntPtr data);
 [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr hwnd,Callback callback,IntPtr data);
 [DllImport("user32.dll")] static extern IntPtr GetAncestor(IntPtr hwnd,uint flag);
 [DllImport("user32.dll")] static extern int GetDlgCtrlID(IntPtr hwnd);
 [DllImport("user32.dll")] static extern bool IsWindowEnabled(IntPtr hwnd);
 [DllImport("user32.dll")] static extern IntPtr SendMessageTimeout(IntPtr hwnd,uint message,IntPtr wparam,IntPtr lparam,uint flags,uint milliseconds,out IntPtr result);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd,out uint pid);
 [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr hwnd,uint command);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hwnd);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr hwnd,StringBuilder value,int limit);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr hwnd,StringBuilder value,int limit);
 [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr hwnd,out Rect rect);
 [DllImport("user32.dll")] static extern bool PrintWindow(IntPtr hwnd,IntPtr dc,uint flags);
 public static long[] OwnDialogs(int pid,string title){
  var handles=new List<long>();
  EnumWindows((hwnd,data)=>{uint owner;GetWindowThreadProcessId(hwnd,out owner);
   if(owner!=(uint)pid||!IsWindowVisible(hwnd))return true;
   var parent=GetWindow(hwnd,4);uint parentPid;GetWindowThreadProcessId(parent,out parentPid);
   if(parent==IntPtr.Zero||parentPid!=(uint)pid)return true;
   var cls=new StringBuilder(100);GetClassName(hwnd,cls,100);if(cls.ToString()!="#32770")return true;
   var name=new StringBuilder(300);GetWindowText(hwnd,name,300);if(name.ToString()==title)handles.Add(hwnd.ToInt64());return true;
  },IntPtr.Zero);return handles.ToArray();
 }
 public static OwnedButton[] OwnChildButtons(long handle,int pid){
  IntPtr root=new IntPtr(handle);uint actual;GetWindowThreadProcessId(root,out actual);if(actual!=(uint)pid)throw new Exception("owned dialog changed");
  var buttons=new List<OwnedButton>();
  EnumChildWindows(root,(hwnd,data)=>{uint childPid;GetWindowThreadProcessId(hwnd,out childPid);
   if(childPid!=(uint)pid||GetAncestor(hwnd,2)!=root)return true;
   var cls=new StringBuilder(100);GetClassName(hwnd,cls,100);if(cls.ToString()!="Button")return true;
   var name=new StringBuilder(300);GetWindowText(hwnd,name,300);
   buttons.Add(new OwnedButton {Handle=hwnd.ToInt64(),Id=GetDlgCtrlID(hwnd),Text=name.ToString()});return buttons.Count<20;
  },IntPtr.Zero);return buttons.ToArray();
 }
 public static void ClickKnownButton(long handle,int pid,string title,long child,int id,string label){
  var dialogs=OwnDialogs(pid,title);if(dialogs.Length!=1||dialogs[0]!=handle)throw new Exception("owned dialog changed before fixed button click");
  var buttons=OwnChildButtons(handle,pid);OwnedButton expected=null;int matches=0;
  foreach(var button in buttons)if(button.Id==id&&button.Text==label){expected=button;matches++;}
  if(matches!=1||expected.Handle!=child||!IsWindowEnabled(new IntPtr(child)))throw new Exception("known owned native button changed");
  IntPtr result; // 仅已核对的原生Button发送固定BM_CLICK一次；无通用消息/坐标入口。
  if(SendMessageTimeout(new IntPtr(child),0x00f5,IntPtr.Zero,IntPtr.Zero,2,2000,out result)==IntPtr.Zero)throw new Exception("fixed native button timeout; no retry");
 }
 public static bool Capture(long handle,int pid,string filename){
  IntPtr hwnd=new IntPtr(handle);uint actual;GetWindowThreadProcessId(hwnd,out actual);if(actual!=(uint)pid)throw new Exception("owned HWND changed");
  Rect r;if(!GetWindowRect(hwnd,out r))return false;int width=r.Right-r.Left,height=r.Bottom-r.Top;
  if(width<10||height<10||width>2400||height>1800)throw new Exception("owned dialog size rejected");
  using(var bitmap=new Bitmap(width,height))using(var graphics=Graphics.FromImage(bitmap)){
   IntPtr dc=graphics.GetHdc();bool ok;try{ok=PrintWindow(hwnd,dc,2);}finally{graphics.ReleaseHdc(dc);}
   if(ok)bitmap.Save(filename,ImageFormat.Png);return ok;
  }
 }
}
'@ -ReferencedAssemblies System.Drawing
$orviaNativeDeadline=[DateTime]::UtcNow.AddSeconds(20)
do{
  $orviaNativeHandles=[M20DialogNative]::OwnDialogs($OwnerProcess,$DialogTitle)
  if($orviaNativeHandles.Length -gt 1){throw '所属原生框不唯一'}
  if($orviaNativeHandles.Length -eq 1){break}
  Start-Sleep -Milliseconds 100
}while([DateTime]::UtcNow -lt $orviaNativeDeadline)
if($orviaNativeHandles.Length-ne 1){throw '未发现唯一所属原生框'}
$orviaNativeHandle=$orviaNativeHandles[0]
$orviaNativeDialog=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]$orviaNativeHandle)
if($orviaNativeDialog.Current.ProcessId-ne $OwnerProcess){throw 'UIA所属PID改变'}
$orviaNativeCaptured=$false
$orviaNativeFieldReadback=$false
$orviaNativeSelectionReadback=$false
$orviaNativeAll=$orviaNativeDialog.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
if($Action-eq 'Folder'){
  # Win11 FOS_PICKFOLDERS无文件名输入框；只选择本次合成起始树中唯一的指定文件夹。
  if(-not [IO.Path]::GetDirectoryName($SyntheticPath).Equals([IO.Path]::GetDirectoryName($orviaNativeProfile),[StringComparison]::OrdinalIgnoreCase)){throw '目录不属于本次合成起始树'}
  $orviaNativeLeaf=[IO.Path]::GetFileName($SyntheticPath)
  $orviaNativeFolders=@($orviaNativeAll | Where-Object {
    $_.Current.IsEnabled -and $_.Current.ControlType-in @([Windows.Automation.ControlType]::ListItem,[Windows.Automation.ControlType]::DataItem) -and $_.Current.Name-eq $orviaNativeLeaf -and $_.GetSupportedPatterns().Id-contains [Windows.Automation.SelectionItemPattern]::Pattern.Id
  })
  if($orviaNativeFolders.Count-ne 1){throw '合成文件夹条目不唯一或不支持SelectionItemPattern'}
  $orviaNativeSelection=$orviaNativeFolders[0].GetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern)
  $orviaNativeSelection.Select()
  if(-not $orviaNativeSelection.Current.IsSelected){throw '合成文件夹选择读回不一致'}
  $orviaNativeSelectionReadback=$true
}elseif($Action-eq 'File'){
  if(-not [IO.Path]::GetDirectoryName($SyntheticPath).Equals([IO.Path]::GetDirectoryName($orviaNativeProfile),[StringComparison]::OrdinalIgnoreCase)-or [IO.Path]::GetFileName($SyntheticPath)-ne 'synthetic.docx'){throw 'File仅允许本次合成树的synthetic.docx'}
  # Windows公共选择器的文件名／文件夹名字段；不向未知编辑控件或地址栏写值。
  $orviaNativeEdits=@($orviaNativeAll | Where-Object {$_.Current.ControlType-eq [Windows.Automation.ControlType]::Edit -and $_.Current.AutomationId-in @('1148','1001')})
  $orviaNativeWritable=@($orviaNativeEdits | Where-Object {$_.Current.IsEnabled -and $null-ne $_.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern) -and -not $_.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).Current.IsReadOnly})
  if($orviaNativeWritable.Count-ne 1){
    # 同系统provider可能不暴露文件名字段；仅选中当前合成树唯一固定文件，不写未知字段。
    $orviaNativeFiles=@($orviaNativeAll | Where-Object {$_.Current.IsEnabled-and $_.Current.ControlType-in @([Windows.Automation.ControlType]::ListItem,[Windows.Automation.ControlType]::DataItem)-and $_.Current.Name-eq 'synthetic.docx'-and $_.GetSupportedPatterns().Id-contains [Windows.Automation.SelectionItemPattern]::Pattern.Id})
    if($orviaNativeFiles.Count-eq 1){
      $orviaNativeSelection=$orviaNativeFiles[0].GetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern)
      $orviaNativeSelection.Select()
      if(-not $orviaNativeSelection.Current.IsSelected){throw '合成文件选择读回不一致'}
      $orviaNativeSelectionReadback=$true
    }else{
    if($CapturePath){
      # 拒绝现场仅保留本次所属dialog的控件类型/ID/模式，不读取名称、值或其他窗口。
      $orviaNativeMeta=@($orviaNativeAll | Where-Object {$_.Current.ControlType-in @([Windows.Automation.ControlType]::Edit,[Windows.Automation.ControlType]::ComboBox)} | Select-Object -First 32 | ForEach-Object {
        $orviaNativeParent=[Windows.Automation.TreeWalker]::ControlViewWalker.GetParent($_)
        @{type=$_.Current.ControlType.ProgrammaticName;automationId=$_.Current.AutomationId;parentId=$orviaNativeParent.Current.AutomationId;enabled=$_.Current.IsEnabled;patterns=@($_.GetSupportedPatterns() | ForEach-Object ProgrammaticName)}
      })
      [IO.File]::WriteAllText($CapturePath+'.controls.json',($orviaNativeMeta | ConvertTo-Json -Depth 5),(New-Object Text.UTF8Encoding($false)))
    }
    throw '原生固定合成文件条目不唯一或不支持SelectionItemPattern'
    }
  }else{
    $orviaNativeValue=$orviaNativeWritable[0].GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern)
    $orviaNativeValue.SetValue($SyntheticPath)
    if($orviaNativeValue.Current.Value-ne $SyntheticPath){throw '原生字段读回不一致'}
    $orviaNativeFieldReadback=$true
  }
}
$orviaNativeButtonName=switch($Action){'Folder'{'选择并授权'} 'File'{'添加并在本机解析'} 'Cancel'{'取消'}}
$orviaNativeButtons=@($orviaNativeAll | Where-Object {$_.Current.ControlType-eq [Windows.Automation.ControlType]::Button -and $_.Current.IsEnabled -and $_.Current.Name-eq $orviaNativeButtonName -and $_.GetSupportedPatterns().Id-contains [Windows.Automation.InvokePattern]::Pattern.Id})
$orviaNativeExpectedId=if($Action-eq 'Cancel'){
  if($DialogTitle-ne '确认向固定 Main 模型发送证据片段'){throw 'id0取消仅允许本次准确Main原生审批标题'}
  0
}else{1}
$orviaNativeKnownButtons=@([M20DialogNative]::OwnChildButtons($orviaNativeHandle,$OwnerProcess) | Where-Object {$_.Id-eq $orviaNativeExpectedId-and $_.Text-eq $orviaNativeButtonName})
if($orviaNativeButtons.Count-ne 1-and $orviaNativeKnownButtons.Count-ne 1){
  if($CapturePath){
    # 按钮适配失败仅保留本次所属dialog内最多20个Button，不读列表、输入值或其他窗口。
    $orviaNativeButtonMeta=@($orviaNativeAll | Where-Object {$_.Current.ControlType-eq [Windows.Automation.ControlType]::Button} | Select-Object -First 20 | ForEach-Object {
      @{name=$_.Current.Name;automationId=$_.Current.AutomationId;enabled=$_.Current.IsEnabled;invokeSupported=($_.GetSupportedPatterns().Id-contains [Windows.Automation.InvokePattern]::Pattern.Id)}
    })
    $orviaNativeChildMeta=@([M20DialogNative]::OwnChildButtons($orviaNativeHandle,$OwnerProcess) | ForEach-Object {
      $orviaNativeChild=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]$_.Handle)
      @{hwnd=$_.Handle;id=$_.Id;windowText=$_.Text;uiaName=$orviaNativeChild.Current.Name;uiaType=$orviaNativeChild.Current.ControlType.ProgrammaticName;enabled=$orviaNativeChild.Current.IsEnabled;invokeSupported=($orviaNativeChild.GetSupportedPatterns().Id-contains [Windows.Automation.InvokePattern]::Pattern.Id)}
    })
    [IO.File]::WriteAllText($CapturePath+'.buttons.json',(@{expectedName=$orviaNativeButtonName;matchingCount=$orviaNativeButtons.Count;buttons=$orviaNativeButtonMeta;ownedWin32Buttons=$orviaNativeChildMeta} | ConvertTo-Json -Depth 5),(New-Object Text.UTF8Encoding($false)))
  }
  throw '原生确认／取消按钮不唯一'
}
if($CapturePath){$orviaNativeCaptured=[M20DialogNative]::Capture($orviaNativeHandle,$OwnerProcess,$CapturePath)}
$orviaNativeActivation='UIA InvokePattern'
if($orviaNativeButtons.Count-eq 1){$orviaNativeButtons[0].GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()}else{
  # 只在实际观测的标准Win32 Button存在且pattern缺失时使用固定语义；再次核对PID/profile/准确对话框。
  $orviaNativeFreshProcess=Get-Process -Id $OwnerProcess
  $orviaNativeFreshCommand=(Get-CimInstance Win32_Process -Filter "ProcessId=$OwnerProcess").CommandLine
  if(-not $orviaNativeFreshProcess.Path.Equals($orviaNativeExpected,[StringComparison]::OrdinalIgnoreCase)-or -not $orviaNativeFreshCommand.Contains('--user-data-dir='+$orviaNativeProfile)){throw '原生按钮调用前PID/profile改变'}
  if($Action-ne 'Cancel'-and -not ($orviaNativeFieldReadback-or $orviaNativeSelectionReadback)){throw '缺少实际选择读回，拒绝确认'}
  [M20DialogNative]::ClickKnownButton($orviaNativeHandle,$OwnerProcess,$DialogTitle,$orviaNativeKnownButtons[0].Handle,$orviaNativeExpectedId,$orviaNativeButtonName)
  $orviaNativeActivation='guarded fixed Win32 BM_CLICK; observed UIA Pane without InvokePattern'
}
@{action=$Action;ownerMatched=$true;windowHandle=$orviaNativeHandle;process=$OwnerProcess;nativeAPI=$true;fieldReadback=$orviaNativeFieldReadback;selectionReadback=$orviaNativeSelectionReadback;activation=$orviaNativeActivation;captured=$orviaNativeCaptured;scope='only this isolated Electron PID and owned dialog HWND'} | ConvertTo-Json -Compress
