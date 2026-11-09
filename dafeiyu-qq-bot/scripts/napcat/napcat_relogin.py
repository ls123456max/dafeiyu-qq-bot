#!/usr/bin/env python3
"""NapCat 登录状态检查 / 快速登录。

常见用法：
    python napcat_relogin.py --napcat-dir D:\\NapCat --status
    python napcat_relogin.py --napcat-dir D:\\NapCat --uin 1000000000
    python napcat_relogin.py --napcat-dir D:\\NapCat --uin 1000000000 --wait 120

退出码：
    0  已登录（或快速登录成功）
    1  快速登录被拒（“登录态已失效”，需要人工扫码）
    2  NapCat 连不上
"""

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:6099"


def _post(path: str, body: dict | None = None, credential: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if credential:
        headers["Authorization"] = "Bearer " + credential
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def login(napcat_dir: str) -> str:
    cfg = os.path.join(napcat_dir, "config", "webui.json")
    with open(cfg, "r", encoding="utf-8") as fh:
        token = str(json.load(fh).get("token") or "")
    digest = hashlib.sha256((token + ".napcat").encode()).hexdigest()
    resp = _post("/api/auth/login", {"hash": digest})
    credential = (resp.get("data") or {}).get("Credential")
    if not credential:
        raise RuntimeError(f"login failed: {resp}")
    return credential


def status(credential: str) -> dict:
    resp = _post("/api/QQLogin/CheckLoginStatus", {}, credential)
    data = resp.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"napcat: {resp.get('message') or resp}")
    return data


def quick_login(credential: str, uin: str) -> dict:
    return _post("/api/QQLogin/SetQuickLogin", {"uin": uin}, credential)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--napcat-dir", default=os.environ.get("NAPCAT_DIR", r"D:\NapCat"))
    parser.add_argument("--uin", help="要登录的 QQ 号")
    parser.add_argument("--status", action="store_true", help="只打印状态")
    parser.add_argument("--wait", type=int, default=0, help="登录后再等几秒（等 6200 起来）")
    args = parser.parse_args()

    try:
        credential = login(args.napcat_dir)
        st = status(credential)
    except Exception as exc:  # noqa: BLE001
        print(f"[relogin] napcat unreachable: {exc}")
        return 2

    print("[relogin] status:", json.dumps(
        {k: st.get(k) for k in ("isLogin", "loginPhase", "uin", "nickname")}, ensure_ascii=False))

    if args.status or st.get("isLogin"):
        return 0

    if not args.uin:
        print("[relogin] not logged in; pass --uin to try quick login")
        return 1

    try:
        res = quick_login(credential, args.uin)
    except Exception as exc:  # noqa: BLE001
        print(f"[relogin] quick login error: {exc}")
        return 1

    if res.get("code") not in (0, None):
        print(f"[relogin] quick login rejected: {res.get('message')} -> needs QR scan")
        return 1

    if args.wait:
        time.sleep(args.wait)
    try:
        st = status(credential)
    except Exception:  # noqa: BLE001
        return 0
    ok = bool(st.get("isLogin"))
    print("[relogin] after quick login:", json.dumps(
        {k: st.get(k) for k in ("isLogin", "loginPhase", "uin", "nickname")}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
