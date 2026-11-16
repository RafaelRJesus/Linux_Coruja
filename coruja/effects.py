"""Efeitos em volta da coruja: partículas, sol, ninho e objetos das animações."""

import colorsys
import math
from dataclasses import dataclass
from enum import Enum, auto

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QPainter, QPainterPath, QPen

from .owl import Geo, fill_oval, fill_path, rgb, stroke_path, triangle

PINK = rgb(0.98, 0.42, 0.58)
NEST = rgb(0.55, 0.40, 0.22)
NEST_DARK = rgb(0.40, 0.28, 0.14)


class Kind(Enum):
    HEART = auto()
    ZZZ = auto()
    NOTE = auto()
    SPARKLE = auto()
    STEAM = auto()
    CRUMB = auto()
    CONFETTI = auto()


@dataclass
class Particle:
    kind: Kind
    x: float          # unidades da coruja, y para cima
    y: float
    vx: float         # unidades por segundo
    vy: float
    life: float       # segundos
    size: float       # unidades da coruja
    age: float = 0.0
    hue: float = 0.0  # cor do confete


class Prop(Enum):
    MUG = auto()        # café
    BOWL = auto()       # almoço
    COOKIE = auto()     # lanche
    PARTY_HAT = auto()  # sexta-feira


# Partículas

def draw_particle(p: QPainter, pt: Particle, g: Geo):
    fade = max(0.0, 1 - pt.age / pt.life)
    if fade <= 0.01:
        return
    c = g.P(pt.x, pt.y)
    s = pt.size * g.s
    p.save()
    p.setOpacity(fade)
    k = pt.kind
    if k is Kind.HEART:
        fill_path(p, heart_path(c, s), PINK)
    elif k is Kind.ZZZ:
        draw_text(p, "z", c, s, rgb(0.95, 0.95, 0.95))
    elif k is Kind.NOTE:
        draw_text(p, "♪", c, s, rgb(0.55, 0.75, 1))
    elif k is Kind.SPARKLE:
        fill_path(p, star_path(c, s), rgb(1, 0.95, 0.6))
    elif k is Kind.STEAM:
        fill_oval(p, QRectF(c.x() - s / 2, c.y() - s / 2, s, s), rgb(1, 1, 1, 0.6))
    elif k is Kind.CRUMB:
        fill_oval(p, QRectF(c.x() - s / 2, c.y() - s / 2, s, s), rgb(0.85, 0.65, 0.35))
    elif k is Kind.CONFETTI:
        r, gg, b = colorsys.hsv_to_rgb(pt.hue, 0.7, 1)
        p.fillRect(QRectF(c.x(), c.y() - s * 0.5, s, s * 0.5), rgb(r, gg, b))
    p.restore()


def draw_text(p: QPainter, text: str, c: QPointF, size: float, color):
    f = QFont()
    f.setBold(True)
    f.setPixelSize(max(6, int(size)))
    p.setFont(f)
    p.setPen(color)
    p.drawText(QRectF(c.x() - size, c.y() - size, 2 * size, 2 * size), Qt.AlignCenter, text)


def heart_path(c: QPointF, s: float) -> QPainterPath:
    def q(dx, dy):  # y para cima, em relação ao centro
        return QPointF(c.x() + dx * s, c.y() - dy * s)

    path = QPainterPath(q(0, -0.5))
    path.cubicTo(q(-0.15, -0.25), q(-0.5, -0.1), q(-0.5, 0.15))
    path.cubicTo(q(-0.5, 0.5), q(-0.05, 0.5), q(0, 0.2))
    path.cubicTo(q(0.05, 0.5), q(0.5, 0.5), q(0.5, 0.15))
    path.cubicTo(q(0.5, -0.1), q(0.15, -0.25), q(0, -0.5))
    path.closeSubpath()
    return path


def star_path(c: QPointF, s: float) -> QPainterPath:
    r, k = s / 2, s / 2 * 0.3
    pts = [(0, r), (k, k), (r, 0), (k, -k), (0, -r), (-k, -k), (-r, 0), (-k, k)]
    path = QPainterPath(QPointF(c.x() + pts[0][0], c.y() - pts[0][1]))
    for x, y in pts[1:]:
        path.lineTo(QPointF(c.x() + x, c.y() - y))
    path.closeSubpath()
    return path


# Sol (do lado esquerdo da coruja, sobe e desce como no horizonte)

def draw_sun(p: QPainter, g: Geo, progress: float, spin: float, alpha: float):
    if alpha <= 0.01:
        return
    pr = max(0.0, min(1.0, progress))
    center = g.P(0.04, 0.10 + 0.72 * pr)
    r = 0.11 * g.s
    color = rgb(1, 0.55 + 0.35 * pr, 0.15 + 0.2 * pr)
    p.save()
    p.setOpacity(alpha)
    glow = rgb(1, 0.55 + 0.35 * pr, 0.15 + 0.2 * pr, 0.35 * pr + 0.15)
    fill_oval(p, QRectF(center.x() - r * 1.7, center.y() - r * 1.7, r * 3.4, r * 3.4), glow)
    rays = QPainterPath()
    for i in range(8):
        a = i / 8 * 2 * math.pi + spin
        rays.moveTo(center.x() + math.cos(a) * r * 1.3, center.y() + math.sin(a) * r * 1.3)
        rays.lineTo(center.x() + math.cos(a) * r * 1.7, center.y() + math.sin(a) * r * 1.7)
    stroke_path(p, rays, color, 0.02 * g.s)
    fill_oval(p, QRectF(center.x() - r, center.y() - r, 2 * r, 2 * r), color)
    p.restore()


# Ninho (na frente da coruja, cobrindo pés e barriga)

def draw_nest(p: QPainter, g: Geo, amount: float):
    if amount <= 0.01:
        return
    dy = (1 - amount) * 0.25  # sobe de baixo quando aparece
    p.save()
    p.setOpacity(min(1.0, amount))
    bowl = QPainterPath(g.P(0.08, 0.20 - dy))
    bowl.cubicTo(g.P(0.10, -0.08 - dy), g.P(0.90, -0.08 - dy), g.P(0.92, 0.20 - dy))
    bowl.closeSubpath()
    fill_path(p, bowl, NEST)
    fill_oval(p, g.R(0.07, 0.15 - dy, 0.86, 0.09), NEST_DARK)
    twigs = QPainterPath()
    for x1, y1, x2, y2 in [(0.12, 0.14, 0.40, 0.04), (0.30, 0.17, 0.62, 0.06), (0.55, 0.15, 0.88, 0.12),
                           (0.20, 0.06, 0.48, 0.13), (0.50, 0.03, 0.80, 0.14), (0.05, 0.19, 0.22, 0.22),
                           (0.78, 0.22, 0.95, 0.18)]:
        twigs.moveTo(g.P(x1, y1 - dy))
        twigs.lineTo(g.P(x2, y2 - dy))
    stroke_path(p, twigs, NEST_DARK, 0.012 * g.s)
    p.restore()


# Objetos

def draw_prop(p: QPainter, prop: Prop, g: Geo, phase: float):
    if prop is Prop.MUG:
        # canequinha na asa esquerda; sobe um pouco no gole
        cream = rgb(0.95, 0.93, 0.88)
        cup = g.R(0.10, 0.22 + phase * 0.08, 0.15, 0.14)
        p.setPen(Qt.NoPen)
        p.setBrush(cream)
        p.drawRoundedRect(cup, 0.02 * g.s, 0.02 * g.s)
        p.fillRect(QRectF(cup.left() + 0.015 * g.s, cup.top() + 0.01 * g.s, cup.width() - 0.03 * g.s, 0.02 * g.s),
                   rgb(0.45, 0.28, 0.15))
        p.setPen(QPen(cream, 0.015 * g.s))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(cup.left() - 0.05 * g.s, cup.center().y() - 0.035 * g.s, 0.07 * g.s, 0.07 * g.s))
    elif prop is Prop.BOWL:
        bowl = QPainterPath(g.P(0.30, 0.10))
        bowl.cubicTo(g.P(0.32, -0.02), g.P(0.68, -0.02), g.P(0.70, 0.10))
        bowl.closeSubpath()
        fill_path(p, bowl, rgb(0.30, 0.55, 0.85))
        fill_oval(p, g.R(0.32, 0.075, 0.36, 0.05), rgb(0.90, 0.75, 0.40))
    elif prop is Prop.COOKIE:
        # biscoito na asa direita; a mordida cresce com a fase
        cookie = QPainterPath()
        cookie.addEllipse(g.R(0.76, 0.24, 0.15, 0.15))
        if phase > 0.3:
            bite = QPainterPath()
            b = 0.07 + phase * 0.03
            bite.addEllipse(g.R(0.86, 0.33, b, b))
            cookie = cookie.subtracted(bite)
        fill_path(p, cookie, rgb(0.82, 0.60, 0.32))
        p.save()
        p.setClipPath(cookie)
        for x, y in [(0.80, 0.33), (0.85, 0.28), (0.79, 0.26)]:
            fill_oval(p, g.R(x, y, 0.02, 0.02), rgb(0.35, 0.20, 0.10))
        p.restore()
    elif prop is Prop.PARTY_HAT:
        fill_path(p, triangle(g.P(0.40, 0.83), g.P(0.60, 0.83), g.P(0.52, 1.05)), rgb(0.55, 0.35, 0.95))
        fill_oval(p, g.R(0.495, 1.02, 0.05, 0.05), rgb(1, 0.85, 0.3))
