"""Desenho da coruja com QPainter.

As medidas são em "unidades da coruja" (0 a 1), com y crescendo para cima,
iguais às da versão macOS. A classe Geo converte para pixels do Qt (y para baixo).
"""

import math
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QTransform


def rgb(r, g, b, a=1.0) -> QColor:
    return QColor.fromRgbF(r, g, b, a)


BODY = rgb(0.48, 0.33, 0.22)
DARK = rgb(0.33, 0.21, 0.13)
BELLY = rgb(0.88, 0.76, 0.58)
MASK = rgb(0.93, 0.85, 0.70)
BEAK = rgb(0.96, 0.64, 0.16)
IRIS = rgb(0.99, 0.76, 0.10)
GOLD = rgb(0.95, 0.78, 0.25)
WHITE = rgb(1, 1, 1)
BLACK = rgb(0, 0, 0)
DEFAULT_GEM = (0.95, 0.55, 0.10)


class Geo:
    """Converte unidades da coruja (0..1, y para cima) em pixels."""

    def __init__(self, rect: QRectF):
        self.s = min(rect.width(), rect.height())
        self.left = rect.center().x() - self.s / 2
        self.top = rect.center().y() - self.s / 2

    def P(self, x, y) -> QPointF:
        return QPointF(self.left + x * self.s, self.top + (1 - y) * self.s)

    def R(self, x, y, w, h) -> QRectF:
        return QRectF(self.left + x * self.s, self.top + (1 - y - h) * self.s, w * self.s, h * self.s)


@dataclass
class Pose:
    lid: float = 0.0          # pálpebra: 0 = aberto, 1 = fechado
    look: tuple = (0.0, 0.0)  # direção do olhar (-1..1), y para cima
    puppy: float = 0.0        # carinha de filhote
    happy: bool = False       # olhinhos ^^
    wing: float = 0.0         # asas levantadas
    step: float = 0.0         # passinho (-1..1)
    beak_open: float = 0.0    # bico aberto


AWAKE = Pose()
ASLEEP = Pose(lid=1.0)


# Áreas clicáveis

def eye_areas(rect: QRectF):
    g = Geo(rect)
    return [g.R(0.21, 0.45, 0.30, 0.30), g.R(0.49, 0.45, 0.30, 0.30)]


def right_ear_area(rect: QRectF) -> QRectF:
    """Orelha direita (com brinco): quando dormir."""
    g = Geo(rect)
    return g.R(0.56, 0.76, 0.28, 0.19).united(g.R(0.75, 0.70, 0.11, 0.14))


def left_ear_area(rect: QRectF) -> QRectF:
    """Orelha esquerda (sem brinco): animações."""
    return Geo(rect).R(0.16, 0.76, 0.28, 0.19)


def belly_area(rect: QRectF) -> QRectF:
    """Barriga: carinho."""
    return Geo(rect).R(0.32, 0.10, 0.36, 0.30)


# Formas

def triangle(a: QPointF, b: QPointF, c: QPointF) -> QPainterPath:
    p = QPainterPath(a)
    p.lineTo(b)
    p.lineTo(c)
    p.closeSubpath()
    return p


def fill_oval(p: QPainter, r: QRectF, color: QColor):
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawEllipse(r)


def fill_path(p: QPainter, path: QPainterPath, color: QColor):
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPath(path)


def stroke_path(p: QPainter, path: QPainterPath, color: QColor, width: float):
    p.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)


# Coruja completa

def draw(p: QPainter, rect: QRectF, pose: Pose = AWAKE, gem=DEFAULT_GEM):
    g = Geo(rect)

    # tufos das orelhas
    fill_path(p, triangle(g.P(0.24, 0.68), g.P(0.19, 0.93), g.P(0.42, 0.80)), DARK)
    fill_path(p, triangle(g.P(0.76, 0.68), g.P(0.81, 0.93), g.P(0.58, 0.80)), DARK)

    # asas
    draw_wing(p, g, left=True, lift=pose.wing)
    draw_wing(p, g, left=False, lift=pose.wing)

    # corpo, barriga e penas
    fill_oval(p, g.R(0.18, 0.07, 0.64, 0.80), BODY)
    fill_oval(p, g.R(0.30, 0.09, 0.40, 0.42), BELLY)
    feathers = QPainterPath()
    for x, y in [(0.42, 0.33), (0.58, 0.33), (0.50, 0.25), (0.42, 0.17), (0.58, 0.17)]:
        feathers.moveTo(g.P(x - 0.03, y + 0.02))
        feathers.lineTo(g.P(x, y))
        feathers.lineTo(g.P(x + 0.03, y + 0.02))
    stroke_path(p, feathers, rgb(0.33, 0.21, 0.13, 0.45), 0.012 * g.s)

    # pés (um sobe a cada passinho)
    fill_oval(p, g.R(0.36, 0.045 + max(0, pose.step) * 0.025, 0.11, 0.05), BEAK)
    fill_oval(p, g.R(0.53, 0.045 + max(0, -pose.step) * 0.025, 0.11, 0.05), BEAK)

    # olhos
    eyes = eye_areas(rect)
    for e in eyes:
        fill_oval(p, e, MASK)
    for e in eyes:
        inset = 0.03 * g.s
        draw_eye(p, e.adjusted(inset, inset, -inset, -inset), g, pose)

    draw_beak(p, g, pose.beak_open)
    draw_earring(p, g, gem)


def draw_wing(p: QPainter, g: Geo, left: bool, lift: float):
    rect = g.R(0.12, 0.18, 0.20, 0.42) if left else g.R(0.68, 0.18, 0.20, 0.42)
    pivot = g.P(0.25, 0.55) if left else g.P(0.75, 0.55)
    path = QPainterPath()
    path.addEllipse(rect)
    if lift > 0.01:
        # no Qt, ângulo positivo gira no sentido horário da tela
        angle = (1 if left else -1) * lift * 60
        t = QTransform().translate(pivot.x(), pivot.y()).rotate(angle).translate(-pivot.x(), -pivot.y())
        path = t.map(path)
    fill_path(p, path, DARK)


def draw_eye(p: QPainter, inner: QRectF, g: Geo, pose: Pose):
    w, h = inner.width(), inner.height()

    # olhinhos de alegria: ^^
    if pose.happy:
        fill_oval(p, inner, BODY)
        y = inner.center().y() + h * 0.08
        arc = QPainterPath(QPointF(inner.left() + w * 0.18, y))
        arc.cubicTo(QPointF(inner.left() + w * 0.30, y - h * 0.38),
                    QPointF(inner.right() - w * 0.30, y - h * 0.38),
                    QPointF(inner.right() - w * 0.18, y))
        stroke_path(p, arc, DARK, 0.022 * g.s)
        return

    # olho fechado: curvinha para baixo
    if pose.lid >= 0.97:
        fill_oval(p, inner, BODY)
        y = inner.center().y()
        arc = QPainterPath(QPointF(inner.left() + w * 0.12, y))
        arc.cubicTo(QPointF(inner.left() + w * 0.30, y + h * 0.30),
                    QPointF(inner.right() - w * 0.30, y + h * 0.30),
                    QPointF(inner.right() - w * 0.12, y))
        stroke_path(p, arc, DARK, 0.02 * g.s)
        return

    # olho aberto (íris e pupila maiores na carinha de filhote)
    fill_oval(p, inner, WHITE)
    ins = 0.18 - pose.puppy * 0.07
    shift = w * 0.11
    ir = inner.adjusted(w * ins, h * ins, -w * ins, -h * ins)
    ir.translate(pose.look[0] * shift, -pose.look[1] * shift)
    fill_oval(p, ir, IRIS)

    pin = 0.25 - pose.puppy * 0.13
    pupil = ir.adjusted(ir.width() * pin, ir.height() * pin, -ir.width() * pin, -ir.height() * pin)
    fill_oval(p, pupil, BLACK)

    hs = pupil.width() * (0.35 + pose.puppy * 0.1)
    fill_oval(p, QRectF(pupil.center().x(), pupil.center().y() - hs, hs, hs), WHITE)
    if pose.puppy > 0.2:
        hs2 = pupil.width() * 0.18
        fill_oval(p, QRectF(pupil.left() + pupil.width() * 0.2, pupil.bottom() - pupil.height() * 0.22 - hs2, hs2, hs2),
                  rgb(1, 1, 1, pose.puppy))

    # pálpebra descendo de cima
    if pose.lid > 0.01:
        p.save()
        clip = QPainterPath()
        clip.addEllipse(inner)
        p.setClipPath(clip, Qt.IntersectClip)
        lid_h = h * pose.lid
        p.fillRect(QRectF(inner.left(), inner.top(), w, lid_h), BODY)
        p.setPen(QPen(DARK, 0.014 * g.s))
        p.drawLine(QPointF(inner.left(), inner.top() + lid_h), QPointF(inner.right(), inner.top() + lid_h))
        p.restore()


def draw_beak(p: QPainter, g: Geo, open_: float):
    if open_ <= 0.05:
        fill_path(p, triangle(g.P(0.46, 0.47), g.P(0.54, 0.47), g.P(0.50, 0.37)), BEAK)
        return
    gap = open_ * 0.05
    fill_oval(p, g.R(0.465, 0.375 - gap, 0.07, 0.05 + gap), DARK)
    fill_path(p, triangle(g.P(0.46, 0.47), g.P(0.54, 0.47), g.P(0.50, 0.40)), BEAK)
    fill_path(p, triangle(g.P(0.475, 0.395 - gap), g.P(0.525, 0.395 - gap), g.P(0.50, 0.36 - gap)), BEAK)


def draw_earring(p: QPainter, g: Geo, gem):
    """Argolinha dourada com uma pedra redonda. A cor da pedra mostra a configuração ativa."""
    p.setPen(QPen(GOLD, 0.012 * g.s))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(g.R(0.765, 0.785, 0.045, 0.045))

    ball = g.R(0.762, 0.715, 0.06, 0.06)
    pad = 0.008 * g.s
    fill_oval(p, ball.adjusted(-pad, -pad, pad, pad), GOLD)
    fill_oval(p, ball, rgb(*gem))
    bw = ball.width()
    fill_oval(p, QRectF(ball.left() + bw * 0.22, ball.top() + bw * 0.17, bw * 0.28, bw * 0.28), rgb(1, 1, 1, 0.8))


def icon_image(size: int = 512) -> QImage:
    """Ícone do app: fundo noturno arredondado + coruja de olhos abertos."""
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    bg = QRectF(size * 0.1, size * 0.1, size * 0.8, size * 0.8)
    grad = QLinearGradient(bg.topLeft(), bg.bottomLeft())
    grad.setColorAt(0, rgb(0.16, 0.20, 0.38))
    grad.setColorAt(1, rgb(0.07, 0.09, 0.20))
    p.setPen(Qt.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(bg, size * 0.18, size * 0.18)
    m = size * 0.06
    draw(p, bg.adjusted(m, m, -m, -m))
    p.end()
    return img
