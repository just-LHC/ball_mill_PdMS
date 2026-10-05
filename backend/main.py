import asyncio
import csv
import io
import json
from datetime import date, datetime, timezone
from typing import Literal
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse
from asset_config import MILL_UNITS, get_equipment_for_mill, get_mill_inventory
from db_engine import (
    DATABASE_URL,
    count_mill_alerts,
    fetch_alert_overview,
    fetch_all_alerts,
    fetch_mill_alerts,
    init_alert_db_table,
    save_alert_feedback,
)

app = FastAPI(title="LafargeHolcim PdM Suite API")


@app.on_event("startup")
def initialize_database_schema():
    if DATABASE_URL:
        init_alert_db_table()


def build_sensor_readings(sensor_definitions: list[dict], elapsed: float):
    readings = []
    for index, sensor in enumerate(sensor_definitions):
        if sensor["kind"] == "vibration":
            value = round(2.2 + ((elapsed + index * 0.11) % 0.5), 2)
        else:
            value = round(58.0 + ((elapsed + index * 0.23) % 4.0), 1)
        source_label = sensor.get("source_label")
        source = f"DEMO DATA · {source_label} source label" if source_label else "DEMO DATA · source not configured"
        readings.append({
            **sensor,
            "channel_key": f"channel-{index + 1}",
            "value": value,
            "source": source,
        })
    return readings


class ServicingFeedback(BaseModel):
    serviced_by: str = Field(min_length=2, max_length=120)
    outcome: Literal["GENUINE_ISSUE", "FALSE_ALARM"]
    service_notes: str = Field(default="", max_length=2000)


def validate_mill(mill: str):
    if mill not in MILL_UNITS:
        raise HTTPException(status_code=404, detail="Mill unit not found")


def require_database():
    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="Alert storage is unavailable because DATABASE_URL is not configured.")

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
    require_database()
    return fetch_all_alerts()

@app.get("/api/overview")
def get_overview(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    before_timestamp: datetime | None = None,
    before_id: int | None = Query(default=None, ge=1),
):
    require_database()
    if (before_timestamp is None) != (before_id is None):
        raise HTTPException(status_code=422, detail="Both cursor fields are required")
    return fetch_alert_overview(limit, offset, before_timestamp, before_id)


@app.get("/api/mills")
def get_mill_units():
    return list(MILL_UNITS)


@app.get("/api/mills/{mill}/equipment")
def get_mill_equipment(mill: str):
    validate_mill(mill)
    return get_equipment_for_mill(mill)


@app.get("/api/mills/{mill}/inventory")
def get_mill_asset_inventory(mill: str):
    validate_mill(mill)
    return get_mill_inventory(mill)


@app.get("/api/mills/{mill}/alerts/export.csv")
def export_mill_alerts(mill: str, start_date: date | None = None, end_date: date | None = None):
    validate_mill(mill)
    require_database()
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="Start date must be before end date")
    total = count_mill_alerts(mill, start_date, end_date)
    alerts = fetch_mill_alerts(mill, start_date, end_date, limit=total, offset=0)
    output = io.StringIO()
    columns = (
        "id", "timestamp", "mill", "equipment", "severity", "issue", "status",
        "serviced_by", "servicing_outcome", "service_notes", "serviced_at",
        "vibration_snapshot", "temperature_snapshot",
    )
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for alert in alerts:
        writer.writerow({key: "" if alert.get(key) is None else alert.get(key) for key in columns})
    output.seek(0)
    filename = mill.lower().replace(" ", "-") + "-alert-log.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/mills/{mill}/alerts")
def get_mill_alert_log(
    mill: str,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    validate_mill(mill)
    require_database()
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="Start date must be before end date")
    return {
        "total": count_mill_alerts(mill, start_date, end_date),
        "alerts": fetch_mill_alerts(mill, start_date, end_date, limit, offset),
    }


@app.post("/api/mills/{mill}/alerts/{alert_id}/service")
def submit_servicing_feedback(mill: str, alert_id: int, feedback: ServicingFeedback):
    validate_mill(mill)
    require_database()
    serviced_by = feedback.serviced_by.strip()
    if len(serviced_by) < 2:
        raise HTTPException(status_code=422, detail="Enter at least two non-space characters for the servicing name")
    alert = save_alert_feedback(
        alert_id=alert_id,
        mill=mill,
        serviced_by=serviced_by,
        outcome=feedback.outcome,
        service_notes=feedback.service_notes.strip(),
    )
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found for this mill")
    model_status = {
        "trained": False,
        "samples": 0,
        "message": "Model updates are disabled until sensor tags and calibration data are verified.",
    }
    return {"saved": True, "model": model_status}

# WebSocket Endpoint: Stream continuous telemetry without page refreshes
@app.websocket("/ws/telemetry/{mill}")
@app.websocket("/ws/telemetry/{mill}/{equipment}")
async def stream_telemetry(websocket: WebSocket, mill: str, equipment: str = "Mill Main Control"):
    if mill not in MILL_UNITS:
        await websocket.close(code=1008, reason="Mill is not configured")
        return
    inventory = get_mill_inventory(mill)
    asset = next((item for item in inventory["equipment"] if item["name"] == equipment), None)
    if asset is None:
        await websocket.close(code=1008, reason="Equipment inventory is not configured")
        return

    await manager.connect(websocket)
    try:
        while True:
            elapsed = asyncio.get_running_loop().time()
            sample_time = datetime.now(timezone.utc).isoformat()
            sensors = build_sensor_readings(asset["sensors"], elapsed)
            payload = {
                "mill": mill,
                "equipment": equipment,
                "source": "DEMO DATA (SIMULATED)",
                "sample_time": sample_time,
                "prediction": {
                    "available": False,
                    "severity": "NOT CONFIGURED",
                    "anomaly_score": None,
                    "score_label": "No calibrated model configured",
                    "diagnostic_comments": "Model output is unavailable until engineering-approved sensor mapping and model validation are supplied.",
                },
                "sensors": sensors,
            }
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(1) # Smooth 1-second continuous stream tick
    except WebSocketDisconnect:
        manager.disconnect(websocket)