from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .simulation import Simulation

simulation = Simulation()
clients: set[WebSocket] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(simulation.run())
    yield
    task.cancel()


app = FastAPI(title="Specimens Evolution Engine", lifespan=lifespan)
frontend = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend), name="static")


@app.get("/")
async def index():
    return FileResponse(frontend / "index.html")


@app.get("/api/status")
async def status():
    return simulation.packet()


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
            await websocket.send_text(json.dumps({"type": "command_ack", "running": simulation.running}))
    except WebSocketDisconnect:
        clients.discard(websocket)


async def broadcaster():
    while True:
        if clients:
            payload = json.dumps(simulation.packet())
            disconnected = set()
            for client in clients:
                try:
                    await client.send_text(payload)
                except Exception:
                    disconnected.add(client)
            clients.difference_update(disconnected)
        await asyncio.sleep(.1)


@app.on_event("startup")
async def start_broadcaster():
    asyncio.create_task(broadcaster())
