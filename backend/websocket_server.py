from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .simulation import Simulation
from .llm import generate_commentary, generate_analysis, generate_optimal_traits, specimen_think

simulation = Simulation()
clients: set[WebSocket] = set()
_llm_commentary: str = ""
_llm_thoughts: dict[int, str] = {}   # specimen_id → last LLM thought
_LLM_WORLD_INTERVAL = 10.0           # seconds between world-observer calls
_LLM_SPECIMEN_INTERVAL = 20.0        # seconds between per-specimen thought batches


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(simulation.run())
    broadcast_task = asyncio.create_task(broadcaster())
    llm_task = asyncio.create_task(llm_loop())
    yield
    task.cancel()
    broadcast_task.cancel()
    llm_task.cancel()


app = FastAPI(title="Specimens Evolution Engine", lifespan=lifespan)
frontend = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend), name="static")


@app.get("/")
async def index():
    return FileResponse(frontend / "index.html")


@app.get("/api/status")
async def status():
    pkt = simulation.packet()
    pkt["llm_commentary"] = _llm_commentary
    return pkt


@app.post("/api/analyse")
async def analyse():
    snapshot = simulation.packet()
    return await generate_analysis(snapshot)


@app.post("/api/optimise")
async def optimise():
    snapshot = simulation.packet()
    result = await generate_optimal_traits(snapshot)
    return result


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            if message == "toggle":
                simulation.running = not simulation.running
            elif message == "reset":
                simulation.reset_population()
            else:
                try:
                    command = json.loads(message)
                except json.JSONDecodeError:
                    command = {}
                if command.get("type") == "add_specimen":
                    simulation.add_specimen(command.get("values", {}))
                elif command.get("type") == "wake_specimen":
                    simulation.wake_specimen(int(command.get("id", 0)))
                elif command.get("type") == "set_speed":
                    simulation.time_scale = max(0.25, min(10000.0, float(command.get("speed", 1.0))))
            await websocket.send_text(json.dumps({"type": "command_ack", "running": simulation.running}))
    except WebSocketDisconnect:
        clients.discard(websocket)


async def llm_loop():
    global _llm_commentary, _llm_thoughts
    world_timer = 0.0
    specimen_timer = 0.0
    sleep_interval = 2.0
    while True:
        await asyncio.sleep(sleep_interval)
        if not simulation.running or simulation.game_over:
            continue
        world_timer += sleep_interval
        specimen_timer += sleep_interval
        packet = simulation.packet()
        specimens = packet.get("specimens", [])
        if not specimens:
            continue
        tod = packet.get("time_of_day", 12)
        hh = str(int(tod)).zfill(2)
        mm = str(int(tod % 1 * 60)).zfill(2)
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_name = day_names[(packet.get("day_number", 1) - 1) % 7]
        # World commentary
        if world_timer >= _LLM_WORLD_INTERVAL:
            world_timer = 0.0
            notable = list({s["action"] for s in specimens if s["action"] not in ("wander", "return_home", "sleep", "work", "explore")})
            snapshot = {
                "top_specimens": specimens[:4],
                "weather": packet.get("weather", "clear"),
                "time_label": f"{day_name} {hh}:{mm}",
                "population": len(specimens),
                "notable_actions": notable[:4],
            }
            try:
                text = await generate_commentary(snapshot)
                if text:
                    _llm_commentary = text
            except Exception:
                pass
        # Per-specimen thoughts — pick 2 interesting specimens
        if specimen_timer >= _LLM_SPECIMEN_INTERVAL:
            specimen_timer = 0.0
            zones = {z["name"]: z for z in packet.get("zones", [])}
            interesting = [s for s in specimens if s["action"] not in ("wander", "sleep", "work")][:4]
            picks = interesting[:2] if interesting else specimens[:2]
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
                        _llm_thoughts[s["id"]] = thought
                except Exception:
                    pass


async def broadcaster():
    while True:
        if clients:
            pkt = simulation.packet()
            pkt["llm_commentary"] = _llm_commentary
            # Attach thoughts only for specimens still alive; prune the rest
            live_ids = {s["id"] for s in pkt.get("specimens", [])}
            stale = [k for k in _llm_thoughts if k not in live_ids]
            for k in stale:
                del _llm_thoughts[k]
            pkt["llm_thoughts"] = _llm_thoughts
            payload = json.dumps(pkt)
            disconnected = set()
            for client in clients:
                try:
                    await client.send_text(payload)
                except Exception:
                    disconnected.add(client)
            clients.difference_update(disconnected)
        await asyncio.sleep(.1)


