# M18 专用合成 WinForms 窗口。源码仅测试使用，生成 exe/日志全部放忽略的 M18 产物目录。
param([Parameter(Mandatory=$true)][string]$OutputDirectory, [switch]$PrepareOnly, [string]$Title = 'Orvia M18 synthetic desktop')
$ErrorActionPreference = 'Stop'
$orviaFixtureDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
if (-not [System.IO.Directory]::Exists($orviaFixtureDirectory)) { [System.IO.Directory]::CreateDirectory($orviaFixtureDirectory) | Out-Null }
$orviaFixtureExe = Join-Path $orviaFixtureDirectory 'm18_desktop_fixture.exe'
$orviaFixtureSource = Join-Path $orviaFixtureDirectory 'm18_desktop_fixture.cs'
$orviaFixtureCode = @'
using System;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;
public class M18DesktopFixture : Form {
  IntPtr input, output;
  [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern IntPtr CreateWindowEx(int ex,string cls,string caption,int style,int x,int y,int w,int h,IntPtr parent,IntPtr id,IntPtr instance,IntPtr data);
  [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr hwnd,StringBuilder text,int limit);
  [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern bool SetWindowText(IntPtr hwnd,string text);
  string TextValue(){ var text=new StringBuilder(2049);GetWindowText(input,text,2049);return text.ToString(); }
  public M18DesktopFixture(string title) {
    Text=title; Width=620; Height=330; StartPosition=FormStartPosition.CenterScreen;
  }
  protected override void OnLoad(EventArgs e) {
    base.OnLoad(e);
    // 原生标准控件提供可稳定验收的系统 UIA provider；不以此宣称自绘/所有 WinForms 兼容。
    input=CreateWindowEx(0,"EDIT","",0x50810000,25,25,530,30,Handle,(IntPtr)101,IntPtr.Zero,IntPtr.Zero);
    output=CreateWindowEx(0,"STATIC","READY",0x50000000,25,70,530,40,Handle,(IntPtr)102,IntPtr.Zero,IntPtr.Zero);
    CreateWindowEx(0,"BUTTON","M18 apply",0x50010000,25,130,125,35,Handle,(IntPtr)103,IntPtr.Zero,IntPtr.Zero);
    CreateWindowEx(0,"BUTTON","M18 synthetic toggle",0x50010003,180,130,210,35,Handle,(IntPtr)104,IntPtr.Zero,IntPtr.Zero);
    CreateWindowEx(0,"BUTTON","M18 synthetic radio",0x50010009,400,130,180,35,Handle,(IntPtr)105,IntPtr.Zero,IntPtr.Zero);
    CreateWindowEx(0,"BUTTON","M18 open save dialog",0x50010000,25,190,240,35,Handle,(IntPtr)106,IntPtr.Zero,IntPtr.Zero);
    CreateWindowEx(0,"EDIT","SYNTHETIC-DO-NOT-EXPOSE",0x50810020,300,195,250,30,Handle,(IntPtr)107,IntPtr.Zero,IntPtr.Zero);
  }
  protected override void WndProc(ref Message message) {
    if(message.Msg==0x111 && (message.WParam.ToInt64()>>16)==0) {
      int id=(int)(message.WParam.ToInt64()&0xffff);
      if(id==103){SetWindowText(output,"APPLIED:"+TextValue());return;}
      if(id==106){SaveCopy();return;}
    }
    base.WndProc(ref message);
  }
  void SaveCopy() {
      using(var dialog=new SaveFileDialog()) {
        dialog.Title="M18 synthetic Save"; dialog.InitialDirectory=Path.GetDirectoryName(Application.ExecutablePath);
        dialog.Filter="Text|*.txt"; dialog.AddExtension=false; dialog.OverwritePrompt=true; dialog.CheckPathExists=true;
        if(dialog.ShowDialog(this)==DialogResult.OK) {
          using(var file=new FileStream(dialog.FileName,FileMode.CreateNew,FileAccess.Write)) {
            var bytes=new UTF8Encoding(false).GetBytes(TextValue()); file.Write(bytes,0,bytes.Length); file.Flush(true);
          }
          SetWindowText(output,"SAVED SYNTHETIC COPY");
        }
      }
  }
  [STAThread] public static void Main(string[] args) {
    Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
    if(args.Length>0 && args[0]=="--confirmation") {
      using(var confirmation=new Form()) {
        confirmation.Text="M18 synthetic native confirmation";confirmation.Width=370;confirmation.Height=160;confirmation.TopMost=true;
        var label=new Label();label.Text="Synthetic approval focus test";label.Dock=DockStyle.Fill;confirmation.Controls.Add(label);
        confirmation.Shown += delegate { confirmation.Activate(); };Application.Run(confirmation);
      }
      return;
    }
    Application.Run(new M18DesktopFixture(args.Length>0?args[0]:"Orvia M18 synthetic desktop"));
  }
}
'@
[System.IO.File]::WriteAllText($orviaFixtureSource, $orviaFixtureCode, (New-Object System.Text.UTF8Encoding($false)))
$orviaFixtureCompiler = Join-Path $env:SystemRoot 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $orviaFixtureCompiler /nologo /target:winexe /platform:anycpu "/out:$orviaFixtureExe" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll $orviaFixtureSource
if ($LASTEXITCODE -ne 0) { throw 'M18 synthetic fixture compilation failed' }
if ($PrepareOnly) { Write-Output $orviaFixtureExe; exit 0 }
# 本测试窗口必须可见，才能验证 UIA 焦点和控件；仅由测试明确启动，不接管用户窗口。
$orviaFixtureProcess = Start-Process -FilePath $orviaFixtureExe -ArgumentList @('"' + $Title.Replace('"','') + '"') -WindowStyle Normal -PassThru
Write-Output $orviaFixtureProcess.Id
