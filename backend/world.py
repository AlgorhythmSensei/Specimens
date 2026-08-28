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
        self.growth_rate = random.uniform(0.3, 1.5) if kind == "plant" else 0.0
        self.mad_remaining_hours = 0.0
        self.sleeping = False
        self.sleep_remaining = 0.0
        self.chasing = False
        self.age_hours = 0.0
        self.last_fed_hours: float = -8.0
        self.run_remaining_hours: float = 10 / 60
        self.wander_remaining_hours: float = 0.0
        if kind == "animal":
            if species == "bear":
                self.max_age_hours = random.uniform(72, 180)
            else:
                self.max_age_hours = random.uniform(36, 96)
        else:
            self.max_age_hours = float("inf")
        angle = random.uniform(0, 6.28318)
        speed = random.uniform(5.0, 9.0)
        self.velocity = (random.uniform(0.7, 1.3) * speed * math.cos(angle), random.uniform(0.7, 1.3) * speed * math.sin(angle))

    def to_packet(self) -> dict:
        return {"id": self.id, "kind": self.kind, "species": self.species, "x": round(self.position[0], 1), "y": round(self.position[1], 1), "energy": round(self.energy, 1), "poisonous": self.poisonous, "sleeping": self.sleeping, "mad": self.mad_remaining_hours > 0, "new_arrival": self.age_hours < 1}


class World:
    width = 1000.0
    height = 1000.0

    def __init__(self) -> None:
        self.apartments = [(160 + column * 105, 650 + row * 70) for row in range(4) for column in range(5)]
        self.resources: Dict[int, ForestResource] = {}
        self._next_resource_id = 1
        self.forest_shelters: list = []
        self._fixed_zones = [
            Zone("cafe", 90, 110, 180, 130),
            Zone("bar", 330, 90, 170, 115),
            Zone("work", 510, 270, 180, 120),
            Zone("church", 80, 380, 190, 155),
            Zone("forest", 750, 0, 250, 1000),
            Zone("homes", 100, 590, 600, 320),
        ]
        self.zones: list = list(self._fixed_zones)
        self.pop_up: Zone = Zone("pop_up", 350, 540, 200, 80)
        self.pop_up_active: bool = False
        self.pop_up_topic: str = ""
        self.pop_up_trait: str = "curiosity"
        self._world_elapsed: float = 0.0
        self._pop_up_day: int = -1
        self._pop_up_start_hour: float = 10.0
        self._seed_forest_resources()

    def update_pop_up(self, seconds: float) -> None:
        self._world_elapsed += seconds
        day = int(self._world_elapsed / (25 * 24))
        time_of_day = (self._world_elapsed / 25) % 24
        if day != self._pop_up_day:
            self._pop_up_day = day
            self._pop_up_start_hour = random.uniform(8, 16)
            self._schedule_event()
        was_active = self.pop_up_active
        self.pop_up_active = self._pop_up_start_hour <= time_of_day < self._pop_up_start_hour + 6
        if self.pop_up_active and not was_active:
            self.zones.append(self.pop_up)
        elif not self.pop_up_active and was_active:
            self.zones = [z for z in self.zones if z.name != "pop_up"]

    def _overlaps_fixed(self, x: float, y: float, w: float, h: float, margin: float = 25) -> bool:
        for zone in self._fixed_zones:
            if (x - margin < zone.x + zone.width and x + w + margin > zone.x and
                    y - margin < zone.y + zone.height and y + h + margin > zone.y):
                return True
        return False

    def _schedule_event(self) -> None:
        ew, eh = 200, 80
        position = (350.0, 540.0)
        for _ in range(50):
            cx = random.uniform(30, 710)
            cy = random.uniform(30, 890)
            if not self._overlaps_fixed(cx, cy, ew, eh):
                position = (cx, cy)
                break
        self.pop_up = Zone("pop_up", position[0], position[1], ew, eh)
        if self.pop_up_active:
            self.zones = [z for z in self.zones if z.name != "pop_up"]
            self.zones.append(self.pop_up)
        cx, cy = position[0] + ew / 2, position[1] + eh / 2
        nearest = min(
            [z for z in self._fixed_zones if z.name != "forest"],
            key=lambda z: math.dist((z.x + z.width / 2, z.y + z.height / 2), (cx, cy)),
        )
        near_dist = math.dist((nearest.x + nearest.width / 2, nearest.y + nearest.height / 2), (cx, cy))
        zone_key = nearest.name if near_dist < 280 else "open"
        topics = _EVENT_TOPICS.get(zone_key, _EVENT_TOPICS["open"])
        choice = random.choice(topics)
        self.pop_up_topic, self.pop_up_trait = choice

    def _seed_forest_resources(self) -> None:
        forest = next(zone for zone in self.zones if zone.name == "forest")
        self._next_resource_id = 1
        for _ in range(14):
            position = (random.uniform(forest.x + 8, forest.x + forest.width - 8), random.uniform(forest.y + 8, forest.y + forest.height - 8))
            self.resources[self._next_resource_id] = ForestResource(self._next_resource_id, "animal", position, 28, species="deer")
            self._next_resource_id += 1
        for _ in range(4):
            position = (random.uniform(forest.x + 12, forest.x + forest.width - 12), random.uniform(forest.y + 12, forest.y + forest.height - 12))
            self.resources[self._next_resource_id] = ForestResource(self._next_resource_id, "animal", position, 60, species="bear")
            self._next_resource_id += 1
        for _ in range(34):
            position = (random.uniform(forest.x + 5, forest.x + forest.width - 5), random.uniform(forest.y + 5, forest.y + forest.height - 5))
            self.resources[self._next_resource_id] = ForestResource(self._next_resource_id, "plant", position, 18, poisonous=random.random() < 0.2)
            self._next_resource_id += 1

    def grow_plants(self, seconds: float, weather: str = "clear") -> None:
        weather_multipliers = {"clear": 1.0, "rain": 1.4, "drought": 0.5, "storm": 1.8}
        spawn_multipliers = {"clear": 1.0, "rain": 1.4, "drought": 0.5, "storm": 1.8}
        growth_multiplier = weather_multipliers.get(weather, 1.0)
        spawn_multiplier = spawn_multipliers.get(weather, 1.0)
        forest = next(zone for zone in self.zones if zone.name == "forest")
        for resource in self.resources.values():
            if resource.kind == "plant":
                resource.energy = min(resource.max_energy, resource.energy + seconds * resource.growth_rate * growth_multiplier)
        plant_count = sum(1 for r in self.resources.values() if r.kind == "plant")
        if plant_count < 60 and random.random() < seconds * 0.12 * spawn_multiplier:
            position = (random.uniform(forest.x + 5, forest.x + forest.width - 5), random.uniform(forest.y + 5, forest.y + forest.height - 5))
            self.resources[self._next_resource_id] = ForestResource(self._next_resource_id, "plant", position, 18, poisonous=random.random() < 0.2)
            self._next_resource_id += 1

    def move_animals(self, seconds: float = 0.1) -> None:
        forest = next(zone for zone in self.zones if zone.name == "forest")
        for animal in self.resources.values():
            if animal.kind == "animal":
                if animal.sleeping:
                    animal.sleep_remaining -= seconds
                    if animal.sleep_remaining <= 0:
                        animal.sleeping = False
                    continue
                if animal.chasing:
                    continue
                if random.random() < 0.0008:
                    animal.sleeping = True
                    animal.sleep_remaining = random.uniform(1.5, 3.0)
                    continue
                next_x = animal.position[0] + animal.velocity[0] * seconds * 10
                next_y = animal.position[1] + animal.velocity[1] * seconds * 10
                if getattr(animal, "wander_remaining_hours", 0.0) > 0:
                    if next_x <= 5 or next_x >= self.width - 5:
                        animal.velocity = (-animal.velocity[0], animal.velocity[1])
                    if next_y <= 5 or next_y >= self.height - 5:
                        animal.velocity = (animal.velocity[0], -animal.velocity[1])
                    animal.position = (max(5.0, min(self.width - 5, next_x)), max(5.0, min(self.height - 5, next_y)))
                else:
                    if next_x <= forest.x + 5 or next_x >= forest.x + forest.width - 5:
                        animal.velocity = (-animal.velocity[0], animal.velocity[1])
                    if next_y <= forest.y + 5 or next_y >= forest.y + forest.height - 5:
                        animal.velocity = (animal.velocity[0], -animal.velocity[1])
                    animal.position = (max(forest.x + 5, min(forest.x + forest.width - 5, next_x)), max(forest.y + 5, min(forest.y + forest.height - 5, next_y)))

    def add_forest_shelter(self, position: Tuple[float, float]) -> Zone:
        x = max(755, min(position[0] - 30, 965))
        y = max(5, min(position[1] - 25, 945))
        shelter = Zone("forest_shelter", x, y, 60, 50)
        self.forest_shelters.append(shelter)
        return shelter

    def in_shelter(self, position: Tuple[float, float]) -> bool:
        return any(shelter.contains(position) for shelter in self.forest_shelters)

    def zone_at(self, position: Tuple[float, float]) -> str:
        for zone in self.zones:
            if zone.contains(position):
                return zone.name
        return "open"

    def clamp(self, position: Tuple[float, float]) -> Tuple[float, float]:
        return max(0, min(self.width, position[0])), max(0, min(self.height, position[1]))


_EVENT_TOPICS: dict = {
    "cafe": [
        ("Farmers market: local produce, handmade goods, and easy conversation.", "friendliness"),
        ("Poetry slam: open verse and instant applause.", "curiosity"),
        ("Food swap: bring a dish, leave with a recipe.", "friendliness"),
    ],
    "bar": [
        ("Jazz night: live music and late-night dancing.", "friendliness"),
        ("Open mic: anyone can take the stage tonight.", "curiosity"),
        ("Vinyl exchange: bring a record, leave with one.", "curiosity"),
        ("Comedy night: sharp jokes and a loose crowd.", "friendliness"),
    ],
    "church": [
        ("Candlelight vigil: a quiet gathering for reflection.", "morality"),
        ("Community prayer walk: solidarity and shared kindness.", "morality"),
        ("Meditation circle: silent sitting, shared presence.", "morality"),
        ("Charity auction: donate what you have, bid on what you need.", "morality"),
    ],
    "work": [
        ("Career fair: networking and new opportunities.", "discipline"),
        ("Startup showcase: pitches and bold ideas.", "curiosity"),
        ("Skills workshop: hands-on learning for professionals.", "discipline"),
        ("Mentorship circle: experience trading experience.", "loyalty"),
    ],
    "homes": [
        ("Block party: neighbours gathering for food and music.", "loyalty"),
        ("Garden swap: seeds, cuttings, and gardening advice.", "friendliness"),
        ("Neighbourhood cleanup: community pride in action.", "loyalty"),
        ("Street game tournament: classic games, fresh rivalries.", "friendliness"),
    ],
    "open": [
        ("Astronomy club: looking for strange stars and good company.", "curiosity"),
        ("Lantern festival: paper lanterns released into the night sky.", "friendliness"),
        ("Outdoor cinema: classic films on an improvised screen.", "curiosity"),
        ("Foragers walk: edible plants, wild herbs, and forest lore.", "curiosity"),
        ("Drumming circle: rhythm, noise, and community trance.", "friendliness"),
    ],
}
