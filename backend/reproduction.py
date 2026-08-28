from __future__ import annotations

import math
import random

from .personality import Personality
from .genetics import Genetics
from .specimen import Specimen


def attempt_reproduction(first: Specimen, specimens: dict, next_id: int) -> Specimen | None:
    if first.hunger > 60 or first.gender not in ("man", "woman") or first.home is None:
        return None
    for second in specimens.values():
        if second.id == first.id or second.gender == first.gender or second.hunger > 60 or second.home is None:
            continue
        if math.dist(first.position, second.position) > 25 or first.relationship_with(second.id) < 35:
            continue
        gender = random.choice(("man", "woman"))
        child_name = f"{random.choice(('Alex', 'Robin', 'Casey', 'Avery'))} ({first.name}+{second.name})"
        child_home = None if first.is_homeless and second.is_homeless else first.home
        child = Specimen(next_id, gender, child_home is None, name=child_name, home_kind=first.home_kind if child_home else "apartment", personality=Personality.inherit(first.personality, second.personality, (first.genetics.mutation_rate + second.genetics.mutation_rate) // 2), genetics=Genetics.inherit(first.genetics, second.genetics), position=first.position, home=child_home)
        return child
    return None
