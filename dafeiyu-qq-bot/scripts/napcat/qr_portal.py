#!/usr/bin/env python3
"""NapCat 扫码登录页面（本地，无外部依赖页面）。

为什么不用 NapCat 自带的 WebUI 扫码页：
  - 自带页面在 QQ 重启后经常停在旧码上，不会自动刷新；
  - 这个页面每 20 秒自动换图，服务端最多每 55 秒刷新一次二维码，
    把窗口最小化也没关系，扫码随时都是新的。

用法：
    pip install "qrcode[pil]"
    pythonw qr_portal.py --napcat-dir D:\\NapCat --port 6210

浏览器打开 http://127.0.0.1:6210
"""

import argparse
import hashlib
import io
import json
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import qrcode

STATE_LOCK = threading.Lock()
STATE = {
    "credential": None,
    "qr_png": None,
    "qr_at": 0.0,      # unix ts of last successful refresh
    "err": "",
    "phase": "",
    "uin": "",
    "nickname": "",
}


def now() -> float:
    return time.time()


def load_token(napcat_dir: str) -> str:
    path = os.path.join(napcat_dir, "config", "webui.json")
    with open(path, "r", encoding="utf-8") as fh:
        return str(json.load(fh).get("token") or "")


class Napcat:
    def __init__(self, napcat_dir: str, port: int = 6099) -> None:
        self.base = f"http://127.0.0.1:{port}"
        self.token = load_token(napcat_dir)

    def _post(self, path: str, body: dict, credential: str | None = None) -> dict:
        data = json.dumps(body).encode()
        headers = {"Content-Type": "application/json"}
        if credential:
            headers["Authorization"] = "Bearer " + credential
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def login(self) -> str:
        digest = hashlib.sha256((self.token + ".napcat").encode()).hexdigest()
        resp = self._post("/api/auth/login", {"hash": digest})
        credential = (resp.get("data") or {}).get("Credential")
        if not credential:
            raise RuntimeError("napcat auth failed")
        return credential

    def status(self, credential: str) -> dict:
        resp = self._post("/api/QQLogin/CheckLoginStatus", {}, credential)
        data = resp.get("data")
        if not isinstance(data, dict):
            raise RuntimeError(f"napcat: {resp.get('message') or resp}")
        return data

    def qq_info(self, credential: str) -> dict:
        """已登录时拿当前账号信息（uin / nickname）。"""
        try:
            resp = self._post("/api/QQLogin/GetQQLoginInfo", {}, credential)
            data = resp.get("data")
            if not isinstance(data, dict):
                return {}
            return {"uin": data.get("uin") or "", "nickname": data.get("nick") or data.get("nickname") or ""}
        except Exception:  # noqa: BLE001
            return {}

    def refresh_qr(self, credential: str) -> str:
        self._post("/api/QQLogin/RefreshQRcode", {}, credential)
        resp = self._post("/api/QQLogin/GetQQLoginQrcode", {}, credential)
        data = resp.get("data")
        if not isinstance(data, dict) or not data.get("qrcode"):
            raise RuntimeError(f"napcat: {resp.get('message') or resp}")
        return data["qrcode"]


def render(url: str) -> bytes:
    img = qrcode.make(url, box_size=8, border=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def refresh(napcat: Napcat) -> None:
    """刷新二维码；凭据失效时重新登录再试一次。"""
    with STATE_LOCK:
        credential = STATE["credential"]
    try:
        if credential is None:
            raise RuntimeError("no credential")
        status = napcat.status(credential)
    except Exception:
        try:
            with STATE_LOCK:
                STATE["credential"] = None
            credential = napcat.login()
            with STATE_LOCK:
                STATE["credential"] = credential
            status = napcat.status(credential)
        except Exception as exc:  # noqa: BLE001
            with STATE_LOCK:
                STATE["err"] = str(exc)[:200]
            return

    with STATE_LOCK:
        STATE["phase"] = str(status.get("loginPhase") or "")
        STATE["uin"] = str(status.get("uin") or "")
        STATE["nickname"] = str(status.get("nickname") or "")
        STATE["err"] = ""

    if status.get("isLogin"):
        # CheckLoginStatus 有时不带 uin，单独问一次
        with STATE_LOCK:
            missing = STATE["uin"] == ""
        if missing:
            info = napcat.qq_info(credential)
            if info:
                with STATE_LOCK:
                    STATE["uin"] = str(info.get("uin") or "")
                    STATE["nickname"] = str(info.get("nickname") or "")
        return  # 已登录就不用二维码了

    url = str(status.get("qrcodeurl") or "")
    try:
        if not url or now() - STATE["qr_at"] > 55:
            url = napcat.refresh_qr(credential)
        png = render(url)
        with STATE_LOCK:
            STATE["qr_png"] = png
            STATE["qr_at"] = now()
            STATE["err"] = ""
    except Exception as exc:  # noqa: BLE001
        with STATE_LOCK:
            STATE["err"] = str(exc)[:200]


PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>大肥鱼 · QQ 扫码登录</title>
<style>
 body{margin:0;font-family:system-ui,"Microsoft YaHei",sans-serif;background:#0f1115;color:#e8eaf0;
      display:flex;min-height:100vh;align-items:center;justify-content:center}
 .card{background:#171a21;border:1px solid #262b36;border-radius:16px;padding:28px 32px;text-align:center;
       box-shadow:0 12px 40px rgba(0,0,0,.45)}
 h1{font-size:18px;margin:0 0 14px;font-weight:600}
 img{width:300px;height:300px;image-rendering:pixelated;background:#fff;border-radius:10px;padding:8px}
 .hint{margin-top:14px;font-size:13px;color:#8b93a5;line-height:1.6}
 .ok{color:#57d38c;font-size:16px;margin-top:10px}
 .err{color:#ff7b7b;font-size:12px;margin-top:8px;word-break:break-all}
</style></head>
<body><div class="card">
<h1>用手机 QQ 扫这个码登录</h1>
<img id="qr" src="/qr.png" alt="QR">
<div class="hint" id="hint">每 20 秒自动刷新</div>
<div class="ok" id="ok" style="display:none">已登录 ✓</div>
<div class="err" id="err"></div>
</div>
<script>
async function tick(){
  try{
    const s=await (await fetch('/state.json',{cache:'no-store'})).json();
    const img=document.getElementById('qr'), ok=document.getElementById('ok');
    ok.style.display=s.isLogin?'block':'none';
    img.style.display=s.isLogin?'none':'block';
    if(!s.isLogin) img.src='/qr.png?_='+Date.now();
    document.getElementById('err').textContent=s.err||'';
    document.getElementById('hint').textContent=s.isLogin
      ? ('当前账号：'+(s.nickname||'')+' '+(s.uin||''))
      : ('状态：'+(s.phase||'waiting_qrcode'));
  }catch(e){}
}
tick(); setInterval(tick,20000);
</script></body></html>
"""


def make_handler(napcat: Napcat):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # 安静一点
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            path = self.path.split("?")[0]
            if path == "/":
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/qr.png":
                with STATE_LOCK:
                    png = STATE["qr_png"]
                    age = now() - STATE["qr_at"]
                    is_login = bool(STATE["phase"]) and STATE["phase"] == "ready"
                if png is None or (age > 55 and not is_login):
                    refresh(napcat)
                    with STATE_LOCK:
                        png = STATE["qr_png"]
                if png is None:
                    self._send(503, b"QR not ready", "text/plain")
                    return
                self._send(200, png, "image/png")
                return
            if path == "/state.json":
                with STATE_LOCK:
                    payload = {
                        "age": round(now() - STATE["qr_at"], 1) if STATE["qr_at"] else None,
                        "err": STATE["err"],
                        "phase": STATE["phase"],
                        "uin": STATE["uin"],
                        "nickname": STATE["nickname"],
                        "isLogin": STATE["phase"] == "ready",
                    }
                self._send(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                return
            self._send(404, b"not found", "text/plain")

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--napcat-dir", default=os.environ.get("NAPCAT_DIR", r"D:\NapCat"))
    parser.add_argument("--port", type=int, default=6210)
    args = parser.parse_args()

    napcat = Napcat(args.napcat_dir)
    refresh(napcat)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(napcat))
    print(f"qr portal: http://127.0.0.1:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
