/**
 * 每天一条「她自己」的 QQ 空间说说 + 个性签名。
 *
 * 设计要点：
 * - 只在虚拟时间到了设定的小时之后执行一次；用 kv `feed.last` 记日期，天然幂等。
 * - 内容来自她今天真实经历过的记忆（episode / self），有节气或节日时会自然带一句。
 * - 发表走 OneBot 的 `send_qzone_msg`，签名走 `set_self_longnick`（都要 NapCat 支持）。
 * - 任何一步失败只记日志，不影响聊天主流程。
 */
import { getKv, setKv } from './db.js';

const DAY = 86400_000;

/** 用虚拟时钟算「她那边」的日期和小时（UTC+8）。 */
function dayOf(ms) {
	const d = new Date(ms + 8 * 3600_000);
	return { date: d.toISOString().slice(0, 10), hour: d.getUTCHours() };
}

/**
 * 二十四节气（2026-11 ~ 2027-12，够用一阵子；过期了加表即可）。
 * 只列她可能发动态的这段时间，避免维护负担。
 */
const SOLAR_TERMS = {
	'2026-11-22': '小雪',
	'2026-12-07': '大雪',
	'2026-12-21': '冬至',
	'2027-01-05': '小寒',
	'2027-01-20': '大寒',
	'2027-02-04': '立春',
	'2027-02-19': '雨水',
	'2027-03-06': '惊蛰',
	'2027-03-21': '春分',
	'2027-04-05': '清明',
	'2027-04-20': '谷雨',
	'2027-05-06': '立夏',
	'2027-05-21': '小满',
	'2027-06-06': '芒种',
	'2027-06-21': '夏至',
	'2027-07-07': '小暑',
	'2027-07-23': '大暑',
	'2027-08-08': '立秋',
	'2027-08-23': '处暑',
	'2027-09-08': '白露',
	'2027-09-23': '秋分',
	'2027-10-08': '寒露',
	'2027-10-24': '霜降',
	'2027-11-08': '立冬',
	'2027-11-22': '小雪',
	'2027-12-07': '大雪',
	'2027-12-22': '冬至',
};

/** 常用节日（只收她真会提的）。 */
const FESTIVALS = {
	'2026-12-24': '平安夜',
	'2026-12-25': '圣诞节',
	'2026-12-31': '跨年',
	'2027-01-01': '元旦',
	'2027-02-05': '除夕',
	'2027-02-06': '春节',
	'2027-02-14': '情人节',
	'2027-02-21': '元宵节',
	'2027-05-01': '劳动节',
	'2027-05-20': '520',
	'2027-06-01': '儿童节',
	'2027-06-18': '端午节',
	'2027-10-01': '国庆节',
	'2027-10-06': '中秋节',
};

/** 今天是什么日子（没有就返回空串）。 */
export function themeOf(date) {
	return SOLAR_TERMS[date] ?? FESTIVALS[date] ?? '';
}

/** 从模型回复里抠 JSON（模型偶尔会带解释或代码块）。 */
function parseJson(text) {
	if (typeof text !== 'string') return null;
	const s = text.replace(/```(?:json)?/gi, '').trim();
	const a = s.indexOf('{');
	const b = s.lastIndexOf('}');
	if (a < 0 || b <= a) return null;
	try { return JSON.parse(s.slice(a, b + 1)); } catch { return null; }
}

function clampInt(v, min, max, fallback) {
	const n = Math.floor(Number(v));
	return Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : fallback;
}

export class FeedWriter {
	constructor({ db, clock, worker, callLlm, getConfig, personaName, channel, note, log }) {
		Object.assign(this, { db, clock, worker, callLlm, getConfig, personaName, channel, note });
		this.log = log ?? (() => {});
		this.timer = null;
		this.running = false;
	}

	start(everyMs = 10 * 60_000) {
		if (this.timer !== null) return;
		this.timer = setInterval(() => { void this.tick().catch(() => {}); }, everyMs);
		this.timer.unref?.();
	}

	stop() {
		if (this.timer !== null) clearInterval(this.timer);
		this.timer = null;
	}

	cfg() {
		// 配置文件里的 feed 段落 + kv `feed.config` 覆盖（方便不改配置/不重启插件就调整）
		const f = { ...(this.getConfig().feed ?? {}), ...(getKv(this.db, 'feed.config', {}) ?? {}) };
		return {
			// 默认开：用户要的是「她自己会发动态和签名」
			enabled: f.enabled !== false,
			hour: clampInt(f.hour, 6, 22, 9),
			// 1=公开 4=好友 16/128=指定好友（要 target_uins）；默认好友可见，低调一点
			ugcRight: [1, 4, 16, 64, 128].includes(Number(f.ugcRight)) ? Number(f.ugcRight) : 4,
			setSignature: f.signature !== false,
		};
	}

	/** 今天的写作材料：她经历的片段 + 她自己说过的话（最多几条，避免提示词太长）。 */
	material(date) {
		const start = Date.parse(`${date}T00:00:00+08:00`);
		const end = start + DAY;
		try {
			const eps = this.db.prepare(`SELECT content FROM memory
				WHERE character_id = 'feiyu' AND kind = 'episode' AND status = 'active'
				AND created_at >= ? AND created_at < ? ORDER BY created_at LIMIT 6`).all(start, end);
			const self = this.db.prepare(`SELECT content FROM memory
				WHERE character_id = 'feiyu' AND owner_id = 'self' AND kind <> 'diary' AND status = 'active'
				AND created_at >= ? AND created_at < ? ORDER BY created_at LIMIT 4`).all(start, end);
			return [...eps.map((x) => x.content), ...self.map((x) => x.content)];
		} catch {
			return [];
		}
	}

	/**
	 * 到点就发一条（force = 手动触发，跳过时间和去重）。
	 * 返回 { date, feed, signature } 或 null。
	 */
	async tick({ force = false } = {}) {
		const cfg = this.cfg();
		if (!cfg.enabled) return null;
		const now = this.clock.now();
		const { date, hour } = dayOf(now);
		if (!force && (hour < cfg.hour || getKv(this.db, 'feed.last', '') === date)) return null;
		if (this.running) return null;
		this.running = true;
		try {
			setKv(this.db, `feed.tries.${date}`, (Number(getKv(this.db, `feed.tries.${date}`, 0)) || 0) + 1);
			const theme = themeOf(date);
			const mat = this.material(date);
			const name = this.personaName();
			const prompt = `你是${name}。今天是 ${date}。\n` +
				`写一条 QQ 空间说说，像真人随手发的那种：1~2 句、40 字以内，具体、有画面、带点自己的情绪或小心思；不要写成朋友圈文案模板，不要堆 emoji（最多一个），不要话题标签、不要 @ 任何人，不要提 AI/模型。\n` +
				(theme ? `今天是${theme}，可以自然带一句有关它的感受，但别写得像节日宣传海报。\n` : '') +
				(mat.length ? `今天你经历过、想过的事（挑有感觉的用，别照抄，也别硬凑）：\n${mat.map((x) => `- ${String(x).slice(0, 80)}`).join('\n')}\n` : '今天比较平淡，就写平淡本身也行。\n') +
				`再写一句个性签名：4~12 个字，直接、像她自己会挂的那种（可以跟今天的心情或节气有关）。\n` +
				'只输出 JSON：{"feed":"说说正文","signature":"签名"}';
			const reply = await this.callLlm(prompt, { maxTokens: 400, thinkFallback: true });
			const parsed = parseJson(reply) ?? {};
			const feed = String(parsed.feed ?? '').trim().replace(/\s+/g, ' ').slice(0, 120);
			const signature = String(parsed.signature ?? '').trim().replace(/\s+/g, ' ').slice(0, 24);
			if (feed === '') {
				this.note?.('failed', { title: '动态', reason: '模型没给出能发的说说' });
				return null;
			}
			await this.channel.call('send_qzone_msg', {
				content: feed, images: [], ugc_right: cfg.ugcRight, target_uins: []
			});
			let sig = '';
			if (cfg.setSignature && signature !== '') {
				await this.channel.call('set_self_longnick', { longNick: signature });
				sig = signature;
			}
			setKv(this.db, 'feed.last', date);
			setKv(this.db, 'feed.history', [{ date, at: now, feed, signature: sig }].concat(
				Array.isArray(getKv(this.db, 'feed.history', [])) ? getKv(this.db, 'feed.history', []) : []
			).slice(0, 30));
			this.note?.('feed', { title: '动态', reason: `发了今天的说说${theme ? `（${theme}）` : ''}`, text: feed });
			return { date, feed, signature: sig };
		} catch (error) {
			this.log('warn', `[fish-soul] 发动态失败：${String(error instanceof Error ? error.message : error)}`);
			this.note?.('failed', { title: '动态', reason: `说说没发出去：${String(error instanceof Error ? error.message : error).slice(0, 80)}` });
			return null;
		} finally {
			this.running = false;
		}
	}
}
