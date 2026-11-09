# fish-soul 可选补丁

给 [dsh-fish-soul](https://github.com/Britneycode/dsh-fish-soul) 加两个小功能，**不修改它的任何原有行为**：

1. **`sticker_find` 工具**：她可以自己找表情包 —— 先翻 `_stickers` 图库，没有再上网搜（Bing 图片），存进图库后就能发。
2. **图库优先**：问「大肥鱼 / 鲸鱼」这类指向她自己的词时，直接从她自己的图库里挑，而不是搜回一堆真鱼照片。

## 安装

```bash
python apply_patches.py          # 自动找 ~/.dsh/profiles/*/node_modules/dsh-fish-soul
python apply_patches.py --pkg <dsh-fish-soul 包目录>   # 手动指定
```

脚本会：

- 复制 `sticker-find.js` 到 `lib/`
- 在 `lib/index.js` 里加 import + 注册工具（插在 `fish_search` 后面）
- 在 `lib/gateway.js` 的 `QQ_SESSION_TOOLS` 里加 `'sticker_find'`
- 原文件备份为 `*.bak-sticker`

**打完要重启 DSH** 才生效（插件代码在启动时加载，没有热重载）。

## 卸载

```bash
python apply_patches.py --revert
```

## 可选配置

```bash
# 本地表情包原件目录（多个用 ; 分隔），用来识别「哪些图是她自己那套」
set FISH_SOUL_STICKER_PACKS=D:\memes\bfpack\memes;D:\memes\dafeiyu512
```

不配也能用，只是「大肥鱼」这个词的图库优先选择会退化成随机挑。

## 兼容性

- 只在 `dsh-fish-soul 0.15.x` 上验证过
- 依赖 `index.js` 里的两个锚点：`} from './db.js';` 和 `})), 'dsh-fish-soul: fish_search');`
- 如果上游改了这两个位置的写法，脚本会直接报错退出，不会改坏文件

## 她怎么用

人格卡里加一条（或者直接让她自己想到）：

> 想找新表情包时，用 sticker_find 搜「XX 表情包」，找完存下来，以后想发就发。别一次找太多。

工具返回的是文件名，她发图的写法是 `![名字](_stickers/文件名)`。
