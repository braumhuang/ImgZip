#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ImgZip —— 字幕图种生成工具（入口）。

封面 jpg + (index.json + 字幕) 的 zip = 图种（只输出图种一个文件）
"""

import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from imgzip import APP_NAME, APP_VERSION
from imgzip.main_window import MainWindow


def resource_path(relative):
    """资源路径：源码运行取项目目录；PyInstaller 打包后取 _MEIPASS。

    打包脚本里用 --add-data "assets;assets"(Win) / "assets:assets"(Mac)
    把 assets 目录一起带进包里。
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def main():
    # 启动顺序：配置 Qt 显示属性 -> 创建 QApplication -> 设置应用元数据与图标 -> 显示主窗口。
    # 高分屏适配（Win7 / Win10 / macOS 均有效，必须在创建 QApplication 之前设置）
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    icon_path = resource_path(os.path.join("assets", "icon.png"))
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
