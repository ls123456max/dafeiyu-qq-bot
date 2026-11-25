' 隐藏方式跑每日换会话（计划任务用，全程无窗口）
'
' 放在 NapCat 目录下（和 rotate_session.ps1 同级），用法：
'   wscript.exe "D:\NapCat\rotate_hidden.vbs"
'
' 计划任务里直接写 powershell.exe 会闪一下控制台窗口；用这个脚本就没有。
Dim fso, sh, here, ps1
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
here = fso.GetParentFolderName(WScript.ScriptFullName)
ps1 = here & "\rotate_session.ps1"
If Not fso.FileExists(ps1) Then
    WScript.Quit 1
End If
sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1 & """", 0, True
