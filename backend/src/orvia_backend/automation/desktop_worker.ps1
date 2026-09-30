# M18 固定 UIA helper：MTA、独立进程、单条 JSON；输入只能选择白名单动作，不能执行代码。
# 启动命令不得使用 -Command/-EncodedCommand，不加载个人 profile 或修改执行策略。
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$orviaRequest = $null
$orviaIssued = $false
try {
    $line = [Console]::ReadLine()
    if ($null -eq $line -or $line.Length -gt 60000) { throw [System.InvalidOperationException]::new('DESKTOP_LIMIT') }
    $orviaRequest = ConvertFrom-Json -InputObject $line
    if ($orviaRequest.v -ne 1 -or [string]$orviaRequest.nonce -notmatch '^[0-9a-f]{32}$') { throw [System.InvalidOperationException]::new('DESKTOP_DENIED') }
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
    Add-Type -AssemblyName WindowsBase
    # 固定系统代理使传统 Win32/WinForms 控件暴露实际 UIA pattern；不注册来自应用/网页的代理。
    Add-Type -AssemblyName UIAutomationClientsideProviders
    $orviaProviderName = [UIAutomationClientsideProviders.UIAutomationClientSideProviders].Assembly.GetName()
    # 本机 .NET 4.8 首次固定代理注册触发初始化 NullReference，第二次初始化成功；
    # 只针对已验证的这一类型补一次初始化，其他异常停止，不重试任何 UI 动作。
    $orviaProviderInitializationRetry = $false
    try { [System.Windows.Automation.ClientSettings]::RegisterClientSideProviderAssembly($orviaProviderName) }
    catch [System.Management.Automation.MethodInvocationException] {
        if ($_.Exception.InnerException -isnot [System.NullReferenceException]) { throw }
        $orviaProviderInitializationRetry = $true
    }
    if ($orviaProviderInitializationRetry) {
        [System.Windows.Automation.ClientSettings]::RegisterClientSideProviderAssembly($orviaProviderName)
    }
    # 固定 P/Invoke 声明；从不把输入文本放入 Add-Type 或反射调用。
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
public static class OrviaDesktopNative {
  public delegate bool EnumProc(IntPtr hwnd, IntPtr param);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc proc, IntPtr param);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr hwnd, uint command);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int max);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr hwnd, StringBuilder text, int max);
  [DllImport("user32.dll", EntryPoint="GetWindowLongW")] static extern int GetWindowLong(IntPtr hwnd, int index);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
  [DllImport("kernel32.dll")] static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);
  [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
  [DllImport("advapi32.dll")] static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);
  [DllImport("advapi32.dll")] static extern bool GetTokenInformation(IntPtr token, int cls, IntPtr buffer, int len, out int needed);
  [DllImport("advapi32.dll")] static extern IntPtr GetSidSubAuthorityCount(IntPtr sid);
  [DllImport("advapi32.dll")] static extern IntPtr GetSidSubAuthority(IntPtr sid, uint index);
  public static bool SameUser(uint pid) {
    IntPtr process=OpenProcess(0x1000,false,pid), token=IntPtr.Zero, buffer=IntPtr.Zero;
    try {
      if(process==IntPtr.Zero || !OpenProcessToken(process,8,out token)) return false;
      int needed=0; GetTokenInformation(token,1,IntPtr.Zero,0,out needed);
      if(needed<=0 || needed>65536) return false;
      buffer=Marshal.AllocHGlobal(needed);
      if(!GetTokenInformation(token,1,buffer,needed,out needed)) return false;
      // 只比较访问令牌的 TokenUser SID，不输出 SID 或读取目标进程内存/凭据。
      var targetSid=new System.Security.Principal.SecurityIdentifier(Marshal.ReadIntPtr(buffer));
      using(var current=System.Security.Principal.WindowsIdentity.GetCurrent()) {
        return current.User!=null && targetSid.Equals(current.User);
      }
    } finally { if(buffer!=IntPtr.Zero)Marshal.FreeHGlobal(buffer); if(token!=IntPtr.Zero)CloseHandle(token); if(process!=IntPtr.Zero)CloseHandle(process); }
  }
  public static int Integrity(uint pid) {
    IntPtr process=OpenProcess(0x1000,false,pid), token=IntPtr.Zero, buffer=IntPtr.Zero;
    try {
      if(process==IntPtr.Zero || !OpenProcessToken(process,8,out token)) return -1;
      int needed=0; GetTokenInformation(token,25,IntPtr.Zero,0,out needed);
      if(needed<=0 || needed>65536) return -1;
      buffer=Marshal.AllocHGlobal(needed);
      if(!GetTokenInformation(token,25,buffer,needed,out needed)) return -1;
      IntPtr sid=Marshal.ReadIntPtr(buffer);
      byte count=Marshal.ReadByte(GetSidSubAuthorityCount(sid));
      if(count==0) return -1;
      return Marshal.ReadInt32(GetSidSubAuthority(sid,(uint)(count-1)));
    } finally { if(buffer!=IntPtr.Zero)Marshal.FreeHGlobal(buffer); if(token!=IntPtr.Zero)CloseHandle(token); if(process!=IntPtr.Zero)CloseHandle(process); }
  }
  public static long[] Windows() {
    var result=new List<long>();
    EnumWindows(delegate(IntPtr hwnd,IntPtr arg){ if(IsWindowVisible(hwnd))result.Add(hwnd.ToInt64()); return result.Count<200; },IntPtr.Zero);
    return result.ToArray();
  }
  public static string Caption(IntPtr hwnd) { var value=new StringBuilder(161); GetWindowText(hwnd,value,161); return value.ToString(); }
  public static string ClassName(IntPtr hwnd) { var value=new StringBuilder(129); GetClassName(hwnd,value,129); return value.ToString(); }
  public static bool PasswordWindow(IntPtr hwnd) { return hwnd!=IntPtr.Zero && ClassName(hwnd).ToUpperInvariant().Contains("EDIT") && (GetWindowLong(hwnd,-16)&0x20)!=0; }
  public static bool OwnedBy(IntPtr hwnd,IntPtr root) {
    IntPtr current=hwnd; for(int i=0;i<12 && current!=IntPtr.Zero;i++){ if(current==root)return true; current=GetWindow(current,4); } return false;
  }
}
'@

    function Fail([string]$code) { throw [System.InvalidOperationException]::new($code) }
    function Limit-Text($value, [int]$length) {
        if ($null -eq $value) { return '' }
        $text = [string]$value
        if ($text.Length -gt $length) { return $text.Substring(0, $length) }
        return $text
    }
    function Get-Binding([long]$handle) {
        $hwnd = [IntPtr]$handle
        if (-not [OrviaDesktopNative]::IsWindow($hwnd)) { Fail 'DESKTOP_TARGET_CHANGED' }
        [uint32]$processId = 0
        [void][OrviaDesktopNative]::GetWindowThreadProcessId($hwnd, [ref]$processId)
        if ($orviaRequest.deny_pids -contains [int]$processId) { Fail 'DESKTOP_DENIED' }
        $process = [System.Diagnostics.Process]::GetProcessById([int]$processId)
        $integrity = [OrviaDesktopNative]::Integrity($processId)
        if ($integrity -lt 4096 -or $integrity -gt 8192) { Fail 'DESKTOP_DENIED' }
        $currentSession = [System.Diagnostics.Process]::GetCurrentProcess().SessionId
        if ($process.SessionId -ne $currentSession) { Fail 'DESKTOP_DENIED' }
        if (-not [OrviaDesktopNative]::SameUser($processId)) { Fail 'DESKTOP_DENIED' }
        return [ordered]@{
            hwnd = $handle; pid = [int]$processId; start_ticks = [string]$process.StartTime.ToUniversalTime().Ticks
            exe_path = $process.MainModule.FileName; process_name = [System.IO.Path]::GetFileName($process.MainModule.FileName)
            class_name = [OrviaDesktopNative]::ClassName($hwnd); label = [OrviaDesktopNative]::Caption($hwnd)
            integrity = $integrity; same_session = $true; same_user = $true; visible = [OrviaDesktopNative]::IsWindowVisible($hwnd)
        }
    }
    function Check-Binding($expected) {
        $fresh = Get-Binding ([long]$expected.hwnd)
        foreach ($key in @('pid','start_ticks','exe_path','hwnd','class_name')) {
            if ([string]$fresh[$key] -cne [string]$expected.$key) { Fail 'DESKTOP_TARGET_CHANGED' }
        }
        if (-not $fresh.visible) { Fail 'DESKTOP_TARGET_CHANGED' }
        return $fresh
    }
    function Get-Pattern($element, [string]$name) {
        $patternType = switch ($name) {
            'invoke' { [System.Windows.Automation.InvokePattern]::Pattern }
            'value' { [System.Windows.Automation.ValuePattern]::Pattern }
            'select' { [System.Windows.Automation.SelectionItemPattern]::Pattern }
            'toggle' { [System.Windows.Automation.TogglePattern]::Pattern }
            'text' { [System.Windows.Automation.TextPattern]::Pattern }
            default { Fail 'DESKTOP_UNSUPPORTED' }
        }
        $pattern = $null
        if (-not $element.TryGetCurrentPattern($patternType, [ref]$pattern)) { return $null }
        return $pattern
    }
    function Get-Snapshot($binding) {
        $fresh = Check-Binding $binding
        $active = [IntPtr][long]$binding.hwnd
        # 只读授权窗及其同进程拥有的当前弹窗，不能扫描其他应用的 UI 树。
        foreach ($handle in [OrviaDesktopNative]::Windows()) {
            $candidate = [IntPtr]$handle
            if ($candidate -ne $active -and [OrviaDesktopNative]::OwnedBy($candidate, [IntPtr][long]$binding.hwnd)) {
                [uint32]$candidatePid = 0
                [void][OrviaDesktopNative]::GetWindowThreadProcessId($candidate, [ref]$candidatePid)
                if ($candidatePid -eq [uint32]$binding.pid -and [OrviaDesktopNative]::IsWindowEnabled($candidate)) { $active = $candidate; break }
            }
        }
        $root = [System.Windows.Automation.AutomationElement]::FromHandle($active)
        if ($null -eq $root) { Fail 'DESKTOP_UNAVAILABLE' }
        $rootRectangle = $root.Current.BoundingRectangle
        $queue = New-Object 'System.Collections.Generic.Queue[object]'
        $queue.Enqueue(@($root, '0', 0))
        $dialogMode = [OrviaDesktopNative]::ClassName($active) -eq '#32770'
        if ($dialogMode) {
            # 公共保存框只观察文件名与确认控件；不读取其目录列表、最近文件或树导航。
            [System.Windows.Automation.Condition[]]$dialogConditions = @(
                [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::AutomationIdProperty, '1148'),
                [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::AutomationIdProperty, '1001'),
                [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::AutomationIdProperty, '1'))
            $dialogElements = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.OrCondition]::new($dialogConditions))
            for ($dialogIndex = 0; $dialogIndex -lt $dialogElements.Count; $dialogIndex++) {
                $queue.Enqueue(@($dialogElements[$dialogIndex], "0.dialog.$dialogIndex", 1))
            }
        }
        $rows = New-Object 'System.Collections.Generic.List[object]'
        $elements = @{}
        $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
        $truncated = $false
        while ($queue.Count -gt 0) {
            if ($rows.Count -ge 160) { $truncated = $true; break }
            $item = $queue.Dequeue(); $element = $item[0]; $path = $item[1]; $depth = [int]$item[2]
            $current = $element.Current
            if ($current.ProcessId -ne [int]$binding.pid) { Fail 'DESKTOP_TARGET_CHANGED' }
            $runtime = @($element.GetRuntimeId())
            $runtimeKey = [string]::Join(',', $runtime)
            if ($elements.ContainsKey($runtimeKey)) { Fail 'DESKTOP_STALE' }
            $elements[$runtimeKey] = $element
            $patterns = New-Object 'System.Collections.Generic.List[string]'
            $value = $null; $text = $null; $selected = $null; $toggle = $null
            # 部分 WinForms/MSAA provider 的子 Pane 会把密码当 Name 返回；复核原生 ES_PASSWORD，并不遍历其子树。
            $isPassword = $current.IsPassword -or [OrviaDesktopNative]::PasswordWindow([IntPtr]$current.NativeWindowHandle)
            $blocked = if ($isPassword) { 'password' } else { $null }
            if (-not $isPassword) {
                foreach ($name in @('invoke','value','select','toggle','text')) {
                    $pattern = Get-Pattern $element $name
                    if ($null -ne $pattern) {
                        $patterns.Add($name)
                        switch ($name) {
                            'value' { $value = Limit-Text $pattern.Current.Value 2048; if ($pattern.Current.IsReadOnly) { $patterns.Remove('value') | Out-Null } }
                            'select' { $selected = $pattern.Current.IsSelected }
                            'toggle' { $toggle = [string]$pattern.Current.ToggleState }
                            'text' { $text = Limit-Text ($pattern.DocumentRange.GetText(2048)) 2048 }
                        }
                    }
                }
                if ($current.IsKeyboardFocusable) { $patterns.Add('focus') }
            }
            $rect = $current.BoundingRectangle
            # 无坐标点击：绑定控件相对布局/尺寸；OS将同一窗口整体移屏不改变控件授权。
            $originX = if ($rootRectangle.IsEmpty) { 0 } else { [int]$rootRectangle.X }
            $originY = if ($rootRectangle.IsEmpty) { 0 } else { [int]$rootRectangle.Y }
            $rectangle = if ($rect.IsEmpty) { @(0,0,0,0) } else { @(([int]$rect.X - $originX), ([int]$rect.Y - $originY), [int]$rect.Width, [int]$rect.Height) }
            $rows.Add([ordered]@{
                runtime_id = $runtime; window_hwnd = $active.ToInt64(); path = $path
                native_id = $current.AutomationId; name = if ($isPassword) { '[protected password control]' } else { Limit-Text $current.Name 160 }
                control_type = $current.ControlType.ProgrammaticName.Replace('ControlType.','')
                patterns = @($patterns.ToArray()); enabled = $current.IsEnabled; offscreen = $current.IsOffscreen
                focused = $current.HasKeyboardFocus; value = $value; text = $text; selected = $selected; toggle_state = $toggle
                rectangle = $rectangle
                blocked_reason = $blocked; save_button = $false
            })
            $child = if ($isPassword -or $dialogMode) { $null } else { $walker.GetFirstChild($element) }
            if ($depth -ge 10 -and $null -ne $child) { $truncated = $true; break }
            $index = 0
            while ($null -ne $child) {
                if ($queue.Count + $rows.Count -ge 160) { $truncated = $true; break }
                $queue.Enqueue(@($child, "$path.$index", $depth + 1)); $index++
                $child = $walker.GetNextSibling($child)
            }
            if ($truncated) { break }
        }
        $save = @($rows | Where-Object { $_.native_id -eq '1' -and $_.control_type -eq 'Button' -and $_.name -match '^(Save|保存)' })
        $names = @($rows | Where-Object { $_.native_id -in @('1148','1001') -and $_.patterns -contains 'value' })
        $fileDialog = $dialogMode -and $names.Count -gt 0
        if ($dialogMode) {
            foreach ($row in $rows) { $row.blocked_reason = 'file_dialog'; if ($save.Count -eq 1 -and $row -eq $save[0]) { $row.save_button = $true } }
        }
        return @{ snapshot = [ordered]@{ binding = $fresh; active_hwnd = $active.ToInt64(); controls = @($rows.ToArray()); file_dialog = $fileDialog; truncated = $truncated }; elements = $elements; root = $root }
    }
    function Stable-Controls($rows) {
        $stable = foreach ($row in $rows) {
            # 不比较被原生审批框改变的焦点；动作开始前单独验证当前目标焦点。
            [ordered]@{ runtime_id=@($row.runtime_id); window_hwnd=$row.window_hwnd; native_id=$row.native_id; name=$row.name
                control_type=$row.control_type; patterns=@($row.patterns); enabled=$row.enabled; offscreen=$row.offscreen
                value=$row.value; text=$row.text; selected=$row.selected; toggle_state=$row.toggle_state
                rectangle=@($row.rectangle); blocked_reason=$row.blocked_reason; save_button=$row.save_button }
        }
        return ConvertTo-Json -InputObject @($stable) -Depth 12 -Compress
    }

    $result = $null
    switch ($orviaRequest.op) {
        'windows' {
            $bindings = New-Object 'System.Collections.Generic.List[object]'
            foreach ($handle in [OrviaDesktopNative]::Windows()) {
                if ($bindings.Count -ge 40) { break }
                if ([OrviaDesktopNative]::GetWindow([IntPtr]$handle, 4) -ne [IntPtr]::Zero) { continue }
                # 测试传入自有 fixture PID 时，在读取任何标题前排除其他窗口。
                if ($null -ne $orviaRequest.filter_pid) {
                    [uint32]$orviaFixturePid = 0
                    [void][OrviaDesktopNative]::GetWindowThreadProcessId([IntPtr]$handle, [ref]$orviaFixturePid)
                    if ($orviaFixturePid -ne [uint32]$orviaRequest.filter_pid) { continue }
                }
                try { $binding = Get-Binding $handle; if ($binding.label.Length -gt 0) { $bindings.Add($binding) } } catch { }
            }
            $result = @{ windows = @($bindings.ToArray()) }
        }
        'observe' { $result = (Get-Snapshot $orviaRequest.binding).snapshot }
        'act' {
            $observed = Get-Snapshot $orviaRequest.binding
            $snapshot = $observed.snapshot
            if ($snapshot.truncated -or $snapshot.active_hwnd -ne $orviaRequest.expected_snapshot.active_hwnd -or
                (Stable-Controls $snapshot.controls) -cne (Stable-Controls $orviaRequest.expected_snapshot.controls)) { Fail 'DESKTOP_STALE' }
            $runtimeKey = [string]::Join(',', @($orviaRequest.control.runtime_id))
            $matches = @($snapshot.controls | Where-Object { [string]::Join(',', @($_.runtime_id)) -ceq $runtimeKey })
            if ($matches.Count -ne 1) { Fail 'DESKTOP_STALE' }
            $row = $matches[0]; $target = $observed.elements[$runtimeKey]
            if (-not $row.enabled -or $row.offscreen -or $row.blocked_reason -eq 'password') { Fail 'DESKTOP_DENIED' }
            $action = [string]$orviaRequest.action
            if ($snapshot.file_dialog -and $action -ne 'save_new') { Fail 'DESKTOP_DENIED' }
            if ($action -eq 'save_new' -and (-not $snapshot.file_dialog -or -not $row.save_button)) { Fail 'DESKTOP_UNSUPPORTED' }
            [void][OrviaDesktopNative]::SetForegroundWindow([IntPtr][long]$snapshot.active_hwnd)
            try { $observed.root.SetFocus() } catch { }
            if ([OrviaDesktopNative]::GetForegroundWindow().ToInt64() -ne [long]$snapshot.active_hwnd) { Fail 'DESKTOP_FOCUS' }
            $verified = $false
            switch ($action) {
                'invoke' { $pattern = Get-Pattern $target 'invoke'; if ($null -eq $pattern) { Fail 'DESKTOP_UNSUPPORTED' }; $orviaIssued = $true; $pattern.Invoke() }
                'set_value' { $pattern = Get-Pattern $target 'value'; if ($null -eq $pattern -or $pattern.Current.IsReadOnly) { Fail 'DESKTOP_UNSUPPORTED' }; $orviaIssued = $true; $pattern.SetValue([string]$orviaRequest.value); $verified = $pattern.Current.Value -ceq [string]$orviaRequest.value }
                'select' { $pattern = Get-Pattern $target 'select'; if ($null -eq $pattern) { Fail 'DESKTOP_UNSUPPORTED' }; $orviaIssued = $true; $pattern.Select(); $verified = $pattern.Current.IsSelected }
                'toggle' { $pattern = Get-Pattern $target 'toggle'; if ($null -eq $pattern) { Fail 'DESKTOP_UNSUPPORTED' }; $previous = $pattern.Current.ToggleState; $orviaIssued = $true; $pattern.Toggle(); $verified = $previous -ne $pattern.Current.ToggleState }
                'focus' { if (-not ($row.patterns -contains 'focus')) { Fail 'DESKTOP_UNSUPPORTED' }; $orviaIssued = $true; $target.SetFocus(); $verified = $target.Current.HasKeyboardFocus }
                'save_new' {
                    $inputRows = @($snapshot.controls | Where-Object { $_.native_id -eq '1001' -and $_.patterns -contains 'value' })
                    if ($inputRows.Count -ne 1) { $inputRows = @($snapshot.controls | Where-Object { $_.native_id -eq '1148' -and $_.patterns -contains 'value' }) }
                    if ($inputRows.Count -ne 1) { Fail 'DESKTOP_UNSUPPORTED' }
                    $inputTarget = $observed.elements[[string]::Join(',', @($inputRows[0].runtime_id))]
                    $inputPattern = Get-Pattern $inputTarget 'value'
                    if ($null -eq $inputPattern -or $inputPattern.Current.IsReadOnly) { Fail 'DESKTOP_UNSUPPORTED' }
                    $orviaIssued = $true
                    $inputPattern.SetValue([string]$orviaRequest.value)
                    if ($inputPattern.Current.Value -cne [string]$orviaRequest.value) { Fail 'DESKTOP_STALE' }
                    $savePattern = Get-Pattern $target 'invoke'
                    if ($null -eq $savePattern) { Fail 'DESKTOP_UNSUPPORTED' }
                    $savePattern.Invoke()
                }
                default { Fail 'DESKTOP_DENIED' }
            }
            Start-Sleep -Milliseconds 120
            $after = (Get-Snapshot $orviaRequest.binding).snapshot
            $result = @{ verified = $verified; observation = $after }
        }
        default { Fail 'DESKTOP_DENIED' }
    }
    $response = @{ v = 1; nonce = $orviaRequest.nonce; ok = $true; result = $result }
    $encoded = ConvertTo-Json -InputObject $response -Compress -Depth 20
    if ([System.Text.Encoding]::UTF8.GetByteCount($encoded) -gt 48000) { Fail 'DESKTOP_LIMIT' }
    [Console]::WriteLine($encoded)
} catch {
    $code = if ($_.Exception.Message -match '^DESKTOP_[A-Z_]+$') { $_.Exception.Message } else { 'DESKTOP_UNAVAILABLE' }
    [Console]::WriteLine((ConvertTo-Json -Compress -InputObject @{ v=1; nonce=$orviaRequest.nonce; ok=$false; code=$code; issued=$orviaIssued }))
    exit 1
}
