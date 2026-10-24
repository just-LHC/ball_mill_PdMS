import os
import ssl
import time
from datetime import datetime, timedelta
import urllib3
import pandas as pd
import requests

# Bypass SSL inspection for test/corporate gateway environments
ssl._create_default_https_context = ssl._create_unverified_context
os.environ["PYTHONHTTPSVERIFY"] = "0"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================================================================
# 1. CONFIGURATION & WEBHOOK SETTINGS
# ==============================================================================
# Paste your Google Chat Space Webhook URL below:
GOOGLE_CHAT_WEBHOOK_URL = "https://chat.googleapis.com/v1/spaces/AAQAhCAZeVk/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=utVU99kndt6AZj8ytN8QmRwe2tbO8xLD7f5IrLQFV0s"

# Platform API Credentials
EMAIL = "justice.wiruu.ext@holcim.com"
PASSWORD = "wj0fgjx6"
BASE_URL = "https://v3back-demo.i-sense.io/api/i-sense-v3"
ASSET_IDS = []
ASSET_NAME = " Commande Broyeur 6 (Ref. 566-EP1)"  # [cite: 7]

# Polling Interval
POLL_INTERVAL_SECONDS = 20 * 60  # 20 minutes between gateway pushes[cite: 7]

# Alarm Thresholds
THRESHOLD_VELOCITY_CRITICAL = 7.0  # mm/s (NGV overall trip limit)[cite: 1, 9]
THRESHOLD_TEMP_CRITICAL = 60.0  # °C (Absolute high limit)[cite: 5]
THRESHOLD_TEMP_DELTA_20MIN = 5.0  # °C rise in a single 20-min cycle[cite: 5]
THRESHOLD_TEMP_DELTA_1HR = 15.0  # °C rise over a rolling 1-hour window[cite: 5]

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
# 2. AUTHENTICATION & SESSION MANAGEMENT
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
# 3. GOOGLE CHAT DISPATCHER (PORT 443 - ZERO FIREWALL BLOCKS)
# ==============================================================================
def send_google_chat_alert(alarms: list[str], summary_df: pd.DataFrame):
    """Formats and posts an immediate alert to Google Chat via HTTPS Webhook."""
    if not GOOGLE_CHAT_WEBHOOK_URL or "PASTE_YOUR" in GOOGLE_CHAT_WEBHOOK_URL:
        print(
            "[!] ERROR: Google Chat Webhook URL is not set in GOOGLE_CHAT_WEBHOOK_URL."
        )
        return

    # Build ASCII status table for the message block
    table_lines = [
        "```",
        f"{'Sensor':<7} | {'NGV (mm/s)':<11} | {'Temp (°C)':<9} | {'VCC (g)':<7} | {'Time'}",
        "-" * 55,
    ]
    for _, row in summary_df.iterrows():
        sensor = str(row.get("sensor_position", "N/A"))
        vel = row.get("Velocity (mm/s)")
        temp = row.get("Temperature (°C)")
        vcc = row.get("VCC_G (g)")
        ts = str(row.get("timestamp", "N/A"))[-8:]  # Keep HH:MM:SS

        vel_str = (
            f"{vel:.2f}" if isinstance(vel, (int, float)) and pd.notna(vel) else "nan"
        )
        temp_str = (
            f"{temp:.1f}"
            if isinstance(temp, (int, float)) and pd.notna(temp)
            else "nan"
        )
        vcc_str = (
            f"{vcc:.1f}" if isinstance(vcc, (int, float)) and pd.notna(vcc) else "nan"
        )

        table_lines.append(
            f"{sensor:<7} | {vel_str:<11} | {temp_str:<9} | {vcc_str:<7} | {ts}"
        )
    table_lines.append("```")

    table_block = "\n".join(table_lines)
    alarms_block = "\n".join([f"🔴 *{a}*" for a in alarms])

    message_text = (
        f"🚨 *CRITICAL TRIP THRESHOLD BREACH*\n"
        f"**Asset:** {ASSET_NAME}\n"  # [cite: 7]
        f"**Alert Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"*Active Alarm Conditions:*\n"
        f"{alarms_block}\n\n"
        f"*Latest Sensor Snapshot:*\n"
        f"{table_block}\n"
        f"⚠️ _Action: Check control room console, verify bearing temperatures, and evaluate feed rate._"
    )

    try:
        response = requests.post(
            GOOGLE_CHAT_WEBHOOK_URL,
            json={"text": message_text},
            headers={"Content-Type": "application/json; charset=UTF-8"},
            timeout=15,
        )
        response.raise_for_status()
        print(f"[{datetime.now()}] Alert successfully delivered to Google Chat Space.")
    except Exception as e:
        print(f"[{datetime.now()}] ERROR posting to Google Chat: {e}")


# ==============================================================================
# 4. TELEMETRY FETCHING (6-HOUR ROLLING LOOKBACK)
# ==============================================================================
def fetch_recent_measurements(session: requests.Session) -> pd.DataFrame:
    """Fetches the last 6 hours of measurements to ensure latest packets are captured."""
    now = datetime.now()
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
# 5. THRESHOLD EVALUATION (HANDLES SPARSE IoT PACKETS)
# ==============================================================================
def evaluate_thresholds(df: pd.DataFrame) -> tuple[list[str], pd.DataFrame]:
    """Isolates each sensor, extracts latest valid values, and checks thresholds."""
    alarms = []
    latest_rows = []

    for sensor_id, sensor_df in df.groupby("sensor_position"):
        s_df = sensor_df.sort_values(by="timestamp").copy()

        vel_col = "Velocity (mm/s)"
        temp_col = "Temperature (°C)"
        vcc_col = "VCC_G (g)"

        # Pull clean series without NaNs from sparse intermediate packets
        vel_series = (
            s_df[vel_col].dropna() if vel_col in s_df else pd.Series(dtype=float)
        )
        temp_series = (
            s_df[temp_col].dropna() if temp_col in s_df else pd.Series(dtype=float)
        )
        vcc_series = (
            s_df[vcc_col].dropna() if vcc_col in s_df else pd.Series(dtype=float)
        )

        latest_vel = vel_series.iloc[-1] if not vel_series.empty else None
        latest_temp = temp_series.iloc[-1] if not temp_series.empty else None
        latest_vcc = vcc_series.iloc[-1] if not vcc_series.empty else None
        latest_time = s_df["timestamp"].iloc[-1]

        sensor_name = str(sensor_id)

        latest_rows.append(
            {
                "sensor_position": sensor_name,
                "Velocity (mm/s)": latest_vel,
                "Temperature (°C)": latest_temp,
                "VCC_G (g)": latest_vcc,
                "timestamp": latest_time,
            }
        )

        # Check 1: NGV Over-Velocity Limit (>= 11.0 mm/s)
        if latest_vel is not None and latest_vel >= THRESHOLD_VELOCITY_CRITICAL:
            alarms.append(
                f"[{sensor_name}] Velocity NGV = {latest_vel:.2f} mm/s "
                f"(Trip limit: {THRESHOLD_VELOCITY_CRITICAL} mm/s)"
            )

        # Check 2: Absolute High Temperature (>= 70.0 °C)
        if latest_temp is not None and latest_temp >= THRESHOLD_TEMP_CRITICAL:
            alarms.append(
                f"[{sensor_name}] Temp = {latest_temp:.1f} °C "
                f"(Trip limit: {THRESHOLD_TEMP_CRITICAL} °C)"
            )

        # Check 3: Temperature Deltas
        if len(temp_series) >= 2:
            cur_t = temp_series.iloc[-1]
            prev_t = temp_series.iloc[-2]
            step_delta = cur_t - prev_t

            # 20-min cycle rise
            if step_delta >= THRESHOLD_TEMP_DELTA_20MIN:
                alarms.append(
                    f"[{sensor_name}] Rapid Rise: +{step_delta:.1f} °C in 20 min "
                    f"({prev_t:.1f} °C -> {cur_t:.1f} °C)"
                )

            # Rolling 1-hour window rise
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
                        f"[{sensor_name}] Thermal Runaway: +{hour_delta:.1f} °C in ~1 hr "
                        f"({old_t:.1f} °C -> {cur_t:.1f} °C)"
                    )

    summary_df = pd.DataFrame(latest_rows)
    return alarms, summary_df


# ==============================================================================
# 6. MAIN EXECUTION LOOP
# ==============================================================================
def main():
    print("=" * 65)
    print(f"GOOGLE CHAT WATCHDOG ACTIVE FOR: {ASSET_NAME}")  # [cite: 7]
    print(
        f"Trip Thresholds: NGV >= {THRESHOLD_VELOCITY_CRITICAL} mm/s | Temp >= {THRESHOLD_TEMP_CRITICAL} °C"
    )  # [cite: 1, 5]
    print(
        f"Temp Deltas: >= +{THRESHOLD_TEMP_DELTA_20MIN} °C / 20min | >= +{THRESHOLD_TEMP_DELTA_1HR} °C / 1hr"
    )  # [cite: 5]
    print("=" * 65)

    session = get_authenticated_session()

    while True:
        cycle_start = time.time()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now_str}] Polling platform for new gateway transmission...")

        try:
            try:
                df = fetch_recent_measurements(session)
            except PermissionError:
                print("  -> Session expired. Re-authenticating...")
                session = get_authenticated_session()
                df = fetch_recent_measurements(session)

            if df.empty:
                print("  -> Warning: No data received in the 6-hour lookback window.")
            else:
                alarms, summary_df = evaluate_thresholds(df)

                # Print summary to laptop console
                print("  -> Latest Packet Summary:")
                for _, row in summary_df.iterrows():
                    vel = row.get("Velocity (mm/s)")
                    temp = row.get("Temperature (°C)")
                    vel_str = f"{vel:.2f} mm/s" if pd.notna(vel) else "nan"
                    temp_str = f"{temp:.1f} °C" if pd.notna(temp) else "nan"
                    print(
                        f"     * {row['sensor_position']:<6}: NGV = {vel_str:<12} Temp = {temp_str}"
                    )

                if alarms:
                    print(
                        f"\n[!] BREACH DETECTED: {len(alarms)} active alarm condition(s)!"
                    )
                    for alarm in alarms:
                        print(f"    - {alarm}")
                    send_google_chat_alert(alarms, summary_df)
                else:
                    print("  -> Status Normal: All channels within temporary limits.")

        except Exception as e:
            print(f"[{datetime.now()}] ERROR during execution cycle: {e}")

        # Sleep precisely until the next 20-minute cycle
        elapsed = time.time() - cycle_start
        sleep_sec = max(0, POLL_INTERVAL_SECONDS - elapsed)
        print(f"Sleeping for {sleep_sec / 60:.1f} minutes until next check...")
        time.sleep(sleep_sec)


if __name__ == "__main__":
    main()
