#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将应用版本同步到源码与 Windows 文件版本资源。

用法：
    python tools/sync_version.py 1.0.0
    python tools/sync_version.py v1.0.0  # 接受带 v 前缀的 Git tag

版本号统一维护在 imgzip/__init__.py 的 APP_VERSION。
本脚本将同一版本写入 version_info.txt，确保 Windows EXE 属性页一致。
GitHub Actions 会在发布时根据推送的 vX.Y.Z tag 自动执行本脚本。
"""

import re
import sys
from pathlib import Path

# Windows 控制台默认 cp1252（中文环境 GBK），直接 print 中文可能
# UnicodeEncodeError 崩溃（CI 作业已设 PYTHONIOENCODING=utf-8，这里再兜
# 一层，保证本地任意控制台 / 任意编码下也绝不因打印而失败）
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
INIT_FILE = ROOT / "imgzip" / "__init__.py"
VERSION_FILE = ROOT / "version_info.txt"


def fail(msg):
    print("[sync_version] 错误：%s" % msg)
    sys.exit(2)


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write(path, text):
    # newline=""：原样保留换行符，不跟随平台转换成 CRLF
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)

    ver = sys.argv[1].strip().lstrip("vV")
    if not re.fullmatch(r"\d+\.\d+\.\d+", ver):
        fail("版本号 %r 应为 X.Y.Z 格式（例如 1.0.0）" % ver)
    major, minor, patch = ver.split(".")
    quad = "%s, %s, %s, 0" % (major, minor, patch)

    # 1) imgzip/__init__.py —— APP_VERSION
    src = read(INIT_FILE)
    new = re.sub(r'APP_VERSION\s*=\s*"[^"]*"',
                 'APP_VERSION = "%s"' % ver, src, count=1)
    if new == src and ('APP_VERSION = "%s"' % ver) not in src:
        fail("imgzip/__init__.py 中未找到 APP_VERSION 赋值行")
    write(INIT_FILE, new)
    print('[sync_version] imgzip/__init__.py   APP_VERSION = "%s"' % ver)

    # 2) version_info.txt —— Windows exe 版本资源
    src = read(VERSION_FILE)
    src = re.sub(r"（v[0-9]+\.[0-9]+\.[0-9]+）", "（v%s）" % ver, src, count=1)
    src = re.sub(r"filevers=\(\d+,\s*\d+,\s*\d+,\s*\d+\)",
                 "filevers=(%s)" % quad, src, count=1)
    src = re.sub(r"prodvers=\(\d+,\s*\d+,\s*\d+,\s*\d+\)",
                 "prodvers=(%s)" % quad, src, count=1)
    src = re.sub(r"(StringStruct\('FileVersion',\s*)'[\d.]+'\)",
                 r"\g<1>'%s.0')" % ver, src, count=1)
    src = re.sub(r"(StringStruct\('ProductVersion',\s*)'[\d.]+'\)",
                 r"\g<1>'%s')" % ver, src, count=1)
    write(VERSION_FILE, src)
    print("[sync_version] version_info.txt     filevers/prodvers=(%s)" % quad)
    print("[sync_version] version_info.txt     FileVersion=%s.0, ProductVersion=%s"
          % (ver, ver))
    print("[sync_version] 完成：%s" % ver)


if __name__ == "__main__":
    main()
