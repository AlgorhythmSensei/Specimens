from __future__ import annotations

from typing import TYPE_CHECKING, Dict
import math
import random

if TYPE_CHECKING:
    from .simulation import Simulation
    from .specimen import Specimen


class BehaviorEngine:
    actions = ("eat", "sleep", "donate", "socialize", "explore", "gather", "hunt", "build_shelter", "sell_goods", "buy_home", "return_home", "sell_home", "move_in", "reproduce", "conflict", "wander")

    def choose(self, specimen: "Specimen", simulation: "Simulation") -> str:
        zone = simulation.world.zone_at(specimen.position)
        utilities: Dict[str, float] = {
            "eat": specimen.hunger * 1.8 + (35 if zone == "cafe" else 0),
            "donate": self._donation_utility(specimen, simulation),
            "gather": 32 if zone == "forest" else 0,
            "hunt": specimen.genetics.speed * .45 if zone == "forest" and specimen.genetics.speed >= 60 and specimen.fatigue <= 70 else 0,
            "build_shelter": self._shelter_utility(specimen, simulation),
            "sell_goods": (specimen.plant_goods * 5 + specimen.animal_goods * 12) if zone == "cafe" else 0,
            "buy_home": 80 if specimen.is_homeless and zone == "cafe" and specimen.wallet >= 60 else 0,
            "sleep": specimen.fatigue * 1.5 + (30 if zone == "homes" else 0),
            "return_home": (specimen.fatigue + specimen.hunger * .2) if specimen.home else 0,
            "sell_home": specimen.personality.risk_taking * .12 if specimen.home and specimen.wallet < 8 else 0,
            "move_in": 35 if specimen.is_homeless else 0,
            "explore": specimen.personality.curiosity * .7 + (25 if zone == "forest" else 0),
            "socialize": specimen.personality.friendliness * .7,
            "reproduce": self._reproduction_utility(specimen, simulation),
            "conflict": specimen.personality.aggression * .55 - specimen.personality.fearfulness * .25,
            "wander": 15.0,
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
                utilities["explore"] += 120
            elif specimen.home:
                utilities["return_home"] += 120
        if specimen.is_homeless and simulation.is_daytime:
            utilities["move_in"] += specimen.personality.loyalty * .3
        return max(utilities, key=utilities.get)

    def execute(self, specimen: "Specimen", action: str, simulation: "Simulation") -> None:
        specimen.current_action = action
        if action == "eat" and simulation.world.zone_at(specimen.position) == "cafe" and specimen.wallet >= 2:
            specimen.wallet -= 2
            specimen.hunger = max(0, specimen.hunger - 35)
        elif action == "eat":
            cafe = next(zone for zone in simulation.world.zones if zone.name == "cafe")
            self._move_toward(specimen, (cafe.x + cafe.width / 2, cafe.y + cafe.height / 2), simulation, 5.0)
        elif action == "donate":
            simulation.donate_to_homeless(specimen)
        elif action == "gather":
            self._move_toward_forest_resource(specimen, simulation, "plant", 4.0)
        elif action == "hunt":
            self._move_toward_forest_resource(specimen, simulation, "animal", 5.5)
        elif action == "build_shelter":
            simulation.build_forest_shelter(specimen)
        elif action == "sell_goods" and simulation.world.zone_at(specimen.position) == "cafe":
            simulation.sell_goods_at_cafe(specimen)
        elif action == "buy_home" and simulation.world.zone_at(specimen.position) == "cafe":
            simulation.buy_or_negotiate_home(specimen)
        elif action == "sleep":
            specimen.sleeping = True
            specimen.fatigue = max(0, specimen.fatigue - 18)
        elif action == "return_home" and specimen.home:
            self._move_toward(specimen, specimen.home, simulation, 2.4)
        elif action == "sell_home" and specimen.home:
            specimen.wallet += 25
            specimen.home = None
            specimen.is_homeless = True
        elif action == "move_in" and specimen.is_homeless:
            nearby_housed = [candidate for candidate in simulation.specimens.values() if candidate.home and math.dist(candidate.position, specimen.position) < 100]
            if nearby_housed:
                host = max(nearby_housed, key=lambda candidate: specimen.relationship_with(candidate.id))
                specimen.home = host.home
                specimen.is_homeless = False
                self._move_toward(specimen, host.position, simulation, 5.0)
        elif action == "explore":
            destination = next(zone for zone in simulation.world.zones if zone.name == "forest")
            self._move_toward(specimen, (destination.x + destination.width / 2, destination.y + destination.height / 2), simulation, 5.0)
        elif action in ("reproduce", "conflict"):
            self._interact(specimen, simulation, action)
        elif action == "socialize":
            venues = [zone for zone in simulation.world.zones if zone.name in ("bar", "church", "pop_up")]
            if venues:
                preferred = max(venues, key=lambda venue: specimen.personality.friendliness if venue.name == "bar" else specimen.personality.morality if venue.name == "church" else specimen.personality.curiosity)
                self._move_toward(specimen, (preferred.x + preferred.width / 2, preferred.y + preferred.height / 2), simulation, 4.0)
            self._interact(specimen, simulation, action)
        else:
            specimen.position = simulation.world.clamp((specimen.position[0] + random.uniform(-8, 8), specimen.position[1] + random.uniform(-8, 8)))

    def _move_toward(self, specimen: "Specimen", target, simulation: "Simulation", speed: float) -> None:
        dx, dy = target[0] - specimen.position[0], target[1] - specimen.position[1]
        distance = math.hypot(dx, dy) or 1
        specimen.position = simulation.world.clamp((specimen.position[0] + dx / distance * speed * specimen.genetics.speed / 50, specimen.position[1] + dy / distance * speed * specimen.genetics.speed / 50))

    def _move_toward_forest_resource(self, specimen: "Specimen", simulation: "Simulation", kind: str, speed: float) -> None:
        resources = [resource for resource in simulation.world.resources.values() if resource.kind == kind and resource.energy > 0]
        if resources:
            target = min(resources, key=lambda resource: math.dist(resource.position, specimen.position))
            self._move_toward(specimen, target.position, simulation, speed)

    def _interact(self, specimen: "Specimen", simulation: "Simulation", action: str) -> None:
        nearby = [candidate for candidate in simulation.specimens.values() if candidate.id != specimen.id and math.dist(candidate.position, specimen.position) < 45]
        if not nearby:
            return
        other = random.choice(nearby)
        if action == "conflict":
            damage = max(1, specimen.genetics.attack - other.genetics.defense / 2) / 8
            other.hunger += damage
            specimen.adjust_relationship(other.id, -5)
        else:
            specimen.adjust_relationship(other.id, 2 + specimen.personality.friendliness / 30)
            other.adjust_relationship(specimen.id, 2)

    def _reproduction_utility(self, specimen: "Specimen", simulation: "Simulation") -> float:
        return 0 if specimen.hunger > 60 or simulation.is_daytime else specimen.genetics.fertility * .35

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
