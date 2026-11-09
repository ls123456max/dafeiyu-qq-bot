#!/usr/bin/env python3
"""让 fish-soul 下一条消息开一个新会话（老的聊天记录留在库里，不再进上下文）。

为什么需要：模型每轮都会把「系统提示 + 全部历史」重发一遍。一个聊很久的会话
能长到 7 万 token/轮，成本是刚开局的 15 倍。每天换一次会话，成本基本封顶。

原理：dsh-fish-soul 在 gateway.js 里判断
    kv["persona.freshAfter"] > chat_session.created_at  =>  新建会话
所以只要把 kv 里的时间戳推到「现在」，下一次收到消息时就会换新会话。

用法：
    python rotate_session.py --dry     # 只看现在会在什么时候换、当前会话多大
    python rotate_session.py           # 立刻换
"""

import argparse
import json
import os
import sqlite3
import sys
import time

DEFAULT_DB = os.path.expanduser(r"~\.dsh\fish-soul\soul.db")


def connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path, timeout=15)
    con.execute("PRAGMA busy_timeout = 15000")
    return con


def get_kv(con: sqlite3.Connection, key: str):
    row = con.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
    if row is None:
        return None
    try:
        return json.loads(row[0])
    except (TypeError, ValueError):
        return row[0]


def set_kv(con: sqlite3.Connection, key: str, value) -> None:
    raw = json.dumps(value, ensure_ascii=False)
    con.execute(
        "INSERT INTO kv (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, raw),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--dry", action="store_true", help="只打印，不修改")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"[rotate] soul.db not found: {args.db}")
        return 1

    con = connect(args.db)
    fresh_after = get_kv(con, "persona.freshAfter")
    print(f"[rotate] persona.freshAfter = {fresh_after!r}")

    rows = con.execute(
        "SELECT channel_id, session_id, created_at, status FROM chat_session "
        "WHERE status = 'active' ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    for channel_id, session_id, created_at, status in rows:
        created = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(created_at / 1000))
        flag = "-> will rotate" if fresh_after is not None and created_at < int(fresh_after) else ""
        print(f"[rotate] {channel_id:28s} {session_id} created {created} {flag}")

    if args.dry:
        print("[rotate] dry run, nothing changed")
        return 0

    stamp = int(time.time() * 1000)
    set_kv(con, "persona.freshAfter", str(stamp))
    con.commit()
    print(f"[rotate] persona.freshAfter -> {stamp} (next inbound message opens a new session)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
