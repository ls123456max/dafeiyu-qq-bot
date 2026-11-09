# AGENTS.md —— 给 AI 代理的安装 / 操作指南

> 如果你是一个 AI 工具（Codex / Claude Code / Cursor / DSH / 其它 agent），请按本文执行。
> 人类用户只需要把仓库地址丢给你，并回答第 3 节里的几个问题。

## 1. 这个仓库是什么

一套把「大肥鱼」角色接进 QQ 的**运维工具包**，不是独立框架。运行时依赖：

| 组件 | 作用 | 谁装 |
|---|---|---|
| QQ NT 客户端 | 真正登录的客户端 | 人 |
| NapCat | 注入 QQNT，暴露 OneBot 11 | 人（下载）/ 你（启动） |
| DeepSeek Harness (DSH) | 宿主，跑插件 | 人 |
| `dsh-fish-soul` | 人格 / 记忆 / 表情包 / 抖音 | 你（`dsh plugin add`） |
| 本仓库 scripts | 守护、扫码页、换会话、表情包导入 | 你 |

## 2. 你可以自动做的事

按顺序执行，每步都要检查退出码：

```powershell
# 0) 读文档
Get-Content docs/deploy.md -TotalCount 120

# 1) 环境探测
$PSVersionTable.PSVersion           # 需要 5.1+
Test-Path 'C:\Program Files\Tencent\QQNT\QQ.exe'
Test-Path "$env:USERPROFILE\.dsh\profiles\desktop\node_modules\dsh-fish-soul"
python --version                    # 可选（扫码页 / 压图）

# 2) 安装（复制脚本 + 生成隐藏启动器 + 可选打补丁 + 注册任务）
powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 `
    -NapCatDir 'D:\NapCat' `
    -QqDir 'C:\Program Files\Tencent\QQNT' `
    -TargetUin '<小号QQ>' `
    -PortalPort 6210

# 3) 首次启动 NapCat（必须 WMI 分离，否则 6099 不监听）
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = 'cmd.exe /c start "" /min D:\NapCat\start_napcat.bat'
    CurrentDirectory = 'D:\NapCat'
}

# 4) 起扫码页，把地址给人类
Start-Process pythonw.exe -ArgumentList 'D:\NapCat\qr_portal.py','--napcat-dir','D:\NapCat','--port','6210' -WindowStyle Hidden
# 人类打开 http://127.0.0.1:6210 扫码

# 5) 等登录（NapCat 启动到就绪要 2–3 分钟，别重复拉起！）
python D:\NapCat\napcat_relogin.py --napcat-dir D:\NapCat --wait 300
# 退出码 0 = 已登录；1 = 仍需扫码；2 = 连不上 NapCat

# 6) 给 fish-soul 打补丁（可选，加了 sticker_find 工具）
python patches\fish-soul\apply_patches.py
# 还原：python patches\fish-soul\apply_patches.py --revert
```

## 3. 必须停下来问人类的事

| 需要什么 | 为什么 AI 不能自己来 |
|---|---|
| **小号 QQ 号** + 手机扫码 | 二维码必须真人扫；不要用人类的主号 |
| **模型 API Key**（DeepSeek / 智谱 GLM） | 密钥属于人类，绝不写进仓库 |
| **人格设定**（名字、性格、口头禅、底线） | 这是创作，不是配置 |
| **是否允许自动登录 / 记住密码** | 涉及账号安全，需本人决定 |
| **群号白名单** | 拉群需要人在 QQ 里操作 |

拿到答案后，写进：

- `%USERPROFILE%\.dsh\fish-soul-config.json`（结构见 `examples/fish-soul-config.example.json`）
- DSH 的 provider 配置（模型 / apiKey / baseURL）
- 人格卡（结构见 `examples/persona.example.json`，真正内容由人类定）

## 4. 安装后自检（必须全绿）

```powershell
# 端口：6099 = NapCat 后台，6200 = QQ 通道
Get-NetTCPConnection -State Listen -LocalPort 6099,6200 | Format-Table LocalPort,OwningProcess

# NapCat 登录态
python D:\NapCat\napcat_relogin.py --napcat-dir D:\NapCat --status
# 期望：isLogin=true, loginPhase=ready

# fish-soul 通道（端口换成 DSH 实际端口，见 DSH 窗口标题或设置）
curl "http://127.0.0.1:<DSH端口>/api/plugins/fish-soul/channels/state"
# 期望：connected=true，selfId=小号

# 守护任务
schtasks /Query /TN DafeiyuGuard /V /FO LIST | Select-String 'Last Result|Next Run'
```

冒烟测试：请人类在 QQ 私聊里发一句「在吗」，确认有回复（不是「正在输入」卡住）。

## 5. 硬性约束（违反会出事）

1. **NapCat 必须 WMI 分离启动**。从 agent 的 shell 直接起，进程会活着但 6099 永不监听（沙箱/进程树限制）。
2. **同一 QQ 号只能有一个实例**。双开会让登录态失效、快速登录票据作废，之后每次都要扫码。`start_napcat.bat` 已内置单实例保护，**不要**绕过。
3. **NapCat 启动要 2–3 分钟**。这期间不要重复拉起，否则就是第 2 条。
4. **全屏游戏时不要动 QQ**。守护脚本已实现，别把这段逻辑删掉。
5. **密钥、`soul.db`、`persona.json`、`_stickers/`、`webui.json` 一律不进仓库**（`.gitignore` 已覆盖）。
6. 提交前跑 `python scripts\check_secrets.py`，必须 0 命中。

## 6. 常见失败速查

| 症状 | 先看 |
|---|---|
| 她不回消息 | `docs/troubleshooting.md` 第 1 条：6200 是否监听 → 登录态 → fish-soul connected |
| 6099 打不开 | 第 13 条：是否还在启动（最长 3 分钟）、是否双开 |
| 每次都要扫码 | 第 12 条：双开 / 快速登录票据失效 |
| 表情包发不出 | 文件名非法字符 / 假 GIF（按文件头判断）/ >4MB |
| 费用突然变高 | `docs/cost.md`：会话太长、思考模式、插话概率 |

## 7. 卸载

```powershell
schtasks /Delete /TN DafeiyuGuard /F
# 再删除 <NapCatDir>\guard\、start_napcat.bat、qr_portal.py、napcat_relogin.py
# 数据不会自动删：%USERPROFILE%\.dsh\fish-soul\soul.db 需要人类确认后再删
```
