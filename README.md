# Specimens

Specimens is a browser-based evolutionary world. Autonomous human agents move through a shared world, make utility-based decisions, form relationships, hold jobs, earn and spend money, find housing, gather food, copulate, become pregnant, give birth, fight, run, get drunk, and die. Bears, deer, and plants form a living forest ecology. A roaming teleporter and a daily social event add unpredictable interactions.

The project is intentionally local-first. The live behavior analysis is generated from simulation state and uses **zero LLM tokens**.

## Run

```bash
cd Specimens
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.websocket_server:app --reload
```

Open `http://127.0.0.1:8000`. If that port is busy, add `--port 8003`.

The server runs the simulation at 10 ticks per second. One simulated 24-hour day takes 10 real minutes:

- 25 real seconds per simulated hour
- 6:00–18:00 is daytime; 18:00–6:00 is nighttime
- The browser clock shows `Day  HH:MM` and advances smoothly between server packets
- One simulated week is 70 real minutes. Day 7 is Sunday.

The **speed control** in the toolbar (0.5× – 20×) scales simulated time relative to real time without changing the tick rate. At 20× a full simulated day passes in 30 real seconds.

Run tests with:

```bash
python3 -m pytest -q
node --check frontend/main.js
python3 -m py_compile backend/*.py
```

## World

The world is 1000 × 1000 metres. Fixed zones:

| Zone | Position | Purpose |
|---|---|---|
| Café | top-left | buy food, sell goods, buy or negotiate a home |
| Bar | top-centre | socialise; extended stays cause intoxication |
| Work | centre | earn salary during shift hours |
| Church | left | reflection and relationship building; Sunday attendance |
| Forest | right strip (x 750–1000) | ecology, gathering, hunting, shelter building |
| Homes | lower-centre | 20 apartments; residents rest and reproduce here |
| Social event | random daily | 6-hour pop-up; topic and trait from nearest zone |
| Forest shelter | player-built | protects from bears; requires teamwork and materials |

Hovering over any zone shows a description. The social event hover shows the live topic.

## Specimens

Each specimen has:

- **Identity**: numeric id, name, gender, age
- **Housing**: homeless status and apartment location when housed
- **Needs**: hunger, fatigue, wallet
- **Position**: live x/y coordinates and current action
- **Inventory**: gathered plant goods and hunted animal goods
- **Relationships**: per-specimen relationship score (−100 to +100)
- **Reputation**: community standing (0–100); affected by conflict, theft, work, and donation
- **Personality traits** (1–100): friendliness, curiosity, aggression, risk taking, loyalty, morality, pride, discipline, fearfulness, honesty, forgetfulness, religious
- **Genetic traits** (1–100): eyesight, speed, defense, attack, fertility, mutation rate
- **Job**: 90% of adults hold a job with a personal salary and a random shift (start 8–9 AM, end 4–6 PM)
- **Lifespan**: 120–300 simulated hours per specimen
- **Run stamina**: 1 simulated hour of sprint capacity, recovering at 25%/hour when not running
- **Intoxication**: builds up while socialising in the bar; causes zigzag movement for up to 3 simulated hours
- **Pregnancy**: women carry for 9 simulated hours before giving birth

Names are drawn from a pool of 200 (100 masculine, 100 feminine). Newborn names are plain first names — parents are not encoded in the name.

## Behavior

Every tick each awake specimen scores every action and executes the highest-value one:

| Action | Triggered by |
|---|---|
| `eat` | high hunger; moves to café or eats in place |
| `sleep` | high fatigue; boosted strongly after 22:00 |
| `work` | has job, inside shift window, daytime |
| `attend_church` | Sunday 7–8 AM, religious trait |
| `attend_event` | social event active, matching personality trait |
| `socialize` | friendliness; targets bar, church, or social event |
| `donate` | high morality + wallet, homeless recipient nearby |
| `gather` | in forest, collects plants |
| `hunt` | in forest, speed ≥ 60, fatigue ≤ 70 |
| `chase_deer` | homeless, deer in eyesight range |
| `sell_goods` | carrying goods, at café |
| `buy_home` / `negotiate_home` | homeless, wallet ≥ $60, at café |
| `build_shelter` | homeless, in forest, 2+ teammates and 2+ materials |
| `return_home` | night; homeless seek nearest building wall instead |
| `move_in` | homeless, nearby housed relationship with good reputation |
| `sell_home` | housed but financially desperate |
| `explore` | curiosity; moves toward forest |
| `reproduce` | night, compatible nearby partner (see Reproduction) |
| `conflict` | aggression-driven; pursues target at run speed, fights on contact |
| `flee` | bear in eyesight; sprints away; suppressed inside shelters |
| `flee_human` | aggressive nearby stranger detected; fearful specimens run |
| `theft` | low wallet, low reputation, high aggression, rich target nearby |
| `wander` | default fallback |

**Priority overrides**: hunger > 90 adds +100 to eat. Night adds +60/+80 to sleep. Storm outdoors boosts return_home. Pregnant women strongly prefer return_home and avoid hunting and conflict.

## Running And Stamina

Each specimen has **1 simulated hour of sprint stamina**:

- `flee`, `flee_human`, and conflict pursuit all consume stamina
- When stamina is depleted the specimen drops to walk speed (~half)
- Stamina recovers passively at 25%/hour while walking
- Sprint speed is approximately 2× the specimen's base walk speed (genetics-scaled)

## Reproduction And Pregnancy

Copulation requires man + woman within 22 units, relationship ≥ 40 on both sides, hunger < 55, fatigue < 70, age ≥ 24 simulated hours, and a fertility dice roll:

- **Successful copulation**: both get +8 relationship; woman becomes **pregnant** for 9 simulated hours
- Pregnant women display a pulsing **pink ♥ ring** and strongly prefer returning home; they cannot hunt, fight, or copulate again until after birth
- **Birth**: child spawns at the mother's position; mother takes a hunger and fatigue hit; father is notified; both parents earn points
- If the father has died before birth the child still arrives, inheriting random paternal genetics
- The child inherits a blend of both parents' personality and genetics, with mutation applied at the average of both mutation rates

## Aggression And Fighting

Specimens with **aggression > 65** are visible threats. Fearful or unaggressive specimens choose `flee_human` when one is within eyesight range, sprinting away.

When two specimens fight on contact:

- Damage = `(attacker.attack − defender.defense × 0.4) / 6` added to defender's hunger
- If **both are aggressive** (>55): damage doubles and the defender has an 8% chance to retaliate immediately
- Hunger ≥ 100 → death; recorded as `killed_in_fight`; killer loses 15 reputation points

## Intoxication

Socialising inside the Bar zone builds intoxication up to 3 simulated hours. While intoxicated:

- Movement has a sine-wave lateral wobble — the specimen visibly zigzags
- Intoxication drains at 1 sim-hour per real hour; the specimen sobers up naturally

## Homelessness And Group Behaviour

Homeless specimens have additional survival strategies:

- **Night shelter-seeking**: at night homeless suppress explore, boost `return_home`, and move toward the nearest building wall to sleep against it
- **Group sleep**: 3+ homeless within 40 units cluster and sleep together at night for safety
- **Group bear hunt**: if 5+ homeless mob a bear within 60 units they collectively damage it. A successful kill gives every member: −40 hunger, +0.3 stamina bonus, +2 animal goods, +20 points

## Weather

Weather cycles stochastically through four states:

| State | Duration | Effect on specimens | Effect on ecology |
|---|---|---|---|
| Clear | 4–8 sim-hours | baseline | baseline |
| Rain | 1–3 sim-hours | outdoor hunger ×1.2, fatigue ×1.3; slower movement | plants grow and spawn ×1.4 |
| Drought | 2–4 sim-hours | everyone's hunger ×1.35 | plants grow and spawn ×0.5 |
| Storm | 0.5–1.5 sim-hours | outdoor hunger ×1.6, fatigue ×1.8; homeless worst-affected | plants grow and spawn ×1.8 |

Indoor zones (homes, café, bar, church, work, forest shelters) fully protect from rain and storm penalties.

## Forest Ecology

### Plants

Plants are green and rooted. Each has an individual growth rate (0.3–1.5 energy/sec). New plants sprout spontaneously up to a cap of 60. ~20% of plants are poisonous.

### Deer

Deer are brown herbivores. They:

- Get hungry and die of starvation when energy reaches zero
- Seek plants when energy < 50%; avoid poisonous ones 95% of the time
- Gravitate toward their herd (within 180 units) when unthreatened
- Flee bears at 35–45 units/tick; flee humans at 6–12 units/tick
- Reproduce when two deer meet (capped at 30); display a **green halo** for 1 sim-hour after birth
- Live 36–96 simulated hours; if all die, 5–10 new deer spawn immediately

### Bears

Bears are large dark predators. They:

- Walk at ~7 units/tick; sprint at 35–40 units/tick with a **10 sim-minute sprint limit** (recovers at 0.5× rate)
- Hunt prey once every **8 simulated hours**; between hunts they wander or eat plants
- **Sleep for 3 simulated hours** after successfully eating a deer or human
- Roam the **entire 1000 × 1000 map** approximately 10% of their awake time (1–2 sim-hour wander periods); the rest of the time they stay in the forest
- Become **mad for 30 simulated minutes** after eating a poisonous plant — attack anything within range
- Cannot enter forest shelters
- Live 72–180 simulated hours; population is always topped up to at least 2

### Speed Reference

| Entity | Walk | Sprint | Limit |
|---|---|---|---|
| Bear | ~7 units/tick | 35–40 units/tick | 10 sim-min sprint |
| Deer (bear threat) | ~7 units/tick | 35–45 units/tick | — |
| Deer (human threat) | ~7 units/tick | 6–12 units/tick | — |
| Human (flee/fight) | genetics-scaled | ~2× walk speed | 1 sim-hour stamina |

## Teleporter

The glowing yellow orb drifts through the world. Before relocating it **grows to 5× its normal size** over 3 real seconds with intensifying glow, then snaps to a new random position.

Specimens within 90 units are pulled toward it (quadratic falloff). Contact teleports the specimen to a random location anywhere in the world.

## Social Event

Appears once per simulated day, active for 6 sim-hours at a start time randomly chosen between 8 AM and 4 PM. Location is rejection-sampled to never overlap a fixed zone.

Topic and attracted trait by nearest zone:

| Nearest zone | Example topics | Trait |
|---|---|---|
| Café | Farmers market, poetry slam | friendliness / curiosity |
| Bar | Jazz night, open mic, vinyl exchange | friendliness / curiosity |
| Church | Candlelight vigil, meditation circle | morality |
| Work | Career fair, skills workshop | discipline / curiosity |
| Homes | Block party, neighbourhood cleanup | loyalty / friendliness |
| Open | Astronomy club, lantern festival | curiosity / friendliness |

## Scoring

Points accumulate through: hunting, gathering, selling goods, housing changes, reproduction, building shelters, donating, working, killing bears (group hunt), and sleep. The leaderboard shows the top five. Conflict deaths and theft cost points.

## UI Features

- **Clock**: shows `Day  HH:MM` in the toolbar with the simulated day name (Mon–Sun)
- **Speed control**: 0.5× / 1× / 2× / 5× / 10× / 20× buttons; active speed highlighted
- **Pause**: turns the status dot red and shows `PAUSED`; resuming restores green `LIVE`
- **Hover cards**: specimen quick stats, zone descriptions, animal energy/state, death markers
- **Trail fade**: movement trails fade from invisible at the tail to full opacity at the head
- **New arrival**: manually added specimens and newborns pulse a bright yellow `NEW` ring for 2 simulated hours; initial population and resets do not blink
- **Pregnant**: pulsing pink ♥ ring
- **Weather overlay**: rain draws diagonal streaks; drought adds an amber tint
- **Simulation label**: `TEST SIMULATION #N · Day D`; resets increment the number

## Add Specimen

The **Add specimen** button opens a form with gender, housing preference, hunger, fatigue, friendliness, curiosity, aggression, speed, fertility, and mutation-rate sliders. The browser sends values to the server over WebSocket; the server assigns the next id, name, and apartment if available.

## API And WebSocket Protocol

HTTP endpoints:

- `GET /`: Canvas observatory
- `GET /api/status`: current world packet
- `/static/*`: frontend assets

WebSocket `/ws` — client commands:

```text
toggle
reset
```

JSON commands:

```json
{"type": "add_specimen", "values": {"gender": "woman", "housed": false, "speed": 80}}
{"type": "wake_specimen", "id": 7}
{"type": "set_speed", "speed": 5}
```

Broadcast packet includes: `tick`, `simulation_number`, `time_scale`, `time_of_day`, `is_daytime`, `weather`, `day_number`, `event_active`, `event_topic`, specimens, leaderboard, behavior analysis, animals, plants, teleporter (with `grow_phase`), and zone geometry. Each specimen packet includes identity, position, needs, housing, action, inventory, points, `new_arrival`, `sleeping`, `pregnant`, `is_running`, `run_stamina`, `intoxicated`, and `reputation`.

## Project Structure

```text
backend/
    behavior.py          utility scoring, action execution, conflict, intoxication, flee
    death.py             death conditions (starvation, old age, bear attack, fight)
    genetics.py          inherited genetic traits and mutation
    names.py             200-name pool
    personality.py       personality traits, inheritance, mutation (incl. religious)
    reproduction.py      copulation, pregnancy, birth
    simulation.py        clock, tick loop, economy, ecology, weather, scoring, packets
    specimen.py          specimen state and serialization
    teleporter.py        roaming orb, suction, grow-before-relocate
    websocket_server.py  FastAPI HTTP/WebSocket server
    world.py             zones, apartments, plants, animals, social event scheduling

frontend/
    index.html           observatory layout, toolbar, speed control, add-specimen form
    main.js              Canvas rendering, interpolation, trails, hover, focus
    style.css            observatory styling and responsive layout

tests/
    test_simulation.py   simulation, ecology, economy, and behavior tests
```

## Local Start

```bash
cd /Users/mikko/Documents/VSCodeIDE/Specimens
source .venv/bin/activate
python3 -m pytest -q
uvicorn backend.websocket_server:app --reload
```

The simulation is local-first and requires no API key. The main behavior decision path is in `backend/behavior.py`; state, ticking, ecology, and packet construction are in `backend/simulation.py`; rendering and interaction are in `frontend/main.js`.
