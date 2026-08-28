from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, Optional, Tuple
import random

from .genetics import Genetics
from .personality import Personality


@dataclass
class Specimen:
    id: int
    gender: str
    is_homeless: bool
    name: str = ""
    home_kind: str = "apartment"
    personality: Personality = field(default_factory=Personality.random)
    genetics: Genetics = field(default_factory=Genetics.random)
    hunger: float = 20.0
    fatigue: float = 20.0
    wallet: float = 100.0
    pay_accrual: float = 0.0
    credit_score: float = 650.0
    position: Tuple[float, float] = (500.0, 500.0)
    relationships: Dict[int, float] = field(default_factory=dict)
    home: Optional[Tuple[float, float]] = None
    age_hours: float = 0.0
    alive: bool = True
    current_action: str = "wandering"
    plant_goods: int = 0
    animal_goods: int = 0
    sleeping: bool = False
    points: int = 0
    new_arrival: bool = True
    has_job: bool = False
    salary: float = 0.0
    max_age_hours: float = 0.0
    work_start: float = 8.0
    work_end: float = 17.0
    reputation: float = 50.0
    pregnant: bool = False
    pregnancy_hours_remaining: float = 0.0
    partner_id: int = -1
    run_remaining_hours: float = 1.0
    is_running: bool = False
    intoxicated_hours_remaining: float = 0.0

    @classmethod
    def spawn(cls, specimen_id: int, position: Tuple[float, float], home: Optional[Tuple[float, float]] = None) -> "Specimen":
        homeless = home is None
        return cls(specimen_id, random.choice(("man", "woman")), homeless, position=position, home=home)

    def to_packet(self) -> dict:
        return {"id": self.id, "name": self.name, "x": round(self.position[0], 1), "y": round(self.position[1], 1), "hunger": round(self.hunger, 1), "fatigue": round(self.fatigue, 1), "wallet": round(self.wallet, 1), "gender": self.gender, "is_homeless": self.is_homeless, "home_kind": self.home_kind if self.home else None, "action": self.current_action, "age_hours": round(self.age_hours, 1), "plant_goods": self.plant_goods, "animal_goods": self.animal_goods, "sleeping": self.sleeping, "points": self.points, "new_arrival": self.new_arrival, "reputation": round(self.reputation, 1), "pregnant": self.pregnant, "is_running": self.is_running, "run_stamina": round(self.run_remaining_hours, 2), "intoxicated": self.intoxicated_hours_remaining > 0}

    def relationship_with(self, other_id: int) -> float:
        return self.relationships.get(other_id, 0.0)

    def adjust_relationship(self, other_id: int, amount: float) -> None:
        self.relationships[other_id] = max(-100.0, min(100.0, self.relationship_with(other_id) + amount))
