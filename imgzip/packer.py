# -*- coding: utf-8 -*-
"""打包核心：index.json 生成、字幕 zip 打包、jpg+zip 图种合成。

图种原理：
- JPEG 解码器读到结束标记 FF D9 即认为图片结束，其后字节被忽略；
- ZIP 解压器从头开始找 PK 头，不在乎文件前部是什么；
- 因此「图种 = cover.jpg 全部字节 + 字幕包.zip 全部字节」，
  图片软件照常预览，改名 .zip 即可解出字幕包。

为什么要修正 zip 偏移量（关键）：
Python 的 zipfile 写出的 zip，内部记录的偏移量（每个文件的本地
文件头位置、中央目录位置）都以 zip 自身第 0 字节为基准。前面拼上
jpg 之后，这些偏移全部“差了 jpg 的长度”：宽容的解压器（7-Zip、
WinRAR 等）会自动推算差值，而 Windows 资源管理器、macOS 归档
实用工具等严格按记录偏移定位的解压器，就会报“压缩包无效 /
无法解压”。

所以合成图种时，把 zip 内全部偏移统一加上 jpg 的长度（等价于
Info-ZIP 的 `zip -A` 自解压修正），让图种成为一个带 jpg 前缀
stub 的标准 zip —— 与自解压安装包同构，任何常见解压软件都能
直接打开。
"""

import io
import json
import os
import struct
import zipfile

_CDH_SIG = b"PK\x01\x02"    # 中央目录头
_EOCD_SIG = b"PK\x05\x06"   # 中央目录结束记录（EOCD）


def build_index_bytes(info) -> bytes:
    """MovieInfo -> index.json 字节内容（UTF-8、Tab 缩进、中文不转义）。"""
    text = json.dumps(info.to_dict(), ensure_ascii=False, indent="\t")
    return text.encode("utf-8")


def make_zip_bytes(index_bytes, subtitle_paths):
    """在内存中生成 zip 数据：index.json + 字幕文件按原文件名打包。

    重名文件（或与 index.json 重名）自动加 _2、_3 后缀，避免相互覆盖。
    返回 bytes 而不落盘（保存时只输出图种一个文件，zip 不另外导出）。
    """
    buf = io.BytesIO()
    used = {"index.json"}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.json", index_bytes)
        for path in subtitle_paths:
            name = os.path.basename(path)
            if name.lower() in used:
                stem, ext = os.path.splitext(name)
                i = 2
                while ("%s_%d%s" % (stem, i, ext)).lower() in used:
                    i += 1
                name = "%s_%d%s" % (stem, i, ext)
            used.add(name.lower())
            # Python3 的 zipfile 对非 ASCII 文件名自动置 UTF-8 标志位
            zf.write(path, name)
    return buf.getvalue()


def patch_zip_offsets(zip_bytes, delta):
    r"""把 zip 内部记录的所有偏移量整体 +delta（承认前面有 delta 字节的前缀）。

    需要修正的位置（均为小端 4 字节）：
    - 每条中央目录头（PK\x01\x02）内记录的「本地文件头偏移」；
    - 尾部 EOCD（PK\x05\x06）内记录的「中央目录起始偏移」。

    修正后，把 delta 字节任意数据拼在 zip 前面，所有偏移依然准确，
    与自解压压缩包（SFX）的结构完全一致。
    """
    if delta <= 0:
        return bytes(zip_bytes)
    buf = bytearray(zip_bytes)
    eocd = zip_bytes.rfind(_EOCD_SIG)
    if eocd < 0:
        raise ValueError("zip 数据无效：找不到中央目录结束记录")
    cd_size = struct.unpack_from("<I", buf, eocd + 12)[0]
    cd_start = eocd - cd_size
    if cd_start < 0 or bytes(buf[cd_start:cd_start + 4]) != _CDH_SIG:
        raise ValueError("zip 数据无效：中央目录定位失败")
    # 逐条遍历中央目录（文件内容不在该区域，不会把数据误认成目录头）
    pos = cd_start
    while pos < eocd:
        if bytes(buf[pos:pos + 4]) != _CDH_SIG:
            raise ValueError("zip 数据无效：中央目录解析失败")
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", buf, pos + 28)
        off = struct.unpack_from("<I", buf, pos + 42)[0]
        struct.pack_into("<I", buf, pos + 42, off + delta)
        pos += 46 + name_len + extra_len + comment_len
    cd_off = struct.unpack_from("<I", buf, eocd + 16)[0]
    struct.pack_into("<I", buf, eocd + 16, cd_off + delta)
    return bytes(buf)


def make_image_torrent(jpg_bytes, index_bytes, subtitle_paths, out_path):
    """封面 jpg + 字幕包 zip 合成图种，写入 out_path。

    流程：内存中生成 zip（index.json + 字幕）→ 偏移量修正（见
    patch_zip_offsets）→ 与 jpg 字节拼接写出。保证改名 .zip 后用
    Windows 资源管理器 / macOS 归档实用工具 / WinRAR / 7-Zip
    都能正常解压。返回 (jpg 大小, zip 大小)。
    """
    zip_bytes = make_zip_bytes(index_bytes, subtitle_paths)
    zip_bytes = patch_zip_offsets(zip_bytes, len(jpg_bytes))
    with open(out_path, "wb") as f:
        f.write(jpg_bytes)
        f.write(zip_bytes)
    return len(jpg_bytes), len(zip_bytes)
