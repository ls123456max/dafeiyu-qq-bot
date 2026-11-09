#!/usr/bin/env python3
"""给 dsh-fish-soul 打两个补丁（可重复执行，已打过就跳过）。

1. lib/sticker-find.js           —— 新增「自己找表情包」模块
2. lib/feed.js                   —— 新增「每天发一条 QQ 空间说说 + 改签名」模块
3. lib/index.js                  —— import 两个模块、注册 sticker_find 工具、启动 FeedWriter
4. lib/gateway.js                —— 把 sticker_find 加进 QQ 会话可用工具

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

# ── 动态/签名补丁（v1.1）──
FEED_IMPORT_ANCHOR = "} from './behavior.js';"
FEED_IMPORT_LINE = "import { FeedWriter } from './feed.js';"
FEED_ANCHOR = "ctx.effect(() => () => diary.stop(), 'dsh-fish-soul: diary');"
FEED_BLOCK = """
	// ── 每天一条自己的 QQ 空间说说 + 个性签名（有节气/节日时自然带到）──
	const feed = new FeedWriter({
		db, clock, worker, callLlm: llmRouter.bound('diary'), getConfig, personaName: () => persona.name, channel, note: noteAct, log
	});
	feed.start(hook.feedEveryMs ?? 10 * 60_000);
	ctx.effect(() => () => feed.stop(), 'dsh-fish-soul: feed');
"""

# ── 群聊每日回复上限（v1.3.1）：防止和群里的机器人无限对刷 ──
CAP_DAY_ANCHOR = "/** QQ 会话里模型能用的全部工具"
CAP_HELPER = """/** 北京时间当天（YYYY-MM-DD），记在 burst 计数里方便排查。 */
function bjDay(ms) {
	return new Date(ms + 8 * 3600_000).toISOString().slice(0, 10);
}

"""
CAP_DISPATCH_ANCHOR = (
    "\tasync dispatch(channelId, items) {\n"
    "\t\tif (this.stopped || items.length === 0) return;\n"
    "\t\tconst first = items[0].m;"
)
CAP_DISPATCH_BLOCK = CAP_DISPATCH_ANCHOR + """
\t\t// 群里「连着说」上限：一次接话最多 N 条，说完冷却 M 分钟才能再开口。
\t\t// 冷掉（超过 M 分钟没说话）就重新计数；私聊不限。
\t\tif (first.chatType === 'group') {
\t\t\tconst cfg = this.qqConfig();
\t\t\tconst limit = Number(cfg.burstLimit ?? 15) || 0;
\t\t\tconst cooldownMs = (Number(cfg.burstCooldownMinutes ?? 10) || 10) * 60_000;
\t\t\tif (limit > 0) {
\t\t\t\tconst key = `qq.burst.${channelId}`;
\t\t\t\tconst st = getKv(this.db, key, null) ?? {};
\t\t\t\tconst now = this.clock.now();
\t\t\t\tconst lastAt = Number(st.lastAt) || 0;
\t\t\t\tlet count = Number(st.count) || 0;
\t\t\t\tif (now - lastAt >= cooldownMs) count = 0;
\t\t\t\tif (count >= limit) {
\t\t\t\t\tconst left = Math.max(1, Math.ceil((cooldownMs - (now - lastAt)) / 60000));
\t\t\t\t\tthis.note('capped', { channelId, reason: `连着说了 ${count} 条，冷却中（约 ${left} 分钟后能再开口）` });
\t\t\t\t\treturn;
\t\t\t\t}
\t\t\t\tsetKv(this.db, key, { count: count + 1, lastAt: now, date: bjDay(now) });
\t\t\t}
\t\t}
"""

# 旧版（v1.4 之前的「每天 15 条」）：升级时整段替换掉
OLD_DAILY_BLOCK = """
\t\t// 每个群每天最多回 N 条（默认 15），防止和群里的机器人无限对刷；私聊不限。
\t\tif (first.chatType === 'group') {
\t\t\tconst cap = Number(this.qqConfig().groupDailyCap ?? 15) || 0;
\t\t\tif (cap > 0) {
\t\t\t\tconst key = `qq.dailyReplies.${channelId}.${bjDay(this.clock.now())}`;
\t\t\t\tconst used = Number(getKv(this.db, key, 0)) || 0;
\t\t\t\tif (used >= cap) {
\t\t\t\t\tthis.note('capped', { channelId, reason: `今天这个群已经回了 ${used} 条（上限 ${cap}），先不再开口` });
\t\t\t\t\treturn;
\t\t\t\t}
\t\t\t\tsetKv(this.db, key, used + 1);
\t\t\t}
\t\t}
"""

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
    changed = False

    if IMPORT_LINE not in text:
        if IMPORT_ANCHOR not in text:
            raise SystemExit("index.js 结构不符（找不到 db.js 的 import 结尾），版本可能不同")
        text = text.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + "\n" + IMPORT_LINE, 1)
        changed = True

    if "sticker_find" not in text:
        if TOOL_ANCHOR not in text:
            raise SystemExit("index.js 结构不符（找不到 fish_search 注册结尾）")
        text = text.replace(TOOL_ANCHOR, TOOL_ANCHOR + "\n" + TOOL_BLOCK, 1)
        changed = True

    if FEED_IMPORT_LINE not in text:
        if FEED_IMPORT_ANCHOR not in text:
            raise SystemExit("index.js 结构不符（找不到 behavior.js 的 import 结尾）")
        text = text.replace(FEED_IMPORT_ANCHOR, FEED_IMPORT_ANCHOR + "\n" + FEED_IMPORT_LINE, 1)
        changed = True

    if "new FeedWriter(" not in text:
        if FEED_ANCHOR not in text:
            raise SystemExit("index.js 结构不符（找不到 diary.stop 那行）")
        text = text.replace(FEED_ANCHOR, FEED_ANCHOR + "\n" + FEED_BLOCK, 1)
        changed = True

    if not changed:
        print("[patch] index.js already patched")
        return False
    backup(path)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("[patch] index.js patched")
    return True


def patch_gateway(lib: str) -> bool:
    path = os.path.join(lib, "gateway.js")
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    changed = False

    # ① sticker_find 加进 QQ 会话工具白名单
    pattern = re.compile(r"export const QQ_SESSION_TOOLS = \[([^\]]*)\];")
    m = pattern.search(text)
    if m is None:
        raise SystemExit("gateway.js 里找不到 QQ_SESSION_TOOLS")
    if "'sticker_find'" not in m.group(1):
        items = [s.strip() for s in m.group(1).split(",") if s.strip()]
        items.append("'sticker_find'")
        text = text[:m.start()] + "export const QQ_SESSION_TOOLS = [" + ", ".join(items) + "];" + text[m.end():]
        changed = True

    # ② 群聊「连着说」上限（burst，默认 15 条 + 冷却 10 分钟）
    if "function bjDay(" not in text:
        if CAP_DAY_ANCHOR not in text:
            raise SystemExit("gateway.js 结构不符（找不到 QQ_SESSION_TOOLS 注释行）")
        text = text.replace(CAP_DAY_ANCHOR, CAP_HELPER + CAP_DAY_ANCHOR, 1)
        changed = True
    if "qq.burst." not in text:
        if "qq.dailyReplies" in text:
            # 从旧的「每天 15 条」升级
            if OLD_DAILY_BLOCK not in text:
                raise SystemExit("检测到旧的每日上限补丁，但没找到可替换的代码块；请先 --revert 再打")
            text = text.replace(OLD_DAILY_BLOCK, "", 1)
        if CAP_DISPATCH_ANCHOR not in text:
            raise SystemExit("gateway.js 结构不符（找不到 dispatch 开头）")
        text = text.replace(CAP_DISPATCH_ANCHOR, CAP_DISPATCH_BLOCK, 1)
        changed = True

    if not changed:
        print("[patch] gateway.js already patched")
        return False
    backup(path)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("[patch] gateway.js patched")
    return True


def copy_module(lib: str) -> None:
    for name in ("sticker-find.js", "feed.js"):
        src = os.path.join(HERE, name)
        dst = os.path.join(lib, name)
        if os.path.exists(dst):
            print(f"[patch] {name} exists, overwrite")
        shutil.copy2(src, dst)
        print(f"[patch] {name} installed")


def revert(lib: str) -> None:
    for name in ("index.js", "gateway.js"):
        path = os.path.join(lib, name)
        bak = path + ".bak-sticker"
        if os.path.exists(bak):
            shutil.copy2(bak, path)
            print(f"[revert] {name} restored")
    for name in ("sticker-find.js", "feed.js"):
        module = os.path.join(lib, name)
        if os.path.exists(module):
            os.remove(module)
            print(f"[revert] {name} removed")
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
