# 注册「每 5 分钟跑一次守护」的计划任务
#
# 为什么不用 Register-ScheduledTask：
#   实测在很多机器上（含 Win11 24H2）会报 Access is denied，
#   用 XML 方式（含 Principal、中文任务名）同样被拒。
#   最稳的是最朴素的 schtasks.exe 命令行，且任务名只能用 ASCII。
#
# 手动执行（管理员或普通用户都行，登录态下用 /SC MINUTE 不需要提权）：
#   右键「使用 PowerShell 运行」，或：
#   powershell -NoProfile -ExecutionPolicy Bypass -File register-task.ps1
#
# 卸载：
#   schtasks /Delete /TN "DafeiyuGuard" /F

$ErrorActionPreference = 'Stop'

$TaskName = 'DafeiyuGuard'                       # 只能 ASCII
$GuardDir = Split-Path -Parent $PSScriptRoot     # scripts\guard
$VbsPath  = Join-Path $PSScriptRoot 'guard_hidden.vbs'

if (-not (Test-Path $VbsPath)) {
    throw "guard_hidden.vbs not found: $VbsPath"
}

$action = 'wscript.exe "' + $VbsPath + '"'

# 先删旧的（存在时会提示 ERROR，忽略）
schtasks /Delete /TN $TaskName /F 2>$null | Out-Null

schtasks /Create /TN $TaskName /TR $action /SC MINUTE /MO 5 /F | Out-Host

# 立刻跑一次，验证没有报错
Start-Process -FilePath 'wscript.exe' -ArgumentList $VbsPath -WindowStyle Hidden
Start-Sleep -Seconds 5

Write-Host ''
Write-Host '已注册。查看状态：' -ForegroundColor Green
Write-Host ('  schtasks /Query /TN ' + $TaskName + ' /V /FO LIST')
Write-Host '下次运行时间见 Next Run Time；日志在 guard_once.ps1 里配置的 $LogFile。'
