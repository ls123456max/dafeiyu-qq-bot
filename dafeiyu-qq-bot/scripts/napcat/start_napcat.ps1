# 用 WMI 分离启动 NapCat（避免「进程活着但 6099 不监听」）
#
# 在自动化脚本 / 计划任务里直接调用 start_napcat.bat 常常失败：
# 启动出来的 QQ+NapCat 挂在调用者的进程树下，命名管道 / worker 起不来，
# 结果是进程在、WebUI 永远不通。用 WMI 让 Win32_Process 去启，进程挂到
# explorer 名下，就正常了。

param(
    [string]$NapCatDir = 'D:\NapCat'
)

$ErrorActionPreference = 'Stop'
$bat = Join-Path $NapCatDir 'start_napcat.bat'
if (-not (Test-Path $bat)) { throw "not found: $bat" }

$args = "cmd.exe /c start `"`" /min `"$bat`""
$res = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine      = $args
    CurrentDirectory = $NapCatDir
}
Write-Host ("spawned pid={0} return={1}" -f $res.ProcessId, $res.ReturnValue)
