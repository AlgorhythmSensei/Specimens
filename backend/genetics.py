from __future__ import annotations

from dataclasses import dataclass, fields
import random


@dataclass
class Genetics:
    eyesight: int
    speed: int
    defense: int
    attack: int
    fertility: int
    mutation_rate: int

    @classmethod
    def random(cls) -> "Genetics":
        return cls(**{field.name: random.randint(30, 85) for field in fields(cls)})

    @classmethod
    def inherit(cls, first: "Genetics", second: "Genetics") -> "Genetics":
        mutation_rate = (first.mutation_rate + second.mutation_rate) // 2
        values = {}
        for field in fields(cls):
            average = (getattr(first, field.name) + getattr(second, field.name)) // 2
            spread = random.randint(-8, 8) if random.random() < mutation_rate / 100 else 0
            values[field.name] = max(1, min(100, average + spread))
        return cls(**values)
