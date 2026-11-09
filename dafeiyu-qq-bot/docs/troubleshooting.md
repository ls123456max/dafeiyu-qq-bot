# 故障排查

按「症状 → 先查什么 → 常见原因 → 怎么修」组织。所有命令都可以直接复制。

## 快速体检

```powershell
# 三个端口：6099 NapCat 后台 / 6200 QQ 通道 / DSH 本体
Get-NetTCPConnection -State Listen -LocalPort 6099,6200,<DSH端口> | Format-Table LocalPort,OwningProcess

# NapCat 登录状态
python scripts\napcat\napcat_relogin.py --napcat-dir D:\NapCat --status

# fish-soul 通道状态
curl http://127.0.0.1:<DSH端口>/api/plugins/fish-soul/channels/state
```

`channels/state` 里 `connected: true` + `selfId` 正确 = 她此刻能收到消息。

## 1. 她完全不回消息

按顺序查：

1. **6200 没监听** → NapCat 没登录 / 登录态失效
   - `--status` 看 `loginPhase`：`ready` 正常，`waiting_qrcode` 要扫码，`qrcode_scanned` 卡住要重启 NapCat
2. **6200 在、但 connected:false** → DSH 没连上，重启 DSH
3. **都正常但群里不回** → 见第 5 条
4. **私聊不回但群里回** → 对方不是好友；私聊默认只回好友

## 2. NapCat 进程在，但 6099 打不开

原因只有两个：

- **路径带中文**：挪到 `D:\NapCat`
- **从脚本子进程直接启动**：QQ/NapCat 挂在调用者进程树下，注入的 worker 起不来。
  改用 WMI 分离启动：

```powershell
powershell -File scripts\napcat\start_napcat.ps1 -NapCatDir D:\NapCat
```

另外：**从启动到 6099 监听要 2–3 分钟**，别 20 秒就判死刑。

## 3. 动不动就要重新扫码

最常见的原因是**同时跑了两个 QQ 实例**：后登录的那个把前一个的登录态顶掉，快速登录票据随之失效。

- `start_napcat.bat` 里已经有单实例保护（`tasklist | find QQ.exe`），别删
- 守护脚本里「6099 不通就重启 QQ」必须限流（默认 30 分钟一次），否则会陷入
  「重启 → 需扫码 → 再重启」的死循环
- 登录后建议在 QQ 设置里勾上「自动登录」，并给机器人账号固定：NapCat 接口
  `POST /api/QQLogin/SetQuickLoginQQ {"uin": "<小号>"}`

## 4. 二维码扫了没反应 / 提示过期

- NapCat 的登录码 **1–2 分钟就失效**，截图发来发去基本来不及
- 用本地常驻页面：`pythonw scripts\napcat\qr_portal.py --napcat-dir D:\NapCat`
  打开 `http://127.0.0.1:6210`，每 20 秒自动换新码
- 扫码后卡在 `qrcode_scanned` 超过 30 秒：杀干净 QQ 再启动一次，通常能过

## 5. 群里 @ 她不理

依次排除：

1. `groupAllowList` 里有没有这个群号（空 = 谁都不理）
2. 是否真的 @ 了（或者引用了她的消息）
3. **QQ 客户端本身的群消息推送卡住**——重启一次 QQ 客户端即可恢复
   （这个坑很隐蔽：私聊正常、群里一条都进不来，日志上看不出错误）
4. 群里有人刷屏时会被限流（冷却 + 每小时上限），这是设计如此

## 6. PowerShell 脚本报「找不到路径」

PowerShell 5.1 读**无 BOM** 的 UTF-8 脚本会按 ANSI 解码，中文路径变乱码。
写 `.ps1` 时用：

```powershell
Set-Content -Path x.ps1 -Value $content -Encoding UTF8   # 5.1 会写成带 BOM
```

## 7. WMI 启动 powershell 没反应

实测 `Win32_Process.Create` 启 `powershell.exe`（带 `-File` 或 `-Command`）可能不执行，
但启 `cmd.exe /c ...` 正常。
所以：用 `cmd` 包一层，或者用 `wscript.exe` 跑 VBS（`guard_hidden.vbs` 就是这么干的）。

## 8. 她的表情包发不出来

- 文件名不能带空格、括号、`|`、`#` 等；用 `scripts/stickers/import_stickers.py` 导入会自动清理
- 有的图站把 JPEG 当 GIF 返回（content-type 骗人），QQ 会拒收。
  按**文件头**判断真实格式：`FF D8 FF` = JPEG，`89 50 4E 47` = PNG，`47 49 46` = GIF
- GIF 超过 4MB 容易失败，导入时缩到 420px

## 9. 费用突然变高

- 会话太长：跑 `python scripts\session\rotate_session.py --dry` 看当前会话大小，
  每天自动换一次
- 开了语音/思考模式：关掉
- 群聊白名单太宽、或者 `interject` 概率太高（每次插话判断也是一次调用）

## 10. 电脑关机 / 睡眠后不恢复

- 关机 = 全停，没有云端兜底；开机后靠「启动文件夹 + 计划任务」恢复
- 睡眠会掐断 NapCat 的连接；确认电源设置里「接通电源时永不休眠」
- QQ 长时间挂机后群消息可能推送卡死，重启 QQ 客户端

## 11. 备份

数据全在 `%USERPROFILE%\.dsh\fish-soul\soul.db`（人格、记忆、好感、日程、待办）。
直接复制这个文件即可；`persona.json`、`fish-soul-config.json` 也建议一起备份。

## 12. 「明明勾了记住密码，还是要扫码」——多半是双开

同一个 QQ 号开两个实例，后登的会把先登的顶下去，快速登录票据随之失效
（`SetQuickLogin` 返回 `{"code":-1,"message":"登录态已失效，请重新登录。"}`）。

- `Get-Process QQ | Measure-Object` 或任务管理器确认只有**一个** QQ
- `start_napcat.bat` 里已经有单实例保护（`tasklist | find "QQ.exe"`），不要自己再拉一次
- 守护脚本的限流文件（`%TEMP%\dafeiyu_last_qqkill.txt` / `dafeiyu_last_quicktry.txt`）
  就是为防「重启→要扫码→再重启」的死循环

## 13. NapCat 启动了但 6099 一直不开

从双击到 6099 监听、6200 起来，实测要 **2–3 分钟**（4800X/低配机更久）。
这期间**绝对不要**再拉一个实例，否则就是第 12 条的双开。

判断「还在启动」而不是「已经死了」：

```powershell
Get-Process NapCatWinBootMain -ErrorAction SilentlyContinue        # 注入器还在跑
Get-Process QQ | Sort-Object StartTime -Descending | Select-Object -First 1   # 看最新 QQ 进程起了多久
```

`guard_once.ps1` 的做法：最新 QQ 进程启动不到 200 秒，就记一行
`6099 not up yet (NapCat still starting, wait)` 直接退出，等下一轮（5 分钟后）再看。

