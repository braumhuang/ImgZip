# -*- coding: utf-8 -*-
"""右侧电影信息面板：ID / 番号(banko) / 链接(magnet) + 动态字幕列表。

字幕行数在选择文件后自动解析字幕内容（可手动修改）：
- SRT / VTT：按字幕条数（时间轴条目）统计；
- ASS / SSA：按 Dialogue: 行数统计；
- 其他格式：按非空行统计。
匹配时长手动输入，格式如 02:53:52。
"""

import os

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from imgzip.models import MovieInfo, SubtitleItem
from imgzip.subtitle_utils import count_subtitle_lines

# 任意格式原样打包：默认过滤器为“所有文件”，仅把常见字幕格式列在前面供快速筛选
SUBTITLE_FILTER = "所有文件 (*.*);;字幕文件 (*.srt *.ass *.ssa *.vtt *.sub *.txt)"


class SubtitleRow(QFrame):
    """一条字幕：选择本地路径 + 字幕行数 + 匹配时长。"""

    removeRequested = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.path = ""

        self.btn_pick = QPushButton("选择字幕文件")
        self.btn_pick.clicked.connect(self.pick_file)
        self.path_label = QLabel("未选择文件")
        self.path_label.setStyleSheet("color: #666;")
        self.btn_remove = QPushButton("删除")
        self.btn_remove.clicked.connect(lambda: self.removeRequested.emit(self))

        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("自动解析")
        self.line_edit.setToolTip(
            "选择文件后自动解析字幕行数：SRT/VTT 按字幕条数、ASS/SSA 按 Dialogue 行数；"
            "其他格式按非空行统计。也可手动修改")
        self.duration_edit = QLineEdit()
        self.duration_edit.setPlaceholderText("02:53:52")
        self.duration_edit.setToolTip("匹配时长，手动输入，格式如 02:53:52")

        grid = QGridLayout(self)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.addWidget(self.btn_pick, 0, 0)
        grid.addWidget(self.path_label, 0, 1)
        grid.addWidget(self.btn_remove, 0, 2)
        grid.addWidget(QLabel("字幕行数"), 1, 0)
        grid.addWidget(self.line_edit, 1, 1)
        grid.addWidget(QLabel("匹配时长"), 2, 0)
        grid.addWidget(self.duration_edit, 2, 1)
        grid.setColumnStretch(1, 1)

    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择字幕文件", "", SUBTITLE_FILTER)
        if not path:
            return
        self.path = path
        self.path_label.setText(os.path.basename(path))
        self.path_label.setToolTip(path)
        try:
            self.line_edit.setText(count_subtitle_lines(path))
        except Exception as e:
            self.line_edit.clear()
            QMessageBox.warning(self, "读取失败", "无法统计该文件行数：\n%s" % e)


class InfoPanel(QWidget):
    """电影信息面板本体（由主窗口放进 QScrollArea 实现上下滚动）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.subtitle_rows = []

        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("ID，如 V40e3")
        self.banko_edit = QLineEdit()
        self.banko_edit.setPlaceholderText("番号，如 IPZ-001")
        self.magnet_edit = QLineEdit()
        self.magnet_edit.setPlaceholderText("magnet:?xt=urn:btih:...")

        form = QGridLayout()
        form.addWidget(QLabel("ID (JavDB)"), 0, 0)
        form.addWidget(self.id_edit, 0, 1)
        form.addWidget(QLabel("番号 (banko)"), 1, 0)
        form.addWidget(self.banko_edit, 1, 1)
        form.addWidget(QLabel("链接 (magnet)"), 2, 0)
        form.addWidget(self.magnet_edit, 2, 1)
        form.setColumnStretch(1, 1)

        # 字幕列表允许动态增删；每行独立保存文件路径、字幕条数和匹配时长。
        self.subtitle_box = QGroupBox("字幕列表（一部电影可含多个字幕）")
        self.subtitle_layout = QVBoxLayout(self.subtitle_box)
        self.subtitle_layout.setSpacing(8)

        self.btn_add = QPushButton("+ 添加字幕")
        self.btn_add.clicked.connect(self.add_subtitle_row)

        outer = QVBoxLayout(self)
        outer.setSpacing(10)
        outer.addLayout(form)
        outer.addWidget(self.subtitle_box)
        outer.addWidget(self.btn_add, 0, Qt.AlignLeft)
        outer.addStretch(1)

        self.add_subtitle_row()  # 默认先给一行，方便直接开始

    # ---------------- 字幕行管理 ----------------
    def add_subtitle_row(self):
        row = SubtitleRow()
        row.removeRequested.connect(self.remove_subtitle_row)
        self.subtitle_rows.append(row)
        self.subtitle_layout.addWidget(row)
        return row

    def remove_subtitle_row(self, row):
        if row in self.subtitle_rows:
            self.subtitle_rows.remove(row)
            row.setParent(None)
            row.deleteLater()

    # ---------------- 数据收集 ----------------
    def collect(self):
        """把界面内容收集成 MovieInfo（未选择文件的字幕行被忽略）。"""
        # 这里只整理表单数据，不读取或复制字幕文件；文件路径交给封装模块处理。
        info = MovieInfo(
            id=self.id_edit.text().strip(),
            banko=self.banko_edit.text().strip(),
            magnet=self.magnet_edit.text().strip(),
        )
        for row in self.subtitle_rows:
            if not row.path:
                continue
            info.subtitle.append(SubtitleItem(
                name=os.path.basename(row.path),
                path=row.path,
                line=row.line_edit.text().strip(),
                duration=row.duration_edit.text().strip(),
            ))
        return info
