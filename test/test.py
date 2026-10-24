import os
import smtplib
import ssl
import time
import urllib3
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd
import requests

# Global SSL bypass for test environment
ssl._create_default_https_context = ssl._create_unverified_context
os.environ["PYTHONHTTPSVERIFY"] = "0"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================================================================
# 1. CONFIGURATION & CREDENTIALS
# ==============================================================================
# Platform Credentials
EMAIL = "justice.wiruu.ext@holcim.com"
PASSWORD = "wj0fgjx6"
BASE_URL = "https://v3back-demo.i-sense.io/api/i-sense-v3"
ASSET_IDS = [87]
ASSET_NAME = "Harnais de Commande Broyeur (Ref. 566-EP1)"

# Execution & Watchdog Settings
POLL_INTERVAL_SECONDS = 20 * 60  # 20 minutes between gateway updates

# Vibration & Temperature Thresholds
THRESHOLD_VELOCITY_CRITICAL = 7.0  # mm/s (NGV trip limit)
THRESHOLD_TEMP_CRITICAL = 60.0  # °C (Absolute high limit)
THRESHOLD_TEMP_DELTA_20MIN = 5.0  # °C sharp rise in a single 20-min cycle
THRESHOLD_TEMP_DELTA_1HR = 15.0  # °C rise over a rolling 1-hour window

# Email Notification Settings
SMTP_SERVER = "smtp.gmail.com"  # e.g., smtp.office365.com for Outlook
SMTP_PORT = 587
SENDER_EMAIL = "justice.wiruu.ext@holcim.com"
SENDER_PASSWORD = "zces tsvn wwaf izlp"  # Use an App Password, not standard password
ALERT_RECIPIENTS = [
    "justice.wiruu.ext@holcim.com",
    # "control_room_operator@holcim.com",
]

# Feature ID mapping per API documentation
FEATURE_MAPPING = {
    1: "Velocity (mm/s)",
    2: "Acceleration (g)",
    4: "VCC_G (g)",
    14: "K Factor",
    15: "Temperature (°C)",
    18: "Level (m)",
    31: "FC",
    32: "VC_G (g)",
    46: "Battery (%)",
    69: "Rpm",
    88: "Distance (mm)",
}


# ==============================================================================
# 2. AUTHENTICATION & RE-AUTHENTICATION
# ==============================================================================
def get_authenticated_session() -> requests.Session:
    """Authenticates and returns a requests.Session with an active Bearer token."""
    session = requests.Session()
    session.verify = False

    payload = {"email": EMAIL, "password": PASSWORD}
    res = session.post(f"{BASE_URL}/auth/login", json=payload, timeout=20)
    res.raise_for_status()

    token = res.json().get("token") or res.json()["data"]["token"]
    session.headers.update(
        {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    )
    return session


# ==============================================================================
# 3. EMAIL ALERT DISPATCHER
# ==============================================================================
def send_email_alert(alarms: list[str], latest_summary_df: pd.DataFrame):
    """Formats and sends an immediate HTML notification via SMTP."""
    subject = f"CRITICAL VIBRATION/TEMP ALERT: {ASSET_NAME}"

    # Build HTML table of current sensor states
    table_rows = ""
    for _, row in latest_summary_df.iterrows():
        sensor = row.get("sensor_position", "Unknown")
        vel = row.get("Velocity (mm/s)", "N/A")
        temp = row.get("Temperature (°C)", "N/A")
        vcc = row.get("VCC_G (g)", "N/A")
        ts = row.get("timestamp", "N/A")

        vel_str = f"{vel:.2f} mm/s" if isinstance(vel, (int, float)) else str(vel)
        temp_str = f"{temp:.1f} °C" if isinstance(temp, (int, float)) else str(temp)
        vcc_str = f"{vcc:.1f} g" if isinstance(vcc, (int, float)) else str(vcc)

        table_rows += f"""
        <tr>
            <td style="padding:6px;border:1px solid #ddd;"><b>{sensor}</b></td>
            <td style="padding:6px;border:1px solid #ddd;">{vel_str}</td>
            <td style="padding:6px;border:1px solid #ddd;">{temp_str}</td>
            <td style="padding:6px;border:1px solid #ddd;">{vcc_str}</td>
            <td style="padding:6px;border:1px solid #ddd;">{ts}</td>
        </tr>
        """

    alarm_bullets = "".join(f"<li><b>{a}</b></li>" for a in alarms)

    body_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #222;">
        <h2 style="color: #b30000; border-bottom: 2px solid #b30000;">CRITICAL DRIVE TRAIN TRIP ALERT</h2>
        <p><b>Asset:</b> {ASSET_NAME}</p>
        <p><b>Alert Trigger Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        
        <div style="background-color: #ffe6e6; border-left: 5px solid #cc0000; padding: 12px; margin: 15px 0;">
            <h3 style="margin-top: 0; color: #cc0000;">Active Alarm Conditions:</h3>
            <ul>{alarm_bullets}</ul>
        </div>

        <h3>Latest Readings Snapshot:</h3>
        <table style="border-collapse: collapse; width: 100%; max-width: 650px; text-align: left;">
            <tr style="background-color: #f2f2f2;">
                <th style="padding:6px;border:1px solid #ddd;">Sensor</th>
                <th style="padding:6px;border:1px solid #ddd;">Velocity (NGV)</th>
                <th style="padding:6px;border:1px solid #ddd;">Temperature</th>
                <th style="padding:6px;border:1px solid #ddd;">Peak Accel (VCC)</th>
                <th style="padding:6px;border:1px solid #ddd;">Packet Time</th>
            </tr>
            {table_rows}
        </table>
        
        <p style="margin-top: 20px; color: #777;">
            <i>This is an automated threshold watchdog executing locally from the plant monitoring laptop.</i>
        </p>
      </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(ALERT_RECIPIENTS)
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, ALERT_RECIPIENTS, msg.as_string())
        print(
            f"[{datetime.now()}] Alert email successfully delivered to: {ALERT_RECIPIENTS}"
        )
    except Exception as e:
        print(f"[{datetime.now()}] ERROR: Failed to dispatch email: {e}")


# ==============================================================================
# 4. TELEMETRY FETCHING (WIDENED ROLLING WINDOW)
# ==============================================================================
def fetch_recent_measurements(session: requests.Session) -> pd.DataFrame:
    """
    Fetches the last 6 hours of data to guarantee capturing recent transmissions
    even across transmission lulls, shift changes, or gateway latency.
    """
    now = datetime.now()
    # 6-hour lookback window ensures 07:02:00 packets are captured when running at 10:00
    start_str = (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
    end_str = (now + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")

    all_rows = []
    for asset_id in ASSET_IDS:
        url = f"{BASE_URL}/tenant/assets/{asset_id}/nv-measurements"
        params = {"startDate": start_str, "endDate": end_str}

        response = session.get(url, params=params, timeout=30)
        if response.status_code == 401:
            raise PermissionError("Token expired")
        if response.status_code != 200:
            print(f"  -> Asset {asset_id} query failed (HTTP {response.status_code})")
            continue

        data = response.json().get("data", {})
        if not data:
            continue

        for timestamp, sensor_dict in data.items():
            if not isinstance(sensor_dict, dict):
                continue
            for sensor_pos, features in sensor_dict.items():
                if not isinstance(features, dict):
                    continue
                row = {
                    "timestamp": timestamp,
                    "asset_id": asset_id,
                    "sensor_position": sensor_pos,
                }
                for fid_str, val in features.items():
                    fid = int(fid_str) if str(fid_str).isdigit() else fid_str
                    col_name = FEATURE_MAPPING.get(fid, f"Feature_{fid}")
                    row[col_name] = val
                all_rows.append(row)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.sort_values(by=["timestamp", "sensor_position"])


# ==============================================================================
# 5. THRESHOLD EVALUATION ENGINE (ROBUST TO SPARSE IoT PACKETS)
# ==============================================================================
def evaluate_thresholds(df: pd.DataFrame) -> tuple[list[str], pd.DataFrame]:
    """
    Groups strictly by sensor_position, forward-fills sparse metrics,
    and extracts the latest valid non-null engineering values.
    """
    alarms = []
    latest_rows = []

    for sensor_id, sensor_df in df.groupby("sensor_position"):
        # 1. Sort chronologically for this specific sensor
        s_df = sensor_df.sort_values(by="timestamp").copy()

        # 2. Extract valid non-null time series for Velocity and Temperature
        vel_col = "Velocity (mm/s)"
        temp_col = "Temperature (°C)"
        vcc_col = "VCC_G (g)"

        vel_series = (
            s_df[vel_col].dropna() if vel_col in s_df else pd.Series(dtype=float)
        )
        temp_series = (
            s_df[temp_col].dropna() if temp_col in s_df else pd.Series(dtype=float)
        )
        vcc_series = (
            s_df[vcc_col].dropna() if vcc_col in s_df else pd.Series(dtype=float)
        )

        # 3. Get the latest valid values
        latest_vel = vel_series.iloc[-1] if not vel_series.empty else None
        latest_temp = temp_series.iloc[-1] if not temp_series.empty else None
        latest_vcc = vcc_series.iloc[-1] if not vcc_series.empty else None

        # Determine the latest measurement timestamp
        latest_time = s_df["timestamp"].iloc[-1]

        sensor_name = str(sensor_id)

        # Build snapshot row for reporting and email tables
        latest_rows.append(
            {
                "sensor_position": sensor_name,
                "Velocity (mm/s)": latest_vel,
                "Temperature (°C)": latest_temp,
                "VCC_G (g)": latest_vcc,
                "timestamp": latest_time,
            }
        )

        # --- ALARM EVALUATIONS ---
        # 1. Overall Velocity Trip (NGV >= 11.0 mm/s)
        if latest_vel is not None and latest_vel >= THRESHOLD_VELOCITY_CRITICAL:
            alarms.append(
                f"[{sensor_name}] CRITICAL VELOCITY: {latest_vel:.2f} mm/s "
                f"(Exceeds trip limit of {THRESHOLD_VELOCITY_CRITICAL} mm/s)"
            )

        # 2. Absolute High Temperature Ceiling (Temp >= 70 °C)
        if latest_temp is not None and latest_temp >= THRESHOLD_TEMP_CRITICAL:
            alarms.append(
                f"[{sensor_name}] CRITICAL TEMPERATURE: {latest_temp:.1f} °C "
                f"(Exceeds ceiling of {THRESHOLD_TEMP_CRITICAL} °C)"
            )

        # 3. Dynamic Temperature Deltas (evaluated only across valid temp readings)
        if len(temp_series) >= 2:
            cur_t = temp_series.iloc[-1]
            prev_t = temp_series.iloc[-2]
            step_delta = cur_t - prev_t

            # Check 20-min consecutive packet spike
            if step_delta >= THRESHOLD_TEMP_DELTA_20MIN:
                alarms.append(
                    f"[{sensor_name}] RAPID 20-MIN TEMP RISE: +{step_delta:.1f} °C "
                    f"({prev_t:.1f} °C -> {cur_t:.1f} °C)"
                )

            # Check rolling 1-hour window (lookback 40–75 minutes)
            temp_df = s_df[[temp_col, "timestamp"]].dropna()
            one_hr_candidates = temp_df[
                (latest_time - temp_df["timestamp"])
                .dt.total_seconds()
                .between(40 * 60, 75 * 60)
            ]
            if not one_hr_candidates.empty:
                old_t = one_hr_candidates.iloc[0][temp_col]
                hour_delta = cur_t - old_t
                if hour_delta >= THRESHOLD_TEMP_DELTA_1HR:
                    alarms.append(
                        f"[{sensor_name}] THERMAL RUNAWAY: +{hour_delta:.1f} °C across ~1 hr "
                        f"({old_t:.1f} °C -> {cur_t:.1f} °C)"
                    )

    summary_df = pd.DataFrame(latest_rows)
    return alarms, summary_df


# ==============================================================================
# 6. MAIN WATCHDOG LOOP
# ==============================================================================
def main():
    print("=" * 70)
    print(f"STARTING 20-MIN IIoT WATCHDOG FOR {ASSET_NAME}")
    print(
        f"Thresholds: NGV >= {THRESHOLD_VELOCITY_CRITICAL} mm/s | Temp >= {THRESHOLD_TEMP_CRITICAL} °C"
    )
    print(
        f"Temp Deltas: >= +{THRESHOLD_TEMP_DELTA_20MIN} °C / 20min | >= +{THRESHOLD_TEMP_DELTA_1HR} °C / 1hr"
    )
    print("=" * 70)

    session = get_authenticated_session()

    while True:
        cycle_start = time.time()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now_str}] Polling platform for new gateway transmission...")

        try:
            try:
                df = fetch_recent_measurements(session)
            except PermissionError:
                print("  -> Session token expired. Re-authenticating...")
                session = get_authenticated_session()
                df = fetch_recent_measurements(session)

            if df.empty:
                print("  -> Warning: No telemetry points returned in the last 2 hours.")
            else:
                alarms, summary_df = evaluate_thresholds(df)

                # Console readout of latest values
                print("  -> Latest Packet Summary:")
                for _, row in summary_df.iterrows():
                    vel = row.get("Velocity (mm/s)", "N/A")
                    temp = row.get("Temperature (°C)", "N/A")
                    vel_str = (
                        f"{vel:.2f} mm/s" if isinstance(vel, (int, float)) else str(vel)
                    )
                    temp_str = (
                        f"{temp:.1f} °C"
                        if isinstance(temp, (int, float))
                        else str(temp)
                    )
                    print(
                        f"     * {row['sensor_position']:<6}: NGV = {vel_str:<12} Temp = {temp_str}"
                    )

                if alarms:
                    print(
                        f"\n[!] BREACH DETECTED: {len(alarms)} alarm condition(s) active!"
                    )
                    for alarm in alarms:
                        print(f"    - {alarm}")
                    send_email_alert(alarms, summary_df)
                else:
                    print("  -> Status Normal: All channels within temporary limits.")

        except Exception as e:
            print(f"[{datetime.now()}] ERROR during polling cycle: {e}")

        # Sleep until the next 20-minute transmission window
        elapsed = time.time() - cycle_start
        sleep_sec = max(0, POLL_INTERVAL_SECONDS - elapsed)
        print(f"Sleeping for {sleep_sec / 60:.1f} minutes until next check...")
        time.sleep(sleep_sec)


if __name__ == "__main__":
    main()
