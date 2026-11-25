# 更新记录

## v1.3.9（2026-11-25）

### 新增：开机就自动登录，不用等人扫码

- `scripts/napcat/start_napcat.bat` 在拉起 `NapCatWinBootMain.exe` 之前，若存在 `<NapCatDir>\secrets\quick_login.env`，先 `call` 它，把 `NAPCAT_QUICK_ACCOUNT` / `NAPCAT_QUICK_PASSWORD_MD5` 注入环境。NapCat 启动时会用这两个值走 `requestQuickLogin`，失败再退到 `requestPasswordLogin`，全程不拉二维码。
- `scripts/napcat/set-qq-password.ps1` 新增 `-Uin` / `-QuickLogin`：存 DPAPI 密文的同一次，额外生成这份 env（ASCII、无 BOM、ACL 只留当前 Windows 用户）。MD5 算法与 `guard_once.ps1` 的 `Invoke-PasswordLogin` 完全一致（明文按 UTF-8 取 MD5，32 位小写）。
- 背景：v1.3.8 修的是「掉线后能自愈」，但**开机/重启**那一轮仍要扫码——QQ 重建后快速登录票据表里没有小号，密码登录又撞风控。补上 env 后，正常关机的下一次开机可以做到零人工。
- 现象对照：补之前开机日志是 `quick login failed -> no record`，随后 `needCaptcha`；补之后同一条链路直接走通。
- 注意：env 里是明文 MD5，等同于密码的 API 凭据。不要提交，`secrets/` 已在 `.gitignore` 里。

## v1.3.8（2026-11-16）

### 修复：隐藏启动器会挂住

- v1.3.7 引入的 `wscript.exe start_napcat_hidden.vbs` 在 **QQ 完全没运行** 时会把 wscript 挂住、不启动 NapCat：守护每 5 分钟记录一次 `NapCat(6099) down -> start`，但永远拉不起来（2026-11-16 21:18–22:22 连续 4 次失败）。
- `guard_once.ps1` 的两处启动命令改回稳定的 `cmd.exe /c start "" /min "<NapCatDir>\start_napcat.bat"`（WMI 分离启动），并在 6099 起来后调用新增的 `Hide-NapcatWindow`，把那个最小化控制台用 `ShowWindow(hwnd, 0)` 藏掉，不杀进程。
- 日志新增：`hid console window: <进程名> pid <pid>`。
- `start_napcat_hidden.vbs` 仍保留在仓库里，但**不再被守护使用**（手动双击仍可用，前提是 QQ 已在运行）。

## v1.3.7（2026-11-11）

### 修复：控制台窗口不再弹到桌面

- 新增 `scripts/napcat/start_napcat_hidden.vbs`：自定位到同目录的 `start_napcat.bat`，用 `WScript.Shell.Run` 的窗口样式 `0` 启动，控制台从头就是隐藏的，任务栏不留东西。
- `scripts/guard/guard_once.ps1` 里两处拉起 NapCat 的命令从 `cmd.exe /c start "" /min ...` 改成 `wscript.exe <NapCatDir>\start_napcat_hidden.vbs`。
- 新增 `scripts/session/rotate_hidden.vbs`：给「每天 05:00 换会话」的计划任务用，不再闪 powershell 窗口。
- `install.ps1` 会一并复制隐藏启动器；`README.md` / `AGENTS.md` 里的 WMI 启动示例同步更新。
- 说明：`cmd /c start "" /min xxx.bat` 只把窗口最小化，NapCat 进程挂在这个控制台下面，窗口会一直留在任务栏——这是之前「老弹黑框」的根源。

## v1.3.6（2026-11-10）

### 修复：v1.3.4 的闸门插错了位置，机器重启后守护永远不启动 NapCat

v1.3.4 想加「6099 没起来就别试登录」，但字符串替换匹配到了前面「去重检查」那行 `if (-not (Listening 6200))`，闸门被插到「启动 NapCat」之前。结果：机器重启后每一轮守护都在启动 NapCat 前就 `exit 0`，日志只有 `6099 not up yet -> skip login this round`，一整天没把她拉起来。

现在闸门挪到 6099 启动逻辑之后、6200 检查之前。实测：修好后手动跑一次，6099 正常起来（pid 15788）。

## v1.3.5（2026-11-09）

### 改进：整树重启先「温和退出」，别再把 QQ 的账号凭据弄丢

根因：QQ 把「记住密码」的账号表写在 `nt_db\login.db`（另有 4MB 的 `login.db-wal`）。守护过去用 `Stop-Process -Force` 直接砍进程，WAL 来不及 checkpoint，账号记录就一直没落盘——于是 `GetQuickLoginListNew` 里永远只有别的号。

现在 `Repair-Qq` 改为先 `Stop-QqSoft()`：对每个 QQ 进程 `CloseMainWindow()` → 等最多 8 秒 → 还在才 `Stop-Process -Force`，然后再清 QQEX / NapCatWinBootMain。只影响「整树修复」这一条路径，日常检查不会碰 QQ。

## v1.3.4（2026-11-09）

### 修复：NapCat 还在启动时不要去试登录

22:16 那次掉线里，守护在 6099 还没起来时就去快速登录，拿到 `无法连接到远程服务器`，却把 30 分钟限流用掉了，后面真正的重试反而被挡。现在 6099 不为听时直接跳过本轮，不消耗限流。

## v1.3.3（2026-11-09）

### 修复：密码登录与整树重启的三个坑

- **密码登录不再把 `needCaptcha` 当成功**：QQ 风控要求短信验证时，登录不会真的完成；现在把验证链接写到 `<NapCatDir>\last_captcha.txt`，日志记 `password login needs SMS captcha -> ...`，并直接进入「需要扫码」分支。
- **需要扫码时不再做整树重启**：快速登录记录已丢 / 要求短信验证的情况下重启只会把仅存的票据也清掉；现在这两种情况只开扫码页 + 托盘提醒。
- **整树重启降频**：45 分钟一次 → **每天最多一次**，避免持续触发风控。

实测（2026-11-09 19:53）：QQ 要求短信验证，守护按新逻辑不再空转重启；用户扫码后 6200 立刻恢复。

## v1.3.2（2026-11-09）

### 新增：群聊「连着说」上限

- 一次接话最多连续说 15 条（`qq.burstLimit`），说完冷却 10 分钟（`qq.burstCooldownMinutes`）才能再开口；冷却按她最后一条消息起算，超过 10 分钟没说话就重新计数。
- 私聊不受限；计数存 `soul.db` 的 kv（`qq.burst.<群号>`），重启不清零。
- 触发时日志记 `连着说了 N 条，冷却中（约 M 分钟后能再开口）`，本条不回。
- 补丁在 `patches/fish-soul/apply_patches.py` 里作为第三个改动点；从旧的「每天 15 条」版本升级需先 `--revert`。

## v1.3（2026-11-09）

### 新增：密码登录，掉线后不用再扫码

- `scripts/napcat/set-qq-password.ps1`：交互式输入小号密码，存成 Windows DPAPI 密文（`<NapCatDir>\secrets\qq_pwd.dpapi`，只有本机当前用户能解，已进 `.gitignore`）。
- `scripts/guard/guard_once.ps1` 增加 `Invoke-PasswordLogin`：调用 NapCat 的 `POST /api/QQLogin/PasswordLogin`（`{uin, passwordMd5}`）。
- 守护顺序变为：**快速登录 → 密码登录 → 整树重启 + 重试 → 扫码页 + 托盘气泡**。
- 实测（2026-11-09）：快速登录票据被 QQ 清掉、只剩大号的情况下，`PasswordLogin` 一次成功，6200 立刻恢复、无需扫码。

### 其它

- `docs/troubleshooting.md` 第 16 条：密码登录失败怎么查（`passwordMd5 is empty` / `登录态已失效` / 需要设备验证）。

## v1.2（2026-11-09）

### 修复：掉线后「静默两小时」

- 现象：QQ 自己重建子进程（`utility/node`、`network`、`gpu`）后，跑在里面的 NapCat 随之重启，6200 消失、快速登录票据被清；守护按「不弹窗」的约定只写日志，于是从掉线到被发现可能隔几个小时。
- `scripts/guard/guard_once.ps1` 现在分三级处理：
  1. 先快速登录（30 分钟限流，不变）；
  2. 快速登录失败时，**整棵 QQ 重起一次**再试（`Repair-Qq`，45 分钟限流）——子进程重建导致的失联，多数情况能靠这一步把票据带回来；
  3. 仍失败才开扫码页，并发一条**托盘气泡通知**（`Notify-Scan`，60 分钟限流，不抢焦点、不弹窗口，全屏游戏时仍然完全不打扰）。
- 快速登录成功后顺带重新钉一次「自动登录账号」（`SetQuickLoginQQ`），减少下次又退回大号。
- 日志新增：`repair: restart QQ tree...`、`repair: NapCat back up, retry quick login`、`notified: needs QR scan`。

### 其它


- `docs/troubleshooting.md` 第 15 条：为什么「什么都没干」也会掉线。

## v1.1（2026-11-09）

### 新增：她自己发说说、改个性签名

- `patches/fish-soul/feed.js`：每天 9 点后检查一次，当天没发过就让模型按「当天节气 / 节日 + 最近记忆」写 1–2 句（40 字内），发一条 QQ 空间说说，并把个性签名换成同一条。
- 节气表覆盖 2026-11 至 2027-12；节日表含除夕、春节、元宵、520、中秋、国庆等。
- 可配置：`soul.db` 的 `kv` 表写 `feed.config`，字段 `enabled` / `hour` / `ugcRight` / `setSignature`。
- 说明：`send_qzone_msg` 的 `ugc_right` 只支持 `1 / 4 / 16 / 64 / 128`；`get_qzone_msg_list` 在 NapCat 上不可用。

### 新增：守护脚本自动清理双开 QQ

- `scripts/guard/guard_once.ps1` 增加 `Remove-DuplicateQq`：按进程树找出多个 QQ 根实例时，保留最早启动的那个（NapCat 注入的），杀掉其余；只在 6200 不通时触发，全屏游戏时仍然什么都不做。
- 双开是「登录态反复失效、每次都要扫码」的根因，这一版起会自动收敛。

### 其它


- README 增加「4.4 让她自己发说说 / 改签名」；已知坑补两条（`get_supported_actions` 不可信、`ugc_right` 取值范围）。
- `patches/fish-soul/apply_patches.py` 同时管理两个补丁，仍是幂等的，`--revert` 会一并还原。

## v1.0（2026-11-09）

- 首次发布：NapCat + DSH/fish-soul 的部署与长期挂机工具包。
- 守护脚本（全屏跳过、单实例、30 分钟限流、快速登录、扫码页）、扫码页面、每日换会话、表情包导入、密钥自检。
- `patches/fish-soul`：`sticker_find` 工具（图库优先，再 Bing 搜图）。
