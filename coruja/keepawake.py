"""Mantém o Linux acordado enquanto a coruja está de olhos abertos.

Cada ambiente gráfico faz isso de um jeito, então tentamos todos e
ignoramos o que não existir:

1. org.freedesktop.ScreenSaver.Inhibit  (KDE, XFCE, Cinnamon, MATE, LXQt...)
2. org.gnome.SessionManager.Inhibit     (GNOME)
3. systemd-inhibit                      (bloqueia suspensão/ociosidade no logind)
4. A cada 4 min, avisa que há atividade (SimulateUserActivity e, no X11, xdotool),
   para apps de chat não marcarem "ausente".

O D-Bus usa o jeepney (Python puro) porque o GNOME exige números sem sinal,
e as inibições valem enquanto a conexão ficar aberta.
"""

import os
import shutil
import subprocess

from PySide6.QtCore import QObject, QTimer

try:
    from jeepney import DBusAddress, new_method_call
    from jeepney.io.blocking import open_dbus_connection
    from jeepney.wrappers import unwrap_msg
except ImportError:   # sem jeepney, fica só com o systemd-inhibit
    open_dbus_connection = None

PING_MS = 4 * 60 * 1000
REASON = "Coruja acordada"

FDO = ("/org/freedesktop/ScreenSaver", "org.freedesktop.ScreenSaver", "org.freedesktop.ScreenSaver")
GNOME = ("/org/gnome/SessionManager", "org.gnome.SessionManager", "org.gnome.SessionManager")


class KeepAwake(QObject):
    def __init__(self):
        super().__init__()
        self.active = False
        self._conn = None
        self._fdo_cookie = None
        self._gnome_cookie = None
        self._inhibit_proc = None
        self._timer = QTimer(self)
        self._timer.setInterval(PING_MS)
        self._timer.timeout.connect(self._ping)

    def start(self):
        if self.active:
            return
        self.active = True
        self._fdo_cookie = self._call(FDO, "Inhibit", "ss", ("Coruja", REASON))
        # flags: 4 = suspender, 8 = ficar ocioso
        self._gnome_cookie = self._call(GNOME, "Inhibit", "susu", ("coruja", 0, REASON, 4 | 8))
        self._inhibit_systemd()
        self._ping()
        self._timer.start()

    def stop(self):
        if not self.active:
            return
        self.active = False
        self._timer.stop()
        if self._fdo_cookie is not None:
            self._call(FDO, "UnInhibit", "u", (self._fdo_cookie,))
            self._fdo_cookie = None
        if self._gnome_cookie is not None:
            self._call(GNOME, "Uninhibit", "u", (self._gnome_cookie,))
            self._gnome_cookie = None
        if self._inhibit_proc is not None:
            self._inhibit_proc.terminate()
            self._inhibit_proc = None

    # D-Bus

    def _connection(self):
        if self._conn is None and open_dbus_connection is not None:
            try:
                self._conn = open_dbus_connection(bus="SESSION")
            except Exception:
                self._conn = None
        return self._conn

    def _call(self, target, method, signature="", args=()):
        """Chama um método no D-Bus; devolve o primeiro valor da resposta ou None se não existir."""
        conn = self._connection()
        if conn is None:
            return None
        path, name, interface = target
        try:
            msg = new_method_call(DBusAddress(path, bus_name=name, interface=interface), method, signature, args)
            body = unwrap_msg(conn.send_and_get_reply(msg, timeout=2))
            return body[0] if body else None
        except Exception:
            return None

    def _inhibit_systemd(self):
        exe = shutil.which("systemd-inhibit")
        if not exe:
            return
        try:
            self._inhibit_proc = subprocess.Popen(
                [exe, "--what=idle:sleep", "--who=Coruja", f"--why={REASON}", "--mode=block",
                 "sleep", "infinity"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            self._inhibit_proc = None

    # Atividade

    def _ping(self):
        self._call(FDO, "SimulateUserActivity")
        # No X11, uma tecla que não existe no teclado (F15) zera o tempo ocioso
        if os.environ.get("DISPLAY") and shutil.which("xdotool"):
            subprocess.Popen(["xdotool", "key", "--clearmodifiers", "F15"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
