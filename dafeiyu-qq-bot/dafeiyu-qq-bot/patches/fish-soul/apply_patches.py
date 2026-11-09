#!/usr/bin/env python3
"""给 dsh-fish-soul 打两个补丁（可重复执行，已打过就跳过）。

1. lib/sticker-find.js           —— 新增「自己找表情包」模块
2. lib/index.js                  —— import 该模块 + 注册 sticker_find 工具
3. lib/gateway.js                —— 把 sticker_find 加进 QQ 会话可用工具

用法：
    python apply_patches.py                     # 自动找 ~/.dsh/profiles/*/node_modules
    python apply_patches.py --pkg C:\\path\\to\\dsh-fish-soul
    python apply_patches.py --revert

打完必须**重启 DSH** 才生效（插件代码在启动时加载）。
"""

import argparse
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

IMPORT_ANCHOR = "} from './db.js';"
IMPORT_LINE = "import { findAndSaveStickers } from './sticker-find.js';"
TOOL_ANCHOR = "})), 'dsh-fish-soul: fish_search');"

TOOL_BLOCK = """
	// ── 工具：sticker_find（自己找表情包，优先翻图库，再上网搜；只在聊天会话里能用）──
	ctx.effect(() => ctx.tools.register(defineTool({
		name: 'sticker_find',
		description: '找表情包 / 图片（比如「大肥鱼 表情包」「小猫 表情包」）。先翻自己的图库，没有再上网找，找到存起来就能发。找完回一句存了几张、都叫什么。',
		parameters: objectSchema({
			query: { type: 'string', required: true, description: '搜索词，带上「表情包」更好找' },
			count: { type: 'number', description: '想要几张，1–6，默认 3' }
		}),
		output: textOutput,
		async execute(args, toolCtx) {
			const query = String(args.query ?? '').trim();
			if (query === '') return '没给搜索词，找不了。';
			const sid = String(toolCtx?.agent?.id ?? toolCtx?.sessionId ?? '');
			const sess = sid === '' ? undefined : sessionFor(sid);
			let ws = String(sess?.workspacePath ?? '').trim();
			if (ws === '') ws = String(currentConfig.sessions?.workspacePath ?? '').trim();
			if (ws === '') ws = dedicatedWorkspacePath();
			try {
				const r = await findAndSaveStickers({
					query, count: args.count, workspacePath: ws, box: stickers, log, signal: toolCtx?.signal
				});
				if (r.picked.length > 0) {
					return `图库里就有 ${r.picked.length} 张：${r.picked.join('、')}。想发就写 ![名字](_stickers/文件名)`;
				}
				if (r.saved.length === 0) {
					const why = r.skipped.slice(0, 2).join('；') || '没找到合适的图';
					return `找了一圈没存下来（试了 ${r.tried} 个链接：${why}）。`;
				}
				const list = r.saved.map((x) => x.file).join('、');
				return `存好了 ${r.saved.length} 张：${list}。想发就写 ![名字](_stickers/文件名)`;
			} catch (error) {
				const msg = String(error instanceof Error ? error.message : error);
				log('warn', `[fish-soul] 找表情包失败：${msg}`);
				return `这次没找成（${msg.slice(0, 120)}）。`;
			}
		}
	})), 'dsh-fish-soul: sticker_find');
"""


def find_pkg(explicit: str | None) -> str:
    if explicit:
        return explicit
    home = os.path.expanduser("~")
    profiles = os.path.join(home, ".dsh", "profiles")
    hits = []
    if os.path.isdir(profiles):
        for name in os.listdir(profiles):
            pkg = os.path.join(profiles, name, "node_modules", "dsh-fish-soul")
            if os.path.isdir(os.path.join(pkg, "lib")):
                hits.append(pkg)
    if not hits:
        raise SystemExit("找不到 dsh-fish-soul，请用 --pkg 指定目录")
    if len(hits) > 1:
        print("找到多个 profile，使用第一个：", hits[0])
    return hits[0]


def backup(path: str) -> None:
    bak = path + ".bak-sticker"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)


def patch_index(lib: str) -> bool:
    path = os.path.join(lib, "index.js")
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    if "sticker_find" in text and "sticker-find.js" in text:
        print("[patch] index.js already patched")
        return False

    if IMPORT_LINE not in text:
        if IMPORT_ANCHOR not in text:
            raise SystemExit("index.js 结构不符（找不到 db.js 的 import 结尾），版本可能不同")
        text = text.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + "\n" + IMPORT_LINE, 1)

    if "sticker_find" not in text:
        if TOOL_ANCHOR not in text:
            raise SystemExit("index.js 结构不符（找不到 fish_search 注册结尾）")
        text = text.replace(TOOL_ANCHOR, TOOL_ANCHOR + "\n" + TOOL_BLOCK, 1)

    backup(path)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("[patch] index.js patched")
    return True


def patch_gateway(lib: str) -> bool:
    path = os.path.join(lib, "gateway.js")
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    pattern = re.compile(r"export const QQ_SESSION_TOOLS = \[([^\]]*)\];")
    m = pattern.search(text)
    if m is None:
        raise SystemExit("gateway.js 里找不到 QQ_SESSION_TOOLS")
    if "'sticker_find'" in m.group(1):
        print("[patch] gateway.js already patched")
        return False
    items = [s.strip() for s in m.group(1).split(",") if s.strip()]
    items.append("'sticker_find'")
    text = text[:m.start()] + "export const QQ_SESSION_TOOLS = [" + ", ".join(items) + "];" + text[m.end():]
    backup(path)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("[patch] gateway.js patched")
    return True


def copy_module(lib: str) -> None:
    src = os.path.join(HERE, "sticker-find.js")
    dst = os.path.join(lib, "sticker-find.js")
    if os.path.exists(dst):
        print("[patch] sticker-find.js exists, overwrite")
    shutil.copy2(src, dst)
    print("[patch] sticker-find.js installed")


def revert(lib: str) -> None:
    for name in ("index.js", "gateway.js"):
        path = os.path.join(lib, name)
        bak = path + ".bak-sticker"
        if os.path.exists(bak):
            shutil.copy2(bak, path)
            print(f"[revert] {name} restored")
    module = os.path.join(lib, "sticker-find.js")
    if os.path.exists(module):
        os.remove(module)
        print("[revert] sticker-find.js removed")
    print("[revert] 重启 DSH 生效")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pkg", help="dsh-fish-soul 包目录")
    parser.add_argument("--revert", action="store_true")
    args = parser.parse_args()

    pkg = find_pkg(args.pkg)
    lib = os.path.join(pkg, "lib")
    print("[patch] package:", pkg)

    if args.revert:
        revert(lib)
        return 0

    copy_module(lib)
    changed = patch_index(lib) | patch_gateway(lib)
    print("[patch] done", "(需重启 DSH)" if changed else "(无改动)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
