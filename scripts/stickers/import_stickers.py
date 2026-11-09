#!/usr/bin/env python3
"""把一个表情包目录导入 fish-soul 的 _stickers（她发图时用的名字就是文件名）。

规则：
  - 只收 png/jpg/gif
  - 文件名清理：去掉 `001-` / `14N01_` 这类序号前缀、去掉空白和非法字符、截断长度
  - >4MB 的 GIF 默认跳过（QQ 发大图容易失败）；加 --shrink 会缩到 420px 后保留
  - 已存在同名文件时跳过，可以反复执行

用法：
    python import_stickers.py --src D:\\memes\\pack --prefix "大肥鱼-"
    python import_stickers.py --src .\\pack --prefix "大肥鱼-" --shrink --dry
"""

import argparse
import os
import re
import shutil
import sys

DEFAULT_DST = os.path.expanduser(r"~\.dsh\fish-soul\workspace\_stickers")

IMG_EXT = {".png", ".jpg", ".jpeg", ".gif"}
ILLEGAL = re.compile(r'[\\/:*?"<>|\s]')
PREFIX_RE = re.compile(r"^\d+[A-Za-z]?\d*[-_]\s*")
MAX_BYTES = 4 * 1024 * 1024


def clean_name(filename: str, limit: int = 24) -> str:
    stem, ext = os.path.splitext(filename)
    stem = PREFIX_RE.sub("", stem)
    stem = ILLEGAL.sub("", stem)
    return (stem[:limit] or "sticker") + ext.lower()


def shrink_gif(path: str, out_path: str, size: int = 420) -> bool:
    try:
        from PIL import Image
    except ImportError:
        return False
    try:
        with Image.open(path) as im:
            frames = []
            for frame in ImageSequence(im):
                frames.append(frame.convert("RGBA").resize((size, size)))
            if not frames:
                return False
            frames[0].save(
                out_path, save_all=True, append_images=frames[1:],
                duration=im.info.get("duration", 80), loop=im.info.get("loop", 0),
                disposal=2, optimize=True,
            )
        return True
    except Exception:  # noqa: BLE001
        return False


def ImageSequence(im):  # 兼容不同 Pillow 版本
    try:
        while True:
            yield im.copy()
            im.seek(im.tell() + 1)
    except EOFError:
        return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True, help="表情包目录")
    parser.add_argument("--dst", default=DEFAULT_DST, help="_stickers 目录")
    parser.add_argument("--prefix", default="", help="加在文件名前，例如 大肥鱼-")
    parser.add_argument("--shrink", action="store_true", help="大 GIF 缩到 420px 而不是跳过")
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()

    if not os.path.isdir(args.src):
        print(f"[import] not a directory: {args.src}")
        return 1
    os.makedirs(args.dst, exist_ok=True)

    copied = skipped = shrunk = 0
    for name in sorted(os.listdir(args.src)):
        path = os.path.join(args.src, name)
        if not os.path.isfile(path) or os.path.splitext(name)[1].lower() not in IMG_EXT:
            continue
        target_name = args.prefix + clean_name(name)
        target = os.path.join(args.dst, target_name)
        if os.path.exists(target):
            skipped += 1
            continue

        size = os.path.getsize(path)
        if size > MAX_BYTES:
            if args.shrink:
                tmp = target + ".tmp"
                if shrink_gif(path, tmp):
                    if not args.dry:
                        os.replace(tmp, target)
                    shrunk += 1
                    continue
                if os.path.exists(tmp):
                    os.remove(tmp)
            print(f"[import] skip (>4MB): {name} {size // 1024}KB")
            skipped += 1
            continue

        if not args.dry:
            shutil.copy2(path, target)
        copied += 1

    print(f"[import] copied={copied} shrunk={shrunk} skipped={skipped} dst={args.dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
