# 部署步骤（从零到能聊天）

预计 40–60 分钟。全程只需要一台 Windows；**不要用主力 QQ**。

## 0. 准备

- Windows 10/11，64 位
- QQ NT 客户端（9.9.x；先登一次确认能正常登录）
- 一个 QQ 小号（加几个好友、建一个测试群，别拿它加重要的人）
- DeepSeek Harness（下称 DSH）已安装，`dsh-fish-soul` 插件已能正常启动
- Python 3.10+（可选，只给扫码页 / 导入脚本用）
- 一个模型 API key（DeepSeek 或智谱皆可）

## 1. NapCat

1. 下 [NapCat.Shell.Windows.OneKey.zip](https://github.com/NapNeko/NapCatQQ/releases)
2. **解压到纯英文路径**，例如 `D:\NapCat`
   - 中文路径会直接失败：`Cannot find module '...\loadNapCat.js'`
3. 把 `scripts/napcat/start_napcat.bat` 复制进 `D:\NapCat`，改成你的 QQ 安装路径
4. 双击运行，等 2–3 分钟（**真的需要这么久**），直到 `http://127.0.0.1:6099` 能打开
5. 用**小号**扫码登录

> 如果 6099 一直打不开：99% 是启动方式问题。不用双击，改用
> `powershell -File scripts/napcat/start_napcat.ps1 -NapCatDir D:\NapCat`
> 它用 WMI 把进程从当前终端里分离出去。

首次登录后，在 NapCat 后台的「网络配置」里加：

| 项 | 值 |
|---|---|
| 类型 | WebSocket 服务器 |
| 地址 | `127.0.0.1` |
| 端口 | `6200` |
| 消息格式 | `array` |

保存后会立刻生效，不用重启 QQ（重启也无妨）。

## 2. fish-soul 插件

```bash
dsh plugin --profile desktop add dsh-fish-soul
```

装完在 DSH 设置里能找到「大肥鱼」相关的设置页。**如果装完不生效，重启一次 DSH。**

### 2.1 连接 QQ

配置文件是 `%USERPROFILE%\.dsh\fish-soul-config.json`，最小可用：

```jsonc
{
  "masterQqUin": "你的大号QQ",
  "qq": {
    "enabled": true,
    "wsUrl": "ws://127.0.0.1:6200",
    "accessToken": "",
    "allGroups": false,
    "groupAllowList": ["你的测试群号"],
    "callNames": ["小鱼", "大肥鱼"]
  }
}
```

- `groupAllowList` 是**白名单**：空数组 = 任何群都不理；`allGroups: true` = 所有群都理（不建议）
- 群里默认只响应 @ 和引用；`interject` 是「没被点名也插一句」，默认关闭

### 2.2 人格卡

自己写，或者从开源配置包导入。最小结构（`%USERPROFILE%\.dsh\fish-soul\persona.json`）：

```jsonc
{
  "spec": "chara_card_v2",
  "spec_version": "2.0",
  "data": {
    "name": "大肥鱼",
    "description": "她是谁、什么性格、怎么说话（这里权重最高）",
    "personality": "用「什么时候会怎么做」来写，别用形容词堆",
    "mes_example": "多给例子，例子比规则好使",
    "post_history_instructions": "格式要求，比如「条与条之间空一整行」",
    "character_book": { "entries": [] }
  }
}
```

改完调用接口生效（不用重启）：

```bash
curl -X POST http://127.0.0.1:<DSH端口>/api/plugins/fish-soul/persona/apply \
     -H "Origin: http://127.0.0.1:<DSH端口>" -H "Content-Type: application/json" \
     -d '{"card": {...}}'
```

### 2.3 模型

在 DSH 设置里选模型即可。建议 `deepseek-flash`（便宜、够用），并**关掉推理/思考**以省输出 token。

### 2.4 表情包

```bash
python scripts/stickers/import_stickers.py --src D:\memes\pack --prefix "大肥鱼-"
```

图放进 `%USERPROFILE%\.dsh\fish-soul\workspace\_stickers\`；她发图时写 `![名字](_stickers/文件名)`。
注意：收藏上限 300 张（`_stickers` 满了就不再自动收藏聊天里的图）。

## 3. 守护 + 开机自启

```powershell
# 每 5 分钟检查一次（无窗口）
powershell -File scripts\guard\register-task.ps1
```

再把两个快捷方式放进 `shell:startup`：

- `DeepSeek Harness.exe`
- `wscript.exe "D:\NapCat\guard_hidden.vbs"`

## 4. 验证

1. 用大号私聊小号发「在吗」，看是否回（1–2 条短句）
2. 群里 @ 她，看是否回
3. 看 `guard.log` 有没有 `ok 6099+6200 up`
4. 重启一次电脑，确认开机后 3–5 分钟内能自动恢复、不需要扫码

## 5. 可选

- 每天 05:00 换会话：
  `schtasks /Create /TN "DafeiyuRotate" /TR "python C:\path\rotate_session.py" /SC DAILY /ST 05:00 /F`
- 抖音：`POST /api/plugins/fish-soul/channels/douyin-config` 开 `enabled` + `browse.enabled`，
  再 `POST /douyin/browser/start` 打开专用浏览器登录一次
