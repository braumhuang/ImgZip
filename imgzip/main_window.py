# -*- coding: utf-8 -*-
"""主窗口：左侧封面图片 + 右侧电影信息（可滚动）+ 右下角保存。"""

import os
import re

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from imgzip import APP_NAME, APP_VERSION
from imgzip.image_panel import DISPLAY_W, ImagePanel
from imgzip.info_panel import InfoPanel
from imgzip.packer import build_index_bytes, make_image_torrent

DURATION_RE = re.compile(r"^\d{1,3}:\d{2}:\d{2}")


def _human(n):
    """字节数转可读文本。"""
    if n >= 1024 * 1024:
        return "%.1f MB" % (n / 1024 / 1024)
    return "%.1f KB" % (n / 1024)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("%s v%s —— 字幕图种生成工具" % (APP_NAME, APP_VERSION))

        # 根据当前屏幕可用区域设置窗口初始尺寸，避免固定大窗口超出小屏幕。
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            window_w = min(900, max(1, available.width() - 40))
            window_h = min(700, max(1, available.height() - 40))
            self.setMinimumSize(min(740, window_w), min(540, window_h))
            self.resize(window_w, window_h)
            self.move(
                available.x() + (available.width() - window_w) // 2,
                available.y() + (available.height() - window_h) // 2,
            )
        else:
            self.setMinimumSize(700, 520)
            self.resize(900, 680)

        central = QWidget()
        root = QHBoxLayout()          # 不指定 parent，交给下面的 page 统一挂载
        root.setSpacing(10)

        # ---------- 左侧：封面图片（固定布局，不使用滚动容器） ----------
        left_group = QGroupBox("封面图片（导出 560×800）")
        left_layout = QVBoxLayout(left_group)
        self.image_panel = ImagePanel()
        # 按第一版的布局方式直接放入 ImagePanel。
        # 画布固定为 350×500，左侧区域上下左右均不滚动。
        left_layout.addWidget(self.image_panel)
        left_group.setFixedWidth(DISPLAY_W + 44)
        root.addWidget(left_group)

        # ---------- 右侧：电影信息（可上下滚动） ----------
        right_group = QGroupBox("电影信息")
        right_layout = QVBoxLayout(right_group)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.info_panel = InfoPanel()
        scroll.setWidget(self.info_panel)
        right_layout.addWidget(scroll)
        root.addWidget(right_group, 1)

        # ---------- 底部：提示 + 右下角保存按钮 ----------
        self.btn_save = QPushButton("保存")
        self.btn_save.setObjectName("saveBtn")
        self.btn_save.setMinimumHeight(38)
        self.btn_save.setMinimumWidth(130)
        self.btn_save.clicked.connect(self.on_save)

        bottom = QHBoxLayout()
        hint = QLabel("图种 = 封面 jpg + 字幕包 zip（仅输出图种一个文件；改名 .zip 即可解压字幕）")
        hint.setStyleSheet("color: #888;")
        bottom.addWidget(hint)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_save)

        page = QVBoxLayout()
        page.setSpacing(8)
        page.addLayout(root, 1)
        page.addLayout(bottom)
        central.setLayout(page)
        self.setCentralWidget(central)

        self.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                border: 1px solid #c8ccd4;
                border-radius: 6px;
                margin-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #3a4a5a;
            }
            QPushButton#saveBtn {
                background-color: #2e7d32;
                color: white;
                padding: 8px 28px;
                border: none;
                border-radius: 4px;
                font-size: 15px;
            }
            QPushButton#saveBtn:hover { background-color: #286d2c; }
        """)

        self.statusBar().showMessage("就绪：请先在左侧加载封面图片，再在右侧填写电影信息。")

    # ---------------- 保存流程 ----------------
    def on_save(self):
        # 1) 基础校验：封面
        if self.image_panel.src_image is None:
            QMessageBox.warning(self, "缺少封面", "请先在左侧加载封面图片。")
            return

        info = self.info_panel.collect()

        # 2) 基础校验：ID 与字幕
        if not info.id:
            QMessageBox.warning(self, "缺少 ID", "请填写电影 ID。")
            self.info_panel.id_edit.setFocus()
            return
        empty_rows = [r for r in self.info_panel.subtitle_rows if not r.path]
        if empty_rows:
            QMessageBox.warning(
                self, "字幕未选择文件",
                "有 %d 个字幕行未选择文件，请选择文件或删除该行后重试。" % len(empty_rows))
            return
        if not info.subtitle:
            QMessageBox.warning(self, "缺少字幕", "请至少添加一个字幕文件。")
            return
        missing = [s.path for s in info.subtitle if not os.path.isfile(s.path)]
        if missing:
            QMessageBox.warning(self, "字幕文件不存在",
                                "以下文件不存在：\n" + "\n".join(missing))
            return

        # 3) 匹配时长格式软校验（不强制，提示后可选择继续）
        for s in info.subtitle:
            if s.duration and not DURATION_RE.match(s.duration):
                ret = QMessageBox.question(
                    self, "匹配时长格式提示",
                    "字幕「%s」的匹配时长为“%s”，建议格式如 02:53:52。\n是否继续保存？"
                    % (s.name, s.duration))
                if ret != QMessageBox.Yes:
                    return
                break

        # 4) 弹窗手动输入文件名（只输出图种一个文件）
        out_path, _ = QFileDialog.getSaveFileName(
            self, "保存图种（.jpg）",
            "%s.jpg" % info.id, "JPEG 图片 (*.jpg)")
        if not out_path:
            return
        if os.path.splitext(out_path)[1].lower() not in (".jpg", ".jpeg"):
            out_path += ".jpg"

        # 5) 生成：导出 jpg -> index.json -> zip（内存中生成并修正偏移量）-> 图种。
        #    只输出图种一个文件，字幕包 zip 不落盘、不另外导出。
        self.statusBar().showMessage("正在生成……")
        QApplication.processEvents()
        try:
            jpg_bytes = self.image_panel.export_jpeg_bytes(quality=95)
            index_bytes = build_index_bytes(info)
            jpg_len, zip_len = make_image_torrent(
                jpg_bytes, index_bytes,
                [s.path for s in info.subtitle], out_path)
        except Exception as e:
            QMessageBox.critical(self, "生成失败", "生成图种时出错：\n%s" % e)
            self.statusBar().showMessage("生成失败。", 5000)
            return

        # 6) 输出结果
        QMessageBox.information(
            self, "生成成功",
            "图种文件：%s\n大小：%s\n\n"
            "字幕包（index.json + 字幕）已封装在图种内，不会另外生成 zip。\n\n"
            "解包方法：把扩展名改为 .zip，用 Windows 资源管理器、\n"
            "macOS 归档实用工具或 WinRAR / 7-Zip 均可直接解压；\n"
            "不改名时也可用压缩软件直接打开这个 jpg。"
            % (out_path, _human(jpg_len + zip_len)))
        self.statusBar().showMessage("已生成：%s" % out_path, 10000)
