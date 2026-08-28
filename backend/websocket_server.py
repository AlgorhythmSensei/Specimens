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


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(simulation.run())
    broadcast_task = asyncio.create_task(broadcaster())
    yield
    task.cancel()
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


@app.post("/api/analyse")
async def analyse():
    return await generate_analysis(simulation.packet())


@app.post("/api/optimise")
async def optimise():
    return await generate_optimal_traits(simulation.packet())


@app.post("/api/read-minds")
async def read_minds():
    """Gemini inner thoughts for the 4 most interesting live specimens."""
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
    """Groq world-observer sentence for the current snapshot."""
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
