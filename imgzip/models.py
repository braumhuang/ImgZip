# -*- coding: utf-8 -*-
"""数据结构：电影信息与字幕条目。"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class SubtitleItem:
    """一条字幕。

    name     : 字幕文件名（不含路径，写入 index.json 与 zip 内的文件名）
    path     : 本地完整路径（仅用于读取，不写入 index.json）
    line     : 字幕行数（选择文件后自动统计，可手动修改）
    duration : 匹配时长（手动输入，如 02:53:52）
    """

    name: str = ""
    path: str = ""
    line: str = ""
    duration: str = ""


@dataclass
class MovieInfo:
    """一部电影的信息，与 index.json 一一对应。"""

    id: str = ""
    banko: str = ""
    magnet: str = ""
    subtitle: List[SubtitleItem] = field(default_factory=list)

    def to_dict(self):
        """转成与 index.json 完全一致的字典（path 不写入）。"""
        return {
            "id": self.id,
            "banko": self.banko,
            "magnet": self.magnet,
            "subtitle": [
                {
                    "name": s.name,
                    "line": s.line,
                    "duration": s.duration,
                }
                for s in self.subtitle
            ],
        }
