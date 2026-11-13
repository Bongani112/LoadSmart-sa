import os
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(
    title="LoadSmart SA API",
    description="Smart Electricity Management, Outage Planning & Backup Runtime API",
    version="1.0.0"
)

# Allow frontend prototype (index.html) to communicate with the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        database=os.getenv("PGDATABASE", "loadsmart_sa"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
        port=os.getenv("PGPORT", "5432"),
        cursor_factory=RealDictCursor
    )

# --- Pydantic Request Schemas ---

class OutageReportCreate(BaseModel):
    location_id: int
    title: str
    outage_type: str = Field(..., example="Unexpected Power Outage")
    notes: Optional[str] = None

class ApplianceCalcRequest(BaseModel):
    name: str
    watts: float = Field(..., gt=0)
    daily_hours: float = Field(..., gt=0, le=24)
    tariff_zar: float = Field(default=3.00, gt=0)

class BackupCalcRequest(BaseModel):
    battery_capacity_wh: float = Field(..., gt=0)
    charge_percentage: float = Field(..., ge=0, le=100)
    connected_load_watts: float = Field(..., gt=0)
    inverter_efficiency: float = Field(default=0.90, gt=0, le=1.0)

# --- API Endpoints ---

@app.get("/")
def health_check():
    return {"status": "online", "service": "LoadSmart SA API"}

@app.get("/api/outages")
def get_outages(location_id: Optional[int] = None):
    """Fetch official schedules and community-reported outages."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if location_id:
                cur.execute("""
                    SELECT o.*, l.province, l.municipality, l.suburb
                    FROM outages o
                    JOIN locations l ON o.location_id = l.id
                    WHERE o.location_id = %s
                    ORDER BY o.start_time DESC;
                """, (location_id,))
            else:
                cur.execute("""
                    SELECT o.*, l.province, l.municipality, l.suburb
                    FROM outages o
                    JOIN locations l ON o.location_id = l.id
                    ORDER BY o.start_time DESC;
                """)
            return cur.fetchall()
    finally:
        conn.close()

@app.post("/api/outages/report")
def report_community_outage(report: OutageReportCreate):
    """Submit an unverified community outage or infrastructure report."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO outages (location_id, title, outage_type, source_type, is_verified, start_time, notes)
                VALUES (%s, %s, %s, 'COMMUNITY', FALSE, %s, %s)
                RETURNING *;
            """, (report.location_id, report.title, report.outage_type, datetime.now(), report.notes))
            new_record = cur.fetchone()
            conn.commit()
            return {
                "message": "Community report recorded as unverified.",
                "disclaimer": "Report dangerous fallen cables directly to Eskom (08600 37566) or municipal emergency services.",
                "data": new_record
            }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.post("/api/appliances/calculate")
def calculate_appliance_usage(payload: ApplianceCalcRequest):
    """Calculate daily and monthly kWh consumption and ZAR cost."""
    daily_kwh = (payload.watts * payload.daily_hours) / 1000.0
    monthly_kwh = daily_kwh * 30
    monthly_cost_zar = monthly_kwh * payload.tariff_zar

    return {
        "appliance": payload.name,
        "daily_kwh": round(daily_kwh, 3),
        "monthly_kwh": round(monthly_kwh, 2),
        "estimated_monthly_cost_zar": round(monthly_cost_zar, 2),
        "high_consumption_flag": monthly_kwh > 60
    }

@app.post("/api/backup/calculate")
def calculate_backup_runtime(payload: BackupCalcRequest):
    """Estimate backup battery runtime in hours (both ideal and efficiency-adjusted)."""
    usable_wh = payload.battery_capacity_wh * (payload.charge_percentage / 100.0)
    ideal_hours = usable_wh / payload.connected_load_watts
    practical_hours = (usable_wh * payload.inverter_efficiency) / payload.connected_load_watts

    return {
        "usable_energy_wh": round(usable_wh, 1),
        "ideal_runtime_hours": round(ideal_hours, 2),
        "practical_runtime_hours": round(practical_hours, 2),
        "warning": "High load detected — battery will drain rapidly." if payload.connected_load_watts > 1000 else None
    }