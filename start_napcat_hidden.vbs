' 隐藏方式启动 NapCat（计划任务 / 守护脚本用，全程无窗口、不在任务栏留东西）
'
' 放在 NapCat 目录下（和 start_napcat.bat 同级），用法：
'   wscript.exe "D:\NapCat\start_napcat_hidden.vbs"
'
' 原理：WScript.Shell.Run 的第二个参数 0 = 隐藏窗口，False = 不等待。
' 直接 `cmd /c start /min xxx.bat` 会留下一个控制台窗口（NapCat 进程挂在它下面），
' 这个脚本让控制台从一开始就是隐藏的。
Dim fso, sh, here, bat
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
here = fso.GetParentFolderName(WScript.ScriptFullName)
bat = here & "\start_napcat.bat"
If Not fso.FileExists(bat) Then
    WScript.Quit 1
End If
sh.Run "cmd.exe /c """ & bat & """", 0, False
