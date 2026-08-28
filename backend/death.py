from __future__ import annotations

from .specimen import Specimen


def cause_of_death(specimen: Specimen, is_daytime: bool, in_forest: bool) -> str | None:
    if specimen.hunger >= 100:
        return "starvation"
    if specimen.max_age_hours > 0 and specimen.age_hours >= specimen.max_age_hours:
        return "old_age"
    if not is_daytime and specimen.is_homeless and specimen.fatigue > 99:
        return "night_exposure"
    return None
