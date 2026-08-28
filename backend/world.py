from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple
import math
import random


@dataclass(frozen=True)
class Zone:
    name: str
    x: float
    y: float
    width: float
    height: float

    def contains(self, position: Tuple[float, float]) -> bool:
        return self.x <= position[0] <= self.x + self.width and self.y <= position[1] <= self.y + self.height


class ForestResource:
    def __init__(self, resource_id: int, kind: str, position: Tuple[float, float], energy: float, poisonous: bool = False, species: str = "deer") -> None:
        self.id = resource_id
        self.kind = kind
        self.position = position
        self.energy = energy
        self.max_energy = energy
        self.poisonous = poisonous
        self.species = species if kind == "animal" else "plant"
        self.mad_remaining_hours = 0.0
        self.sleeping = False
        self.sleep_remaining = 0.0
        angle = random.uniform(0, 6.28318)
        speed = random.uniform(5.0, 9.0)
        self.velocity = (random.uniform(0.7, 1.3) * speed * math.cos(angle), random.uniform(0.7, 1.3) * speed * math.sin(angle))

    def to_packet(self) -> dict:
        return {"id": self.id, "kind": self.kind, "species": self.species, "x": round(self.position[0], 1), "y": round(self.position[1], 1), "energy": round(self.energy, 1), "poisonous": self.poisonous, "sleeping": self.sleeping, "mad": self.mad_remaining_hours > 0}


class World:
    width = 1000.0
    height = 1000.0

    def __init__(self) -> None:
        self.apartments = [(180 + column * 105, 700 + row * 65) for row in range(4) for column in range(5)]
        self.pop_up = Zone("pop_up", 520, 360, 230, 90)
        self.pop_up_elapsed = 0.0
        self.resources: Dict[int, ForestResource] = {}
        self.zones = [
            Zone("cafe", 90, 110, 180, 130),
            Zone("bar", 330, 90, 170, 115),
            Zone("church", 80, 380, 190, 155),
            Zone("forest", 750, 0, 250, 1000),
            Zone("homes", 120, 650, 500, 240),
            self.pop_up,
        ]
        self._seed_forest_resources()

    def update_pop_up(self, seconds: float) -> None:
        self.pop_up_elapsed += seconds
        if self.pop_up_elapsed >= 90:
            self.pop_up_elapsed = 0.0
            self.pop_up = Zone("pop_up", 250 + (self.pop_up.x * 1.7) % 500, 280 + (self.pop_up.y * 1.3) % 400, 230, 90)
            self.zones[-1] = self.pop_up

    def _seed_forest_resources(self) -> None:
        forest = next(zone for zone in self.zones if zone.name == "forest")
        resource_id = 1
        for _ in range(14):
            position = (random.uniform(forest.x + 8, forest.x + forest.width - 8), random.uniform(forest.y + 8, forest.y + forest.height - 8))
            self.resources[resource_id] = ForestResource(resource_id, "animal", position, 28, species="deer")
            resource_id += 1
        for _ in range(4):
            position = (random.uniform(forest.x + 12, forest.x + forest.width - 12), random.uniform(forest.y + 12, forest.y + forest.height - 12))
            self.resources[resource_id] = ForestResource(resource_id, "animal", position, 60, species="bear")
            resource_id += 1
        for _ in range(34):
            position = (random.uniform(forest.x + 5, forest.x + forest.width - 5), random.uniform(forest.y + 5, forest.y + forest.height - 5))
            self.resources[resource_id] = ForestResource(resource_id, "plant", position, 18, poisonous=random.random() < 0.2)
            resource_id += 1

    def grow_plants(self, seconds: float) -> None:
        for resource in self.resources.values():
            if resource.kind == "plant":
                resource.energy = min(resource.max_energy, resource.energy + seconds * 0.8)

    def move_animals(self, seconds: float = 0.1) -> None:
        forest = next(zone for zone in self.zones if zone.name == "forest")
        for animal in self.resources.values():
            if animal.kind == "animal":
                if animal.sleeping:
                    animal.sleep_remaining -= seconds
                    if animal.sleep_remaining <= 0:
                        animal.sleeping = False
                    continue
                if random.random() < 0.0008:
                    animal.sleeping = True
                    animal.sleep_remaining = random.uniform(1.5, 3.0)
                    continue
                next_x = animal.position[0] + animal.velocity[0] * seconds * 10
                next_y = animal.position[1] + animal.velocity[1] * seconds * 10
                if next_x <= forest.x + 5 or next_x >= forest.x + forest.width - 5:
                    animal.velocity = (-animal.velocity[0], animal.velocity[1])
                if next_y <= forest.y + 5 or next_y >= forest.y + forest.height - 5:
                    animal.velocity = (animal.velocity[0], -animal.velocity[1])
                animal.position = (max(forest.x + 5, min(forest.x + forest.width - 5, next_x)), max(forest.y + 5, min(forest.y + forest.height - 5, next_y)))

    def zone_at(self, position: Tuple[float, float]) -> str:
        for zone in self.zones:
            if zone.contains(position):
                return zone.name
        return "open"

    def clamp(self, position: Tuple[float, float]) -> Tuple[float, float]:
        return max(0, min(self.width, position[0])), max(0, min(self.height, position[1]))
