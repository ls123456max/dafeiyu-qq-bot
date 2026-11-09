# 更新记录

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
