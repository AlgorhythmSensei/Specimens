from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .simulation import Simulation
from .scenarios import SCENARIOS
from .llm import generate_commentary, generate_analysis, generate_optimal_traits, specimen_think

simulation = Simulation()
clients: set[WebSocket] = set()
_sim_task: asyncio.Task | None = None


def _new_simulation() -> Simulation:
    return Simulation()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global simulation, _sim_task
    _sim_task = asyncio.create_task(simulation.run())
    broadcast_task = asyncio.create_task(broadcaster())
    yield
    _sim_task.cancel()
    broadcast_task.cancel()


app = FastAPI(title="Specimens Evolution Engine", lifespan=lifespan)
frontend = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend), name="static")


@app.get("/")
async def index():
    return FileResponse(frontend / "index.html")


@app.get("/api/status")
async def status():
    return simulation.packet()


@app.get("/api/scenarios")
async def get_scenarios():
    return {k: {"label": v["label"], "description": v["description"]} for k, v in SCENARIOS.items()}


@app.post("/api/purge")
async def purge():
    """Instantly kills all specimens and triggers game_over state."""
    simulation.specimens.clear()
    simulation.game_over = True
    simulation.reclamation_active = True
    return {"status": "purged"}


@app.post("/api/analyse")
async def analyse():
    return await generate_analysis(simulation.packet())


@app.post("/api/optimise")
async def optimise():
    return await generate_optimal_traits(simulation.packet())


@app.post("/api/read-minds")
async def read_minds():
    packet = simulation.packet()
    specimens = packet.get("specimens", [])
    interesting = [s for s in specimens if s["action"] not in ("wander", "sleep", "work")][:4]
    picks = interesting[:4] if interesting else specimens[:4]
    thoughts: dict[int, str] = {}
    for s in picks:
        s_zone = "open"
        for z in packet.get("zones", []):
            if z["x"] <= s["x"] <= z["x"] + z["width"] and z["y"] <= s["y"] <= z["y"] + z["height"]:
                s_zone = z["name"]
                break
        enriched = {**s, "zone": s_zone}
        try:
            thought = await specimen_think(enriched)
            if thought:
                thoughts[s["id"]] = {"name": s["name"], "action": s["action"], "thought": thought}
        except Exception:
            pass
    return {"thoughts": thoughts}


@app.post("/api/field-notes")
async def field_notes():
    packet = simulation.packet()
    specimens = packet.get("specimens", [])
    tod = packet.get("time_of_day", 12)
    hh = str(int(tod)).zfill(2)
    mm = str(int(tod % 1 * 60)).zfill(2)
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_name = day_names[(packet.get("day_number", 1) - 1) % 7]
    notable = list({s["action"] for s in specimens if s["action"] not in ("wander", "return_home", "sleep", "work", "explore")})
    snapshot = {
        "top_specimens": specimens[:4],
        "weather": packet.get("weather", "clear"),
        "time_label": f"{day_name} {hh}:{mm}",
        "population": len(specimens),
        "notable_actions": notable[:4],
    }
    text = await generate_commentary(snapshot)
    return {"commentary": text}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global simulation, _sim_task
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            try:
                command = json.loads(message)
            except json.JSONDecodeError:
                command = {}
            cmd_type = command.get("type") if isinstance(command, dict) else message

            if message == "toggle":
                simulation.running = not simulation.running
            elif message == "purge":
                simulation.specimens.clear()
                simulation.game_over = True
                simulation.reclamation_active = True
            elif message == "reset" or cmd_type == "reset_scenario":
                scenario = command.get("scenario", "balanced") if cmd_type == "reset_scenario" else "balanced"
                intensity = int(command.get("intensity", 100)) if cmd_type == "reset_scenario" else 100
                if _sim_task and not _sim_task.done():
                    _sim_task.cancel()
                    try:
                        await _sim_task
                    except asyncio.CancelledError:
                        pass
                sim_number = simulation.simulation_number + 1
                simulation = _new_simulation()
                simulation.simulation_number = sim_number
                simulation.set_scenario(scenario, intensity)
                _sim_task = asyncio.create_task(simulation.run())
            elif cmd_type == "add_specimen":
                simulation.add_specimen(command.get("values", {}))
            elif cmd_type == "wake_specimen":
                simulation.wake_specimen(int(command.get("id", 0)))
            elif cmd_type == "set_speed":
                simulation.time_scale = max(0.25, min(10000.0, float(command.get("speed", 1.0))))
            await websocket.send_text(json.dumps({"type": "command_ack", "running": simulation.running}))
    except WebSocketDisconnect:
        clients.discard(websocket)


async def broadcaster():
    while True:
        if clients:
            pkt = simulation.packet()
            payload = json.dumps(pkt)
            disconnected = set()
            for client in clients:
                try:
                    await client.send_text(payload)
                except Exception:
                    disconnected.add(client)
            clients.difference_update(disconnected)
        await asyncio.sleep(.1)
