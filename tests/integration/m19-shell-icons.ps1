$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System;using System.Runtime.InteropServices;
public static class M19ShellIcon{
 [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)]public struct Info{public IntPtr icon;public int index;public uint attributes;[MarshalAs(UnmanagedType.ByValTStr,SizeConst=260)]public string display;[MarshalAs(UnmanagedType.ByValTStr,SizeConst=80)]public string type;}
 [DllImport("shell32.dll",CharSet=CharSet.Unicode)]public static extern IntPtr SHGetFileInfo(string path,uint attrs,out Info info,uint size,uint flags);
 [DllImport("user32.dll")]public static extern bool DestroyIcon(IntPtr icon);
}
'@
$resultRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../artifacts/test-results/M19'))
$targets=@{executable=(Join-Path $resultRoot 'release/win-unpacked/Orvia M19 Visual Test.exe');installer=(Join-Path $resultRoot 'release/Orvia-M19-visual-test-0.2.0-rc.1-win-x64-setup.exe')}
$installed=Join-Path $resultRoot 'install-smoke/Orvia M19 Visual Test.exe'
if(Test-Path -LiteralPath $installed){$targets.installed=$installed;$targets.uninstaller=Join-Path $resultRoot 'install-smoke/Uninstall Orvia M19 Visual Test.exe'}
$reports=@()
foreach($name in $targets.Keys){
    # Windows实际从构建EXE提取关联图标，不启动进程或清除用户图标缓存。
    $icon=[Drawing.Icon]::ExtractAssociatedIcon($targets[$name])
    if($null -eq $icon){throw 'Windows未提取出实际EXE图标'}
    $bitmap=$icon.ToBitmap()
    try{
        $bitmap.Save((Join-Path $resultRoot ('shell-icon-'+$name+'.png')),[Drawing.Imaging.ImageFormat]::Png)
        $reports+=@{kind=$name;size=@{width=$bitmap.Width;height=$bitmap.Height};signature=[string](Get-AuthenticodeSignature -LiteralPath $targets[$name]).Status}
    }finally{$bitmap.Dispose();$icon.Dispose()}
}
$shortcut=Join-Path ([Environment]::GetFolderPath('Programs')) 'Orvia M19 Visual Test.lnk'
if(Test-Path -LiteralPath $shortcut){
    $shell=New-Object -ComObject WScript.Shell
    if($shell.CreateShortcut($shortcut).TargetPath -ne $installed){throw '本轮快捷方式目标已改变，拒绝图标提取'}
    $info=New-Object M19ShellIcon+Info
    if([M19ShellIcon]::SHGetFileInfo($shortcut,0,[ref]$info,[Runtime.InteropServices.Marshal]::SizeOf($info),0x100) -eq [IntPtr]::Zero -or $info.icon -eq [IntPtr]::Zero){throw '实际Shell快捷方式图标读取失败'}
    $icon=[Drawing.Icon]::FromHandle($info.icon);$bitmap=$icon.ToBitmap()
    try{$bitmap.Save((Join-Path $resultRoot 'shell-icon-shortcut.png'),[Drawing.Imaging.ImageFormat]::Png);$reports+=@{kind='shortcut';size=@{width=$bitmap.Width;height=$bitmap.Height};method='Windows SHGetFileInfo实际lnk'}}finally{$bitmap.Dispose();$icon.Dispose();[void][M19ShellIcon]::DestroyIcon($info.icon)}
}
@{scope='Windows实际ExtractAssociatedIcon；非任务栏/快捷方式/安装器可见窗口验收';files=$reports}|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $resultRoot 'shell-icons.json') -Encoding utf8
Write-Output 'Windows关联图标提取完成；须与实际PE/源图及后续任务栏共同核验。'
