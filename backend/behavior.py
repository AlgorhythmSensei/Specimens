from __future__ import annotations

from typing import TYPE_CHECKING, Dict
import math
import random

if TYPE_CHECKING:
    from .simulation import Simulation
    from .specimen import Specimen


class BehaviorEngine:
    actions = ("eat", "sleep", "donate", "socialize", "attend_church", "attend_event", "work", "explore", "gather", "hunt", "chase_deer", "build_shelter", "sell_goods", "buy_home", "return_home", "sell_home", "move_in", "reproduce", "conflict", "flee", "flee_human", "wander", "theft")

    def choose(self, specimen: "Specimen", simulation: "Simulation") -> str:
        zone = simulation.world.zone_at(specimen.position)
        utilities: Dict[str, float] = {
            "eat": specimen.hunger * 1.8 + (35 if zone == "cafe" else 0),
            "donate": self._donation_utility(specimen, simulation),
            "gather": 32 if zone == "forest" else 0,
            "hunt": specimen.genetics.speed * .45 if zone == "forest" and specimen.genetics.speed >= 60 and specimen.fatigue <= 70 else 0,
            "chase_deer": self._chase_deer_utility(specimen, simulation),
            "build_shelter": self._shelter_utility(specimen, simulation),
            "sell_goods": (specimen.plant_goods * 5 + specimen.animal_goods * 12) if zone == "cafe" else 0,
            "buy_home": 80 if specimen.is_homeless and zone == "cafe" and specimen.wallet >= 60 else 0,
            "sleep": specimen.fatigue * 1.5 + (30 if zone == "homes" else 0),
            "return_home": (specimen.fatigue + specimen.hunger * .2) if specimen.home else 0,
            "sell_home": specimen.personality.risk_taking * .12 if specimen.home and specimen.wallet < 8 else 0,
            "move_in": 35 if specimen.is_homeless else 0,
            "flee": self._flee_utility(specimen, simulation),
            "explore": specimen.personality.curiosity * .7 + (25 if zone == "forest" else 0),
            "attend_event": self._attend_event_utility(specimen, simulation),
            "work": self._work_utility(specimen, simulation),
            "socialize": specimen.personality.friendliness * .7,
            "attend_church": self._sunday_church_utility(specimen, simulation),
            "reproduce": self._reproduction_utility(specimen, simulation),
            "conflict": specimen.personality.aggression * .55 - specimen.personality.fearfulness * .25,
            "flee_human": self._flee_human_utility(specimen, simulation),
            "wander": 15.0,
            "theft": self._theft_utility(specimen, simulation),
        }
        if specimen.hunger > 90:
            utilities["eat"] += 100
        if zone == "forest" and specimen.hunger > 35:
            utilities["gather"] += 45
            utilities["hunt"] += 30
        if simulation.is_daytime:
            utilities["sleep"] *= .3
        else:
            utilities["explore"] *= .25
        if not simulation.is_daytime:
            if specimen.is_homeless:
                utilities["explore"] *= 0.2
                utilities["return_home"] += 90
                utilities["sleep"] += 40
            elif specimen.home:
                utilities["return_home"] += 120
        if specimen.is_homeless and simulation.is_daytime:
            utilities["move_in"] += specimen.personality.loyalty * .3
        tod = simulation.time_of_day
        if tod >= 22 or tod < 6:
            utilities["sleep"] += 60 + max(0, tod - 22) * 15 if tod >= 22 else 80
            utilities["return_home"] += 40
            utilities["explore"] *= 0.1
            utilities["work"] = 0
            utilities["attend_event"] = 0
        if specimen.fatigue > 85:
            utilities["sleep"] += 50
        if specimen.pregnant:
            utilities["return_home"] += 55
            utilities["explore"] *= 0.3
            utilities["hunt"] = 0
            utilities["conflict"] = 0
        if simulation.weather in ("rain", "storm"):
            utilities["return_home"] += 35
            utilities["sleep"] += 15
            utilities["explore"] *= 0.4
            utilities["attend_event"] = 0
        if simulation.weather == "drought":
            utilities["eat"] += 25
            utilities["gather"] += 20
        return max(utilities, key=utilities.get)

    def execute(self, specimen: "Specimen", action: str, simulation: "Simulation") -> None:
        specimen.current_action = action
        weather_speed = 0.65 if simulation.weather in ("rain", "storm") else 1.0
        if action == "eat" and simulation.world.zone_at(specimen.position) == "cafe" and specimen.wallet >= 2:
            specimen.wallet -= 2
            specimen.hunger = max(0, specimen.hunger - 35)
        elif action == "eat":
            cafe = next(zone for zone in simulation.world.zones if zone.name == "cafe")
            self._move_toward(specimen, (cafe.x + cafe.width / 2, cafe.y + cafe.height / 2), simulation, 5.0 * weather_speed)
        elif action == "donate":
            simulation.donate_to_homeless(specimen)
            specimen.reputation = min(100, specimen.reputation + 2)
        elif action == "gather":
            self._move_toward_forest_resource(specimen, simulation, "plant", 4.0 * weather_speed)
        elif action == "hunt":
            self._move_toward_forest_resource(specimen, simulation, "animal", 5.5 * weather_speed)
        elif action == "build_shelter":
            simulation.build_forest_shelter(specimen)
        elif action == "sell_goods" and simulation.world.zone_at(specimen.position) == "cafe":
            simulation.sell_goods_at_cafe(specimen)
        elif action == "buy_home" and simulation.world.zone_at(specimen.position) == "cafe":
            simulation.buy_or_negotiate_home(specimen)
        elif action == "sleep":
            specimen.sleeping = True
            specimen.fatigue = max(0, specimen.fatigue - 18)
        elif action == "return_home":
            if specimen.home:
                self._move_toward(specimen, specimen.home, simulation, 2.4 * weather_speed)
            elif specimen.is_homeless:
                target = self._nearest_building_point(specimen, simulation)
                if target:
                    self._move_toward(specimen, target, simulation, 2.0 * weather_speed)
                    specimen.current_action = "seeking_shelter"
        elif action == "sell_home" and specimen.home:
            specimen.wallet += 25
            specimen.home = None
            specimen.is_homeless = True
        elif action == "move_in" and specimen.is_homeless:
            nearby_housed = [candidate for candidate in simulation.specimens.values() if candidate.home and math.dist(candidate.position, specimen.position) < 100]
            preferred_housed = [candidate for candidate in nearby_housed if candidate.reputation > 40]
            nearby_housed = preferred_housed if preferred_housed else nearby_housed
            if nearby_housed:
                host = max(nearby_housed, key=lambda candidate: specimen.relationship_with(candidate.id))
                specimen.home = host.home
                specimen.is_homeless = False
                self._move_toward(specimen, host.position, simulation, 5.0 * weather_speed)
        elif action == "work":
            work_zone = next(zone for zone in simulation.world.zones if zone.name == "work")
            self._move_toward(specimen, (work_zone.x + work_zone.width / 2, work_zone.y + work_zone.height / 2), simulation, 4.5 * weather_speed)
            if simulation.world.zone_at(specimen.position) == "work":
                specimen.wallet += specimen.salary
                specimen.points += 1
                specimen.reputation = min(100, specimen.reputation + 0.02)
        elif action == "attend_church":
            church = next(zone for zone in simulation.world.zones if zone.name == "church")
            self._move_toward(specimen, (church.x + church.width / 2, church.y + church.height / 2), simulation, 5.0 * weather_speed)
            self._interact(specimen, simulation)
        elif action == "attend_event":
            pop_up = next((zone for zone in simulation.world.zones if zone.name == "pop_up"), None)
            if pop_up and simulation.world.pop_up_active:
                self._move_toward(specimen, (pop_up.x + pop_up.width / 2, pop_up.y + pop_up.height / 2), simulation, 4.5 * weather_speed)
                self._interact(specimen, simulation)
        elif action == "chase_deer":
            deer_list = [r for r in simulation.world.resources.values() if r.species == "deer" and not r.sleeping]
            if deer_list:
                target = min(deer_list, key=lambda d: math.dist(d.position, specimen.position))
                self._move_toward(specimen, target.position, simulation, 6.5 * weather_speed)
                if math.dist(specimen.position, target.position) < 20:
                    specimen.animal_goods += 1
                    specimen.hunger = max(0, specimen.hunger - target.energy)
                    specimen.fatigue = min(100, specimen.fatigue + 12)
                    simulation.world.resources.pop(target.id, None)
                    simulation._record_death(target.position, "Deer", "animal", "caught_by_human", "chase_deer")
                    specimen.current_action = "caught_deer"
                    specimen.points += 8
        elif action == "flee":
            bears = [r for r in simulation.world.resources.values() if r.species == "bear" and not r.sleeping]
            if bears:
                nearest = min(bears, key=lambda b: math.dist(b.position, specimen.position))
                dx, dy = specimen.position[0] - nearest.position[0], specimen.position[1] - nearest.position[1]
                dist = math.hypot(dx, dy) or 1
                can_run = specimen.run_remaining_hours > 0
                flee_speed = (8.5 if can_run else 4.5) * specimen.genetics.speed / 50
                specimen.is_running = can_run
                if can_run:
                    specimen.run_remaining_hours = max(0.0, specimen.run_remaining_hours - 0.004)
                specimen.position = simulation.world.clamp((specimen.position[0] + dx / dist * flee_speed, specimen.position[1] + dy / dist * flee_speed))
        elif action == "flee_human":
            aggressors = self._nearby_aggressors(specimen, simulation)
            if aggressors:
                nearest = min(aggressors, key=lambda a: math.dist(a.position, specimen.position))
                dx, dy = specimen.position[0] - nearest.position[0], specimen.position[1] - nearest.position[1]
                dist = math.hypot(dx, dy) or 1
                can_run = specimen.run_remaining_hours > 0
                flee_speed = (7.5 if can_run else 3.5) * specimen.genetics.speed / 50
                specimen.is_running = can_run
                if can_run:
                    specimen.run_remaining_hours = max(0.0, specimen.run_remaining_hours - 0.003)
                specimen.position = simulation.world.clamp((specimen.position[0] + dx / dist * flee_speed, specimen.position[1] + dy / dist * flee_speed))
                specimen.current_action = "fleeing_human"
        elif action == "explore":
            destination = next(zone for zone in simulation.world.zones if zone.name == "forest")
            self._move_toward(specimen, (destination.x + destination.width / 2, destination.y + destination.height / 2), simulation, 5.0 * weather_speed)
        elif action == "reproduce":
            self._interact(specimen, simulation)
        elif action == "conflict":
            self._execute_conflict(specimen, simulation, weather_speed)
        elif action == "socialize":
            venues = [zone for zone in simulation.world.zones if zone.name in ("bar", "church", "pop_up")]
            if venues:
                preferred = max(venues, key=lambda venue: specimen.personality.friendliness if venue.name == "bar" else specimen.personality.morality if venue.name == "church" else specimen.personality.curiosity)
                self._move_toward(specimen, (preferred.x + preferred.width / 2, preferred.y + preferred.height / 2), simulation, 4.0 * weather_speed)
            if simulation.world.zone_at(specimen.position) == "bar":
                specimen.intoxicated_hours_remaining = min(3.0, specimen.intoxicated_hours_remaining + 0.04)
            self._interact(specimen, simulation)
        elif action == "theft":
            targets = [c for c in simulation.specimens.values()
                       if c.id != specimen.id and c.wallet > 15
                       and math.dist(c.position, specimen.position) < 50]
            if targets:
                target = min(targets, key=lambda c: math.dist(c.position, specimen.position))
                witnesses = [c for c in simulation.specimens.values()
                             if c.id not in (specimen.id, target.id)
                             and math.dist(c.position, specimen.position) < 80]
                witness_eyesight = sum(c.genetics.eyesight for c in witnesses) / max(1, len(witnesses)) if witnesses else 0
                caught = random.random() < (witness_eyesight / 150) if witnesses else False
                amount = random.uniform(5, 12)
                specimen.wallet += amount
                target.wallet -= amount
                specimen.reputation = max(0, specimen.reputation - (12 if caught else 4))
                target.reputation = min(100, target.reputation + 2)
                specimen.current_action = "caught_stealing" if caught else "theft"
                specimen.points -= 5 if caught else 0
        else:
            specimen.position = simulation.world.clamp((specimen.position[0] + random.uniform(-8, 8), specimen.position[1] + random.uniform(-8, 8)))

    def _execute_conflict(self, specimen: "Specimen", simulation: "Simulation", weather_speed: float) -> None:
        targets = [c for c in simulation.specimens.values()
                   if c.id != specimen.id
                   and math.dist(c.position, specimen.position) < 120
                   and specimen.relationship_with(c.id) < 20]
        if not targets:
            targets = [c for c in simulation.specimens.values()
                       if c.id != specimen.id
                       and math.dist(c.position, specimen.position) < 80]
        if not targets:
            return
        target = min(targets, key=lambda c: math.dist(c.position, specimen.position))
        dist = math.dist(specimen.position, target.position)
        if dist > 18:
            can_run = specimen.run_remaining_hours > 0
            chase_speed = (7.0 if can_run else 3.5) * weather_speed
            specimen.is_running = can_run
            if can_run:
                specimen.run_remaining_hours = max(0.0, specimen.run_remaining_hours - 0.004)
            self._move_toward(specimen, target.position, simulation, chase_speed)
            specimen.current_action = "pursuing"
            return
        both_aggressive = specimen.personality.aggression > 55 and target.personality.aggression > 55
        damage = max(1.0, specimen.genetics.attack - target.genetics.defense * 0.4) / (3.0 if both_aggressive else 6.0)
        target.hunger = min(100, target.hunger + damage)
        specimen.fatigue = min(100, specimen.fatigue + 3)
        specimen.adjust_relationship(target.id, -8)
        target.adjust_relationship(specimen.id, -6)
        specimen.reputation = max(0, specimen.reputation - 4)
        specimen.current_action = "fighting"
        target.current_action = "being_attacked"
        if target.hunger >= 100:
            target.alive = False
            simulation._record_death(target.position, target.name, "human", "killed_in_fight", "conflict")
            specimen.reputation = max(0, specimen.reputation - 15)
            specimen.points -= 10
        elif both_aggressive and random.random() < 0.08:
            retaliating_damage = max(1.0, target.genetics.attack - specimen.genetics.defense * 0.4) / 3.0
            specimen.hunger = min(100, specimen.hunger + retaliating_damage)
            target.current_action = "retaliating"

    def _nearby_aggressors(self, specimen: "Specimen", simulation: "Simulation") -> list:
        detection = 55 + specimen.genetics.eyesight * 0.4
        return [c for c in simulation.specimens.values()
                if c.id != specimen.id
                and c.personality.aggression > 65
                and math.dist(c.position, specimen.position) < detection
                and specimen.relationship_with(c.id) < 30]

    def _move_toward(self, specimen: "Specimen", target, simulation: "Simulation", speed: float) -> None:
        dx, dy = target[0] - specimen.position[0], target[1] - specimen.position[1]
        distance = math.hypot(dx, dy) or 1
        nx = specimen.position[0] + dx / distance * speed * specimen.genetics.speed / 50
        ny = specimen.position[1] + dy / distance * speed * specimen.genetics.speed / 50
        if specimen.intoxicated_hours_remaining > 0:
            zigzag = math.sin(specimen.age_hours * 120) * 7
            nx += -dy / distance * zigzag
            ny += dx / distance * zigzag
        specimen.position = simulation.world.clamp((nx, ny))

    def _nearest_building_point(self, specimen: "Specimen", simulation: "Simulation"):
        candidates = [z for z in simulation.world.zones if z.name not in ("forest", "pop_up", "forest_shelter")]
        if not candidates:
            return None
        zone = min(candidates, key=lambda z: math.dist((z.x + z.width / 2, z.y + z.height / 2), specimen.position))
        cx, cy = zone.x + zone.width / 2, zone.y + zone.height / 2
        dx, dy = specimen.position[0] - cx, specimen.position[1] - cy
        dist = math.hypot(dx, dy) or 1
        return (cx + dx / dist * (max(zone.width, zone.height) / 2 + 12), cy + dy / dist * (max(zone.width, zone.height) / 2 + 12))

    def _move_toward_forest_resource(self, specimen: "Specimen", simulation: "Simulation", kind: str, speed: float) -> None:
        resources = [resource for resource in simulation.world.resources.values() if resource.kind == kind and resource.energy > 0]
        if resources:
            target = min(resources, key=lambda resource: math.dist(resource.position, specimen.position))
            self._move_toward(specimen, target.position, simulation, speed)

    def _interact(self, specimen: "Specimen", simulation: "Simulation") -> None:
        nearby = [candidate for candidate in simulation.specimens.values() if candidate.id != specimen.id and math.dist(candidate.position, specimen.position) < 45]
        if not nearby:
            return
        other = random.choice(nearby)
        gain = 2 + specimen.personality.friendliness / 30
        if other.reputation < 25:
            gain *= 0.5
        specimen.adjust_relationship(other.id, gain)
        other.adjust_relationship(specimen.id, 2)

    def _sunday_church_utility(self, specimen: "Specimen", simulation: "Simulation") -> float:
        if simulation.day_of_week != 6:
            return 0
        tod = simulation.time_of_day
        if not (7 <= tod < 8):
            return 0
        return specimen.personality.religious * 1.8

    def _chase_deer_utility(self, specimen: "Specimen", simulation: "Simulation") -> float:
        if not specimen.is_homeless or specimen.fatigue > 75:
            return 0
        detection = 30 + specimen.genetics.eyesight * 0.6
        has_nearby_deer = any(r.species == "deer" and not r.sleeping and math.dist(r.position, specimen.position) < detection for r in simulation.world.resources.values())
        if not has_nearby_deer:
            return 0
        return 50 + specimen.genetics.speed * 0.5 + specimen.hunger * 0.3

    def _attend_event_utility(self, specimen: "Specimen", simulation: "Simulation") -> float:
        if not simulation.world.pop_up_active:
            return 0
        trait_value = getattr(specimen.personality, simulation.world.pop_up_trait, 50)
        return max(0, trait_value - 40) * 1.8

    def _work_utility(self, specimen: "Specimen", simulation: "Simulation") -> float:
        if not specimen.has_job or not simulation.is_daytime or specimen.age_hours < 48:
            return 0
        tod = simulation.time_of_day
        if not (specimen.work_start <= tod < specimen.work_end):
            return 0
        in_work = simulation.world.zone_at(specimen.position) == "work"
        return 85 + (20 if in_work else 0) - specimen.hunger * 0.3

    def _flee_utility(self, specimen: "Specimen", simulation: "Simulation") -> float:
        if simulation.world.in_shelter(specimen.position):
            return 0
        detection_range = 40 + specimen.genetics.eyesight * 0.8
        nearest_bear = next((r for r in simulation.world.resources.values() if r.species == "bear" and not r.sleeping and math.dist(r.position, specimen.position) < detection_range), None)
        if not nearest_bear:
            return 0
        proximity = 1 - math.dist(nearest_bear.position, specimen.position) / detection_range
        return 180 + specimen.personality.fearfulness * 0.8 + proximity * 60

    def _reproduction_utility(self, specimen: "Specimen", simulation: "Simulation") -> float:
        if specimen.pregnant or specimen.hunger > 55 or specimen.fatigue > 70 or simulation.is_daytime:
            return 0
        if specimen.age_hours < 24:
            return 0
        return specimen.genetics.fertility * .35

    def _donation_utility(self, specimen: "Specimen", simulation: "Simulation") -> float:
        if specimen.is_homeless or specimen.wallet < 10:
            return 0
        has_nearby_recipient = any(candidate.is_homeless and math.dist(candidate.position, specimen.position) < 55 for candidate in simulation.specimens.values())
        if not has_nearby_recipient:
            return 0
        return specimen.personality.morality * .45 + specimen.personality.friendliness * .25 + specimen.personality.loyalty * .15

    def _shelter_utility(self, specimen: "Specimen", simulation: "Simulation") -> float:
        if not specimen.is_homeless or simulation.world.zone_at(specimen.position) != "forest":
            return 0
        nearby = [candidate for candidate in simulation.specimens.values() if candidate.is_homeless and candidate.id != specimen.id and math.dist(candidate.position, specimen.position) < 70]
        materials = specimen.plant_goods + specimen.animal_goods
        return 110 + specimen.personality.loyalty * .3 if nearby and materials >= 2 else 0

    def _flee_human_utility(self, specimen: "Specimen", simulation: "Simulation") -> float:
        if specimen.personality.aggression > 60:
            return 0
        aggressors = self._nearby_aggressors(specimen, simulation)
        if not aggressors:
            return 0
        nearest_dist = min(math.dist(a.position, specimen.position) for a in aggressors)
        detection = 55 + specimen.genetics.eyesight * 0.4
        proximity = 1 - nearest_dist / detection
        return 120 + specimen.personality.fearfulness * 0.9 + proximity * 80

    def _theft_utility(self, specimen: "Specimen", simulation: "Simulation") -> float:
        if specimen.reputation > 60 or specimen.personality.aggression < 50:
            return 0
        if specimen.wallet > 20:
            return 0
        has_target = any(c.id != specimen.id and c.wallet > 15
                         and math.dist(c.position, specimen.position) < 50
                         for c in simulation.specimens.values())
        if not has_target:
            return 0
        return specimen.personality.aggression * 0.5 - specimen.personality.morality * 0.4 + (specimen.hunger - 40) * 0.3
