"""Configurações da Coruja, salvas em ~/.config/coruja/settings.json."""

import json
import os
import random
from datetime import datetime, timedelta
from enum import IntEnum
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "coruja"
CONFIG_FILE = CONFIG_DIR / "settings.json"


class LimitMode(IntEnum):
    NONE = 0    # fica acordada até eu fechar os olhos
    TIMER = 1   # contagem regressiva
    CLOCK = 2   # horário fixo


# Cor da pedra do brinco para cada configuração (r, g, b de 0 a 1)
GEM_COLORS = {
    LimitMode.NONE: (0.95, 0.55, 0.10),    # laranja
    LimitMode.TIMER: (0.25, 0.55, 0.95),   # azul
    LimitMode.CLOCK: (0.20, 0.75, 0.45),   # verde
}


class OwlSize(IntEnum):
    SMALL = 0
    MEDIUM = 1
    LARGE = 2

    @property
    def points(self) -> int:
        return (70, 95, 125)[self]

    @property
    def title(self) -> str:
        return ("Pequena", "Média", "Grande")[self]


DEFAULTS = {
    "mode": int(LimitMode.NONE),
    "timer_minutes": 60,
    "clock_minutes": 18 * 60,
    "animations_on": True,
    "walking_on": True,
    "attention_on": True,
    "schedule_on": True,
    "size": int(OwlSize.SMALL),
    "sunrise": 6 * 60,
    "sunset": 18 * 60 + 30,
    "always_on_top": True,
    "position": None,
    "played": {},
}


class Settings:
    """Lê e grava as configurações em JSON. Cada alteração já é salva."""

    def __init__(self, path: Path = CONFIG_FILE):
        self.path = path
        self.data = dict(DEFAULTS)
        try:
            self.data.update(json.loads(path.read_text()))
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2))
        except OSError:
            pass  # sem conseguir salvar, segue funcionando com o que está na memória

    def get(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()

    # Atalhos tipados

    @property
    def mode(self) -> LimitMode:
        try:
            return LimitMode(self.get("mode"))
        except ValueError:
            return LimitMode.NONE

    @property
    def size(self) -> OwlSize:
        try:
            return OwlSize(self.get("size"))
        except ValueError:
            return OwlSize.SMALL

    # Limite para dormir

    def deadline(self, now: datetime | None = None) -> datetime | None:
        """Quando a coruja deve dormir a partir de agora (None = sem limite)."""
        now = now or datetime.now()
        mode = self.mode
        if mode == LimitMode.TIMER:
            return now + timedelta(minutes=max(1, int(self.get("timer_minutes"))))
        if mode == LimitMode.CLOCK:
            m = int(self.get("clock_minutes"))
            today = now.replace(hour=m // 60, minute=m % 60, second=0, microsecond=0)
            # se o horário de hoje já passou, vale para amanhã
            return today if today > now else today + timedelta(days=1)
        return None

    # Dia e noite

    @staticmethod
    def minutes_now(now: datetime | None = None) -> int:
        now = now or datetime.now()
        return now.hour * 60 + now.minute

    def is_evening(self, now: datetime | None = None) -> bool:
        """Noite: entre o pôr e o nascer do sol (olhos um pouco mais baixos)."""
        m = self.minutes_now(now)
        return m >= int(self.get("sunset")) or m < int(self.get("sunrise"))

    # Animações de horário: tocam só uma vez por dia

    def played_today(self, key: str) -> bool:
        return self.get("played").get(key) == datetime.now().strftime("%Y-%m-%d")

    def mark_played_today(self, key: str):
        played = dict(self.get("played"))
        played[key] = datetime.now().strftime("%Y-%m-%d")
        self.set("played", played)


def format_remaining(seconds: float) -> str:
    s = max(0, int(seconds + 0.999))
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def random_minute(start: int, end: int) -> int:
    """Minuto sorteado dentro de uma janela (deixa 10 min de folga no fim)."""
    return random.randint(start, max(start, end - 10))
