# -*- coding: utf-8 -*-
"""左侧封面面板：加载图片、350×500 预览 560×800 裁剪、马赛克笔刷与撤销、导出 jpg。

裁剪规则（与需求一致）：
- 横图（宽高比大于 560:800）：裁剪框上下顶满图片高度，左右移动取景；
- 竖图（宽高比小于 560:800）：裁剪框左右顶满图片宽度，上下滑动取景；
- 导出时把裁剪框内的画面缩放为精确的 560×800，统一保存为 jpg。
"""

import io
import os

from PIL import Image, ImageDraw
from PyQt5.QtCore import QPoint, QPointF, Qt
from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QKeySequence
from PyQt5.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QRadioButton, QShortcut, QVBoxLayout, QWidget,
)

# 最终裁剪与导出尺寸。所有源图坐标、比例计算和 JPEG 输出均使用此尺寸。
CROP_W = 560
CROP_H = 800

# 界面预览按 350×500 显示；实际裁剪与导出仍为 560×800。
# 鼠标坐标会从显示尺寸换算到原图坐标，导出尺寸不受此显示缩放影响。
DISPLAY_W = 350
DISPLAY_H = 500
TARGET_RATIO = CROP_W / CROP_H

# Pillow 9.4.0 与新版本的采样枚举写法二选一，保证两边都能跑
_LANCZOS = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
_BILINEAR = Image.Resampling.BILINEAR if hasattr(Image, "Resampling") else Image.BILINEAR
_NEAREST = Image.Resampling.NEAREST if hasattr(Image, "Resampling") else Image.NEAREST

BRUSH_RADII = [5.0, 10.0, 17.5]  # 按 350/560 显示比例调整，保持原有笔刷映射到原图后的覆盖范围
HISTORY_LIMIT = 30             # 最多可撤销步数


def _pil_to_qimage(img):
    """PIL Image(RGB) -> QImage。"""
    if img.mode != "RGB":
        img = img.convert("RGB")
    data = img.tobytes("raw", "RGB")
    qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format_RGB888)
    return qimg.copy()  # copy 后脱离对 data 的依赖


def _mosaic_stamp(img, cx, cy, rx, ry):
    """在图像 (cx, cy) 处以椭圆笔刷 (rx, ry) 打马赛克（圆形羽化边缘）。"""
    w, h = img.size
    x0 = max(0, int(cx - rx))
    y0 = max(0, int(cy - ry))
    x1 = min(w, int(cx + rx) + 1)
    y1 = min(h, int(cy + ry) + 1)
    if x1 <= x0 or y1 <= y0:
        return
    region = img.crop((x0, y0, x1, y1))
    rw, rh = region.size
    cell = max(3, int(min(rx, ry) * 2 / 3))   # 马赛克格子大小随笔刷粗细变化
    bw = max(1, rw // cell)
    bh = max(1, rh // cell)
    small = region.resize((bw, bh), _BILINEAR)
    pixelated = small.resize((rw, rh), _NEAREST)
    mask = Image.new("L", (rw, rh), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, rw - 1, rh - 1), fill=255)
    img.paste(pixelated, (x0, y0), mask)


class _Canvas(QWidget):
    """350×500 的预览画布；内部裁剪及导出仍为 560×800。"""

    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.setFixedSize(DISPLAY_W, DISPLAY_H)
        self.setMouseTracking(True)
        self._dragging = False
        self._last_pos = QPoint()
        self._cursor_pos = None      # 马赛克模式下的笔刷预览圈位置

    # ---- 坐标换算：画布坐标 -> 原图坐标 ----
    def _to_image(self, pos):
        p = self.panel
        return (p.off_x + pos.x() * p.frame_w / DISPLAY_W,
                p.off_y + pos.y() * p.frame_h / DISPLAY_H)

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton or self.panel.src_image is None:
            return
        p = self.panel
        self._dragging = True
        self._last_pos = ev.pos()
        if p.mode == "mosaic":
            p.push_history()
            p.stamp_at(ev.pos())
        self.update()

    def mouseMoveEvent(self, ev):
        p = self.panel
        self._cursor_pos = ev.pos()
        if not self._dragging or p.src_image is None:
            self.update()
            return
        if p.mode == "mosaic":
            self._paint_line(self._last_pos, ev.pos())
            self._last_pos = ev.pos()
        else:
            p.pan_by(ev.x() - self._last_pos.x(), ev.y() - self._last_pos.y())
            self._last_pos = ev.pos()
        self.update()

    def mouseReleaseEvent(self, ev):
        if self._dragging:
            self._dragging = False
            self.panel.on_stroke_end()
            self.update()

    def leaveEvent(self, ev):
        self._cursor_pos = None
        self.update()

    def _paint_line(self, p0, p1):
        """沿鼠标轨迹按笔刷半径插值涂抹，避免快速拖动出现断点。"""
        p = self.panel
        r = BRUSH_RADII[p.brush_index]
        dist = ((p1.x() - p0.x()) ** 2 + (p1.y() - p0.y()) ** 2) ** 0.5
        steps = max(1, min(400, int(dist / max(1.0, r / 3.0))))
        for i in range(steps + 1):
            t = i / steps
            x = int(round(p0.x() + (p1.x() - p0.x()) * t))
            y = int(round(p0.y() + (p1.y() - p0.y()) * t))
            p.stamp_at(QPoint(x, y))

    def paintEvent(self, ev):
        painter = QPainter(self)
        p = self.panel
        if p.src_image is None:
            painter.fillRect(self.rect(), QColor(246, 247, 249))
            painter.setPen(QColor(130, 138, 150))
            painter.drawText(self.rect(), Qt.AlignCenter,
                             "请点击“加载图片”\n选择电影封面")
            painter.end()
            return
        qimg = _pil_to_qimage(p.preview_pil())
        # preview_pil 始终返回 560×800；这里只缩放到 350×500 控件显示。
        painter.drawImage(self.rect(), qimg, qimg.rect())
        painter.setPen(QPen(QColor(0, 170, 255), 1, Qt.DashLine))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        # 马赛克模式的笔刷预览圈
        if p.mode == "mosaic" and self._cursor_pos is not None:
            r = BRUSH_RADII[p.brush_index]
            painter.setPen(QPen(QColor(255, 96, 0), 1))
            painter.drawEllipse(QPointF(self._cursor_pos), float(r), float(r))
        painter.end()


class ImagePanel(QWidget):
    """左侧面板：工具栏 + 350×500 预览（输出仍为 560×800）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.src_image = None        # PIL Image（RGB），已包含马赛克涂抹结果
        self.frame_w = 0             # 裁剪框在原图中的宽
        self.frame_h = 0             # 裁剪框在原图中的高
        self.off_x = 0               # 裁剪框左上角（原图坐标）
        self.off_y = 0
        self.mode = "move"           # move=移动取景 / mosaic=马赛克涂抹
        self.brush_index = 1
        self.history = []            # 撤销栈（存原图副本）
        self._drag_quality = False   # 拖动中用低质量缩放，松手后高清重绘

        self._build_ui()

    # ---------------- UI ----------------
    def _build_ui(self):
        self.canvas = _Canvas(self)

        self.btn_load = QPushButton("加载图片")
        self.btn_load.clicked.connect(self.choose_image)

        self.btn_undo = QPushButton("撤销")
        self.btn_undo.clicked.connect(self.undo)
        self.btn_undo.setEnabled(False)

        self.btn_remove = QPushButton("移除图片")
        self.btn_remove.clicked.connect(self.remove_image)
        self.btn_remove.setEnabled(False)

        self.rb_move = QRadioButton("移动")
        self.rb_mosaic = QRadioButton("马赛克")
        self.rb_move.setChecked(True)
        self.rb_move.toggled.connect(self._mode_changed)
        self.rb_mosaic.toggled.connect(self._mode_changed)

        self.brush_combo = QComboBox()
        for label, r in zip(("小笔刷", "中笔刷", "大笔刷"), BRUSH_RADII):
            self.brush_combo.addItem(label, r)
        self.brush_combo.setCurrentIndex(1)
        self.brush_combo.setEnabled(False)
        self.brush_combo.currentIndexChanged.connect(self._brush_changed)

        self.info_label = QLabel("未加载图片")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #666;")

        bar1 = QHBoxLayout()
        bar1.addWidget(self.btn_load)
        bar1.addWidget(self.btn_undo)
        bar1.addWidget(self.btn_remove)
        bar1.addStretch(1)

        bar2 = QHBoxLayout()
        bar2.addWidget(QLabel("模式:"))
        bar2.addWidget(self.rb_move)
        bar2.addWidget(self.rb_mosaic)
        bar2.addSpacing(8)
        bar2.addWidget(QLabel("笔刷:"))
        bar2.addWidget(self.brush_combo)
        bar2.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.addLayout(bar1)
        layout.addLayout(bar2)
        layout.addWidget(self.canvas, 0, Qt.AlignHCenter)
        layout.addWidget(self.info_label)
        layout.addStretch(1)

        # Ctrl+Z 撤销
        self._undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self._undo_shortcut.activated.connect(self.undo)
        self.canvas.setCursor(Qt.OpenHandCursor)

    # ---------------- 加载 / 移除 ----------------
    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择封面图片", "",
            "图片 (*.jpg *.jpeg *.png *.bmp *.webp);;所有文件 (*.*)")
        if not path:
            return
        try:
            img = Image.open(path)
            img.load()
        except Exception as e:
            QMessageBox.critical(self, "加载失败", "无法读取图片：\n%s" % e)
            return
        self.set_image(img.convert("RGB"), path)

    def set_image(self, pil_image, path=""):
        """载入图片并初始化裁剪框（按横竖图规则计算，初始居中）。"""
        self.src_image = pil_image.convert("RGB")
        self.history = []
        w, h = self.src_image.size
        if w / h > TARGET_RATIO:
            # 相对更“横”：裁剪框上下顶满，左右移动
            self.frame_h = h
            self.frame_w = max(1, round(h * TARGET_RATIO))
        else:
            # 相对更“竖”：裁剪框左右顶满，上下滑动
            self.frame_w = w
            self.frame_h = max(1, round(w / TARGET_RATIO))
        self.off_x = (w - self.frame_w) // 2
        self.off_y = (h - self.frame_h) // 2
        self._drag_quality = False
        self.btn_undo.setEnabled(False)
        self.btn_remove.setEnabled(True)
        name = os.path.basename(path) if path else "未命名图片"
        self.info_label.setText(
            "%s   导出分辨率 %d×%d JPG"
            % (name, CROP_W, CROP_H))
        self.canvas.update()

    def remove_image(self):
        self.src_image = None
        self.history = []
        self.btn_undo.setEnabled(False)
        self.btn_remove.setEnabled(False)
        self.info_label.setText("未加载图片")
        self.canvas.update()

    # ---------------- 模式 / 笔刷 ----------------
    def _mode_changed(self):
        self.mode = "mosaic" if self.rb_mosaic.isChecked() else "move"
        self.brush_combo.setEnabled(self.mode == "mosaic")
        self.canvas.setCursor(Qt.CrossCursor if self.mode == "mosaic"
                              else Qt.OpenHandCursor)
        self.canvas.update()

    def _brush_changed(self, idx):
        self.brush_index = idx
        self.canvas.update()

    # ---------------- 拖动平移 ----------------
    def pan_by(self, dx_screen, dy_screen):
        """按画布像素位移平移取景（拖图方向与取景移动方向相反，符合直觉）。"""
        if self.src_image is None:
            return
        self._drag_quality = True
        dx_img = dx_screen * self.frame_w / DISPLAY_W
        dy_img = dy_screen * self.frame_h / DISPLAY_H
        self.off_x -= int(round(dx_img))
        self.off_y -= int(round(dy_img))
        self._clamp_offset()
        self.canvas.update()

    def _clamp_offset(self):
        w, h = self.src_image.size
        self.off_x = max(0, min(self.off_x, w - self.frame_w))
        self.off_y = max(0, min(self.off_y, h - self.frame_h))

    def on_stroke_end(self):
        """松开鼠标：切换回高质量采样重绘一次。"""
        self._drag_quality = False
        self.canvas.update()

    # ---------------- 马赛克 ----------------
    def push_history(self):
        if self.src_image is None:
            return
        self.history.append(self.src_image.copy())
        if len(self.history) > HISTORY_LIMIT:
            self.history.pop(0)
        self.btn_undo.setEnabled(True)

    def undo(self):
        if not self.history:
            return
        self.src_image = self.history.pop()
        self._clamp_offset()
        self.btn_undo.setEnabled(bool(self.history))
        self.canvas.update()

    def stamp_at(self, widget_pos):
        """在画布坐标处盖一记马赛克（画布坐标自动换算回原图坐标）。"""
        if self.src_image is None:
            return
        cx = self.off_x + widget_pos.x() * self.frame_w / DISPLAY_W
        cy = self.off_y + widget_pos.y() * self.frame_h / DISPLAY_H
        r_screen = BRUSH_RADII[self.brush_index]
        rx = max(2.0, r_screen * self.frame_w / DISPLAY_W)
        ry = max(2.0, r_screen * self.frame_h / DISPLAY_H)
        _mosaic_stamp(self.src_image, cx, cy, rx, ry)
        self.canvas.update()

    # ---------------- 预览 / 导出 ----------------
    def preview_pil(self):
        """返回当前取景框的 560×800 全分辨率图像（供预览缩放和最终导出）。"""
        img = self.src_image
        box = (self.off_x, self.off_y,
               self.off_x + self.frame_w, self.off_y + self.frame_h)
        crop = img.crop(box)
        if crop.size != (CROP_W, CROP_H):
            method = _BILINEAR if self._drag_quality else _LANCZOS
            crop = crop.resize((CROP_W, CROP_H), method)
        return crop

    def export_jpeg_bytes(self, quality=95):
        """导出最终封面 jpg 字节（固定 560×800，与界面预览尺寸无关）。"""
        if self.src_image is None:
            raise ValueError("尚未加载图片")
        crop = self.preview_pil().convert("RGB")
        buf = io.BytesIO()
        crop.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()
