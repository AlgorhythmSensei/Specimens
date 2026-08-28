from __future__ import annotations

import asyncio
import json
import os

from dotenv import load_dotenv

load_dotenv()

_GROQ_KEY = os.getenv("GROQ_API_KEY", "")
_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
_GROQ_MODEL = "openai/gpt-oss-20b"
_GEMINI_MODEL = "gemini-2.5-flash-lite"

_groq_client = None
_gemini_client = None


def _groq():
    global _groq_client
    if _groq_client is None and _GROQ_KEY:
        from openai import AsyncOpenAI
        _groq_client = AsyncOpenAI(
            api_key=_GROQ_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
    return _groq_client


def _gemini():
    global _gemini_client
    if _gemini_client is None and _GEMINI_KEY:
        from google import genai
        _gemini_client = genai.Client(api_key=_GEMINI_KEY)
    return _gemini_client


async def _groq_call(prompt: str, max_tokens: int = 400) -> str:
    client = _groq()
    if not client:
        return ""
    resp = await client.chat.completions.create(
        model=_GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.8,
    )
    return (resp.choices[0].message.content or "").strip()


def _gemini_call_sync(prompt: str) -> str:
    client = _gemini()
    if not client:
        return ""
    resp = client.models.generate_content(model=_GEMINI_MODEL, contents=prompt)
    return (resp.text or "").strip()


async def _gemini_call(prompt: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _gemini_call_sync, prompt)


def _specimen_prompt(s: dict) -> str:
    zone = s.get("zone", "open")
    return (
        f"Simulated {s['gender']} named {s['name']} in a city sim. "
        f"Hunger {s['hunger']}%, fatigue {s['fatigue']}%, ${s['wallet']:.0f}, "
        f"{'homeless' if s['is_homeless'] else 'housed'}, zone: {zone}, doing: {s['action']}. "
        f"One inner thought (max 12 words, first person, no quotes):"
    )


async def think_male(specimen: dict) -> str:
    """Gemini-powered inner thought for a male specimen."""
    try:
        return await asyncio.wait_for(_gemini_call(_specimen_prompt(specimen)), timeout=5.0)
    except Exception:
        return ""


async def think_female(specimen: dict) -> str:
    """Gemini-powered inner thought for a female specimen."""
    try:
        return await asyncio.wait_for(_gemini_call(_specimen_prompt(specimen)), timeout=5.0)
    except Exception:
        return ""


async def specimen_think(specimen: dict) -> str:
    """Both genders use Gemini for inner thoughts."""
    return await _gemini_call(_specimen_prompt(specimen))


async def generate_commentary(world_snapshot: dict) -> str:
    """Short world-observer sentence — uses Groq for speed."""
    top = world_snapshot.get("top_specimens", [])
    weather = world_snapshot.get("weather", "clear")
    time_label = world_snapshot.get("time_label", "")
    population = world_snapshot.get("population", 0)
    events = world_snapshot.get("notable_actions", [])

    lines = " | ".join(f"{s['name']}:{s['action']}" for s in top[:4])
    event_str = ",".join(events[:3]) if events else "quiet"

    prompt = (
        f"Field scientist log. {time_label}, {weather}, pop {population}. "
        f"Events: {event_str}. Agents: {lines}. "
        f"One vivid sentence (max 18 words) on what is happening. No quotes."
    )

    try:
        text = await asyncio.wait_for(_groq_call(prompt, max_tokens=400), timeout=5.0)
        if text:
            return text
    except Exception:
        pass

    try:
        text = await asyncio.wait_for(_gemini_call(prompt), timeout=6.0)
        if text:
            return text
    except Exception:
        pass

    return ""


async def generate_analysis(snapshot: dict) -> dict:
    """Deep behavioural analysis of the simulation — Groq primary, Gemini fallback."""
    specimens = snapshot.get("specimens", [])
    day = snapshot.get("day_number", 1)
    weather = snapshot.get("weather", "clear")
    population = len(specimens)
    homeless = sum(1 for s in specimens if s.get("is_homeless"))
    avg_hunger = round(sum(s.get("hunger", 0) for s in specimens) / max(1, population), 1)
    avg_wallet = round(sum(s.get("wallet", 0) for s in specimens) / max(1, population), 1)

    action_counts: dict[str, int] = {}
    for s in specimens:
        a = s.get("action", "unknown")
        action_counts[a] = action_counts.get(a, 0) + 1
    top_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:6]

    stats_block = (
        f"Day {day}, {weather}. Pop {population}, homeless {homeless}. "
        f"Avg hunger {avg_hunger}%, avg wallet ${avg_wallet}. "
        f"Actions: {', '.join(f'{a}:{n}' for a, n in top_actions)}."
    )

    prompt = (
        f"You are a behavioural ecologist analysing a city simulation.\n"
        f"Data: {stats_block}\n"
        f"Write a concise analysis in 3 sections:\n"
        f"1. POPULATION HEALTH (2 sentences)\n"
        f"2. DOMINANT BEHAVIOURS (2 sentences on what the population is doing and why)\n"
        f"3. EMERGING STRAINS (1-2 sentences on risks or interesting patterns)\n"
        f"Be specific and scientific. No filler."
    )

    text = ""
    try:
        text = await asyncio.wait_for(_groq_call(prompt, max_tokens=400), timeout=8.0)
    except Exception:
        pass

    if not text:
        try:
            text = await asyncio.wait_for(_gemini_call(prompt), timeout=10.0)
        except Exception:
            pass

    return {
        "stats": {
            "population": population,
            "homeless": homeless,
            "avg_hunger": avg_hunger,
            "avg_wallet": avg_wallet,
            "top_actions": top_actions,
        },
        "analysis": text or "Analysis unavailable — LLM timeout.",
    }


async def generate_optimal_traits(snapshot: dict) -> dict:
    """Groq identifies problems; Gemini prescribes optimal trait values for men and women."""
    specimens = snapshot.get("specimens", [])
    population = len(specimens)
    homeless = sum(1 for s in specimens if s.get("is_homeless"))
    avg_hunger = round(sum(s.get("hunger", 0) for s in specimens) / max(1, population), 1)
    avg_wallet = round(sum(s.get("wallet", 0) for s in specimens) / max(1, population), 1)
    action_counts: dict[str, int] = {}
    for s in specimens:
        a = s.get("action", "unknown")
        action_counts[a] = action_counts.get(a, 0) + 1
    top_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    stats_block = (
        f"Pop {population}, homeless {homeless}/{population}. "
        f"Avg hunger {avg_hunger}%, avg wallet ${avg_wallet}. "
        f"Top actions: {', '.join(f'{a}:{n}' for a, n in top_actions)}."
    )

    # Step 1 — Groq identifies key problems
    problems_prompt = (
        f"City simulation data: {stats_block}\n"
        f"In 2 sentences, identify the 2 biggest survival problems this population faces. Be blunt and specific."
    )
    problems = ""
    try:
        problems = await asyncio.wait_for(_groq_call(problems_prompt, max_tokens=200), timeout=6.0)
    except Exception:
        pass

    if not problems:
        problems = f"High homelessness ({homeless}/{population}) and average hunger of {avg_hunger}%."

    # Step 2 — Gemini prescribes optimal trait values for men and women
    prescribe_prompt = (
        f"You are a social engineer optimising a city simulation population.\n"
        f"Current problems: {problems}\n"
        f"Personality traits range 1-100: friendliness, curiosity, aggression, risk_taking, loyalty, morality, "
        f"pride, discipline, fearfulness, honesty, forgetfulness, religious.\n"
        f"Genetic traits range 1-100: eyesight, speed, defense, attack, fertility, mutation_rate.\n"
        f"Respond ONLY with valid JSON, no other text:\n"
        f'{{"reasoning":"one sentence why","man":{{"friendliness":50,"curiosity":50,"aggression":30,"risk_taking":50,"loyalty":60,"morality":60,"pride":50,"discipline":70,"fearfulness":30,"honesty":70,"forgetfulness":40,"religious":40,"eyesight":60,"speed":60,"defense":50,"attack":50,"fertility":60,"mutation_rate":40}},"woman":{{"friendliness":60,"curiosity":55,"aggression":20,"risk_taking":40,"loyalty":70,"morality":65,"pride":55,"discipline":65,"fearfulness":40,"honesty":75,"forgetfulness":35,"religious":50,"eyesight":65,"speed":55,"defense":55,"attack":40,"fertility":70,"mutation_rate":35}}}}'
    )

    prescribed = {}
    try:
        raw = await asyncio.wait_for(_gemini_call(prescribe_prompt), timeout=10.0)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            prescribed = json.loads(raw[start:end])
    except Exception:
        pass

    return {
        "problems": problems,
        "prescribed": prescribed,
    }
