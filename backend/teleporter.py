from __future__ import annotations

import random
from typing import Tuple

from .world import World


class Teleporter:
    GROW_DURATION = 3.0

    def __init__(self, world: World) -> None:
        self.world = world
        self.position = (world.width / 2, world.height / 2)
        self._grow_remaining: float = 0.0

    def update(self, seconds: float) -> None:
        if self._grow_remaining > 0:
            self._grow_remaining = max(0.0, self._grow_remaining - seconds)
            if self._grow_remaining <= 0.0:
                self.position = (random.uniform(20, self.world.width - 20), random.uniform(20, self.world.height - 20))
            return
        if random.random() < seconds / 18:
            self._grow_remaining = self.GROW_DURATION

    @property
    def grow_phase(self) -> float:
        return max(0.0, 1.0 - self._grow_remaining / self.GROW_DURATION) if self._grow_remaining > 0 else 0.0

    SUCTION_RADIUS = 90.0
    TELEPORT_RADIUS = 18.0

    def touch(self, position: Tuple[float, float]) -> bool:
        dx = position[0] - self.position[0]
        dy = position[1] - self.position[1]
        return dx * dx + dy * dy < self.TELEPORT_RADIUS ** 2

    def suck(self, position: Tuple[float, float]) -> Tuple[float, float] | None:
        dx = self.position[0] - position[0]
        dy = self.position[1] - position[1]
        dist = (dx * dx + dy * dy) ** 0.5
        if dist >= self.SUCTION_RADIUS or dist < 0.01:
            return None
        strength = (1 - dist / self.SUCTION_RADIUS) ** 2 * 6.0
        return (position[0] + dx / dist * strength, position[1] + dy / dist * strength)

    def teleport(self) -> Tuple[float, float]:
        return random.uniform(20, self.world.width - 20), random.uniform(20, self.world.height - 20)
