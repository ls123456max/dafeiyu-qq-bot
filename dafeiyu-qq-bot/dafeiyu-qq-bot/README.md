# 大肥鱼 QQ Bot · 部署与运维工具包

把「大肥鱼」这类角色人格接进 QQ，让它像真人一样聊天：有记忆、会发表情包、能自己刷抖音、可以在群里被 @ 回应。

这个仓库不是一个新的聊天框架，而是**一套把现成组件粘起来、并解决它在 Windows 上长期挂机时各种「又掉线了」问题的工具与补丁**。主力运行时是 [DeepSeek Harness](https://github.com/deepseek-ai) 的插件 `dsh-fish-soul`，QQ 通道走 [NapCat](https://github.com/NapNeko/NapCatQQ)（OneBot 11）。

> 只想看费用请翻到 [docs/cost.md](docs/cost.md)；只想部署请直接看 [docs/deploy.md](docs/deploy.md)。

---

## 1. 整体架构

```
┌──────────────┐   OneBot 11 (正向 WS)   ┌──────────────────────────┐
│   NapCat     │ ◀─────────────────────── │  DeepSeek Harness (DSH)  │
│ (注入 QQNT)  │                         │  └─ dsh-fish-soul 插件    │
│  127.0.0.1   │ ──────────────────────▶ │       ├─ 人格卡 / 记忆    │
│  :6099 WebUI │   QQ 消息 / 图片 / 语音   │       ├─ 表情包 _stickers │
│  :6200 WS    │                         │       ├─ 抖音/ B 站      │
└──────────────┘                         │       └─ 主动开口 / 养成  │
        ▲                                └──────────────────────────┘
        │ 守护脚本（计划任务，每 5 分钟）
        │  · 检查 6099 / 6200
        │  · 缺 NapCat 就拉起（单实例保护）
        │  · 全屏游戏时什么都不做
        └─ 开机自启：DSH + 守护脚本
```

- **NapCat** 负责「真的登录 QQ」：把 QQNT 客户端注入，暴露 OneBot 11 接口。
- **DSH + dsh-fish-soul** 负责「她是谁」：人格、按人记忆、好感/养成、表情包、抖音、主动开口。
- **本仓库的脚本** 负责「别死」：开机自启、掉线拉起、扫码页面、每日换会话、表情包导入。

## 2. 目录

| 路径 | 作用 |
|---|---|
| `scripts/guard/` | 守护脚本：单次检查、隐藏运行、注册计划任务 |
| `scripts/napcat/` | 启动 NapCat、二维码扫码页面、快速登录与重登 |
| `scripts/session/` | 每天 05:00 换会话（控制 token 成本） |
| `scripts/stickers/` | 把表情包目录导入 `_stickers`（自动改名/压缩大 GIF） |
| `patches/fish-soul/` | 给 `dsh-fish-soul` 打的补丁：她自己上网找表情包（图库优先，再 Bing 搜图） |
| `examples/` | `fish-soul-config` 示例、NapCat OneBot 示例、人格卡模板（都做了脱敏） |
| `docs/` | 部署步骤、费用估算、故障排查 |
| `requirements.txt` | Python 可选依赖：`qrcode`（扫码页）、`pillow`（压大 GIF） |

## 3. 前置条件

- Windows 10/11（脚本按 PowerShell 5.1 + 计划任务写的，无额外依赖）
- QQ NT 客户端（9.9.x 即可；4.x/旧版 QQ 不适用）
- 一个**小号**（强烈建议，见第 7 节合规说明）
- DeepSeek Harness（跑 `dsh-fish-soul`），或愿意改用 AstrBot + 大肥鱼配置包的等价方案
- Python 3.10+（只给扫码页面、导入脚本用；`pip install -r requirements.txt`）

### 3.1 需要你自己准备的东西（仓库里没有）

| 东西 | 说明 |
|---|---|
| QQ 小号 | 单独养一个，别用主号（见第 7 节合规说明） |
| 大模型 API Key | DeepSeek 或智谱 GLM，填进 DSH 的 provider 配置 |
| 人格卡 | `examples/persona.example.json` 是空壳模板；真正的人格按你的角色写，导入 fish-soul 的设置页 |
| 表情包 | 仓库不打包图片；用 `scripts/stickers/import_stickers.py` 把自己的图导进 `_stickers` |
| NapCat | 从官方 Releases 下（`NapCat.Shell.Windows.OneKey.zip`），本仓库不重复分发 |
| DSH + dsh-fish-soul | `dsh plugin --profile desktop add dsh-fish-soul` 安装 |


## 4. 快速开始

### 4.1 装 NapCat 并注入 QQ

1. 从 [NapCat Releases](https://github.com/NapNeko/NapCatQQ/releases) 下 `NapCat.Shell.Windows.OneKey.zip`
2. **解压到纯英文路径**（例如 `D:\NapCat`）。中文路径会导致注入失败：
   `Error: Cannot find module '...\resources\app\loadNapCat.js'`
3. 用 `scripts/napcat/start_napcat.bat` 启动（把里面的路径改成你自己的）
4. 浏览器打开 `http://127.0.0.1:6099`，用 QQ 扫码登录

> 启动 NapCat 必须**脱离启动它的终端进程树**。在自动化脚本里直接 `& NapCatWinBootMain.exe` 会「进程活着但 6099 永远不监听」，正确做法是用 WMI 分离启动：
>
> ```powershell
> Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
>     CommandLine = 'cmd.exe /c start "" /min D:\NapCat\start_napcat.bat'
>     CurrentDirectory = 'D:\NapCat'
> }
> ```

### 4.2 让 fish-soul 连上 QQ

1. 在 NapCat 后台的「网络配置」里加一个 **WebSocket 服务器**：`127.0.0.1:6200`，消息格式 `array`（可直接抄 `examples/napcat-onebot.example.json`）
2. 装插件：`dsh plugin --profile desktop add dsh-fish-soul`
3. 填配置（`~/.dsh/fish-soul-config.json` 或设置页）：

```jsonc
{
  "masterQqUin": "你的大号",
  "qq": {
    "enabled": true,
    "wsUrl": "ws://127.0.0.1:6200",
    "accessToken": "",
    "allGroups": false,
    "groupAllowList": ["123456789"],
    "callNames": ["小鱼", "大肥鱼"]
  }
}
```

4. 导入人格卡（见 `docs/deploy.md` 第 5 节；本仓库不附带人格文本，避免版权问题）

### 4.3 开机自启 + 掉线自愈

```powershell
# 1) 计划任务：每 5 分钟跑一次守护（无窗口）
schtasks /Create /TN "DafeiyuGuard" /TR 'wscript.exe "D:\NapCat\guard_hidden.vbs"' /SC MINUTE /MO 5 /F

# 2) 启动文件夹放两个快捷方式：DSH 本体 + 守护
#    （放到 shell:startup 里即可，开机登录后自动跑）
```

`scripts/guard/register-task.ps1` 里有完整参数和说明。

## 5. 费用（一句话版）

| 项目 | 费用 |
|---|---|
| 大肥鱼人格 / 表情包 / fish-soul 插件 | 0 元（开源） |
| QQ 通道（NapCat） | 0 元，但违反腾讯协议、有封号风险 |
| 模型（DeepSeek `deepseek-flash`） | 约 **0.002–0.005 元/轮**，50 轮/天 ≈ 0.1–0.25 元/天 |
| 模型（智谱 `glm-5.3-flash`，新用户赠送额度内） | 0 元，2000 万 token ≈ 400–700 轮 |
| 语音（Edge TTS） | 0 元；云端 TTS 按分钟计费 |
| 机器 | 你的电脑得一直开着 |

**真正决定花多少的是「每轮上下文长度」**：同一轮对话，缓存命中 0.001 元、全未命中 0.05 元，差 50 倍。
详细测算见 [docs/cost.md](docs/cost.md)。

## 6. 日常运维

| 想做的事 | 怎么做 |
|---|---|
| 看她最近说了什么 | DSH 会话列表 → 对应 QQ 聊天 |
| 改人格 | 编辑 `~/.dsh/fish-soul/persona.json`，或调用 `POST /api/plugins/fish-soul/persona/apply` |
| 加表情包 | 把图丢进 `~/.dsh/fish-soul/workspace/_stickers/`，文件名就是她发图时的「名字」 |
| 清缓存/省钱 | 跑 `scripts/session/rotate_session.py`，让她下一条消息开新会话 |
| 看她花了多少 | DeepSeek 控制台的用量页；本地看 `~/.dsh/.dshw-usage.json`（只有余额差） |
| 临时停掉她 | 停 NapCat（她收不到消息），或把 `qq.enabled` 设 false |

## 7. 合规与风险（务必读）

- **个人 QQ 接机器人违反腾讯用户协议**。用协议端/hook 登录有被风控、冻结、封号的可能；本项目默认只建议用小号，且不与重要账号同设备登录。
- **微信同理**：微信没有官方群机器人接口，个人微信自动化同样违规。企业微信/公众号客服是合规路线，但只能覆盖企微群或一对一。
- 人格、表情包素材多为同人二创，**转载/二次分发前请确认原作者许可**。
- 本项目只包含「胶水代码」，不包含任何官方客户端、模型权重、人格文本或表情包素材。

## 8. 已知坑（都踩过）

1. NapCat 目录不能带中文
2. 从脚本子进程启动 NapCat → 6099 不监听；必须 WMI 分离启动
3. PowerShell 5.1 读**无 BOM** 的 UTF-8 脚本会把中文路径读成乱码 → 写 `.ps1` 用 `Set-Content -Encoding UTF8`（带 BOM）
4. 快速登录/扫码卡在 `qrcode_scanned` → 重启一次 NapCat 通常能过
5. 两个 QQ 实例同时跑（重复拉起）→ 登录态被顶掉、频繁要扫码；**启动前必须检查单实例**
6. NapCat 从启动到 6099 监听要 **2–3 分钟**，等待窗口别设太短
7. 群消息收不到 ≠ 白名单问题，先重启一次 QQ 客户端

## 9. 参考

- [NapCatQQ](https://github.com/NapNeko/NapCatQQ)
- [dsh-fish-soul](https://github.com/Britneycode/dsh-fish-soul)
- [AstrBot](https://github.com/AstrBotDevs/AstrBot)
- [大肥鱼配置包](https://github.com/zexuanw958-svg/dafeiyu-config-pack)（人格/插件，MIT）
- [diwer/ai-biaoqingbao](https://github.com/diwer/ai-biaoqingbao)（表情包，作者声明 AI 二创）

## License

MIT（仅限本仓库脚本）。人格、表情包、QQ 客户端等第三方内容遵循各自许可。

## 上传到 GitHub

```bash
git init
git add .
git commit -m "init: 大肥鱼 QQ bot 部署与运维工具包"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

没装 git 的话，两个替代方案：

1. 到 github.com/new 建空仓库 → 点「uploading an existing file」→ 把本目录所有文件拖进去
2. 用 GitHub Desktop：Add local repository → 选本目录 → Publish repository

提交前建议再跑一遍「有没有把密钥/QQ 号带进去」的自查（见 `docs/troubleshooting.md` 最后一节）。
