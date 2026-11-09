' 大肥鱼守护：无窗口调用 guard_once.ps1
' 由计划任务调用：wscript.exe guard_hidden.vbs
' 用 WScript.Shell.Run(..., 0, True) 的 0 表示隐藏窗口，不闪黑框。

Option Explicit

Dim sh, fso, here, script
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

here = fso.GetParentFolderName(WScript.ScriptFullName)
script = fso.BuildPath(here, "guard_once.ps1")

sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & script & """", 0, True
