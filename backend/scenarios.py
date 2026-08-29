from __future__ import annotations

# Each scenario defines min/max ranges for personality and genetics traits.
# Unspecified traits fall back to the default random range (25–85 personality, 30–85 genetics).
# Intensity (1–100) blends between the default range and the scenario extremes.

_PERSONALITY_DEFAULT = (25, 85)
_GENETICS_DEFAULT = (30, 85)

SCENARIOS: dict[str, dict] = {
    "balanced": {
        "label": "Balanced",
        "description": "Default random population — no trait bias.",
        "personality": {},
        "genetics": {},
    },
    "violent": {
        "label": "Violent Society",
        "description": "High aggression, low morality and fear. Expect frequent fights, theft, and conflict cascades.",
        "personality": {
            "aggression": (75, 99),
            "morality": (1, 20),
            "fearfulness": (1, 20),
            "loyalty": (1, 25),
            "honesty": (1, 25),
        },
        "genetics": {
            "attack": (70, 99),
            "speed": (60, 90),
        },
    },
    "peaceful": {
        "label": "Peaceful Colony",
        "description": "High morality and loyalty, minimal aggression. Donations, cooperation, and community building.",
        "personality": {
            "aggression": (1, 15),
            "morality": (75, 99),
            "loyalty": (70, 99),
            "friendliness": (70, 99),
            "honesty": (70, 99),
        },
        "genetics": {
            "defense": (60, 90),
        },
    },
    "mating": {
        "label": "Mating Frenzy",
        "description": "Maximum fertility and friendliness. Population will boom — watch for overcrowding and homelessness.",
        "personality": {
            "friendliness": (75, 99),
            "fearfulness": (1, 30),
            "discipline": (1, 30),
        },
        "genetics": {
            "fertility": (85, 99),
            "mutation_rate": (60, 90),
        },
    },
    "intelligent": {
        "label": "Intelligent Elite",
        "description": "High curiosity, discipline, and eyesight. Low forgetfulness. Efficient workers, minimal crime.",
        "personality": {
            "curiosity": (75, 99),
            "discipline": (75, 99),
            "forgetfulness": (1, 20),
            "morality": (60, 90),
        },
        "genetics": {
            "eyesight": (75, 99),
            "mutation_rate": (1, 20),
        },
    },
    "dumb": {
        "label": "Dumb & Chaotic",
        "description": "Low discipline, high forgetfulness, poor eyesight. Erratic movement, poor survival decisions.",
        "personality": {
            "curiosity": (1, 25),
            "discipline": (1, 25),
            "forgetfulness": (75, 99),
            "risk_taking": (70, 99),
        },
        "genetics": {
            "eyesight": (1, 25),
            "mutation_rate": (70, 99),
        },
    },
    "survivalist": {
        "label": "Survivalist Tribe",
        "description": "Maximum speed, defense, and attack. High fearfulness keeps them cautious but dangerous when cornered.",
        "personality": {
            "fearfulness": (60, 85),
            "discipline": (60, 85),
            "aggression": (50, 80),
        },
        "genetics": {
            "speed": (80, 99),
            "defense": (75, 99),
            "attack": (70, 99),
            "eyesight": (70, 95),
        },
    },
}


def apply_scenario(scenario_name: str, intensity: int = 100) -> tuple[dict, dict]:
    """Return (personality_ranges, genetics_ranges) blended by intensity (1-100)."""
    scenario = SCENARIOS.get(scenario_name, SCENARIOS["balanced"])
    t = max(0.0, min(1.0, intensity / 100))

    def blend(scenario_range: tuple[int, int], default: tuple[int, int]) -> tuple[int, int]:
        lo = round(default[0] + (scenario_range[0] - default[0]) * t)
        hi = round(default[1] + (scenario_range[1] - default[1]) * t)
        return (lo, hi)

    personality_ranges = {
        trait: blend(rng, _PERSONALITY_DEFAULT)
        for trait, rng in scenario.get("personality", {}).items()
    }
    genetics_ranges = {
        trait: blend(rng, _GENETICS_DEFAULT)
        for trait, rng in scenario.get("genetics", {}).items()
    }
    return personality_ranges, genetics_ranges
