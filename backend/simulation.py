from __future__ import annotations

import asyncio
import math
import random
from typing import Dict, Optional

from .behavior import BehaviorEngine
from .death import cause_of_death
from .reproduction import attempt_reproduction
from .specimen import Specimen
from .teleporter import Teleporter
from .world import World
from .genetics import Genetics
from .personality import Personality
from .names import random_name


class Simulation:
    def __init__(self) -> None:
        self.world = World()
        self.teleporter = Teleporter(self.world)
        self.behavior = BehaviorEngine()
        self.specimens: Dict[int, Specimen] = {}
        self.tick = 0
        self.elapsed_seconds = 0.0
        self.running = True
        self.next_id = 1
        self.simulation_number = 1
        self.death_markers = []
        for _ in range(42):
            self.spawn()

    @property
    def time_of_day(self) -> float:
        return (self.elapsed_seconds / 25) % 24

    @property
    def is_daytime(self) -> bool:
        return 6 <= self.time_of_day < 18

    def spawn(self) -> Specimen:
        home = self.world.apartments[self.next_id - 1] if self.next_id <= len(self.world.apartments) else None
        position = home or (random.uniform(30, 970), random.uniform(30, 970))
        specimen = Specimen.spawn(self.next_id, position, home=home)
        specimen.name = f"{random_name(specimen.gender)}"
        self.specimens[specimen.id] = specimen
        self.next_id += 1
        return specimen

    def add_specimen(self, values: dict) -> Specimen:
        gender = values.get("gender", "man") if values.get("gender") in ("man", "woman") else "man"
        wants_home = bool(values.get("housed", False))
        occupied = {specimen.home for specimen in self.specimens.values() if specimen.home}
        home = next((apartment for apartment in self.world.apartments if apartment not in occupied), None) if wants_home else None
        specimen = Specimen(self.next_id, gender, home is None, name=random_name(gender), position=home or (random.uniform(30, 970), random.uniform(30, 970)), home=home)
        personality_values = {trait: _trait_value(values.get(trait, 50)) for trait in Personality.__dataclass_fields__}
        genetics_values = {trait: _trait_value(values.get(trait, 50)) for trait in Genetics.__dataclass_fields__}
        specimen.personality = Personality(**personality_values)
        specimen.genetics = Genetics(**genetics_values)
        specimen.hunger = _needs_value(values.get("hunger", 20))
        specimen.fatigue = _needs_value(values.get("fatigue", 20))
        self.specimens[specimen.id] = specimen
        self.next_id += 1
        return specimen

    def reset_population(self) -> None:
        self.specimens.clear()
        self.next_id = 1
        self.simulation_number += 1
        self.elapsed_seconds = 0.0
        self.tick = 0
        self.death_markers.clear()
        for _ in range(42):
            self.spawn()

    def step(self, seconds: float = 0.1) -> None:
        if not self.running:
            return
        self.elapsed_seconds += seconds
        self.tick += 1
        self.world.update_pop_up(seconds)
        self.world.grow_plants(seconds)
        self.world.move_animals(seconds)
        self._resolve_deer_feeding()
        self._resolve_bear_behavior(seconds)
        self.teleporter.update(seconds)
        births = []
        for specimen in list(self.specimens.values()):
            specimen.age_hours += seconds / 25
            if specimen.age_hours >= 24:
                specimen.new_arrival = False
            specimen.hunger = min(100, specimen.hunger + seconds * .08)
            specimen.fatigue = min(100, specimen.fatigue + seconds * (.28 if self.is_daytime else .12))
            action = "sleep" if specimen.sleeping else self.behavior.choose(specimen, self)
            self.behavior.execute(specimen, action, self)
            specimen.points += self._action_points(specimen, action)
            self._resolve_forest_food(specimen)
            if self.teleporter.touch(specimen.position):
                specimen.position = self.teleporter.teleport()
                specimen.current_action = "teleported"
            if action == "reproduce" and not self.is_daytime:
                child = attempt_reproduction(specimen, self.specimens, self.next_id)
                if child:
                    births.append(child)
                    self.next_id += 1
            death = cause_of_death(specimen, self.is_daytime, self.world.zone_at(specimen.position) == "forest")
            if death:
                self._record_death(specimen.position, specimen.name, "human", death)
                specimen.alive = False
        for child in births:
            self.specimens[child.id] = child
        self.specimens = {key: value for key, value in self.specimens.items() if value.alive}

    def wake_specimen(self, specimen_id: int) -> bool:
        specimen = self.specimens.get(specimen_id)
        if not specimen or not specimen.sleeping:
            return False
        specimen.sleeping = False
        specimen.current_action = "waking"
        return True

    async def run(self) -> None:
        while True:
            self.step()
            await asyncio.sleep(.1)

    def packet(self) -> dict:
        specimens = [specimen.to_packet() for specimen in self.specimens.values()]
        leaderboard = sorted(specimens, key=lambda specimen: specimen["points"], reverse=True)[:5]
        return {"simulation_number": self.simulation_number, "tick": self.tick, "time_of_day": round(self.time_of_day, 2), "is_daytime": self.is_daytime, "specimens": specimens, "leaderboard": leaderboard, "behavior_analysis": [self._behavior_analysis(specimen) for specimen in sorted(self.specimens.values(), key=lambda item: item.points, reverse=True)[:5]], "death_markers": self.death_markers, "animals": [resource.to_packet() for resource in self.world.resources.values() if resource.kind == "animal"], "plants": [resource.to_packet() for resource in self.world.resources.values() if resource.kind == "plant"], "teleporter": {"x": round(self.teleporter.position[0], 1), "y": round(self.teleporter.position[1], 1)}, "zones": [{"name": zone.name, "x": zone.x, "y": zone.y, "width": zone.width, "height": zone.height} for zone in self.world.zones]}

    def _record_death(self, position, name: str, entity_type: str, cause: str) -> None:
        self.death_markers.append({"x": round(position[0], 1), "y": round(position[1], 1), "name": name, "entity_type": entity_type, "cause": cause, "tick": self.tick})
        self.death_markers = self.death_markers[-100:]

    def _action_points(self, specimen: Specimen, action: str) -> int:
        return {"hunting": 8, "gathering_plant": 4, "sold_at_cafe": 5, "bought_home": 10, "negotiated_home": 10, "reproduce": 12, "donate": 6, "sleep": 1}.get(action, 1)

    def donate_to_homeless(self, donor: Specimen) -> bool:
        if donor.is_homeless or donor.wallet < 10:
            return False
        recipients = [candidate for candidate in self.specimens.values() if candidate.is_homeless and candidate.id != donor.id and math.dist(candidate.position, donor.position) < 55]
        if not recipients:
            return False
        recipient = min(recipients, key=lambda candidate: math.dist(candidate.position, donor.position))
        amount = min(5.0, donor.wallet - 5.0)
        donor.wallet -= amount
        recipient.wallet += amount
        donor.points += 4
        recipient.points += 2
        donor.adjust_relationship(recipient.id, 6)
        recipient.adjust_relationship(donor.id, 8)
        donor.current_action = "donated"
        recipient.current_action = "received_help"
        return True

    def _behavior_analysis(self, specimen: Specimen) -> dict:
        if specimen.sleeping:
            reason = "sleeping to recover fatigue; click the specimen to wake it"
        elif specimen.hunger > 70:
            reason = "high hunger is shaping the next decision"
        elif specimen.is_homeless and self.is_daytime:
            reason = "seeking income, shelter, or a social connection"
        elif not self.is_daytime and specimen.home:
            reason = "night shelter priority is pulling this specimen home"
        elif not self.is_daytime and specimen.is_homeless:
            reason = "homeless night behavior is drawing this specimen toward the forest"
        else:
            reason = "balancing personality, relationships, resources, and risk"
        return {"id": specimen.id, "name": specimen.name, "action": specimen.current_action, "points": specimen.points, "reason": reason}

    def _resolve_forest_food(self, specimen: Specimen) -> None:
        if self.world.zone_at(specimen.position) != "forest":
            return
        nearby = sorted((resource for resource in self.world.resources.values() if resource.energy > 0), key=lambda resource: ((resource.position[0] - specimen.position[0]) ** 2 + (resource.position[1] - specimen.position[1]) ** 2))
        for resource in nearby:
            distance = ((resource.position[0] - specimen.position[0]) ** 2 + (resource.position[1] - specimen.position[1]) ** 2) ** 0.5
            if distance > 22:
                continue
            if resource.kind == "plant":
                specimen.plant_goods += 1
                specimen.hunger = max(0, specimen.hunger - min(24, resource.energy))
                resource.energy = max(0, resource.energy - 12)
                specimen.current_action = "ate_poisonous_plant" if resource.poisonous else "gathering_plant"
                if resource.poisonous:
                    specimen.alive = False
                return
            if resource.species == "deer" and specimen.genetics.speed >= 60 and specimen.fatigue <= 70:
                specimen.animal_goods += 1
                specimen.hunger = max(0, specimen.hunger - resource.energy)
                specimen.fatigue = min(100, specimen.fatigue + 10)
                self.world.resources.pop(resource.id, None)
                self._record_death(resource.position, "Deer", "animal", "hunted")
                specimen.current_action = "hunting"
                return

    def _resolve_bear_behavior(self, seconds: float) -> None:
        for bear in [resource for resource in self.world.resources.values() if resource.species == "bear"]:
            if bear.mad_remaining_hours > 0:
                bear.mad_remaining_hours = max(0.0, bear.mad_remaining_hours - seconds / 25)
            if bear.sleeping:
                continue
            nearby_resources = [resource for resource in self.world.resources.values() if resource.id != bear.id and resource.species != "bear" and resource.energy > 0 and math.dist(resource.position, bear.position) < 30]
            nearby_specimens = [specimen for specimen in self.specimens.values() if math.dist(specimen.position, bear.position) < 30]
            targets = [(resource.position, resource) for resource in nearby_resources]
            if bear.mad_remaining_hours > 0:
                targets.extend((specimen.position, specimen) for specimen in nearby_specimens)
            else:
                targets = [(position, resource) for position, resource in targets if resource.species == "deer" or resource.kind == "plant"]
            if not targets:
                continue
            _, target = min(targets, key=lambda item: math.dist(item[0], bear.position))
            if isinstance(target, Specimen):
                target.alive = False
                target.current_action = "attacked_by_bear"
            elif target.kind == "plant":
                was_poisonous = target.poisonous
                self.world.resources.pop(target.id, None)
                if was_poisonous and bear.mad_remaining_hours <= 0:
                    bear.mad_remaining_hours = 2.0
                bear.current_action = "bear_ate_poisonous_plant" if was_poisonous else "bear_eating_plant"
            else:
                self.world.resources.pop(target.id, None)
                bear.current_action = "bear_hunting_deer"

    def _resolve_deer_feeding(self) -> None:
        deer = [resource for resource in self.world.resources.values() if resource.species == "deer" and not resource.sleeping]
        for herbivore in deer:
            plants = [resource for resource in self.world.resources.values() if resource.kind == "plant" and resource.energy > 0 and math.dist(resource.position, herbivore.position) < 18]
            if not plants:
                continue
            plant = min(plants, key=lambda resource: math.dist(resource.position, herbivore.position))
            self.world.resources.pop(plant.id, None)
            if plant.poisonous:
                self.world.resources.pop(herbivore.id, None)
            else:
                herbivore.current_action = "deer_eating_plant"

    def sell_goods_at_cafe(self, specimen: Specimen) -> None:
        if specimen.is_homeless and (specimen.plant_goods or specimen.animal_goods):
            specimen.wallet += specimen.plant_goods * 5 + specimen.animal_goods * 12
            specimen.plant_goods = 0
            specimen.animal_goods = 0
            specimen.current_action = "sold_at_cafe"

    def buy_or_negotiate_home(self, specimen: Specimen) -> None:
        if not specimen.is_homeless or specimen.wallet < 60:
            return
        occupied = {candidate.home for candidate in self.specimens.values() if candidate.home}
        free_home = next((apartment for apartment in self.world.apartments if apartment not in occupied), None)
        if free_home:
            specimen.wallet -= 60
            specimen.home = free_home
            specimen.is_homeless = False
            specimen.current_action = "bought_home"
            return
        seller = next((candidate for candidate in self.specimens.values() if candidate.home and candidate.wallet <= 12 and candidate.id != specimen.id), None)
        if seller:
            specimen.wallet -= 60
            seller.wallet += 60
            specimen.home = seller.home
            specimen.is_homeless = False
            seller.home = None
            seller.is_homeless = True
            specimen.current_action = "negotiated_home"

    def build_forest_shelter(self, builder: Specimen) -> bool:
        if not builder.is_homeless or self.world.zone_at(builder.position) != "forest":
            return False
        team = [candidate for candidate in self.specimens.values() if candidate.is_homeless and math.dist(candidate.position, builder.position) < 70]
        if len(team) < 2 or sum(candidate.plant_goods + candidate.animal_goods for candidate in team) < 2:
            return False
        shelter_position = (sum(candidate.position[0] for candidate in team) / len(team), sum(candidate.position[1] for candidate in team) / len(team))
        for candidate in team:
            candidate.plant_goods = max(0, candidate.plant_goods - 1)
            candidate.home = shelter_position
            candidate.home_kind = "forest_shelter"
            candidate.is_homeless = False
            candidate.position = shelter_position
            candidate.points += 12
            candidate.current_action = "built_forest_shelter"
        return True


def _trait_value(value: object) -> int:
    try:
        return max(1, min(100, int(value)))
    except (TypeError, ValueError):
        return 50


def _needs_value(value: object) -> float:
    return float(_trait_value(value))
