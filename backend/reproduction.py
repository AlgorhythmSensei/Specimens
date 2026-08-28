from __future__ import annotations

import math
import random

from .names import random_name
from .personality import Personality
from .genetics import Genetics
from .specimen import Specimen

PREGNANCY_HOURS = 9.0
MIN_RELATIONSHIP = 25.0
MAX_HUNGER = 55.0
MAX_FATIGUE = 70.0
COPULATE_RANGE = 22.0


def attempt_copulation(woman: Specimen, specimens: dict) -> bool:
    if woman.gender != "woman" or woman.pregnant:
        return False
    if woman.hunger > MAX_HUNGER or woman.fatigue > MAX_FATIGUE:
        return False
    if woman.age_hours < 24:
        return False
    for man in specimens.values():
        if man.id == woman.id or man.gender != "man":
            continue
        if man.hunger > MAX_HUNGER or man.fatigue > MAX_FATIGUE:
            continue
        if man.age_hours < 24:
            continue
        if math.dist(man.position, woman.position) > COPULATE_RANGE:
            continue
        rel_w = woman.relationship_with(man.id)
        rel_m = man.relationship_with(woman.id)
        if rel_w < MIN_RELATIONSHIP or rel_m < MIN_RELATIONSHIP:
            continue
        fertility_chance = (woman.genetics.fertility + man.genetics.fertility) / 200
        if random.random() > fertility_chance:
            continue
        woman.pregnant = True
        woman.pregnancy_hours_remaining = PREGNANCY_HOURS
        woman.partner_id = man.id
        woman.current_action = "copulating"
        man.current_action = "copulating"
        woman.adjust_relationship(man.id, 8.0)
        man.adjust_relationship(woman.id, 8.0)
        return True
    return False


def attempt_birth(woman: Specimen, specimens: dict, next_id: int) -> Specimen | None:
    if not woman.pregnant or woman.pregnancy_hours_remaining > 0:
        return None
    father = specimens.get(woman.partner_id)
    if father is None:
        father_personality = Personality.random()
        father_genetics = Genetics.random()
    else:
        father_personality = father.personality
        father_genetics = father.genetics
    mutation_rate = (woman.genetics.mutation_rate + father_genetics.mutation_rate) // 2
    gender = random.choice(("man", "woman"))
    child_name = random_name(gender)
    child_home = woman.home
    child = Specimen(
        next_id, gender, child_home is None,
        name=child_name,
        home_kind=woman.home_kind if child_home else "apartment",
        personality=Personality.inherit(woman.personality, father_personality, mutation_rate),
        genetics=Genetics.inherit(woman.genetics, father_genetics),
        position=woman.position,
        home=child_home,
    )
    child.hunger = 30.0
    child.fatigue = 15.0
    child.age_hours = 0.0
    child.new_arrival = True
    woman.pregnant = False
    woman.partner_id = -1
    woman.hunger = min(100, woman.hunger + 20)
    woman.fatigue = min(100, woman.fatigue + 25)
    woman.current_action = "gave_birth"
    woman.points += 15
    if father:
        father.current_action = "became_father"
        father.adjust_relationship(woman.id, 5.0)
        father.points += 8
    return child
