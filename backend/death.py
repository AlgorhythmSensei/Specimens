from __future__ import annotations

from .specimen import Specimen


def cause_of_death(specimen: Specimen, is_daytime: bool, in_forest: bool) -> str | None:
    if specimen.hunger >= 100:
        return "starvation"
    if specimen.age_hours >= 24 * 365 * 80:
        return "old_age"
    if in_forest and specimen.hunger > 94:
        return "forest_danger"
    if not is_daytime and specimen.is_homeless and specimen.fatigue > 99:
        return "night_exposure"
    return None
