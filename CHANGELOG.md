# 更新记录

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
