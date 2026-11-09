/**
 * sticker-find.js —— 让她自己找表情包 / 图片。
 *
 * 两种来源：
 *   1) 自己的图库（`<workspace>/_stickers/`）：按查询词匹配文件名；问「大肥鱼/鲸鱼」这类
 *      指向她自己的词时，直接从图库里随机挑（图库里本来就是她自己的脸）。
 *   2) 上网找：Bing 图片搜索（HTML 里抠 murl）→ 逐张下载 → 走 StickerBox.importImage
 *      存进 `_stickers/`（sha1 去重、最多 300 张、文件名按查询词起）。
 *
 * 只收 image/*、8KB–4MB 的图；一次最多 6 张，避免一口气拉一大堆。
 *
 * 这是对 dsh-fish-soul 的「可选补丁」，不是官方代码。装法见同目录 README.md。
 */
import { readdirSync } from 'node:fs';
import { join } from 'node:path';
import { stickerName } from './stickers.js';

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';
const MAX_BYTES = 4 * 1024 * 1024;
const MIN_BYTES = 8 * 1024;
const IMG_RE = /\.(png|jpe?g|gif)$/i;
const FEIYU_RE = /大肥鱼|肥鱼|鲸鱼|鲸|whale/i;

// 可选：本地表情包原件目录，用环境变量配置（多个用 ; 分隔）。
// 作用是「知道哪些文件名属于她自己那套表情包」，用来在同名/同脸时优先挑。
const PACK_DIRS = String(process.env.FISH_SOUL_STICKER_PACKS ?? '')
	.split(';')
	.map((p) => p.trim())
	.filter((p) => p !== '');
let packNamesCache = null;

/** 表情包里每张图的「好听名字」（去掉 001- / 14N01_ 这类序号前缀）。 */
function packNames() {
	if (packNamesCache !== null) return packNamesCache;
	const set = new Set();
	for (const dir of PACK_DIRS) {
		try {
			for (const rel of readdirSync(dir, { recursive: true })) {
				const name = String(rel);
				if (name.includes('previews')) continue;
				if (!IMG_RE.test(name)) continue;
				const stem = name.split(/[\\/]/).pop().replace(/\.[^.]+$/, '');
				const nice = stem.replace(/^\d+[A-Za-z]?\d*[-_]/, '').replace(/[\\/:*?"<>|()（）\s]+/g, '').slice(0, 16);
				if (nice !== '') set.add(nice);
			}
		} catch {
			// 目录不存在就跳过
		}
	}
	packNamesCache = set;
	return set;
}

function decodeEntities(s) {
	return String(s ?? '')
		.replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'")
		.replace(/&lt;/g, '<').replace(/&gt;/g, '>');
}

function normalizeQuery(query) {
	return [...String(query ?? '').trim().replace(/[\\/:*?"<>|]+/g, ' ')].slice(0, 40).join('');
}

/** 用查询词给存下来的图起名：大肥鱼图1、大肥鱼图2…… */
function nameFor(query, index) {
	const base = stickerName(normalizeQuery(query)) || '找的图';
	return `${base}${index}`;
}

/**
 * Bing 图片搜索，返回候选图片直链。
 * @param {string} query
 * @param {{limit?: number, signal?: AbortSignal}} [opts]
 * @returns {Promise<string[]>}
 */
export async function searchImageUrls(query, { limit = 35, signal } = {}) {
	const url = 'https://cn.bing.com/images/async?q=' + encodeURIComponent(String(query ?? '')) +
		`&first=0&count=${Math.min(50, Math.max(10, limit))}&mkt=zh-CN&setlang=zh`;
	const res = await fetch(url, {
		headers: { 'user-agent': UA, 'accept-language': 'zh-CN,zh;q=0.9', referer: 'https://cn.bing.com/' },
		signal
	});
	if (!res.ok) throw new Error(`图片搜索失败 HTTP ${res.status}`);
	const html = await res.text();
	const found = [];
	const push = (raw) => {
		const u = decodeEntities(raw).trim();
		if (!/^https?:\/\//i.test(u)) return;
		if (!found.includes(u)) found.push(u);
	};
	let m;
	const reA = /murl&quot;:&quot;(.*?)&quot;/g;
	while ((m = reA.exec(html)) !== null) push(m[1]);
	const reB = /"murl":"(.*?)"/g;
	while ((m = reB.exec(html)) !== null) push(m[1]);
	return found;
}

/** 按文件头认格式（有些站点的 content-type 是假的）。 */
function sniffImageType(bytes) {
	if (bytes.length < 12) return null;
	if (bytes[0] === 0xFF && bytes[1] === 0xD8 && bytes[2] === 0xFF) return 'image/jpeg';
	if (bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4E && bytes[3] === 0x47) return 'image/png';
	if (bytes[0] === 0x47 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x38) return 'image/gif';
	return null;
}

/**
 * 下载一张图（只认 image/*，8KB–4MB）。
 * @param {string} url
 * @param {{signal?: AbortSignal}} [opts]
 */
export async function downloadImage(url, { signal } = {}) {
	const res = await fetch(url, {
		headers: { 'user-agent': UA, referer: 'https://cn.bing.com/' },
		redirect: 'follow',
		signal
	});
	if (!res.ok) throw new Error(`下载失败 HTTP ${res.status}`);
	const bytes = Buffer.from(await res.arrayBuffer());
	if (bytes.length < MIN_BYTES) throw new Error('图太小');
	if (bytes.length > MAX_BYTES) throw new Error('图超过 4MB');
	const mediaType = sniffImageType(bytes);
	if (!mediaType) throw new Error('格式不支持（webp 或不是图片）');
	return { bytes, mediaType };
}

/**
 * 从她自己的图库里挑。
 * @returns {string[]} 文件名（带扩展名）
 */
export function pickFromLibrary({ query, count = 3, workspacePath }) {
	const dir = join(String(workspacePath ?? ''), '_stickers');
	let names = [];
	try { names = readdirSync(dir).filter((n) => IMG_RE.test(n)); } catch { return []; }
	if (names.length === 0) return [];
	const words = normalizeQuery(query).split(/[\s,，、]+/)
		.map((w) => w.replace(/表情包|表情|图片|图|照片|包/g, ''))
		.filter((w) => w.length >= 1);
	const hit = words.length === 0 ? [] : names.filter((n) => words.some((w) => n.includes(w)));
	const feiyu = FEIYU_RE.test(String(query ?? ''));
	let pool = [];
	if (feiyu) {
		// 问「大肥鱼/鲸鱼」：优先名字带「大肥鱼-」前缀的那套，其次是她那套表情包原件的图
		const ownNew = names.filter((n) => n.startsWith('大肥鱼-'));
		const pack = packNames();
		const ownOld = names.filter((n) => pack.has(n.replace(/\.[^.]+$/, '').replace(/^大肥鱼-/, '')));
		pool = ownNew.length > 0 ? ownNew : (ownOld.length > 0 ? ownOld : names);
	} else {
		pool = hit;
	}
	if (pool.length === 0) return [];
	const shuffled = [...pool];
	for (let i = shuffled.length - 1; i > 0; i--) {
		const j = Math.floor(Math.random() * (i + 1));
		[shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
	}
	return shuffled.slice(0, Math.min(6, Math.max(1, Number(count) || 3)));
}

/**
 * 找图并保存：先看图库，没有再上网。
 * @returns {Promise<{saved: {file: string}[], picked: string[], tried: number, skipped: string[]}>}
 */
export async function findAndSaveStickers({ query, count = 3, workspacePath, box, log = () => {}, signal }) {
	const want = Math.min(6, Math.max(1, Number(count) || 3));
	const picked = pickFromLibrary({ query, count: want, workspacePath });
	if (picked.length > 0) {
		log('info', `[fish-soul] 找表情包「${query}」：图库里现成 ${picked.length} 张`);
		return { saved: [], picked, tried: 0, skipped: [] };
	}
	const urls = await searchImageUrls(query, { limit: 40, signal });
	const saved = [];
	const skipped = [];
	let tried = 0;
	for (const u of urls) {
		if (saved.length >= want) break;
		if (tried >= 25) break;
		tried += 1;
		try {
			const img = await downloadImage(u, { signal });
			const r = box.importImage({
				bytes: img.bytes,
				mediaType: img.mediaType,
				name: nameFor(query, saved.length + 1),
				workspacePath,
				from: '网上找的',
				summary: normalizeQuery(query).slice(0, 30)
			});
			if (r.ok) saved.push({ file: r.file });
			else if (r.full) { skipped.push('图库满了'); break; }
			else skipped.push(String(r.reason ?? '没存上'));
		} catch (error) {
			skipped.push(String(error instanceof Error ? error.message : error).slice(0, 80));
		}
	}
	log('info', `[fish-soul] 找表情包「${query}」：存了 ${saved.length} 张，试了 ${tried} 个链接`);
	return { saved, picked: [], tried, skipped };
}
