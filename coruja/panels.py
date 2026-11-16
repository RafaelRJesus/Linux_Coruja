"""Painéis que abrem nas orelhas da coruja.

Orelha direita (brinco): quando dormir.
Orelha esquerda: animações.
"""

from PySide6.QtCore import QPoint, QTime, QTimer, Qt
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QTimeEdit, QVBoxLayout,
    QWidget,
)

from .animator import Activity
from .settings import LimitMode, OwlSize


class Panel(QFrame):
    """Janelinha que fecha sozinha ao clicar fora (como um popover)."""

    def __init__(self):
        super().__init__(None, Qt.Popup)
        self.setFrameShape(QFrame.StyledPanel)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(14, 14, 14, 14)
        self.layout_.setSpacing(10)

    def title(self, text):
        label = QLabel(f"<b>{text}</b>")
        self.layout_.addWidget(label)
        return label

    def row(self, *widgets):
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        for w in widgets:
            h.addWidget(QLabel(w) if isinstance(w, str) else w)
        h.addStretch(1)
        self.layout_.addWidget(box)
        return box

    def show_at(self, anchor: QPoint):
        """Abre logo acima do ponto (a orelha), sem sair da tela."""
        self.adjustSize()
        x = anchor.x() - self.width() // 2
        y = anchor.y() - self.height() - 8
        screen = self.screen().availableGeometry() if self.screen() else None
        if screen is not None:
            x = max(screen.left(), min(x, screen.right() - self.width()))
            if y < screen.top():
                y = anchor.y() + 16
        self.move(x, y)
        self.show()


class SleepPanel(Panel):
    """Quando a coruja deve dormir: sem limite, temporizador ou horário."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        s = app.settings
        self.title("Quando a coruja deve dormir?")

        self.group = QButtonGroup(self)
        buttons = []
        for mode, text in ((LimitMode.NONE, "Sem limite"), (LimitMode.TIMER, "Temporizador"),
                           (LimitMode.CLOCK, "Horário")):
            b = QPushButton(text)
            b.setCheckable(True)
            self.group.addButton(b, int(mode))
            buttons.append(b)
        self.row(*buttons)
        self.group.idClicked.connect(self.mode_changed)

        self.hours = QComboBox()
        self.hours.addItems([f"{h} h" for h in range(13)])
        self.minutes = QComboBox()
        self.minutes.addItems([f"{m} min" for m in range(0, 60, 5)])
        self.timer_row = self.row("Dormir em", self.hours, self.minutes)

        self.clock = QTimeEdit()
        self.clock.setDisplayFormat("HH:mm")
        self.clock_row = self.row("Dormir às", self.clock)

        self.status = QLabel()
        self.status.setStyleSheet("color: gray")
        self.layout_.addWidget(self.status)

        self.apply_button = QPushButton()
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self.apply)
        self.layout_.addWidget(self.apply_button)

        for w in (self.hours, self.minutes):
            w.currentIndexChanged.connect(self.values_changed)
        self.clock.timeChanged.connect(self.values_changed)

        # contagem regressiva ao vivo enquanto o painel está aberto
        self.live = QTimer(self)
        self.live.setInterval(1000)
        self.live.timeout.connect(self.refresh)

    def showEvent(self, e):
        s = self.app.settings
        self.group.button(int(s.mode)).setChecked(True)
        m = int(s.get("timer_minutes"))
        self.hours.setCurrentIndex(min(12, m // 60))
        self.minutes.setCurrentIndex((m % 60) // 5)
        c = int(s.get("clock_minutes"))
        self.clock.setTime(QTime(c // 60, c % 60))
        self.refresh()
        self.live.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.live.stop()
        super().hideEvent(e)

    def mode_changed(self, mode_id):
        self.app.settings.set("mode", mode_id)
        self.app.update_gem()
        self.refresh()

    def values_changed(self, *_):
        s = self.app.settings
        s.set("timer_minutes", max(5, self.hours.currentIndex() * 60 + self.minutes.currentIndex() * 5))
        t = self.clock.time()
        s.set("clock_minutes", t.hour() * 60 + t.minute())
        self.refresh()

    def apply(self):
        """Salva e acorda a coruja com o limite escolhido (ou reinicia a contagem)."""
        self.values_changed()
        self.app.wake()
        self.hide()

    def refresh(self):
        mode = self.app.settings.mode
        self.timer_row.setVisible(mode == LimitMode.TIMER)
        self.clock_row.setVisible(mode == LimitMode.CLOCK)
        self.apply_button.setText("Aplicar" if self.app.keeper.active else "Acordar a coruja")
        self.status.setText(self.app.status_text())
        self.adjustSize()


PLAYABLE = [
    ("Carinha de filhote", Activity.PUPPY), ("Piar", Activity.HOOT), ("Bater asas", Activity.FLAP),
    ("Pulinho", Activity.HOP), ("Olhar em volta", Activity.LOOK_AROUND), ("Bocejar", Activity.YAWN),
    ("Descansar no ninho", Activity.NEST), ("Passear", Activity.WALKING), ("Café", Activity.COFFEE),
    ("Almoço", Activity.LUNCH), ("Lanche", Activity.SNACK), ("Festa de sexta", Activity.PARTY),
    ("Nascer do sol", Activity.SUNRISE), ("Pôr do sol", Activity.DUSK),
]


class AnimationPanel(Panel):
    """Liga/desliga as animações e escolhe as opções e o tamanho."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.title("Animações")

        self.master = QCheckBox("Animações ligadas")
        self.walking = QCheckBox("Passear pela tela")
        self.attention = QCheckBox("Chamar atenção de vez em quando")
        self.schedule = QCheckBox("Animações por horário (café, almoço, lanche, sol)")
        for box in (self.master, self.walking, self.attention, self.schedule):
            self.layout_.addWidget(box)
            box.toggled.connect(self.options_changed)

        self.size = QComboBox()
        self.size.addItems([s.title for s in OwlSize])
        self.size.currentIndexChanged.connect(self.size_changed)
        self.row("Tamanho", self.size)

        self.play = QComboBox()
        self.play.addItem("Ver uma animação agora…")
        self.play.addItems([name for name, _ in PLAYABLE])
        self.play.activated.connect(self.play_chosen)
        self.layout_.addWidget(self.play)

        hint = QLabel("Desligadas, a coruja fica parada e não usa processamento.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px")
        self.layout_.addWidget(hint)
        self.setMinimumWidth(320)

    def showEvent(self, e):
        s = self.app.settings
        self._loading = True
        self.master.setChecked(bool(s.get("animations_on")))
        self.walking.setChecked(bool(s.get("walking_on")))
        self.attention.setChecked(bool(s.get("attention_on")))
        self.schedule.setChecked(bool(s.get("schedule_on")))
        self.size.setCurrentIndex(int(s.size))
        self.play.setCurrentIndex(0)
        self._loading = False
        self.refresh_enabled()
        super().showEvent(e)

    def refresh_enabled(self):
        on = self.master.isChecked()
        for w in (self.walking, self.attention, self.schedule, self.play):
            w.setEnabled(on)

    def options_changed(self, *_):
        if getattr(self, "_loading", False):
            return
        s = self.app.settings
        was_on = bool(s.get("animations_on"))
        s.set("animations_on", self.master.isChecked())
        s.set("walking_on", self.walking.isChecked())
        s.set("attention_on", self.attention.isChecked())
        s.set("schedule_on", self.schedule.isChecked())
        self.refresh_enabled()
        if was_on != self.master.isChecked():
            self.app.apply_animation_settings()

    def size_changed(self, index):
        if getattr(self, "_loading", False):
            return
        self.app.settings.set("size", index)
        self.app.apply_size()

    def play_chosen(self, index):
        if index <= 0:
            return
        self.app.play_now(PLAYABLE[index - 1][1])
        self.hide()
