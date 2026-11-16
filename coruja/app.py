"""Coruja para Linux: liga a janela, o animador, os painéis e o KeepAwake."""

import os
import sys
import time
from datetime import datetime

from PySide6.QtCore import QObject, QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import owl
from .animator import Animator
from .keepawake import KeepAwake
from .panels import AnimationPanel, SleepPanel
from .settings import GEM_COLORS, Settings, format_remaining
from .view import OwlWidget


class CorujaApp(QObject):
    def __init__(self, qapp: QApplication):
        super().__init__()
        self.qapp = qapp
        self.settings = Settings()
        self.keeper = KeepAwake()
        self.animator = Animator(self.settings)
        self.deadline = None

        self.icon = QIcon(QPixmap.fromImage(owl.icon_image(256)))
        qapp.setWindowIcon(self.icon)

        self.widget = OwlWidget(self.animator, self.settings.size.points, bool(self.settings.get("always_on_top")))
        self.widget.toggled.connect(self.toggle)
        self.widget.right_ear.connect(lambda: self.show_panel(self.sleep_panel, self.widget.right_ear_rect()))
        self.widget.left_ear.connect(lambda: self.show_panel(self.animation_panel, self.widget.left_ear_rect()))
        self.widget.drag_changed.connect(self.drag_changed)
        self.widget.moved.connect(self.save_position)
        self.widget.setContextMenuPolicy(Qt.ActionsContextMenu)   # botão direito mostra o menu
        self.update_gem()

        self.sleep_panel = SleepPanel(self)
        self.animation_panel = AnimationPanel(self)

        self.animator.can_walk = lambda: not (self.sleep_panel.isVisible() or self.animation_panel.isVisible())
        self.animator.move_window = self.move_window

        self.build_menu()
        self.place_window()
        self.widget.show()

        # laço de animação: a taxa de quadros se adapta ao que está acontecendo
        self.frame_timer = QTimer(self)
        self.frame_timer.timeout.connect(self.frame)
        self.last_frame = time.monotonic()

        # relógio do limite para dormir
        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(1000)
        self.tick_timer.timeout.connect(self.tick)

        self.animator.static_frame()
        self.start_animating()
        self.update_status()
        qapp.aboutToQuit.connect(self.keeper.stop)

    # Menu (botão direito na coruja e ícone na bandeja)

    def build_menu(self):
        self.toggle_action = QAction("Acordar a coruja", self)
        self.toggle_action.triggered.connect(self.toggle)
        sleep_action = QAction("Quando dormir…", self)
        sleep_action.triggered.connect(lambda: self.show_panel(self.sleep_panel, self.widget.right_ear_rect()))
        anim_action = QAction("Animações…", self)
        anim_action.triggered.connect(lambda: self.show_panel(self.animation_panel, self.widget.left_ear_rect()))
        self.on_top_action = QAction("Sempre na frente", self, checkable=True)
        self.on_top_action.setChecked(bool(self.settings.get("always_on_top")))
        self.on_top_action.toggled.connect(self.set_on_top)
        separator = QAction(self)
        separator.setSeparator(True)
        quit_action = QAction("Sair", self)
        quit_action.triggered.connect(self.qapp.quit)

        actions = [self.toggle_action, sleep_action, anim_action, self.on_top_action, separator, quit_action]
        self.widget.addActions(actions)

        if QSystemTrayIcon.isSystemTrayAvailable():
            menu = QMenu()
            menu.addActions(actions)
            self.tray = QSystemTrayIcon(self.icon, self)
            self.tray.setContextMenu(menu)
            self.tray.setToolTip("Coruja")
            self.tray.activated.connect(self.tray_clicked)
            self.tray.show()
        else:
            self.tray = None

    def tray_clicked(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.toggle()

    # Janela

    def place_window(self):
        pos = self.settings.get("position")
        screen = self.qapp.primaryScreen().availableGeometry()
        if pos and any(s.availableGeometry().contains(QPoint(*pos)) for s in self.qapp.screens()):
            self.widget.move(*pos)
        else:
            self.widget.move(screen.right() - self.widget.width() - 30, screen.bottom() - self.widget.height() - 10)

    def save_position(self):
        self.settings.set("position", [self.widget.x(), self.widget.y()])

    def move_window(self, dx: float) -> bool:
        """Passeio: move a janela de lado sem sair da tela."""
        screen = (self.widget.screen() or self.qapp.primaryScreen()).availableGeometry()
        self._walk_x = getattr(self, "_walk_x", float(self.widget.x()))
        if abs(self._walk_x - self.widget.x()) > 2:   # alguém moveu a janela no meio do passeio
            self._walk_x = float(self.widget.x())
        wanted = self._walk_x + dx
        x = max(screen.left(), min(wanted, screen.right() - self.widget.width()))
        self._walk_x = x
        self.widget.move(int(x), self.widget.y())
        if x != wanted:
            self.save_position()
            return False
        return True

    def set_on_top(self, on_top: bool):
        self.settings.set("always_on_top", on_top)
        self.widget.set_on_top(on_top)

    def show_panel(self, panel, ear_rect):
        for other in (self.sleep_panel, self.animation_panel):
            if other is not panel:
                other.hide()
        if panel.isVisible():
            panel.hide()
            return
        anchor = self.widget.mapToGlobal(ear_rect.center().toPoint())
        panel.show_at(QPoint(anchor.x(), self.widget.mapToGlobal(ear_rect.topLeft().toPoint()).y()))

    def update_gem(self):
        self.widget.gem = GEM_COLORS[self.settings.mode]
        self.widget.update()

    def apply_size(self):
        self.widget.set_owl_size(self.settings.size.points)
        self.save_position()

    # Animação

    def start_animating(self):
        if not self.settings.get("animations_on"):
            self.stop_animating()
            return
        self.set_fps(self.animator.desired_fps)

    def stop_animating(self):
        self.frame_timer.stop()
        self.animator.static_frame()
        self.widget.update()

    def set_fps(self, fps: int):
        interval = int(1000 / fps)
        if self.frame_timer.isActive() and self.frame_timer.interval() == interval:
            return
        self.frame_timer.start(interval)
        self.last_frame = time.monotonic()

    def frame(self):
        now = time.monotonic()
        dt = min(0.1, now - self.last_frame)
        self.last_frame = now
        if not self.widget.isVisible():
            return
        self.animator.mouse_look = self.widget.look_at_cursor()
        self.animator.update(dt)
        self.widget.update()
        self.set_fps(self.animator.desired_fps)

    def drag_changed(self, dragging: bool):
        self.animator.dragging = dragging
        if self.settings.get("animations_on"):
            self.set_fps(self.animator.desired_fps)

    def apply_animation_settings(self):
        if self.settings.get("animations_on"):
            self.start_animating()
        else:
            self.stop_animating()

    def play_now(self, activity):
        if not self.settings.get("animations_on"):
            return
        self.animator.play(activity)
        self.start_animating()

    # Acordar e dormir

    def toggle(self):
        if self.keeper.active:
            self.sleep()
        else:
            self.wake()

    def wake(self):
        """Abre os olhos e, se houver limite configurado, começa a contar."""
        if not self.keeper.active:
            self.keeper.start()
            self.toggle_action.setText("Pôr a coruja para dormir")
            if self.settings.get("animations_on"):
                self.animator.wake()
                self.start_animating()
            else:
                self.animator.awake = True
                self.animator.static_frame()
                self.widget.update()
        self.deadline = self.settings.deadline()
        if self.deadline:
            self.tick_timer.start()
        else:
            self.tick_timer.stop()
        self.update_status()

    def sleep(self):
        """Fecha os olhos e devolve o computador ao comportamento normal."""
        self.keeper.stop()
        self.toggle_action.setText("Acordar a coruja")
        self.deadline = None
        self.tick_timer.stop()
        if self.settings.get("animations_on"):
            self.animator.sleep()
            self.start_animating()
        else:
            self.animator.awake = False
            self.animator.static_frame()
            self.widget.update()
        self.update_status()

    def tick(self):
        if self.deadline and datetime.now() >= self.deadline:
            self.sleep()
        else:
            self.update_status()

    def status_text(self) -> str:
        if not self.keeper.active:
            return "Dormindo"
        if not self.deadline:
            return "Acordada, sem limite"
        remaining = (self.deadline - datetime.now()).total_seconds()
        return f"Dorme em {format_remaining(remaining)} (às {self.deadline:%H:%M})"

    def update_status(self):
        text = self.status_text()
        self.widget.setToolTip(text)
        if self.tray:
            self.tray.setToolTip(f"Coruja: {text}")


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--export-icon":
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication(sys.argv)
        ok = owl.icon_image(int(sys.argv[3]) if len(sys.argv) > 3 else 512).save(sys.argv[2])
        sys.exit(0 if ok else 1)

    # No Wayland, janelas não podem se posicionar sozinhas (a coruja não passearia nem
    # lembraria o lugar). Se o XWayland estiver disponível, usamos ele.
    if os.environ.get("WAYLAND_DISPLAY") and os.environ.get("DISPLAY") and "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "xcb"

    app = QApplication(sys.argv)
    app.setApplicationName("Coruja")
    app.setDesktopFileName("coruja")
    app.setQuitOnLastWindowClosed(False)
    _coruja = CorujaApp(app)
    sys.exit(app.exec())
