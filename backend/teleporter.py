from __future__ import annotations

import random
from typing import Tuple

from .world import World


class Teleporter:
    def __init__(self, world: World) -> None:
        self.world = world
        self.position = (world.width / 2, world.height / 2)

    def update(self, seconds: float) -> None:
        if random.random() < seconds / 18:
            self.position = (random.uniform(20, self.world.width - 20), random.uniform(20, self.world.height - 20))

    def touch(self, position: Tuple[float, float]) -> bool:
        dx = position[0] - self.position[0]
        dy = position[1] - self.position[1]
        return dx * dx + dy * dy < 18 * 18

    def teleport(self) -> Tuple[float, float]:
        return random.uniform(20, self.world.width - 20), random.uniform(20, self.world.height - 20)
