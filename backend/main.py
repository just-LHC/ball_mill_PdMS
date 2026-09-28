import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from db_engine import fetch_all_alerts, log_alert_to_db
from ml_engine import analyze_telemetry_diagnostics

app = FastAPI(title="LafargeHolcim PdM Suite API")

# Enable CORS for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TelemetryManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

manager = TelemetryManager()

# REST Endpoint: Fetch active alerts from Supabase PostgreSQL
@app.get("/api/alerts")
def get_alerts():
    return fetch_all_alerts()

# WebSocket Endpoint: Stream continuous telemetry without page refreshes
@app.websocket("/ws/telemetry/{mill}")
async def stream_telemetry(websocket: WebSocket, mill: str):
    await manager.connect(websocket)
    try:
        while True:
            # Generate or stream real-time sensor metrics
            payload = {
                "mill": mill,
                "equipment": "Mill Main Control",
                "vibration_mm_s": round(2.2 + (asyncio.get_event_loop().time() % 0.5), 2),
                "temperature_c": 61.5
            }
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(1) # Smooth 1-second continuous stream tick
    except WebSocketDisconnect:
        manager.disconnect(websocket)