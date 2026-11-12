# -*- coding: utf-8 -*-
"""字幕工具：多编码兼容读取、按字幕格式解析“字幕行数”。

“字幕行数”不是文件的文本行数，而是字幕条数，按格式解析：
- SRT        ：时间轴（-->）条目数，即字幕条数；
- VTT (WebVTT)：同 SRT，但跳过 NOTE / STYLE / REGION 块；
- ASS / SSA  ：[Events] 中 Dialogue: 行数（每条 Dialogue 为一行字幕）；
- MicroDVD .sub：{起始帧}{结束帧} 帧行数；
- 其他/无法识别：退回按“非空行”统计（界面上可手动修改）。
"""

import re

# 常见字幕编码按顺序尝试；latin-1 永不失败，兜底保证能读出内容
ENCODINGS = [
    "utf-8-sig",
    "utf-8",
    "utf-16",
    "gbk",
    "big5",
    "shift_jis",
    "latin-1",
]

_MICRODVD_RE = re.compile(r"^\{\d+\}\{\d+\}")


def read_text_any(path):
    """尝试多种编码读取文本文件，返回字符串。"""
    last_err = None
    for enc in ENCODINGS:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError) as e:
            last_err = e
    raise last_err  # pragma: no cover（latin-1 不会失败，正常到不了这里）


def _count_srt(text):
    """SRT：时间轴条目数（每条字幕一行 HH:MM:SS,mmm --> HH:MM:SS,mmm）。"""
    return sum(1 for ln in text.splitlines() if "-->" in ln)


def _count_vtt(text):
    """VTT：同 SRT，但跳过 NOTE / STYLE / REGION 块内容。"""
    count = 0
    skipping = False
    for raw in text.splitlines():
        s = raw.strip()
        if skipping:
            if not s:
                skipping = False
            continue
        up = s.upper()
        if up.startswith(("NOTE", "STYLE", "REGION")):
            skipping = True
            continue
        if "-->" in s:
            count += 1
    return count


def _count_ass(text):
    """ASS/SSA：Dialogue: 行数。"""
    return sum(1 for ln in text.splitlines()
               if ln.strip().lower().startswith("dialogue:"))


def _count_microdvd(text):
    """MicroDVD .sub：{起始帧}{结束帧}文本 的行数。"""
    return sum(1 for ln in text.splitlines() if _MICRODVD_RE.match(ln.strip()))


def _count_fallback(text):
    """无法识别的格式：非空行数。"""
    return sum(1 for ln in text.splitlines() if ln.strip())


def count_subtitle_entries(text):
    """按内容嗅探统计字幕条数/行数（int），不依赖扩展名。"""
    head = text[:500].lstrip().upper()
    upper = text.upper()
    if head.startswith("WEBVTT"):
        return _count_vtt(text)
    if "[SCRIPT INFO]" in upper or "[EVENTS]" in upper:
        return _count_ass(text)
    srt_n = _count_srt(text)
    if srt_n > 0:
        return srt_n
    micro_n = _count_microdvd(text)
    if micro_n > 0:
        return micro_n
    return _count_fallback(text)


def count_subtitle_lines(path):
    """读取字幕文件并统计行数，返回字符串（供界面直接显示/写入 index.json）。"""
    return str(count_subtitle_entries(read_text_any(path)))
