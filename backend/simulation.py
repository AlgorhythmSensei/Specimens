from __future__ import annotations

import asyncio
import math
import random
from typing import Dict, Optional

from .behavior import BehaviorEngine
from .death import cause_of_death
from .reproduction import attempt_copulation, attempt_birth
from .specimen import Specimen
from .teleporter import Teleporter
from .world import World, ForestResource
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
        self.time_scale: float = 1.0
        self.death_markers = []
        self.weather: str = "clear"
        self._weather_remaining: float = 0.0
        self.reclamation_active: bool = False
        self.game_over: bool = False
        for _ in range(42):
            self.spawn(new_arrival=False)

    @property
    def time_of_day(self) -> float:
        return (self.elapsed_seconds / 25) % 24

    @property
    def is_daytime(self) -> bool:
        return 6 <= self.time_of_day < 18

    @property
    def day_of_week(self) -> int:
        return int(self.elapsed_seconds / (25 * 24)) % 7

    def spawn(self, new_arrival: bool = True) -> Specimen:
        home = self.world.apartments[self.next_id - 1] if self.next_id <= len(self.world.apartments) else None
        position = home or (random.uniform(30, 970), random.uniform(30, 970))
        specimen = Specimen.spawn(self.next_id, position, home=home)
        specimen.name = f"{random_name(specimen.gender)}"
        specimen.max_age_hours = random.uniform(120, 300)
        specimen.new_arrival = new_arrival
        _assign_job(specimen)
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
        specimen.max_age_hours = random.uniform(120, 300)
        _assign_job(specimen)
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
        self.world.resources.clear()
        self.world.forest_shelters.clear()
        self.world._forest_expansion = 0.0
        self.world.zones = list(self.world._fixed_zones)
        self.reclamation_active = False
        self.game_over = False
        self.world._seed_forest_resources()
        for _ in range(42):
            self.spawn(new_arrival=False)

    def _update_weather(self, seconds: float) -> None:
        self._weather_remaining -= seconds / 25
        if self._weather_remaining <= 0:
            weights = [45, 30, 15, 10]
            states = ["clear", "rain", "drought", "storm"]
            total = sum(weights)
            r = random.uniform(0, total)
            cumulative = 0.0
            for state, weight in zip(states, weights):
                cumulative += weight
                if r <= cumulative:
                    self.weather = state
                    break
            durations = {"clear": (4, 8), "rain": (1, 3), "drought": (2, 4), "storm": (0.5, 1.5)}
            lo, hi = durations.get(self.weather, (2, 6))
            self._weather_remaining = random.uniform(lo, hi)

    def step(self, seconds: float = 0.1) -> None:
        if not self.running or self.game_over:
            return
        self.elapsed_seconds += seconds
        self.tick += 1
        self._update_weather(seconds)
        self.world.update_pop_up(seconds)
        self.world.grow_plants(seconds, self.weather, reclaiming=self.reclamation_active)
        self.world.move_animals(seconds)
        for resource in list(self.world.resources.values()):
            if resource.kind == "animal":
                resource.age_hours += seconds / 25
                if resource.age_hours >= resource.max_age_hours:
                    self._record_death(resource.position, resource.species.capitalize(), "animal", "old_age")
                    self.world.resources.pop(resource.id, None)
        self._resolve_deer_feeding()
        self._resolve_deer_reproduction()
        self._resolve_deer_behavior()
        self._resolve_bear_behavior(seconds)
        self._replenish_wildlife()
        self.teleporter.update(seconds)
        births = []
        for specimen in list(self.specimens.values()):
            specimen.age_hours += seconds / 25
            if specimen.age_hours >= 2:
                specimen.new_arrival = False
            if specimen.age_hours >= 48 and not specimen.has_job and specimen.max_age_hours > 0:
                _assign_job(specimen)
            zone = self.world.zone_at(specimen.position)
            sheltered = zone in ("homes", "cafe", "bar", "church", "work") or self.world.in_shelter(specimen.position)
            hunger_rate = 0.08
            fatigue_rate = 0.28 if self.is_daytime else 0.12
            if self.weather == "storm":
                if not sheltered:
                    hunger_rate *= 1.6
                    fatigue_rate *= 1.8
                    if specimen.is_homeless:
                        hunger_rate *= 1.4
                        fatigue_rate *= 1.5
            elif self.weather == "rain":
                if not sheltered:
                    hunger_rate *= 1.2
                    fatigue_rate *= 1.3
            elif self.weather == "drought":
                hunger_rate *= 1.35
            specimen.hunger = min(100, specimen.hunger + seconds * hunger_rate)
            specimen.fatigue = min(100, specimen.fatigue + seconds * fatigue_rate)
            specimen.is_running = False
            if specimen.run_remaining_hours < 1.0:
                specimen.run_remaining_hours = min(1.0, specimen.run_remaining_hours + seconds / 25 * 0.25)
            if specimen.intoxicated_hours_remaining > 0:
                specimen.intoxicated_hours_remaining = max(0.0, specimen.intoxicated_hours_remaining - seconds / 25)
            action = "sleep" if specimen.sleeping else self.behavior.choose(specimen, self)
            self.behavior.execute(specimen, action, self)
            specimen.points += self._action_points(specimen, action)
            self._resolve_forest_food(specimen)
            if not specimen.alive:
                continue
            sucked = self.teleporter.suck(specimen.position)
            if sucked:
                specimen.position = self.world.clamp(sucked)
            if self.teleporter.touch(specimen.position):
                specimen.position = self.teleporter.teleport()
                specimen.current_action = "teleported"
            if specimen.pregnant:
                specimen.pregnancy_hours_remaining = max(0.0, specimen.pregnancy_hours_remaining - seconds / 25)
                specimen.current_action = "pregnant"
                child = attempt_birth(specimen, self.specimens, self.next_id)
                if child:
                    births.append(child)
                    self.next_id += 1
            elif action == "reproduce" and not self.is_daytime:
                attempt_copulation(specimen, self.specimens)
            death = cause_of_death(specimen, self.is_daytime, self.world.zone_at(specimen.position) == "forest")
            if death:
                self._record_death(specimen.position, specimen.name, "human", death, specimen.current_action)
                specimen.alive = False
        for child in births:
            self.specimens[child.id] = child
        self.specimens = {key: value for key, value in self.specimens.items() if value.alive}
        self._resolve_homeless_group_behavior(seconds)
        self._resolve_reclamation(seconds)

    def wake_specimen(self, specimen_id: int) -> bool:
        specimen = self.specimens.get(specimen_id)
        if not specimen or not specimen.sleeping:
            return False
        specimen.sleeping = False
        specimen.current_action = "waking"
        return True

    async def run(self) -> None:
        while True:
            try:
                self.step(0.1 * self.time_scale)
            except Exception as exc:
                print(f"[simulation] step error: {exc}")
            await asyncio.sleep(.1)

    def packet(self) -> dict:
        specimens = [specimen.to_packet() for specimen in self.specimens.values()]
        leaderboard = sorted(specimens, key=lambda specimen: specimen["points"], reverse=True)[:5]
        fight_locations = [{"x": round(s.position[0], 1), "y": round(s.position[1], 1)} for s in self.specimens.values() if s.current_action in ("fighting", "being_attacked", "retaliating")]
        return {"simulation_number": self.simulation_number, "tick": self.tick, "time_scale": self.time_scale, "time_of_day": round(self.time_of_day, 2), "is_daytime": self.is_daytime, "weather": self.weather, "day_number": int(self.elapsed_seconds / (25 * 24)) + 1, "specimens": specimens, "leaderboard": leaderboard, "behavior_analysis": [self._behavior_analysis(specimen) for specimen in sorted(self.specimens.values(), key=lambda item: item.points, reverse=True)[:5]], "death_markers": self.death_markers, "animals": [resource.to_packet() for resource in self.world.resources.values() if resource.kind == "animal"], "plants": [resource.to_packet() for resource in self.world.resources.values() if resource.kind == "plant"], "teleporter": {"x": round(self.teleporter.position[0], 1), "y": round(self.teleporter.position[1], 1), "grow_phase": round(self.teleporter.grow_phase, 3)}, "event_active": self.world.pop_up_active, "event_topic": self.world.pop_up_topic, "fight_locations": fight_locations, "reclamation_active": self.reclamation_active, "forest_coverage": round(self.world.forest_coverage, 3), "game_over": self.game_over, "zones": [{"name": zone.name, "x": zone.x, "y": zone.y, "width": zone.width, "height": zone.height} for zone in self.world.zones + self.world.forest_shelters]}

    def _record_death(self, position, name: str, entity_type: str, cause: str, action: str = "unknown") -> None:
        self.death_markers.append({"x": round(position[0], 1), "y": round(position[1], 1), "name": name, "entity_type": entity_type, "cause": cause, "action": action, "tick": self.tick})
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
                    self._record_death(specimen.position, specimen.name, "human", "poisonous_plant", specimen.current_action)
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
        forest = next(zone for zone in self.world.zones if zone.name == "forest")
        for bear in [resource for resource in self.world.resources.values() if resource.species == "bear"]:
            if bear.mad_remaining_hours > 0:
                bear.mad_remaining_hours = max(0.0, bear.mad_remaining_hours - seconds / 25)
                if bear.mad_remaining_hours <= 0:
                    bear.mad_target_id = -1
            # Circle walk after mad attack
            if bear.circle_remaining_hours > 0:
                bear.circle_remaining_hours = max(0.0, bear.circle_remaining_hours - seconds / 25)
                bear.circle_angle += seconds / 25 * 2 * math.pi
                radius = 35.0
                nx = bear.circle_center[0] + radius * math.cos(bear.circle_angle)
                ny = bear.circle_center[1] + radius * math.sin(bear.circle_angle)
                bear.position = (max(forest.x + 5, min(forest.x + forest.width - 5, nx)), max(forest.y + 5, min(forest.y + forest.height - 5, ny)))
                bear.chasing = False
                bear.current_action = "bear_circling"
                continue
            if bear.wander_remaining_hours > 0:
                bear.wander_remaining_hours = max(0.0, bear.wander_remaining_hours - seconds / 25)
                bear.current_action = "bear_wandering"
                bear.chasing = False
                continue
            if bear.sleeping:
                bear.chasing = False
                continue
            if not bear.chasing and bear.mad_remaining_hours <= 0 and random.random() < seconds * 0.0007:
                bear.wander_remaining_hours = random.uniform(1.0, 2.0)
                bear.current_action = "bear_wandering"
                continue
            chase_range = 120
            attack_range = 30
            _bear_max_run = 10 / 60
            _bear_run_threshold = _bear_max_run * 0.10
            # Mad phase: lock onto one specific human target only, roam outside forest
            if bear.mad_remaining_hours > 0:
                if bear.mad_target_id == -1:
                    # Pick nearest human not inside any building zone
                    candidates = [s for s in self.specimens.values()
                                  if self.world.zone_at(s.position) not in ("homes", "cafe", "bar", "church", "work")
                                  and not self.world.in_shelter(s.position)]
                    if candidates:
                        bear.mad_target_id = min(candidates, key=lambda s: math.dist(s.position, bear.position)).id
                mad_target = self.specimens.get(bear.mad_target_id)
                target_safe = mad_target and (self.world.zone_at(mad_target.position) in ("homes", "cafe", "bar", "church", "work") or self.world.in_shelter(mad_target.position))
                if mad_target and mad_target.alive and not target_safe:
                    distance = math.dist(mad_target.position, bear.position)
                    if distance > attack_range:
                        dx, dy = mad_target.position[0] - bear.position[0], mad_target.position[1] - bear.position[1]
                        run_speed = random.uniform(35, 40)
                        nx = bear.position[0] + dx / distance * run_speed
                        ny = bear.position[1] + dy / distance * run_speed
                        # Mad bears can go anywhere on the map
                        bear.position = (max(5, min(self.world.width - 5, nx)), max(5, min(self.world.height - 5, ny)))
                        bear.chasing = True
                        bear.current_action = "bear_mad_chasing"
                    else:
                        mad_target.current_action = "attacked_by_mad_bear"
                        self._record_death(mad_target.position, mad_target.name, "human", "mad_bear_attack", "bear_mad_attack")
                        mad_target.alive = False
                        bear.energy = bear.max_energy
                        bear.last_fed_hours = bear.age_hours
                        bear.mad_remaining_hours = 0.0
                        bear.mad_target_id = -1
                        bear.chasing = False
                        bear.circle_remaining_hours = 1.0
                        bear.circle_center = bear.position
                        bear.circle_angle = random.uniform(0, 2 * math.pi)
                        bear.current_action = "bear_circling"
                else:
                    # Target went into safety — pick a new one or give up
                    bear.mad_target_id = -1
                    new_candidates = [s for s in self.specimens.values()
                                      if self.world.zone_at(s.position) not in ("homes", "cafe", "bar", "church", "work")
                                      and not self.world.in_shelter(s.position)]
                    if new_candidates:
                        bear.mad_target_id = min(new_candidates, key=lambda s: math.dist(s.position, bear.position)).id
                    else:
                        bear.mad_remaining_hours = 0.0
                        bear.chasing = False
                continue
            # Normal hunting logic — bears only hunt when >50% hungry (energy < 50% of max)
            bear_hungry = bear.energy < bear.max_energy * 0.5
            nearby_resources = [resource for resource in self.world.resources.values() if resource.id != bear.id and resource.species != "bear" and resource.energy > 0 and math.dist(resource.position, bear.position) < chase_range]
            targets = [(position, resource) for position, resource in [(r.position, r) for r in nearby_resources] if resource.species == "deer" or resource.kind == "plant"]
            fed_recently = (bear.age_hours - bear.last_fed_hours) < 8
            if fed_recently or not bear_hungry:
                targets = [(pos, t) for pos, t in targets if t.kind == "plant"]
            if not targets:
                bear.chasing = False
                continue
            target_pos, target = min(targets, key=lambda item: math.dist(item[0], bear.position))
            distance = math.dist(target_pos, bear.position)
            if distance > attack_range:
                if bear.run_remaining_hours > _bear_run_threshold:
                    dx, dy = target_pos[0] - bear.position[0], target_pos[1] - bear.position[1]
                    run_speed = random.uniform(35, 40)
                    nx = bear.position[0] + dx / distance * run_speed
                    ny = bear.position[1] + dy / distance * run_speed
                    bear.position = (max(forest.x + 5, min(forest.x + forest.width - 5, nx)), max(forest.y + 5, min(forest.y + forest.height - 5, ny)))
                    bear.run_remaining_hours = max(0.0, bear.run_remaining_hours - seconds / 25)
                    bear.chasing = True
                    bear.current_action = "bear_chasing"
                else:
                    bear.run_remaining_hours = min(_bear_max_run, bear.run_remaining_hours + seconds / 25 * 0.5)
                    bear.chasing = False
                    bear.current_action = "bear_roaming"
                continue
            bear.chasing = False
            if target.kind == "plant":
                was_poisonous = target.poisonous
                gained = target.energy if not was_poisonous else 0
                self.world.resources.pop(target.id, None)
                if was_poisonous:
                    bear.mad_remaining_hours = 0.5
                    candidates = [s for s in self.specimens.values() if not self.world.in_shelter(s.position)]
                    if candidates:
                        bear.mad_target_id = min(candidates, key=lambda s: math.dist(s.position, bear.position)).id
                    bear.current_action = "bear_ate_poisonous_plant"
                else:
                    bear.energy = min(bear.max_energy, bear.energy + gained)
                    bear.current_action = "bear_eating_plant"
                    if bear.energy >= bear.max_energy:
                        bear.sleeping = True
                        bear.sleep_remaining = 4.0 * 25
                        bear.current_action = "bear_resting_full"
            else:
                self.world.resources.pop(target.id, None)
                bear.energy = bear.max_energy
                bear.last_fed_hours = bear.age_hours
                bear.sleeping = True
                bear.sleep_remaining = 4.0 * 25
                bear.current_action = "bear_resting_full"

    def _resolve_homeless_group_behavior(self, seconds: float) -> None:
        homeless = [s for s in self.specimens.values() if s.is_homeless and s.alive]
        if not homeless:
            return
        # Group sleep: homeless within 40 units of each other rest together at night
        if not self.is_daytime:
            for specimen in homeless:
                if specimen.sleeping:
                    continue
                nearby_homeless = [o for o in homeless if o.id != specimen.id and math.dist(o.position, specimen.position) < 40]
                if len(nearby_homeless) >= 2 and specimen.fatigue > 30:
                    specimen.sleeping = True
                    specimen.sleep_remaining = random.uniform(60, 120)
                    specimen.current_action = "group_sleeping"
        # Team bear fight: 5+ homeless grouped within 60 units attack a nearby bear
        if len(homeless) < 5:
            return
        bears = [r for r in self.world.resources.values() if r.species == "bear" and not r.sleeping]
        for bear in bears:
            group = [s for s in homeless if not s.sleeping and math.dist(s.position, bear.position) < 60]
            if len(group) < 5:
                continue
            damage_per_member = 4.0 * seconds
            bear.energy = max(0, bear.energy - damage_per_member * len(group))
            for member in group:
                member.current_action = "fighting_bear"
                member.fatigue = min(100, member.fatigue + seconds * 0.5)
            if bear.energy <= 0:
                self._record_death(bear.position, "Bear", "animal", "killed_by_group", "group_fight")
                self.world.resources.pop(bear.id, None)
                for member in group:
                    member.hunger = max(0, member.hunger - 40)
                    member.run_remaining_hours = min(1.0, member.run_remaining_hours + 0.3)
                    member.animal_goods += 2
                    member.points += 20
                    member.current_action = "killed_bear"
                break

    def _resolve_reclamation(self, seconds: float) -> None:
        if self.specimens:
            self.reclamation_active = False
            return
        self.reclamation_active = True
        # 10% of map area per simulated day = 100 units wide per sim-day (height is 1000)
        # 1 sim-day = 25 * 24 real seconds → rate = 100 / (25 * 24) units/real-second
        units_per_second = 100.0 / (25 * 24)
        self.world.expand_forest(units_per_second * seconds)
        if self.world.forest_coverage >= 1.0:
            self.game_over = True

    def _replenish_wildlife(self) -> None:
        forest = next(zone for zone in self.world.zones if zone.name == "forest")
        deer_count = sum(1 for r in self.world.resources.values() if r.species == "deer")
        bear_count = sum(1 for r in self.world.resources.values() if r.species == "bear")
        if deer_count == 0:
            for _ in range(random.randint(5, 10)):
                aid = self._next_animal_id()
                pos = (random.uniform(forest.x + 8, forest.x + forest.width - 8), random.uniform(forest.y + 8, forest.y + forest.height - 8))
                self.world.resources[aid] = ForestResource(aid, "animal", pos, 28, species="deer")
        if bear_count < 2:
            for _ in range(2 - bear_count):
                aid = self._next_animal_id()
                pos = (random.uniform(forest.x + 12, forest.x + forest.width - 12), random.uniform(forest.y + 12, forest.y + forest.height - 12))
                self.world.resources[aid] = ForestResource(aid, "animal", pos, 60, species="bear")

    def _resolve_deer_reproduction(self) -> None:
        deer_list = [r for r in self.world.resources.values() if r.species == "deer" and not r.sleeping]
        if len(deer_list) >= 30:
            return
        for deer in deer_list:
            nearby = [r for r in self.world.resources.values() if r.id != deer.id and r.species == "deer" and math.dist(r.position, deer.position) < 25]
            if nearby and random.random() < 0.0004:
                fawn_id = self._next_animal_id()
                position = (deer.position[0] + random.uniform(-10, 10), deer.position[1] + random.uniform(-10, 10))
                forest = next(zone for zone in self.world.zones if zone.name == "forest")
                position = (max(forest.x + 5, min(forest.x + forest.width - 5, position[0])), max(forest.y + 5, min(forest.y + forest.height - 5, position[1])))
                self.world.resources[fawn_id] = ForestResource(fawn_id, "animal", position, 28, species="deer")
                deer.current_action = "deer_mating"

    def _next_animal_id(self) -> int:
        next_id = max(self.world.resources.keys(), default=0) + 1
        return next_id

    def _resolve_deer_behavior(self) -> None:
        forest = next(zone for zone in self.world.zones if zone.name == "forest")
        bears = [r for r in self.world.resources.values() if r.species == "bear" and not r.sleeping]
        all_deer = [r for r in self.world.resources.values() if r.species == "deer"]
        for deer in [r for r in all_deer if not r.sleeping]:
            drought_multiplier = 1.5 if self.weather == "drought" else 1.0
            deer.energy = max(0, deer.energy - 0.002 * drought_multiplier)
            if deer.energy <= 0:
                self._record_death(deer.position, "Deer", "animal", "starvation")
                self.world.resources.pop(deer.id, None)
                continue
            if bears:
                nearest_bear = min(bears, key=lambda b: math.dist(b.position, deer.position))
                if math.dist(nearest_bear.position, deer.position) <= 100:
                    dx, dy = deer.position[0] - nearest_bear.position[0], deer.position[1] - nearest_bear.position[1]
                    dist = math.hypot(dx, dy) or 1
                    nx = deer.position[0] + dx / dist * random.uniform(35, 45)
                    ny = deer.position[1] + dy / dist * random.uniform(35, 45)
                    deer.position = (max(forest.x + 5, min(forest.x + forest.width - 5, nx)), max(forest.y + 5, min(forest.y + forest.height - 5, ny)))
                    deer.chasing = True
                    deer.current_action = "deer_fleeing_bear"
                    continue
            nearby_humans = [s for s in self.specimens.values() if math.dist(s.position, deer.position) < 70]
            if nearby_humans:
                nearest_human = min(nearby_humans, key=lambda s: math.dist(s.position, deer.position))
                dx, dy = deer.position[0] - nearest_human.position[0], deer.position[1] - nearest_human.position[1]
                dist = math.hypot(dx, dy) or 1
                nx = deer.position[0] + dx / dist * random.uniform(6, 12)
                ny = deer.position[1] + dy / dist * random.uniform(6, 12)
                deer.position = (max(forest.x + 5, min(forest.x + forest.width - 5, nx)), max(forest.y + 5, min(forest.y + forest.height - 5, ny)))
                deer.chasing = True
                deer.current_action = "deer_avoiding_human"
                continue
            nearby_plants = [r for r in self.world.resources.values() if r.kind == "plant" and r.energy > 0 and math.dist(r.position, deer.position) < 120]
            pack = [d for d in all_deer if d.id != deer.id and math.dist(d.position, deer.position) < 180]
            if deer.energy < deer.max_energy * 0.5 and nearby_plants:
                deer.chasing = False
                target_plant = min(nearby_plants, key=lambda p: math.dist(p.position, deer.position))
                dx, dy = target_plant.position[0] - deer.position[0], target_plant.position[1] - deer.position[1]
                dist = math.hypot(dx, dy) or 1
                nx = deer.position[0] + dx / dist * 6
                ny = deer.position[1] + dy / dist * 6
                deer.position = (max(forest.x + 5, min(forest.x + forest.width - 5, nx)), max(forest.y + 5, min(forest.y + forest.height - 5, ny)))
                deer.current_action = "deer_grazing"
            elif pack:
                deer.chasing = False
                cx = sum(d.position[0] for d in pack) / len(pack)
                cy = sum(d.position[1] for d in pack) / len(pack)
                dx, dy = cx - deer.position[0], cy - deer.position[1]
                dist = math.hypot(dx, dy) or 1
                if dist > 30:
                    nx = deer.position[0] + dx / dist * 4
                    ny = deer.position[1] + dy / dist * 4
                    deer.position = (max(forest.x + 5, min(forest.x + forest.width - 5, nx)), max(forest.y + 5, min(forest.y + forest.height - 5, ny)))
                    deer.current_action = "deer_with_pack"
            else:
                deer.chasing = False

    def _resolve_deer_feeding(self) -> None:
        deer = [resource for resource in self.world.resources.values() if resource.species == "deer" and not resource.sleeping]
        for herbivore in deer:
            plants = [resource for resource in self.world.resources.values() if resource.kind == "plant" and resource.energy > 0 and math.dist(resource.position, herbivore.position) < 18]
            if not plants:
                continue
            safe = [p for p in plants if not p.poisonous]
            candidates = safe if safe else plants
            if not safe and random.random() > 0.05:
                continue
            plant = min(candidates, key=lambda resource: math.dist(resource.position, herbivore.position))
            self.world.resources.pop(plant.id, None)
            if plant.poisonous:
                self._record_death(herbivore.position, "Deer", "animal", "poisonous_plant", "deer_eating_plant")
                self.world.resources.pop(herbivore.id, None)
            else:
                herbivore.energy = min(herbivore.max_energy, herbivore.energy + plant.energy)
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
        shelter_zone = self.world.add_forest_shelter(shelter_position)
        shelter_center = (shelter_zone.x + shelter_zone.width / 2, shelter_zone.y + shelter_zone.height / 2)
        for candidate in team:
            candidate.plant_goods = max(0, candidate.plant_goods - 1)
            candidate.home = shelter_center
            candidate.home_kind = "forest_shelter"
            candidate.is_homeless = False
            candidate.position = shelter_center
            candidate.points += 12
            candidate.current_action = "built_forest_shelter"
        return True


def _assign_job(specimen) -> None:
    if random.random() < 0.9:
        specimen.has_job = True
        specimen.salary = round(random.uniform(0.024, 0.056), 4)
        specimen.work_start = round(random.uniform(8, 9), 1)
        specimen.work_end = round(random.uniform(16, 18), 1)


def _trait_value(value: object) -> int:
    try:
        return max(1, min(100, int(value)))
    except (TypeError, ValueError):
        return 50


def _needs_value(value: object) -> float:
    return float(_trait_value(value))
