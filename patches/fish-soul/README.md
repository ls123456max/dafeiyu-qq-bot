# fish-soul 可选补丁

给 [dsh-fish-soul](https://github.com/Britneycode/dsh-fish-soul) 加两个小功能，**不修改它原有的任何行为**：

1. **`sticker_find` 工具**：她可以自己找表情包 —— 先翻 `_stickers` 图库，没有再上网搜（Bing 图片），存进图库后就能发。
2. **图库优先**：问「大肥鱼 / 鲸鱼」这类指向她自己的词时，直接从她自己的图库里挑，而不是搜回一堆真鱼照片。
3. **每天发一条说说 + 改签名**（v1.1）：按当天节气/节日和最近记忆写 1–2 句，发 QQ 空间说说，并顺手改个性签名。默认 9 点后一天一次、好友可见。
4. **群聊「连着说」上限**（v1.3.2）：一次接话最多 15 条，说完冷却 10 分钟才能再开口，防止和群里的机器人无限对刷。私聊不限。

## 安装

```bash
python apply_patches.py                             # 自动找 ~/.dsh/profiles/*/node_modules/dsh-fish-soul
python apply_patches.py --pkg <dsh-fish-soul 包目录>   # 手动指定
```

脚本会：

- 复制 `sticker-find.js`、`feed.js` 到 `lib/`
- 在 `lib/index.js` 里加 import、注册 `sticker_find` 工具（插在 `fish_search` 后面）、在 diary 停止之后启动 `FeedWriter`
- 在 `lib/gateway.js` 的 `QQ_SESSION_TOOLS` 里加 `'sticker_find'`
- 在 `lib/gateway.js` 加 `bjDay()` 与 `dispatch()` 开头的群聊 burst 上限
- 原文件备份为 `*.bak-sticker`

脚本是**幂等**的：已经打过的改动会跳过，重复执行不会叠加。

**打完要重启 DSH** 才生效（插件代码在启动时加载，没有热重载）。

## 卸载

```bash
python apply_patches.py --revert
```

会把 `index.js` / `gateway.js` 还原成 `*.bak-sticker`，并删掉 `sticker-find.js` 与 `feed.js`。

## 说说 / 签名配置

不用改代码，在 `soul.db` 的 `kv` 表写 `feed.config`（值为 JSON 字符串）：

```json
{"enabled": true, "hour": 9, "ugcRight": 4, "setSignature": true}
```

- `hour`：当天几点之后才发（默认 9）
- `ugcRight`：`1` 公开 / `4` 好友可见 / `16`、`128` 指定好友（需 `target_uins`）
- `setSignature`：是否同时改个性签名
- `enabled: false` 可临时关闭

节气表覆盖 2026-11 到 2027-12；节日表有除夕、春节、元宵、520、中秋、国庆等。

## 群聊「连着说」配置

不用改代码，`fish-soul-config.json` 里写：

```json
"qq": {"burstLimit": 15, "burstCooldownMinutes": 10}
```

- `burstLimit`：一次接话最多连着说几条（`0` = 不限）
- `burstCooldownMinutes`：说完冷却多少分钟才能再开口；冷却按她最后一条消息起算
- 计数存 `soul.db` 的 kv（`qq.burst.<群号>`），重启不清零

## 可选配置

```bash
# 本地表情包原件目录（多个用 ; 分隔），用来识别「哪些图是她自己那套」
set FISH_SOUL_STICKER_PACKS=D:\memes\bfpack\memes;D:\memes\dafeiyu512
```

不配也能用，只是「大肥鱼」这个词的图库优先选择会退化成随机挑。

## 兼容性

- 只在 `dsh-fish-soul 0.15.x` 上验证过
- 依赖 `index.js` 里的三个锚点：`} from './db.js';`、`})), 'dsh-fish-soul: fish_search');`、`ctx.effect(() => () => diary.stop(), 'dsh-fish-soul: diary');`
- 如果上游改了这些位置的写法，脚本会直接报错退出，不会改坏文件

## 她怎么用

人格卡里加一条（或者直接让她自己想到）：

> 想找新表情包时，用 sticker_find 搜「XX 表情包」，找完存下来，以后想发就发。别一次找太多。

工具返回的是文件名，她发图的写法是 `![名字](_stickers/文件名)`。
