# Specimens: Technical Analysis & Game Architecture

## Executive Summary

**Specimens** is an **autonomous agent-based simulation** where 42+ human characters make utility-driven decisions in a shared 1000×1000m world. The game combines:

- **Economic simulation**: income/expense tracking, job system, housing market
- **Evolutionary genetics**: trait inheritance, mutation, lifespan variation
- **Social dynamics**: relationship tracking, reputation, conflict resolution
- **Ecological simulation**: plants (rooted, regenerating), animals (roaming deer/bears), aging/death
- **Real-time decision-making**: 10 ticks/sec, behavior chosen every frame based on local state
- **Real-time rendering**: Canvas-based browser observatory with smooth interpolation

---

## Core Architecture

### 1. Simulation Loop (`backend/simulation.py`)

**Clock & Time:**
- 10 ticks/second = 1 simulated day per 10 real minutes (at 1× speed)
- 25 real seconds = 1 simulated hour
- 1 simulated week = 5 simulated days + 2 days weekend = 7-day cycle
- Speed slider: 1× to 10,000× (entire day in 0.1 sec at max)

**Per-tick flow:**
```
1. Update weather (probabilistic transitions: clear → rain → drought → storm)
2. Update world state:
   - Pop-up event moves/activates
   - Plants regrow (weather-dependent)
   - Animals move (roaming with bouncing)
   - Aging: animals age by seconds/25; removed if > max_age_hours
3. Resolve ecology:
   - Deer feeding (herbivores eat plants, die if poisoned)
   - Deer reproduction (synchronized at night)
   - Deer behavior (sleep cycles, wandering patterns)
   - Bear behavior (hunting, madness from poisoned plants, attacking)
   - Wildlife replenishment (respawn resources if depleted)
4. Teleporter update (random position change every ~18 sec)
5. For each alive specimen:
   - Age by seconds/25
   - Update new_arrival flag (True first 2 hours)
   - Assign job if age ≥ 48 hours and unemployed
   - Calculate sheltering (in building or forest shelter)
   - Update hunger/fatigue with weather modifiers:
     * Base: hunger +0.08/sec, fatigue +0.28/sec (day) or +0.12/sec (night)
     * Storm: ×1.6 hunger, ×1.8 fatigue (×1.4/×1.5 if homeless)
     * Rain: ×1.2 hunger, ×1.3 fatigue
     * Drought: ×1.35 hunger
   - Recover run stamina (regain 0.25/hour while not running)
   - Recover intoxication (decrement per hour spent sober)
   - **Choose action** (highest utility from 24 possible actions)
   - **Execute action** (movement, transaction, interaction)
   - Award action points (cumulative score)
   - Resolve forest food pickup
   - Check death conditions → create death marker
6. Payroll every 5 days (Friday): accrued pay → wallet
7. Broadcast state packet to all WebSocket clients (full state every tick)
```

### 2. Behavior Engine (`backend/behavior.py`)

**Decision Model: Utility Maximization**

Each specimen scores 24 possible actions. The engine evaluates:

```python
utilities = {
    "eat": hunger * 1.8 + (café bonus),
    "donate": homeless_nearby * relationship_strength,
    "gather": 32 (if in forest),
    "hunt": speed * 0.45 (if speed ≥ 60, fatigue ≤ 70, in forest),
    "chase_deer": immediate prey availability,
    "build_shelter": homeless_count * materials_available,
    "sell_goods": (plant_goods * 5 + animal_goods * 12) if in café,
    "buy_home": 80 (if homeless, wallet ≥ 60, in café),
    "sleep": fatigue * 1.5 + (home bonus),
    "return_home": (fatigue + hunger * 0.2) if has_home,
    "sell_home": risk_taking * 0.12 (desperate, wallet < 8),
    "move_in": 35 (if homeless),
    "flee": bears_nearby * fear_factor,
    "explore": curiosity * 0.7 + (forest bonus),
    "attend_event": event_active * friendliness,
    "work": in_work_zone * discipline,
    "socialize": friendliness * 0.7,
    "attend_church": (Sunday + morality),
    "reproduce": partner_nearby * fertility * (intoxication_boost if home),
    "conflict": (aggression * 0.55) - (fearfulness * 0.25),
    "flee_human": aggressors_nearby * fearfulness,
    "wander": 15.0 (default),
    "theft": wealthy_targets_nearby * (risk_taking - eyesight_penalty),
    "spectate_fight": fighting_nearby * curiosity,
}
```

**Critical Modifiers:**

- **Hunger override**: If hunger > 90, add +100 to eat action
- **Lunch rush**: 11:30–13:30, hungry specimens get +55 eat bonus
- **Night behavior** (18:00–06:00):
  - Homeless: explore ×0.2, return_home +90, sleep +40
  - Housed: return_home +120
- **Late night** (22:00–06:00):
  - sleep +60 + (hour_past_10pm × 15), explore ×0.1, work = 0, event = 0
- **Pregnancy**: return_home +55, explore ×0.3, hunt/conflict = 0
- **Fatigue > 85**: sleep +50
- **Intoxication**: affects movement and decision-making
- **Weather**:
  - Rain/Storm: return_home +35, sleep +15, explore ×0.4, event = 0
  - Drought: eat +25, gather +20

**Action Execution (`execute()` method)**

Each action maps to a behavior:

| Action | Effect |
|--------|--------|
| `eat` | In café: pay $5, reduce hunger −35; otherwise move toward café |
| `sleep` | Set sleeping=True, reduce fatigue −18 |
| `donate` | Transfer $5 to nearby homeless, boost reputation |
| `gather` | Move toward plant, pick up, add to inventory |
| `hunt` | Move toward animal, if close enough kill and add to inventory |
| `work` | Move to work zone; if inside, earn $10/day accrue + reputation +0.02 |
| `return_home` | Move toward home; if homeless, seek shelter building |
| `buy_home` | In café + wallet ≥ $60: buy apartment or negotiate with owner |
| `sell_home` | Become homeless, gain $25 |
| `move_in` | Find nearby housed specimen with good relationship, share their home |
| `reproduce` | Find opposite-gender partner nearby + good relationship; trigger pregnancy (9 hours) |
| `conflict` | Chase and attack target (damage = attack − defense); if hunger > 100, target dies |
| `flee` | Run away from bears at 4.5–8.5 m/s depending on run stamina |
| `flee_human` | Run toward home/shelter, away from aggressors |
| `socialize` | Move to bar/church/event, spend $10–20 (bar), build intoxication |
| `spectate_fight` | Move to nearby fight, watch |
| `theft` | Steal $5–12 from target; reputation −12 if caught by eyesight check |
| `wander` | Random +/−8 position drift |

**Weather Impact on Speed:**

All movement is scaled by `weather_speed = 0.65` if raining/storming, else `1.0`. This slows all pathfinding.

---

### 3. Specimen State Model (`backend/specimen.py`)

**Attributes:**

| Category | Fields |
|----------|--------|
| **Identity** | id, name, gender, age_hours |
| **Housing** | is_homeless, home (coordinate), home_kind ("apartment" / "forest_shelter") |
| **Needs** | hunger (0–100), fatigue (0–100), wallet ($), pay_accrual ($) |
| **Position** | x, y (world coordinates), current_action (string) |
| **Inventory** | plant_goods (int), animal_goods (int) |
| **Social** | relationships (dict of id→score), reputation (0–100), partner_id, pregnant, pregnancy_hours_remaining |
| **Work** | has_job (bool), salary ($/day), pay_accrual, work_start/end (hours), credit_score |
| **State** | alive (bool), sleeping (bool), is_running (bool), intoxicated_hours_remaining, run_remaining_hours |
| **Genetics** | eyesight, speed, defense, attack, fertility, mutation_rate (all 1–100) |
| **Personality** | friendliness, curiosity, aggression, risk_taking, loyalty, morality, pride, discipline, fearfulness, honesty, forgetfulness, religious (all 1–100) |
| **Biology** | max_age_hours (120–300, random per spawn), points (cumulative score) |

**Packet Serialization (`to_packet()`):**

Sends 19 fields to browser: id, name, x, y, hunger, fatigue, wallet, gender, is_homeless, home_kind, action, age, plant_goods, animal_goods, sleeping, points, new_arrival, reputation, pregnant, is_running, run_stamina, intoxicated (boolean).

---

### 4. Genetics & Personality

**Genetics (`backend/genetics.py`)**

Six traits (1–100):
- `eyesight`: witness detection range for theft
- `speed`: movement speed, hunting ability
- `defense`: damage reduction in conflicts
- `attack`: damage dealt in conflicts
- `fertility`: reproduction probability
- `mutation_rate`: trait variance in children

**Inheritance model:**
- Child's value = average(parent1, parent2) + random(−8, +8) with `mutation_rate`% chance
- Mutation spreads traits across generation

**Personality (`backend/personality.py`)**

Twelve traits (1–100):
- `friendliness`: socialize, bar, church preference
- `curiosity`: explore, event preference, spectate fights
- `aggression`: conflict utility
- `risk_taking`: theft, sell_home, bet at bar
- `loyalty`: relationship with housed specimens
- `morality`: church preference, resist theft
- `pride`: status-seeking
- `discipline`: work productivity
- `fearfulness`: flee utility, conflict avoidance
- `honesty`: resist theft
- `forgetfulness`: relationship decay
- `religious`: church attendance (Sundays)

**Inheritance model:**
- Child's value = average(parent1, parent2) + random(−12, +12) with `mutation_rate`% chance

---

### 5. Ecology System

**Plants:**
- Initial: 34 rooted plants (x% are poisonous, rest safe)
- Growth: regrow energy at 0.3–1.5 units/sec (random per plant)
- Harvest: gathering picks up 1 plant, reduces energy
- Death: poisoned plant kills any eater (specimen or deer)
- Weather effect (drought): reduced growth

**Deer:**
- Initial: 14 free-roaming herbivores
- Movement: velocity-based (bouncing at forest edges)
- Feeding: eat nearby plants at night; die if poisonous
- Reproduction: synchronized at night, require energy > threshold
- Hunting: can be caught by fast humans (speed ≥ 60)
- Death: by hunting, poisoning, or age (36–96 hours)
- Aging: die when age_hours ≥ max_age_hours

**Bears:**
- Initial: 4 large predators
- Movement: roam forest with slower speed than deer
- Feeding: eat deer and plants
- Poison madness: if eat poisoned plant, become mad for 2 hours (attack indiscriminately)
- Hunting: attack humans if mad or during specific provocation
- Death: by age (72–180 hours)

**Ecology Loop (every tick):**
1. Grow plants (weather-dependent)
2. Move animals
3. Age animals; remove if expired
4. Resolve deer feeding (plants → deer → poisoning check)
5. Resolve deer reproduction (synchronized)
6. Resolve deer behavior (wandering, circling)
7. Resolve bear behavior (hunting, madness)
8. Replenish wildlife (spawn new deer/bears/plants if depleted)

---

### 6. Economic System

**Starting Capital:** $100

**Income:**
- **Work (Job):** $10/day accrued while in work zone; paid every 5 days (Friday)
  - 90% of specimens age ≥ 48 hours get assigned random job
  - Earn reputation +0.02/tick while working
  - Pay accrual accumulates during shift hours

**Expenses:**
- **Café:** $5/meal (reduces hunger −35)
- **Bar:** $10–20/visit (random, only 10am–4am, boosts intoxication)
- **Theft victim:** −$5 to −$12 (random amount stolen)

**Transactions:**
- **Sell goods:** plants $5 each, animals $12 each (homeless only)
- **Buy home:** $60 upfront to buy apartment or negotiate with desperate owner
- **Sell home:** +$25, become homeless (desperate only)
- **Donation:** −$5 from donor, +$5 to recipient (homeless)

**Housing Market:**
- 20 apartments at fixed locations
- Buy price: $60 (if apartment free, or negotiate with owner wallet ≤ $12)
- Forest shelters: free but require teamwork (≥2 homeless, ≥2 resources, build together)

---

### 7. Reproduction System (`backend/reproduction.py`)

**Copulation Conditions:**
- Woman: not pregnant, not homeless, hunger ≤ 55, fatigue ≤ 70, age ≥ 24 hours
- Man: hunger ≤ 55, fatigue ≤ 70, age ≥ 24 hours
- Both: within 22m, mutual relationship ≥ 25
- Both: at home (or fertility rates plummet)
- **Intoxication boost:** If woman is at home and intoxicated, fertility increases by 80% (0.8 multiplier)

**Pregnancy:**
- Duration: 9 simulated hours
- Woman is immobilized (return_home +55, explore ×0.3, no hunting/conflict)
- Man is unaffected after copulation

**Birth:**
- Child inherits genetics (average + mutation)
- Child inherits personality (average + mutation)
- Child starts age 0, hunger 30, fatigue 15
- Child gets random gender
- Child marked `new_arrival` (true first 2 hours)
- Child's home = mother's home (if she has one)

---

### 8. World Layout

```
         Café (0,0) ——— Bar ——— 
             |              |
             |        Work Zone
             |              |
        Church      Pop-up Event (random)
             |              |
             |       Homes (20 apts)
             |              |
            Forest (roaming animals, plants)
             |              |
            Forest Shelter  (player-built)
```

**Zones:**
- **Café** (90, 110, 180×130): trading hub
- **Bar** (330, 90, 170×115): socializing, drinking (10am–4am)
- **Work** (510, 270, 180×120): employment zone
- **Church** (80, 380, 190×155): reflection, Sunday gathering
- **Forest** (750, 0, 250×1000): ecology, gathering, hunting
- **Homes** (100, 590, 600×320): 20 apartments in 5×4 grid
- **Pop-up event** (random daily, 200×80): temporary 6-hour social event

**Forest Shelters:**
- Player-constructed safe zones (free)
- Requirements: ≥2 homeless, ≥2 gathered resources, same location
- Protects from bears during night
- Counted as "housed" for fatigue calculations

---

### 9. Death System

**Causes (recorded in death_markers):**
- `starvation`: hunger ≥ 100
- `old_age`: age ≥ max_age_hours
- `forest_danger`: in forest, hunger > 94 (exposure to bears)
- `night_exposure`: homeless, night, fatigue > 99
- `poisonous_plant`: ate poisoned plant
- `bear_attack`: killed by mad or hunting bear
- `killed_in_fight`: hunger reached 100 during conflict
- `hunted`: deer caught by fast human
- `caught_by_human`: deer caught during chase action

**Death Marker:**
Stored in `simulation.death_markers` (max 100 most recent):
```json
{
  "x": position_x,
  "y": position_y,
  "name": specimen_name,
  "entity_type": "human" | "animal",
  "cause": cause_string,
  "action": what_they_were_doing,
  "tick": simulation_tick
}
```

Browser renders red `X` at death location; hovering shows cause.

---

### 10. Frontend Rendering (`frontend/main.js`)

**Architecture:**
- Real-time Canvas rendering (1000×1000)
- WebSocket connection receives full state packets every tick (100ms)
- Interpolation between packets (smooth motion at 60fps)
- Hover detection for specimens, resources, zones, teleporter, death markers
- Keyboard/click interactions (pause, reset, add specimen, wake, select)

**Rendering Order:**
1. Background fill
2. Zone rectangles + labels
3. Death markers (red `X`)
4. Plant glyphs (rooted, colored by poison)
5. Animal glyphs (ellipses with ears, bears vs deer)
6. Specimen glyphs (circles with trails)
   - Color by gender (orange = man, teal = woman)
   - Hunger affects radius
   - Notable actions (teleported, conflict) get pulsing rings
   - NEW arrival = orange pulsing ring
   - Selected specimen = green pulsing ring with reticle
7. Teleporter (glowing yellow orb)
8. HUD: population, homeless, tick, clock, events, analysis

**Speed & Optimization:**
- Trail history per specimen (max 12 points)
- Trail history per animal (max 8 points)
- Trails cleaned up when entity dies
- Hover card priority: specimen > resource > zone > teleporter > death marker

---

## Emergent Behaviors & Design Patterns

### 1. **Utility-Driven Autonomy**

Every decision is localized—no global planner. This creates:
- **Emergent coordination**: lunch rush at café when hunger peaks
- **Conflict zones**: bar fights when drunk specimens socialize
- **Housing markets**: poor specimens negotiate; rich buy
- **Ecological feedback**: overhunting → scarcity → foraging → hoarding

### 2. **Time-of-Day Cycles**

Strong 24-hour rhythm:
- **6am–6pm**: work, gathering, eating, socializing
- **6pm–10pm**: return home, sleep prep, socializing
- **10pm–6am**: sleep, nighttime shelter-seeking
- **Sunday 8am–5pm**: church (if religious > 50)

Intoxication and pregnancy break these patterns unpredictably.

### 3. **Multi-generational Lifespan**

- **0–2 hours**: marked NEW, cannot work
- **2–48 hours**: juvenile, no job
- **48–120+ hours**: adult, working
- **120–300 hours**: natural death window (random max_age)

Mutation rates cause trait variance across generations, creating visible family trees if tracked.

### 4. **Ecological Pressure**

- Deer and bears age out → must be replenished
- Overhunting → plant scarcity → human starvation
- Drought → increased hunger → emergency work/theft
- Storms → homeless take damage

This creates natural resource cycles.

### 5. **Reputation & Social Proof**

Reputation affects:
- Theft success (high eyesight witnesses reduce success)
- Home negotiation (reputation threshold for rental)
- Conflict likelihood (low reputation → targeted)
- Work value (higher reputation = better pay)

---

## Key Simulation Parameters

| Parameter | Value | Effect |
|-----------|-------|--------|
| Tick rate | 10 Hz | Real-time responsiveness |
| Time scale | 25 sec/hour | 10 min = 1 day |
| Base hunger rate | 0.08/sec | 8 points/min |
| Base fatigue rate (day) | 0.28/sec | 28 points/min |
| Base fatigue rate (night) | 0.12/sec | 12 points/min |
| Pregnancy duration | 9 hours | 225 real seconds |
| Job assignment | 48 hours age | Mid-life milestone |
| Payday | Every 5 days | Friday |
| Max death markers | 100 | History limit |
| Forest resources | 52 total | 14 deer, 4 bears, 34 plants |
| Apartments | 20 | Housing capacity |
| Max population | Unlimited | Dynamic births/deaths |
| Run stamina | 1 hour | Regenerates 25%/hour |

---

## Recent Enhancements (Session Notes)

1. **Death Marker Hover**: Red `X` now shows what died and why (cause + action at time of death)
2. **Population Reset**: `reset_population()` now clears and re-seeds all 52 forest resources (14 deer, 4 bears, 34 plants)
3. **Weather System**: Probabilistic weather (clear, rain, drought, storm) with hunger/fatigue modifiers
4. **Job System**: 90% of adults work; pay accrues at $10/day, paid every 5 days
5. **Intoxication Mechanics**: Bar drinking raises intoxication; intoxicated at home boosts reproduction by 80%
6. **Conflict System**: Direct combat with damage calculation; high aggression targets die if hunger > 100
7. **Reputation System**: Affects theft success, work value, relationship decay
8. **Run Stamina**: Characters can sprint (×1.5–2× speed) for 1 hour, then must recover
9. **Conflict Detection**: Flee actions prioritize reaching home/shelter over pure distance escape

---

## Testing Coverage

```bash
23 tests pass
- Population dynamics
- Resource reset behavior
- Death marker accuracy
- Poisonous plant mechanics
- Bear attack behavior
- Housing transaction
- Relationship tracking
- Forest ecology
- Job assignment
- Payroll system
```

---

## Performance Notes

- **Bottleneck**: Decision-making loop (24 actions × 40+ specimens × 10 Hz)
- **Mitigation**: Utility scoring is O(1) per action; no expensive pathfinding per tick
- **Network**: Full state packet every tick (100ms) via WebSocket
- **Rendering**: Canvas is very fast; interpolation masks 100ms latency

At 1× speed, smooth 60fps. At 10,000× speed, decisions queue but remain consistent.

---

## Extensions & Hooks

**Easy to add:**
- New actions (extend `choose()` and `execute()`)
- New personality traits (modify `Personality` dataclass)
- New genetic traits (modify `Genetics` dataclass)
- Weather types (add to weather transition table)
- Scenario modes (presets for trait ranges)

**Hard to add:**
- Pathfinding (currently: move toward target, no obstacle avoidance)
- Memory (currently: stateless; forget upon action change)
- LLM integration (separate system; hooks ready)
- Trade routes (currently: no market beyond café)

