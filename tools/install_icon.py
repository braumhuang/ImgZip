#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安装/更新 ImgZip 应用图标：以 .icns 为唯一图源。

用法：
    python tools/install_icon.py  /path/to/你的图标.icns   # 安装新图标（一步到位）
    python tools/install_icon.py                            # 用现有 icns 重新生成 png/ico

生成结果（均在 assets/ 下）：
- icon.icns ：原样保存（macOS App 图标，build_mac.sh 的 --icon 使用）；
- icon.png  ：从 icns 提取的 512×512（运行时窗口图标，main.py 使用）；
- icon.ico  ：由 512 母版缩放的 16~256 多尺寸（Windows exe 图标，build_win.bat 使用）。
"""

import io
import os
import shutil
import struct
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.normpath(os.path.join(HERE, "..", "assets"))

# PNG 编码的 chunk 类型码 -> 像素边长（现代 macOS 图标均为 PNG 编码）
PNG_TYPES = {
    b"icp4": 16, b"icp5": 32, b"icp6": 64,
    b"ic07": 128, b"ic08": 256, b"ic09": 512, b"ic10": 1024,
    b"ic11": 64, b"ic12": 256, b"ic13": 256, b"ic14": 512,
}

# Pillow 9.4 / 11 均可用
_LANCZOS = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS


def iter_chunks(data):
    """逐块遍历 icns 内部 chunk，产出 (类型码, 数据)。"""
    pos, total = 8, len(data)
    while pos + 8 <= total:
        code = data[pos:pos + 4]
        size = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        if size < 8 or pos + size > total:
            break
        yield code, data[pos + 8:pos + size]
        pos += size


def extract_png(icns_path, want_size=512):
    """从 icns 中提取 PNG 图像：优先精确尺寸，缺则取最大块缩放。"""
    with open(icns_path, "rb") as f:
        data = f.read()
    if data[:4] != b"icns":
        raise SystemExit("不是有效的 .icns 文件（缺少 icns 魔数）")
    found = {}
    for code, payload in iter_chunks(data):
        if code in PNG_TYPES and payload.startswith(b"\x89PNG"):
            found[PNG_TYPES[code]] = payload
    if not found:
        raise SystemExit("icns 中未找到 PNG 图像块（过老的 indexed 格式请先转存）")
    if want_size in found:
        return found[want_size]
    im = Image.open(io.BytesIO(found[max(found)])).convert("RGBA")
    im = im.resize((want_size, want_size), _LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ASSETS, "icon.icns")
    if not os.path.isfile(src):
        raise SystemExit("找不到图标文件：%s" % src)
    os.makedirs(ASSETS, exist_ok=True)

    dst_icns = os.path.join(ASSETS, "icon.icns")
    if os.path.abspath(src) != os.path.abspath(dst_icns):
        shutil.copyfile(src, dst_icns)

    png_bytes = extract_png(dst_icns, 512)
    with open(os.path.join(ASSETS, "icon.png"), "wb") as f:
        f.write(png_bytes)

    master = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    master.save(
        os.path.join(ASSETS, "icon.ico"), format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
               (64, 64), (128, 128), (256, 256)])

    print("图标已更新：")
    print("  assets/icon.icns  <- %s（原样）" % src)
    print("  assets/icon.png     512x512（窗口图标）")
    print("  assets/icon.ico     16~256 多尺寸（Windows exe 图标）")


if __name__ == "__main__":
    main()
