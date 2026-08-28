from __future__ import annotations

from dataclasses import dataclass, fields
import random


@dataclass
class Personality:
    friendliness: int
    curiosity: int
    aggression: int
    risk_taking: int
    loyalty: int
    morality: int
    pride: int
    discipline: int
    fearfulness: int
    honesty: int
    forgetfulness: int

    @classmethod
    def random(cls) -> "Personality":
        return cls(**{field.name: random.randint(25, 85) for field in fields(cls)})

    @classmethod
    def inherit(cls, first: "Personality", second: "Personality", mutation_rate: int) -> "Personality":
        return cls(**{field.name: _mutate((getattr(first, field.name) + getattr(second, field.name)) // 2, mutation_rate) for field in fields(cls)})


def _mutate(value: int, rate: int) -> int:
    if random.random() > rate / 100:
        return max(1, min(100, value))
    return max(1, min(100, value + random.randint(-12, 12)))
