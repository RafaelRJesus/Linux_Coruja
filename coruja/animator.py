"""Motor de animação: calcula cada quadro sem desenhar nada.

A view lê pose, deslocamento, inclinação, sol, ninho, objeto e partículas.
"""

import math
import random
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto

from .effects import Kind, Particle, Prop
from .owl import ASLEEP, Pose
from .settings import Settings, random_minute


class Activity(Enum):
    IDLE = auto()
    SLEEPING = auto()
    SUNRISE = auto()
    SUNSET = auto()
    DUSK = auto()
    WALKING = auto()
    PUPPY = auto()
    PETTED = auto()
    HOOT = auto()
    FLAP = auto()
    YAWN = auto()
    LOOK_AROUND = auto()
    HOP = auto()
    NEST = auto()
    COFFEE = auto()
    LUNCH = auto()
    SNACK = auto()
    PARTY = auto()


@dataclass
class Scheduled:
    key: str
    activity: Activity
    start: int              # minutos desde a meia-noite
    end: int
    weekday: int | None     # 0 = segunda ... 4 = sexta (None = todo dia)
    fire_at: int = 0


SCHEDULE = [
    Scheduled("cafe", Activity.COFFEE, 8 * 60 + 30, 10 * 60, None),
    Scheduled("almoco", Activity.LUNCH, 12 * 60, 13 * 60 + 30, None),
    Scheduled("lanche", Activity.SNACK, 15 * 60 + 30, 16 * 60 + 30, None),
    Scheduled("sextou", Activity.PARTY, 17 * 60, 18 * 60, 4),
]

DURATIONS = {
    Activity.SUNRISE: 4.5, Activity.SUNSET: 4.5, Activity.DUSK: 5,
    Activity.PUPPY: 4.5, Activity.PETTED: 1.8, Activity.HOOT: 2, Activity.FLAP: 1.4,
    Activity.YAWN: 2.6, Activity.LOOK_AROUND: 3, Activity.HOP: 1.2,
    Activity.COFFEE: 8, Activity.LUNCH: 9, Activity.SNACK: 8, Activity.PARTY: 6,
}


def clamp01(x):
    return max(0.0, min(1.0, x))


def smooth(a, b, x):
    """Sobe suave de 0 a 1 entre a e b."""
    t = clamp01((x - a) / (b - a))
    return t * t * (3 - 2 * t)


def bump(x, a, b):
    """Sobe e desce (0 -> 1 -> 0) entre a e b."""
    if x <= a or x >= b:
        return 0.0
    return math.sin((x - a) / (b - a) * math.pi)


class Animator:
    def __init__(self, settings: Settings):
        self.settings = settings

        # saída (lida pela view)
        self.pose = ASLEEP
        self.offset = (0.0, 0.0)
        self.tilt = 0.0
        self.squash = 1.0
        self.sun = None          # (posição, transparência) ou None
        self.sun_spin = 0.0
        self.nest = 1.0
        self.prop = None
        self.prop_phase = 0.0
        self.particles: list[Particle] = []
        self.activity = Activity.SLEEPING

        # entrada (preenchida pelo app)
        self.awake = False
        self.mouse_look = (0.0, 0.0)
        self.dragging = False
        self.move_window = None   # função(dx) -> bool (False = bateu na borda)
        self.can_walk = None      # função() -> bool

        # relógio interno
        self.time = 0.0
        self.started = 0.0
        self.duration = 0.0
        self.fired = set()
        self.next_blink = 2.0
        self.blink_end = 0.0
        self.next_random = 40.0
        self.next_attention = random.uniform(15 * 60, 30 * 60)
        self.last_random = None
        self.next_particle = 0.0
        self.last_cycle = -1
        self.walk_dir = 1

        # horários
        self.clock_check = 0.0
        self.evening = settings.is_evening()
        self.schedule: list[Scheduled] = []
        self.schedule_day = None

    # Quadros por segundo de que precisa agora. Parada = poucos quadros (leve).
    @property
    def desired_fps(self) -> int:
        if self.dragging:
            return 30
        if self.activity is Activity.IDLE:
            return 12 if not self.particles else 20
        if self.activity is Activity.SLEEPING:
            return 8
        if self.activity is Activity.NEST:
            return 10
        return 30

    # Comandos

    def wake(self):
        self.awake = True
        self.play(Activity.SUNRISE)

    def sleep(self):
        self.awake = False
        self.play(Activity.SUNSET)

    def pet(self):
        if self.awake:
            self.play(Activity.PETTED)
        else:
            self.spawn_heart()  # dormindo: só um coraçãozinho, sem acordar

    def play(self, activity: Activity, duration: float | None = None):
        self.activity = activity
        self.started = self.time
        self.fired.clear()
        self.last_cycle = -1
        if duration is not None:
            self.duration = duration
        elif activity is Activity.WALKING:
            self.duration = random.uniform(3, 8)
        elif activity is Activity.NEST:
            self.duration = random.uniform(60, 150)
        else:
            self.duration = DURATIONS.get(activity, 0)
        if activity is Activity.WALKING:
            self.walk_dir = random.choice((-1, 1))
            if self.can_walk and not self.can_walk():
                self.finish()

    def static_frame(self):
        """Quadro parado (animações desligadas)."""
        self.activity = Activity.IDLE if self.awake else Activity.SLEEPING
        self.pose = Pose(lid=0.3 if self.evening else 0) if self.awake else ASLEEP
        self.offset = (0.0, 0.0 if self.awake else -0.05)
        self.tilt, self.squash, self.sun, self.prop = 0.0, 1.0, None, None
        self.nest = 0.0 if self.awake else 1.0
        self.particles.clear()

    def finish(self):
        if self.awake:
            self.activity = Activity.IDLE
            self.next_random = self.time + random.uniform(20, 90)
        else:
            self.activity = Activity.SLEEPING
        self.started = self.time
        self.duration = 0

    # Quadro a quadro

    def update(self, dt: float):
        self.time += dt
        self.check_clock()
        if self.awake and self.activity is Activity.IDLE and self.time >= self.next_random:
            self.pick_random()

        t = self.time - self.started
        p = clamp01(t / self.duration) if self.duration > 0 else 0.0
        base_lid = 0.3 if self.evening else 0.0

        pose = Pose(lid=base_lid if self.awake else 1.0, look=self.mouse_look if self.awake else (0.0, 0.0))
        off_y = 0.0
        tilt = 0.0
        squash = 1 + 0.012 * math.sin(self.time * 2.0)   # respiração
        sun = None
        nest_target = 0.0 if self.awake else 1.0
        prop = None
        prop_phase = 0.0
        a = self.activity

        if a is Activity.SLEEPING:
            pose.lid = 1.0
            nest_target = 1.0
            off_y = -0.05
            squash = 1 + 0.025 * math.sin(self.time * 1.2)
            if self.every(1.7):
                self.spawn(Kind.ZZZ, 0.70, 0.82, 0.06, 0.10, 2.8, 0.10 + random.uniform(0, 0.04))

        elif a is Activity.SUNRISE:
            # o sol nasce e ela se espreguiça
            sun = (smooth(0, 0.7, p), 1 - smooth(0.8, 1, p))
            pose.lid = 1 - smooth(0.25, 0.6, p) * (1 - base_lid)
            stretch = bump(p, 0.35, 0.9)
            squash += 0.12 * stretch
            pose.wing = stretch
            pose.beak_open = 0.8 * bump(p, 0.4, 0.75)
            nest_target = 1 - smooth(0.6, 0.95, p)
            off_y = -0.05 * nest_target

        elif a is Activity.SUNSET:
            # o sol se põe, os olhos fecham e ela se aninha
            sun = (1 - smooth(0.1, 1, p), smooth(0, 0.15, p) * (1 - smooth(0.85, 1, p)))
            pose.lid = base_lid + (1 - base_lid) * smooth(0.3, 0.95, p)
            nest_target = smooth(0.45, 0.9, p)
            off_y = -0.05 * nest_target

        elif a is Activity.DUSK:
            # anoitecer com ela acordada: olhos um pouco mais baixos
            sun = (1 - smooth(0.1, 1, p), smooth(0, 0.15, p) * (1 - smooth(0.85, 1, p)))
            pose.lid = 0.3 * smooth(0.3, 1, p)

        elif a is Activity.WALKING:
            phase = self.time * 9
            tilt = 7 * math.sin(phase)
            off_y = 0.03 * abs(math.sin(phase))
            pose.step = math.sin(phase)
            pose.look = (self.walk_dir * 0.7, -0.1)
            if self.move_window and not self.move_window(self.walk_dir * 28 * dt):
                self.duration = t

        elif a is Activity.PUPPY:
            k = smooth(0, 0.12, p) * (1 - smooth(0.85, 1, p))
            pose.puppy = k
            pose.lid = 0.0
            pose.look = (0.0, 0.45 * k)
            tilt = 10 * k
            squash += 0.03 * k
            if p < 0.3:
                off_y = 0.07 * abs(math.sin(p / 0.3 * 2 * math.pi))
            if self.once("heart", p > 0.35):
                self.spawn_heart()
            if self.every(0.45) and k > 0.5:
                self.spawn_sparkle()

        elif a is Activity.PETTED:
            pose.happy = True
            off_y = 0.04 * abs(math.sin(p * 2 * math.pi))
            for i, at in enumerate((0.1, 0.4, 0.7)):
                if self.once(f"h{i}", p > at):
                    self.spawn_heart()

        elif a is Activity.HOOT:
            pose.beak_open = bump(p, 0.1, 0.5) + bump(p, 0.5, 0.9)
            squash += 0.05 * pose.beak_open
            for i, at in enumerate((0.2, 0.6)):
                if self.once(f"n{i}", p > at):
                    self.spawn(Kind.NOTE, 0.62, 0.55, 0.14, 0.18, 1.6, 0.15)

        elif a is Activity.FLAP:
            pose.wing = abs(math.sin(p * math.pi * 4)) * (1 - smooth(0.85, 1, p))
            off_y = 0.03 * pose.wing

        elif a is Activity.YAWN:
            b = bump(p, 0.1, 0.85)
            pose.beak_open = b
            pose.lid = max(base_lid, 0.75 * b)
            squash += 0.06 * b
            tilt = -4 * b

        elif a is Activity.LOOK_AROUND:
            pose.look = (0.9 * math.sin(p * 2 * math.pi), 0.2 * math.sin(p * 4 * math.pi))
            tilt = 6 * math.sin(p * 2 * math.pi)

        elif a is Activity.HOP:
            off_y = 0.08 * abs(math.sin(p * 2 * math.pi))
            squash -= 0.05 * bump(p, 0.45, 0.55) + 0.05 * bump(p, 0.9, 1)

        elif a is Activity.NEST:
            nest_target = 1 - smooth(0.95, 1, p)
            pose.lid = max(base_lid, 0.5)
            off_y = -0.05 * self.nest

        elif a is Activity.COFFEE:
            prop = Prop.MUG
            x, _ = self.cycle(2.5, t)
            prop_phase = bump(x, 0.3, 0.8)
            pose.lid = max(base_lid, 0.6 * prop_phase)   # fecha os olhos no gole
            if self.every(0.5):
                self.spawn(Kind.STEAM, 0.17 + random.uniform(-0.02, 0.02), 0.40 + prop_phase * 0.08,
                           0.01, 0.12, 1.2, 0.04)

        elif a is Activity.LUNCH:
            prop = Prop.BOWL
            x, new = self.cycle(0.8, t)
            peck = bump(x, 0, 1)
            off_y = -0.06 * peck
            pose.look = (0.0, -0.7)
            pose.beak_open = 0.5 if peck > 0.6 else 0.0
            if new and t > 0.5:
                self.spawn_crumbs(0.5, 0.14)
            if p > 0.9:
                pose.happy = True

        elif a is Activity.SNACK:
            prop = Prop.COOKIE
            prop_phase = p
            x, new = self.cycle(1.2, t)
            pose.beak_open = 0.6 * bump(x, 0.2, 0.6)
            pose.look = (0.7, -0.3)
            if new and t > 0.8:
                self.spawn_crumbs(0.80, 0.26)

        elif a is Activity.PARTY:
            prop = Prop.PARTY_HAT
            pose.happy = 0.2 < p < 0.8
            off_y = 0.06 * abs(math.sin(p * 4 * math.pi))
            pose.wing = 0.5 * abs(math.sin(p * 4 * math.pi))
            if self.every(0.12) and p < 0.8:
                self.spawn_confetti()

        # piscadas (às vezes duplas)
        if self.awake and not pose.happy and pose.lid < 0.9:
            if self.time >= self.next_blink:
                self.blink_end = self.time + 0.13
                double = random.random() < 0.15
                self.next_blink = self.time + (0.35 if double else random.uniform(2.5, 6.5))
            if self.time < self.blink_end:
                pose.lid = 1.0

        # sendo arrastada: bate as asas
        if self.dragging:
            pose.wing = max(pose.wing, 0.4 + 0.4 * abs(math.sin(self.time * 16)))

        if self.duration > 0 and t >= self.duration:
            self.finish()

        self.nest += (nest_target - self.nest) * min(1.0, dt * 4)
        self.sun_spin += dt * 0.4
        self.pose = pose
        self.offset = (0.0, off_y)
        self.tilt = tilt
        self.squash = squash
        self.sun = sun
        self.prop = prop
        self.prop_phase = prop_phase
        self.update_particles(dt)

    # Escolha aleatória (imprevisível, sem repetir a última)

    def pick_random(self):
        s = self.settings
        if s.get("attention_on") and self.time >= self.next_attention:
            self.next_attention = self.time + random.uniform(20 * 60, 45 * 60)
            self.play(Activity.PUPPY)
            return
        options = [
            (Activity.LOOK_AROUND, 3), (Activity.HOOT, 2), (Activity.FLAP, 2), (Activity.HOP, 1.5),
            (Activity.NEST, 1), (Activity.YAWN, 2 if self.evening else 0.3),
        ]
        if s.get("walking_on") and self.can_walk and self.can_walk():
            options.append((Activity.WALKING, 2.5))
        options = [o for o in options if o[0] is not self.last_random]
        choice = random.choices([o[0] for o in options], weights=[o[1] for o in options])[0]
        self.last_random = choice
        self.play(choice)

    # Horários (conferidos a cada 20 s, não a cada quadro)

    def check_clock(self):
        if self.time < self.clock_check:
            return
        self.clock_check = self.time + 20
        now = datetime.now()

        if now.date() != self.schedule_day:
            self.schedule_day = now.date()
            self.schedule = []
            for item in SCHEDULE:
                if item.weekday is None or item.weekday == now.weekday():
                    self.schedule.append(Scheduled(item.key, item.activity, item.start, item.end, item.weekday,
                                                   random_minute(item.start, item.end)))

        s = self.settings
        ev = s.is_evening(now)
        if ev != self.evening:
            self.evening = ev
            if s.get("schedule_on") and self.awake and self.activity in (Activity.IDLE, Activity.NEST):
                self.play(Activity.DUSK if ev else Activity.SUNRISE)

        if not (s.get("schedule_on") and self.awake and self.activity is Activity.IDLE):
            return
        m = s.minutes_now(now)
        for item in self.schedule:
            if item.fire_at <= m <= item.end and not s.played_today(item.key):
                s.mark_played_today(item.key)
                self.play(item.activity)
                return

    # Utilitários de tempo

    def once(self, key, cond) -> bool:
        """Verdadeiro uma única vez por animação, quando a condição vira verdadeira."""
        if cond and key not in self.fired:
            self.fired.add(key)
            return True
        return False

    def every(self, interval) -> bool:
        """Verdadeiro a cada `interval` segundos."""
        if self.time >= self.next_particle:
            self.next_particle = self.time + interval
            return True
        return False

    def cycle(self, period, t):
        """Posição (0..1) dentro de um ciclo e se um ciclo novo acabou de começar."""
        n = int(t / period)
        new = n != self.last_cycle
        self.last_cycle = n
        return (t % period) / period, new

    # Partículas

    def spawn(self, kind, x, y, vx, vy, life, size, hue=0.0):
        if len(self.particles) < 40:   # limite para ficar leve
            self.particles.append(Particle(kind, x, y, vx, vy, life, size, hue=hue))

    def spawn_heart(self):
        self.spawn(Kind.HEART, random.uniform(0.35, 0.65), 0.92, random.uniform(-0.05, 0.05), 0.22, 1.6, 0.12)

    def spawn_sparkle(self):
        x = random.uniform(0.15, 0.30) if random.random() < 0.5 else random.uniform(0.70, 0.85)
        self.spawn(Kind.SPARKLE, x, random.uniform(0.55, 0.85), 0, 0.03, 0.7, 0.08)

    def spawn_crumbs(self, x, y):
        for _ in range(3):
            self.spawn(Kind.CRUMB, x, y, random.uniform(-0.15, 0.15), random.uniform(0.05, 0.15), 0.6, 0.025)

    def spawn_confetti(self):
        self.spawn(Kind.CONFETTI, random.uniform(0.1, 0.9), 1.1, random.uniform(-0.08, 0.08), -0.35, 1.8, 0.04,
                   hue=random.random())

    def update_particles(self, dt):
        if not self.particles:
            return
        for pt in self.particles:
            pt.x += pt.vx * dt
            pt.y += pt.vy * dt
            pt.age += dt
            if pt.kind is Kind.CRUMB:
                pt.vy -= 0.6 * dt   # migalha cai
        self.particles = [pt for pt in self.particles if pt.age < pt.life]
