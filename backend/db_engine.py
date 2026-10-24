# backend/db_engine.py
import os
import pandas as pd
from sqlalchemy import create_engine, text

# Database access requires deployment configuration.
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and ":6543" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace(":6543", ":5432")
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

_engine = None

def get_db_engine():
    global _engine
    if _engine is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL must be set to use database-backed features.")
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return _engine

def init_alert_db_table():
    """Ensures the alert and feedback tables and retention indexes exist."""
    engine = get_db_engine()
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS plc_alerts (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        mill VARCHAR(50),
        equipment VARCHAR(100),
        severity VARCHAR(20),
        issue TEXT,
        status VARCHAR(50),
        operator_notes TEXT,
        vibration_snapshot FLOAT,
        temperature_snapshot FLOAT
    );
    """
    try:
        with engine.begin() as conn:
            conn.execute(text(create_table_sql))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS plc_alert_feedback (
                    id SERIAL PRIMARY KEY,
                    alert_id INTEGER NOT NULL REFERENCES plc_alerts(id) ON DELETE CASCADE,
                    serviced_by VARCHAR(120) NOT NULL,
                    outcome VARCHAR(32) NOT NULL CHECK (outcome IN ('GENUINE_ISSUE', 'FALSE_ALARM')),
                    service_notes TEXT,
                    serviced_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS plc_alerts_timestamp_idx ON plc_alerts (timestamp)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS plc_alert_feedback_alert_id_idx ON plc_alert_feedback (alert_id)"))
    except Exception:
        print("[DB INIT ERROR] Could not initialize alert storage schema.")
        raise


def purge_expired_alert_data():
    """Delete alert and feedback rows older than six calendar months."""
    engine = get_db_engine()
    with engine.begin() as conn:
        cutoff = conn.execute(text("SELECT CURRENT_TIMESTAMP - INTERVAL '6 months'")).scalar_one()
        feedback_result = conn.execute(text("""
            DELETE FROM plc_alert_feedback
            WHERE alert_id IN (
                SELECT id FROM plc_alerts WHERE timestamp < :cutoff
            );
        """), {"cutoff": cutoff})
        alerts_result = conn.execute(text("""
            DELETE FROM plc_alerts WHERE timestamp < :cutoff;
        """), {"cutoff": cutoff})
    return {
        "cutoff": cutoff.isoformat(),
        "alerts_deleted": alerts_result.rowcount or 0,
        "feedback_deleted": feedback_result.rowcount or 0,
    }

def fetch_mill_alerts(mill: str, start_date=None, end_date=None, limit: int = 50, offset: int = 0):
    engine = get_db_engine()
    query = text("""
        SELECT alerts.*,
               feedback.serviced_by,
               feedback.outcome AS servicing_outcome,
               feedback.service_notes,
               feedback.serviced_at
        FROM plc_alerts AS alerts
        LEFT JOIN LATERAL (
            SELECT serviced_by, outcome, service_notes, serviced_at
            FROM plc_alert_feedback
            WHERE alert_id = alerts.id
            ORDER BY serviced_at DESC, id DESC
            LIMIT 1
        ) AS feedback ON TRUE
        WHERE alerts.mill = :mill
          AND (:start_date IS NULL OR alerts.timestamp >= :start_date)
          AND (:end_date IS NULL OR alerts.timestamp < CAST(:end_date AS date) + INTERVAL '1 day')
        ORDER BY alerts.timestamp DESC, alerts.id DESC
        LIMIT :limit OFFSET :offset;
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {
            "mill": mill,
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit,
            "offset": offset,
        }).mappings().all()
    return [dict(row) for row in rows]

def count_mill_alerts(mill: str, start_date=None, end_date=None):
    engine = get_db_engine()
    query = text("""
        SELECT COUNT(*)
        FROM plc_alerts
        WHERE mill = :mill
          AND (:start_date IS NULL OR timestamp >= :start_date)
          AND (:end_date IS NULL OR timestamp < CAST(:end_date AS date) + INTERVAL '1 day');
    """)
    with engine.connect() as conn:
        return conn.execute(query, {
            "mill": mill,
            "start_date": start_date,
            "end_date": end_date,
        }).scalar_one()

def save_alert_feedback(alert_id: int, mill: str, serviced_by: str, outcome: str, service_notes: str = ""):
    engine = get_db_engine()
    with engine.begin() as conn:
        alert = conn.execute(text("""
            SELECT id, equipment FROM plc_alerts WHERE id = :alert_id AND mill = :mill
        """), {"alert_id": alert_id, "mill": mill}).mappings().first()
        if alert is None:
            return None

        conn.execute(text("""
            INSERT INTO plc_alert_feedback (alert_id, serviced_by, outcome, service_notes)
            VALUES (:alert_id, :serviced_by, :outcome, :service_notes)
        """), {
            "alert_id": alert_id,
            "serviced_by": serviced_by,
            "outcome": outcome,
            "service_notes": service_notes,
        })
        conn.execute(text("""
            UPDATE plc_alerts
            SET status = 'SERVICED', operator_notes = :operator_notes
            WHERE id = :alert_id
        """), {
            "alert_id": alert_id,
            "operator_notes": f"{serviced_by}: {outcome.replace('_', ' ')}. {service_notes}".strip(),
        })
        return dict(alert)

def fetch_labeled_feedback(mill: str, equipment: str):
    engine = get_db_engine()
    query = text("""
        SELECT alerts.vibration_snapshot, alerts.temperature_snapshot, feedback.outcome
        FROM plc_alert_feedback AS feedback
        JOIN plc_alerts AS alerts ON alerts.id = feedback.alert_id
        WHERE alerts.mill = :mill AND alerts.equipment = :equipment
          AND alerts.vibration_snapshot IS NOT NULL
          AND alerts.temperature_snapshot IS NOT NULL
        ORDER BY feedback.serviced_at;
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"mill": mill, "equipment": equipment}).mappings().all()
    return [dict(row) for row in rows]

def fetch_all_alerts():
    """Fetches all logged alerts from Supabase PostgreSQL."""
    engine = get_db_engine()
    query = "SELECT * FROM plc_alerts ORDER BY timestamp DESC;"
    try:
        return pd.read_sql(query, con=engine).to_dict(orient="records")
    except Exception as e:
        print(f"[DB FETCH ERROR] {e}")
        return []

def fetch_alert_overview(limit: int, offset: int, before_timestamp=None, before_id=None):
    """Fetches alert totals, recent critical alerts, and one page of alert rows."""
    engine = get_db_engine()
    counts_query = text("""
        SELECT
            COUNT(*) AS total_count,
            COUNT(*) FILTER (WHERE UPPER(COALESCE(severity, '')) = 'CRITICAL') AS critical_count,
            COUNT(*) FILTER (WHERE UPPER(COALESCE(severity, '')) = 'WARNING') AS warning_count
        FROM plc_alerts
        WHERE mill IN ('Mill 1', 'Mill 4', 'Mill 5', 'Mill 6');
    """)
    critical_query = text("""
        SELECT * FROM plc_alerts
        WHERE mill IN ('Mill 1', 'Mill 4', 'Mill 5', 'Mill 6')
          AND UPPER(COALESCE(severity, '')) = 'CRITICAL'
        ORDER BY timestamp DESC, id DESC
        LIMIT 3;
    """)
    cursor_filter = ""
    alerts_params = {"limit": limit, "offset": offset}
    if before_timestamp is not None and before_id is not None:
        cursor_filter = "AND (timestamp, id) < (:before_timestamp, :before_id)"
        alerts_params.update({"before_timestamp": before_timestamp, "before_id": before_id})
    alerts_query = text(f"""
        SELECT * FROM plc_alerts
        WHERE mill IN ('Mill 1', 'Mill 4', 'Mill 5', 'Mill 6')
          {cursor_filter}
        ORDER BY timestamp DESC, id DESC
        LIMIT :limit OFFSET :offset;
    """)

    with engine.connect() as connection:
        counts = connection.execute(counts_query).mappings().one()
        critical_alerts = connection.execute(critical_query).mappings().all()
        alerts = connection.execute(alerts_query, alerts_params).mappings().all()

    return {
        "total_count": counts["total_count"],
        "critical_count": counts["critical_count"],
        "warning_count": counts["warning_count"],
        "critical_alerts": [dict(alert) for alert in critical_alerts],
        "alerts": [dict(alert) for alert in alerts],
    }

def log_alert_to_db(mill: str, equipment: str, severity: str, issue: str, vib: float, temp: float):
    """Inserts a new critical alert into central PostgreSQL storage."""
    engine = get_db_engine()
    query = """
    INSERT INTO plc_alerts (timestamp, mill, equipment, severity, issue, status, operator_notes, vibration_snapshot, temperature_snapshot)
    VALUES (NOW(), :mill, :equipment, :severity, :issue, 'ACTIVE / REQUIRES ACTION', 'Automated ML Alert — Pending Sign-off', :vib, :temp);
    """
    try:
        with engine.begin() as conn:
            conn.execute(text(query), {
                "mill": mill,
                "equipment": equipment,
                "severity": severity,
                "issue": issue,
                "vib": vib,
                "temp": temp
            })
    except Exception as e:
        print(f"[DB LOG ERROR] {e}")