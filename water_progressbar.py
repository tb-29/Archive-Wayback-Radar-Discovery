from PySide6.QtWidgets import QProgressBar
from PySide6.QtCore import QTimer, QRectF, Qt
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QPainterPath
import math

class WaterProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.wave_offset = 0
        self.wave_timer = QTimer(self)
        self.wave_timer.timeout.connect(self.animate_wave)
        self.wave_timer.start(30)
        self.setTextVisible(True)
        self.setMinimumHeight(32)
        self.setStyleSheet('QProgressBar { border: 2px solid #4ecdc4; border-radius: 8px; background: #23272e; color: #23272e; font-weight: bold; font-size: 16px; }')

    def animate_wave(self):
        self.wave_offset += 0.15
        if self.wave_offset > 2 * math.pi:
            self.wave_offset = 0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            rect = self.rect()
            percent = (self.value() - self.minimum()) / (self.maximum() - self.minimum() + 1e-6)
            # Arka plan
            painter.setBrush(QColor('#23272e'))
            painter.setPen(QPen(QColor('#4ecdc4'), 2))
            painter.drawRoundedRect(rect, 8, 8)
            # Su dalgası
            wave_path = QPainterPath()
            wave_height = rect.height() * (1 - percent)
            wave_path.moveTo(rect.left(), rect.bottom())
            for x in range(rect.width() + 1):
                y = wave_height + 6 * math.sin(2 * math.pi * (x / rect.width()) + self.wave_offset)
                wave_path.lineTo(rect.left() + x, rect.top() + y)
            wave_path.lineTo(rect.right(), rect.bottom())
            wave_path.lineTo(rect.left(), rect.bottom())
            painter.setBrush(QColor(78, 205, 196, 180))
            painter.setPen(Qt.NoPen)
            painter.drawPath(wave_path)
            # Yüzde metni
            painter.setPen(QColor('#34495e'))
            percent_text = f"%{int(percent * 100)}"
            painter.setFont(self.font())
            painter.drawText(rect, Qt.AlignCenter, percent_text)
        finally:
            painter.end() 