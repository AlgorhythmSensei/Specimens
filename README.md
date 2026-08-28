# Specimens

Specimens is a browser-based evolutionary world. Autonomous human agents move through a shared world, make utility-based decisions, form relationships, earn and spend money, find housing, gather food, reproduce, sleep, and die. A roaming teleporter and a moving social event add unpredictable interactions.

The project is intentionally local-first. The live behavior analysis is generated from simulation state and uses **zero LLM tokens**. Groq can be added later for occasional, opt-in summaries, but it is not required for the simulation loop.

## Run

```bash
cd Specimens
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.websocket_server:app --reload
```

Open `http://127.0.0.1:8000`. If that port is busy, choose another port, for example `--port 8003`.

The server runs the simulation at 10 ticks per second. One simulated 24-hour day takes 10 real minutes:

- 25 real seconds per simulated hour
- 6:00-18:00 is daytime
- 18:00-6:00 is nighttime
- The browser clock advances smoothly between server packets so the live passage of time is visible

Run tests with:

```bash
python3 -m pytest -q
node --check frontend/main.js
python3 -m py_compile backend/*.py
```

## World

The world is 1000 x 1000 metres. The Canvas renders these zones:

- **Café**: agents buy food and homeless agents sell gathered forest goods
- **Bar**: a venue for music, wagers, alliances, and social encounters
- **Church**: a venue for reflection, kindness, vows, and relationship building
- **Forest**: a full-height strip on the right side, from `x=750` to `x=1000`; it is 250 world units wide, representing the 40 x 40 metre forest area in the scenario
- **Homes**: the residential district containing 20 dedicated apartments
- **Social event**: a temporary 230 x 90 event venue that relocates periodically and attracts curious agents

Hovering over a zone shows a rotating description. The social event uses imaginative descriptions such as lantern circles, vinyl exchanges, and astronomy clubs.

## Specimens

Each specimen has:

- Identity: numeric id, name, gender, age, and parent information for children
- Housing: homeless status and an apartment location when housed
- Needs: hunger, fatigue, wallet, and credit score
- Position: live x/y coordinates and current action
- Inventory: gathered plant goods and hunted animal goods
- Relationships: relationship strengths keyed by specimen id
- Personality traits from 1-100: friendliness, curiosity, aggression, risk taking, loyalty, morality, pride, discipline, fearfulness, honesty, and forgetfulness
- Genetic traits from 1-100: eyesight, speed, defense, attack, fertility, and mutation rate
- Points: cumulative score earned through actions

Names are selected from a pool of 200 names: 100 masculine and 100 feminine names inspired by countries and naming traditions around the world. Newborn names include both parents in brackets, for example `James (Tina+Kevin)`.

Names are cosmetic identity only. They do not influence movement, personality, genetics, money, scoring, health, housing, reproduction, or any other behavior decision. Decisions use simulation state and numeric traits, so agents with identical state behave identically regardless of their names.

## Housing And Economy

The first 20 specimens are assigned the 20 apartments in chronological id order. Later specimens start homeless unless a free apartment is requested and available.

Housing can change during play:

- A housed specimen can sell its home and become homeless when its behavior favors the sale
- A homeless specimen can move in with a nearby housed relationship
- Café earnings can fund a home purchase
- If an apartment is free, a homeless specimen can buy it for `$60`
- If all apartments are occupied, a homeless specimen with `$60` can negotiate with a financially vulnerable homeowner; the buyer pays `$60`, the seller receives `$60`, and ownership transfers
- Parents who reproduce pass a home to the child when the family is housed; two homeless parents produce a homeless child
- Nearby homeless specimens can team up in the forest to build a shared `forest_shelter`. The team must have at least two members and two units of gathered forest goods; all builders share the shelter location and become housed there. This does not consume one of the 20 dedicated apartments.

## Behavior

Every tick, each awake specimen evaluates utilities and executes the highest-valued action. The available actions include:

- Eating and sleeping
- Socializing at the bar, church, or current social event
- Exploring and returning home
- Gathering plants and hunting animals
- Selling goods at the café and buying or negotiating housing
- Moving in with another agent or selling a home
- Reproduction, conflict, and ordinary wandering

Urgent hunger can override other goals. At night, housed specimens receive a strong home-return preference, while homeless specimens receive a strong forest-shelter preference. Personality traits shape social venue choice and other decisions.

The **Behavior Analysis** list shows the highest-scoring live specimens and a local explanation of their current motivation. Examples include high hunger, night shelter priority, and seeking income or social connection. Clicking a row selects and focuses that specimen in the world.

## Forest Ecology

The forest contains persistent resources:

- **Plants** are green, rooted, and remain still. They regrow continuously and can feed any specimen.
- Some plants are poisonous. Eating one lowers hunger but kills the specimen and records `ate_poisonous_plant`.
- **Animals** are brown, roam with persistent velocity, bounce inside the forest, and leave visible movement trails.
- Animals occasionally sleep briefly and show `Zzz`; otherwise they continuously move.
- Hunting requires genetic speed of at least `60` and fatigue of `70` or lower. A successful hunt adds animal goods and fatigue.
- The current herbivores are deer. Deer eat plants, can be hunted by fast specimens, and are prey for bears.
- Bears are darker and larger predators. They eat deer and plants, and they can attack specimens when enraged.
- If a bear eats a poisonous plant, it becomes mad for exactly 2 simulated hours, equal to 50 real seconds in the 10-minute-day clock. During that period it attacks nearby deer, plants, and specimens indiscriminately.

Forest resources can be carried to the café. Homeless agents receive `$5` per plant and `$12` per animal when selling goods. The browser explains each plant or animal on hover.

## Sleep And Interaction

Sleeping is an explicit state. A sleeping specimen or animal stops moving and displays `Zzz`. Clicking a sleeping specimen wakes it through a WebSocket command and changes its action to `waking`.

Clicking any specimen opens its vitals panel. Hovering shows quick statistics and the current action. Specimen hover takes priority over zone, resource, and teleporter hover cards so only one explanation is visible at a time.

New specimens, including newborns and agents created through the form, receive a pulsing orange `NEW` indicator for their first 24 simulated hours. A selected specimen receives a pulsing green halo and focus reticle.

## Scoring And Simulations

Points are cumulative and appear in the leaderboard and behavior-analysis list. Actions award points, including hunting, gathering, selling goods, housing changes, reproduction, and sleep.

Every population reset starts a new numbered simulation. The header displays `TEST SIMULATION #N`; reset also clears tick and time and creates a fresh chronological population. The current simulation number is included in every state packet.

## Teleporter

The glowing teleporter orb moves randomly through the world. When it touches a specimen, that specimen is sent to a random location and receives the `teleported` action. Hovering the orb explains this effect.

## Add Specimen

The **Add specimen** button opens a form with:

- Gender and housing preference
- Hunger and fatigue sliders
- Friendliness, curiosity, and aggression sliders
- Speed, fertility, and mutation-rate sliders

The browser sends the values to the server over WebSocket. The server clamps values, assigns the next id and name, assigns an apartment if available, and inserts the new specimen into the active population.

## API And WebSocket Protocol

HTTP endpoints:

- `GET /`: serves the Canvas observatory
- `GET /api/status`: returns the current world packet
- `/static/*`: serves frontend assets

WebSocket endpoint: `/ws`.

Client commands are:

```text
toggle
reset
```

Or JSON commands:

```json
{"type":"add_specimen","values":{"gender":"woman","housed":false,"speed":80}}
{"type":"wake_specimen","id":7}
```

The server broadcasts packets containing `tick`, `simulation_number`, `time_of_day`, `is_daytime`, specimens, leaderboard, behavior analysis, animals, plants, teleporter coordinates, and zone geometry. Each specimen packet includes identity, position, needs, housing, action, inventory, points, and `new_arrival`/`sleeping` state.

## Project Structure

```text
backend/
	behavior.py          utility-based decisions and actions
	death.py             death conditions
	genetics.py          inherited genetic traits and mutation
	names.py             200-name pool
	personality.py       personality traits and inheritance
	reproduction.py      compatibility and child creation
	simulation.py        clock, tick loop, economy, scoring, packets
	specimen.py          specimen state and serialization
	teleporter.py        roaming orb behavior
	websocket_server.py  FastAPI HTTP/WebSocket server
	world.py             zones, apartments, plants, and animals
frontend/
	index.html           observatory layout and add-specimen form
	main.js              Canvas rendering, interpolation, hover, focus
	style.css            observatory styling and responsive layout

tests/
	test_simulation.py   simulation, ecology, economy, and behavior tests
```

## Claude Code Handoff

Continue from the `Specimens` directory in Claude Code:

```bash
cd /Users/mikko/Documents/VSCodeIDE/Specimens
source .venv/bin/activate
python3 -m pytest -q
uvicorn backend.websocket_server:app --reload
```

The simulation is local-first and does not require an API key. Keep the simulation loop independent from optional LLM summaries. The main behavior decision path is in `backend/behavior.py`; state, ticking, scoring, and packet construction are in `backend/simulation.py`; browser rendering and interaction are in `frontend/main.js` and `frontend/style.css`.
