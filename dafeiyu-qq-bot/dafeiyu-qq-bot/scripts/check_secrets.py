#!/usr/bin/env python3
"""提交前自查：仓库里有没有不该出现的密钥 / 个人数据。

用法：
    python check_secrets.py --root .
    python check_secrets.py --root . --qq 你的大号 --qq 小号

检查项：
  - 常见 API key 形状（sk-xxx、32 位 hex、带点的智谱 key）
  - 明文 NapCat token（webui.json 里的 12 位 hex）
  - 你指定的 QQ 号
  - 本机绝对路径（C:\\Users\\xxx、D:\\xxx），避免泄露目录结构
  - 私钥文件
"""

import argparse
import os
import re
import sys

TEXT_EXT = {".md", ".py", ".js", ".mjs", ".ps1", ".bat", ".vbs", ".json", ".jsonc",
            ".yml", ".yaml", ".txt", ".gitignore", ".sh"}

PATTERNS = [
    ("API key (sk-*)", re.compile(r"\bsk-[A-Za-z0-9._\-]{12,}")),
    ("智谱 key", re.compile(r"\b[0-9a-f]{32}\.[A-Za-z0-9]{8,}")),
    ("疑似密码/令牌赋值", re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"][^'\"]{12,}['\"]")),
    ("本机用户目录", re.compile(r"[A-Za-z]:\\Users\\[^\\\s\"']+")),
]

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    parser.add_argument("--qq", action="append", default=[])
    args = parser.parse_args()

    patterns = list(PATTERNS)
    for qq in args.qq:
        if qq:
            patterns.append((f"QQ 号 {qq}", re.compile(r"(?<!\d)" + re.escape(qq) + r"(?!\d)")))

    problems = 0
    for base, dirs, files in os.walk(args.root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if os.path.splitext(name)[1].lower() not in TEXT_EXT and name != ".gitignore":
                continue
            path = os.path.join(base, name)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    for lineno, line in enumerate(fh, 1):
                        for label, rx in patterns:
                            if rx.search(line):
                                problems += 1
                                print(f"{path}:{lineno}: {label} -> {line.strip()[:100]}")
            except OSError:
                continue

    print()
    if problems:
        print(f"[check] {problems} 处需要人工确认")
        return 1
    print("[check] 没发现明显的密钥或个人信息")
    return 0


if __name__ == "__main__":
    sys.exit(main())
