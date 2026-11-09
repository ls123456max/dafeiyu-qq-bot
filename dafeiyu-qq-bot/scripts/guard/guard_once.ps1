# 大肥鱼守护：单次检查（由计划任务每 5 分钟触发一次）
#
# 设计原则：
#   1. 前台在跑全屏游戏时，什么都不做（不重启、不弹窗）
#   2. 永远不弹任何窗口；需要扫码时只启动本地网页 http://127.0.0.1:6210
#   3. NapCat 启动要 2-3 分钟，正在启动时绝不重复拉起（双开会导致 QQ 登录态失效）
#
# ⚠️ 保存本文件时必须使用「UTF-8 带 BOM」，否则 PowerShell 5.1 会按 ANSI 解码，
#    中文路径会变成乱码，报「找不到路径」。在仓库里已经是 UTF-8 with BOM。

param(
    [string]$NapCatDir = 'D:\NapCat',   # NapCat 解压目录（纯英文路径！）
    [string]$TargetUin = '1000000000',  # 机器人小号的 QQ 号
    [int]$PortalPort   = 6210,          # 扫码页端口
    [string]$LogFile   = ''             # 留空 = <NapCatDir>\guard.log
)

$ErrorActionPreference = 'Continue'

if ($LogFile -eq '') { $LogFile = Join-Path $NapCatDir 'guard.log' }
$WorkDir = $env:TEMP                    # 限流状态文件放这里

$lastTryFile  = Join-Path $WorkDir 'dafeiyu_last_quicktry.txt'
$lastKillFile = Join-Path $WorkDir 'dafeiyu_last_qqkill.txt'
$portalUrl    = "http://127.0.0.1:$PortalPort"
$bootBat      = Join-Path $NapCatDir 'start_napcat.bat'

function Log($message) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [guard] $message"
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Test-PortListening([int]$Port) {
    $conn = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    return ($null -ne $conn)
}

# 前台窗口是否占满整块屏幕（全屏游戏 / 全屏视频）
function Test-FullscreenForeground {
    try {
        if (-not ('GuardFgWin' -as [type])) {
            $code = @"
using System;
using System.Runtime.InteropServices;
public class GuardFgWin {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern IntPtr GetShellWindow();
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")] public static extern int GetSystemMetrics(int nIndex);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
            Add-Type -TypeDefinition $code -ErrorAction Stop
        }
        $handle = [GuardFgWin]::GetForegroundWindow()
        if ($handle -eq [IntPtr]::Zero) { return $false }
        if ($handle -eq [GuardFgWin]::GetShellWindow()) { return $false }
        $rect = New-Object 'GuardFgWin+RECT'
        if (-not [GuardFgWin]::GetWindowRect($handle, [ref]$rect)) { return $false }
        $width = $rect.Right - $rect.Left
        $height = $rect.Bottom - $rect.Top
        return ($width -ge [GuardFgWin]::GetSystemMetrics(0) -and $height -ge [GuardFgWin]::GetSystemMetrics(1))
    }
    catch { return $false }
}

function Test-Throttled($file, [int]$minutes) {
    if (-not (Test-Path $file)) { return $false }
    $raw = (Get-Content $file -Raw -ErrorAction SilentlyContinue).Trim()
    $when = [datetime]::MinValue
    if ([datetime]::TryParse($raw, [ref]$when)) {
        return (((Get-Date) - $when).TotalMinutes -lt $minutes)
    }
    return $false
}

function Set-LastAction($file) {
    (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | Set-Content -Path $file -Encoding ASCII
}

function Start-QrPortal {
    if (Test-PortListening $PortalPort) { return }
    $portal = Join-Path $NapCatDir 'qr_portal.py'
    if (-not (Test-Path $portal)) { return }
    Start-Process -FilePath 'pythonw.exe' -ArgumentList "`"$portal`"" -WindowStyle Hidden
    Log "qr portal started ($portalUrl, hidden)"
}

# 用 NapCat 的快速登录接口尝试登回小号；失败返回 $false
function Invoke-QuickLogin {
    $webuiCfg = Join-Path $NapCatDir 'config\webui.json'
    if (-not (Test-Path $webuiCfg)) { Log 'webui.json not found'; return $false }
    $token = (Get-Content $webuiCfg -Raw | ConvertFrom-Json).token
    if (-not $token) { Log 'webui token missing'; return $false }

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($token + '.napcat')
    $sha = [System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
    $hash = -join ($sha | ForEach-Object { $_.ToString('x2') })
    try {
        $cred = (Invoke-RestMethod -Uri 'http://127.0.0.1:6099/api/auth/login' -Method Post `
            -ContentType 'application/json' -Body (@{ hash = $hash } | ConvertTo-Json) -TimeoutSec 15).data.Credential
        if (-not $cred) { Log 'napcat auth failed'; return $false }
        $headers = @{ Authorization = "Bearer $cred" }

        $list = Invoke-RestMethod -Uri 'http://127.0.0.1:6099/api/QQLogin/GetQuickLoginListNew' -Method Post `
            -Headers $headers -ContentType 'application/json' -Body '{}' -TimeoutSec 15
        $hasTarget = @($list.data) | Where-Object { $_.uin -eq $TargetUin }
        if (-not $hasTarget) {
            Log "quick login record for $TargetUin is gone -> needs QR scan ($portalUrl)"
            return $false
        }

        $res = Invoke-RestMethod -Uri 'http://127.0.0.1:6099/api/QQLogin/SetQuickLogin' -Method Post `
            -Headers $headers -ContentType 'application/json' -Body (@{ uin = $TargetUin } | ConvertTo-Json) -TimeoutSec 20
        if ($res.code -ne 0) {
            Log ("quick login rejected: " + $res.message + " -> needs QR scan ($portalUrl)")
            return $false
        }
        for ($i = 0; $i -lt 10; $i++) {
            Start-Sleep -Seconds 6
            if (Test-PortListening 6200) { return $true }
        }
        return $false
    }
    catch {
        Log ("quick login error: " + $_.Exception.Message)
        return $false
    }
}

try {
    # 1. 全屏游戏：完全不动
    if (Test-FullscreenForeground) {
        Log 'skip: fullscreen app in foreground'
        exit 0
    }

    # 2. NapCat 的 WebUI（6099）没起来 → 确保只有一份 QQ，然后拉一次
    if (-not (Test-PortListening 6099)) {
        $starting = $false
        if (Get-Process NapCatWinBootMain -ErrorAction SilentlyContinue) { $starting = $true }
        $qq = Get-Process QQ -ErrorAction SilentlyContinue
        if ($qq) {
            $youngest = $qq | Sort-Object StartTime | Select-Object -First 1
            if ($youngest -and $youngest.StartTime -and ((Get-Date) - $youngest.StartTime).TotalSeconds -lt 200) {
                $starting = $true
            }
        }
        if ($starting) {
            Log '6099 not up yet (NapCat still starting, wait)'
            exit 0
        }

        if ($qq) {
            # 有 QQ 但没注入 NapCat：先杀掉再拉起，但 30 分钟内只做一次，避免死循环
            if (Test-Throttled $lastKillFile 30) {
                Log 'QQ running without NapCat -> skip restart (throttled 30 min)'
                exit 0
            }
            Log 'QQ running without NapCat -> restart QQ'
            Set-LastAction $lastKillFile
            Stop-Process -Name QQ, QQEX -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 3
        }

        if (-not (Test-Path $bootBat)) { Log "start script missing: $bootBat"; exit 1 }
        Log 'NapCat(6099) down -> start'
        # 必须用 WMI 分离启动，否则 6099 永远不监听
        Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
            CommandLine      = "cmd.exe /c start `"`" /min `"$bootBat`""
            CurrentDirectory = $NapCatDir
        } | Out-Null

        for ($i = 0; $i -lt 8; $i++) {
            Start-Sleep -Seconds 25
            if (Test-PortListening 6099) { break }
        }
    }

    # 3. QQ 通道（6200）没起来 → 快速登录一次；不行就开扫码页
    if (-not (Test-PortListening 6200)) {
        if (Test-Throttled $lastTryFile 30) {
            Log '6200 down -> quick login skipped (throttled 30 min)'
            Start-QrPortal
            exit 0
        }
        Set-LastAction $lastTryFile
        Log '6200 down -> quick login attempt'
        $ok = Invoke-QuickLogin
        if (-not $ok) { Start-QrPortal }
        if (Test-PortListening 6200) {
            Log 'ok 6099+6200 up (after quick login)'
            exit 0
        }
        Log 'WARN 6200 still down (needs QR scan)'
        exit 0
    }

    Log 'ok 6099+6200 up'
}
catch {
    Log ("error: " + $_.Exception.Message)
}
