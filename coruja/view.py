"""Janela transparente onde a coruja vive.

Desenha a partir do estado do animador e trata os cliques:
olhos = acordar/dormir, orelha direita (brinco) = quando dormir,
orelha esquerda = animações, barriga = carinho, arrastar = mover.
"""

import math

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QCursor, QPainter
from PySide6.QtWidgets import QWidget

from . import effects, owl
from .animator import Animator
from .effects import Prop
from .owl import Geo


def frame_size(s: float) -> QSize:
    """Tamanho da janela para uma coruja de tamanho s (sobra espaço para sol, corações e ninho)."""
    return QSize(int(s * 1.5), int(s * 1.45))


class OwlWidget(QWidget):
    toggled = Signal()
    right_ear = Signal()
    left_ear = Signal()
    drag_changed = Signal(bool)
    moved = Signal()

    def __init__(self, animator: Animator, owl_size: int, on_top: bool = True):
        super().__init__()
        self.animator = animator
        self.owl_size = owl_size
        self.gem = owl.DEFAULT_GEM
        self._press_global = None
        self._press_pos = None
        self._window_start = None
        self._dragging = False

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.set_on_top(on_top)
        self.setFixedSize(frame_size(owl_size))
        self.setWindowTitle("Coruja")

    def set_on_top(self, on_top: bool):
        flags = Qt.FramelessWindowHint | Qt.Tool
        if on_top:
            flags |= Qt.WindowStaysOnTopHint
        visible = self.isVisible()
        self.setWindowFlags(flags)
        if visible:
            self.show()

    def set_owl_size(self, s: int):
        center_x = self.x() + self.width() / 2
        bottom = self.y() + self.height()
        self.owl_size = s
        size = frame_size(s)
        self.setFixedSize(size)
        self.move(int(center_x - size.width() / 2), int(bottom - size.height()))
        self.update()

    # Geometria

    def base_rect(self) -> QRectF:
        """Quadrado da coruja parada: centralizado, perto da base da janela."""
        s = self.owl_size
        return QRectF((self.width() - s) / 2, self.height() - s * 0.12 - s, s, s)

    def owl_rect(self) -> QRectF:
        """Onde a coruja está agora (com pulinhos e deslocamentos)."""
        ox, oy = self.animator.offset
        return self.base_rect().translated(ox * self.owl_size, -oy * self.owl_size)

    def right_ear_rect(self) -> QRectF:
        return owl.right_ear_area(self.owl_rect())

    def left_ear_rect(self) -> QRectF:
        return owl.left_ear_area(self.owl_rect())

    def eyes_center_global(self) -> QPoint:
        e = owl.eye_areas(self.owl_rect())
        local = QPointF((e[0].center().x() + e[1].center().x()) / 2, e[0].center().y())
        return self.mapToGlobal(local.toPoint())

    def look_at_cursor(self):
        """Direção do olhar para o mouse (-1..1, y para cima)."""
        eye = self.eyes_center_global()
        m = QCursor.pos()
        dx, dy = m.x() - eye.x(), -(m.y() - eye.y())
        d = max(1.0, math.hypot(dx, dy))
        k = min(1.0, d / 200)
        return (dx / d * k, dy / d * k)

    # Desenho

    def paintEvent(self, _event):
        a = self.animator
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        base = Geo(self.base_rect())

        # sol atrás da coruja
        if a.sun:
            effects.draw_sun(p, base, a.sun[0], a.sun_spin, a.sun[1])

        # coruja com inclinação e "respiração", ancorada nos pés
        r = self.owl_rect()
        s = self.owl_size
        anchor = QPointF(r.center().x(), r.bottom() - s * 0.05)
        p.save()
        p.translate(anchor)
        p.rotate(a.tilt)
        p.scale(1 - (a.squash - 1) * 0.5, a.squash)
        p.translate(-anchor)
        owl.draw(p, r, a.pose, self.gem)
        if a.prop is Prop.PARTY_HAT:
            effects.draw_prop(p, a.prop, Geo(r), a.prop_phase)
        p.restore()

        # objetos na frente (a tigela fica no chão; caneca e biscoito acompanham a coruja)
        if a.prop is not None and a.prop is not Prop.PARTY_HAT:
            effects.draw_prop(p, a.prop, base if a.prop is Prop.BOWL else Geo(r), a.prop_phase)

        # ninho na frente e partículas por cima
        effects.draw_nest(p, base, a.nest)
        for pt in a.particles:
            effects.draw_particle(p, pt, base)
        p.end()

    # Mouse

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return super().mousePressEvent(e)
        self._press_global = e.globalPosition().toPoint()
        self._press_pos = e.position()
        self._window_start = self.pos()
        self._dragging = False

    def mouseMoveEvent(self, e):
        if self._press_global is None:
            return
        delta = e.globalPosition().toPoint() - self._press_global
        if not self._dragging and delta.manhattanLength() < 4:
            return
        if not self._dragging:
            self._dragging = True
            self.drag_changed.emit(True)
        self.move(self._window_start + delta)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self._press_global is None:
            return super().mouseReleaseEvent(e)
        self._press_global = None
        if self._dragging:
            self._dragging = False
            self.drag_changed.emit(False)
            self.moved.emit()
            return
        pos = self._press_pos
        r = self.owl_rect()
        if self.right_ear_rect().contains(pos):
            self.right_ear.emit()
        elif self.left_ear_rect().contains(pos):
            self.left_ear.emit()
        elif any(eye.contains(pos) for eye in owl.eye_areas(r)):
            self.toggled.emit()
        elif owl.belly_area(r).contains(pos):
            self.animator.pet()
            self.update()

    def mouseMoveCursor(self, pos: QPointF):
        """Mãozinha sobre os olhos e as orelhas."""
        r = self.owl_rect()
        hot = (self.right_ear_rect().contains(pos) or self.left_ear_rect().contains(pos)
               or any(eye.contains(pos) for eye in owl.eye_areas(r)))
        self.setCursor(Qt.PointingHandCursor if hot else Qt.ArrowCursor)

    def enterEvent(self, e):
        self.setMouseTracking(True)

    def leaveEvent(self, e):
        self.setMouseTracking(False)
        self.unsetCursor()

    def event(self, e):
        # com mouse tracking ligado, o movimento sem botão só serve para trocar o cursor
        if e.type() == e.Type.MouseMove and self._press_global is None:
            self.mouseMoveCursor(e.position())
            return True
        return super().event(e)
