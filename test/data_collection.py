import os
import ssl
import requests
import urllib3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Global SSL bypass for test environment[cite: 1, 15]
ssl._create_default_https_context = ssl._create_unverified_context
os.environ["PYTHONHTTPSVERIFY"] = "0"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================= Configuration =================
EMAIL = "justice.wiruu.ext@holcim.com"
PASSWORD = "wj0fgjx6"
BASE_URL = "https://v3back-demo.i-sense.io/api/i-sense-v3"

# Asset ID configuration[cite: 1, 3, 15]
ASSET_IDS = [92]

# Date range in 'YYYY-MM-DD HH:mm:ss' format required by NV endpoint[cite: 3, 15]
START_DATE = "2022-04-00 00:00:00"
END_DATE = "2026-10-29 00:00:00"

# Output folder for individual sensor CSV files
INDIVIDUAL_SENSOR_DIR = "sensor_datasets_BM5"

# Feature ID mapping per Section 5 of API documentation[cite: 1, 4, 15]
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
# =================================================


def plot_two_sensors(
    df,
    sensor_col="sensor_position",
    time_col="timestamp",
    sensor_ids=None,
    features=None,
    normalize=False,
    save_dir="sensor_plots",
    show=False,
):
    """
    Renders 2 distinct graphs (one per sensor), with all measured features
    overlaid on the same graph with a full legend.
    """
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)

    available_sensors = df[sensor_col].dropna().unique().tolist()
    if len(available_sensors) < 2:
        raise ValueError(
            f"Dataset must contain at least 2 distinct sensors, found: {available_sensors}"
        )

    if sensor_ids is None:
        sensor_ids = available_sensors[:2]
    elif len(sensor_ids) != 2:
        raise ValueError(
            f"Expected exactly 2 sensors, got {len(sensor_ids)}: {sensor_ids}"
        )

    if features is None:
        features = [name for name in FEATURE_MAPPING.values() if name in df.columns]

    print(f"\n[Plotting] Generating 2 separate graphs for sensors: {sensor_ids}...")

    saved_paths = []
    for sensor in sensor_ids:
        sensor_data = df[df[sensor_col] == sensor].sort_values(by=time_col).copy()
        if sensor_data.empty:
            print(f"   -> Warning: No records found for sensor '{sensor}'")
            continue

        fig, ax = plt.subplots(figsize=(13, 6))
        fig.patch.set_facecolor("white")

        for feat in features:
            if feat not in sensor_data.columns:
                continue
            y = sensor_data[feat]

            if normalize:
                min_v, max_v = y.min(), y.max()
                y = (y - min_v) / (max_v - min_v) if max_v > min_v else y * 0
                label_name = f"{feat} (normalized)"
            else:
                label_name = feat

            ax.plot(
                sensor_data[time_col], y, label=label_name, linewidth=1.4, alpha=0.85
            )

        ylabel = "Normalized Scale (0-1)" if normalize else "Measured Engineering Units"
        ax.set_ylabel(ylabel, fontsize=11, fontweight="semibold")
        ax.set_xlabel("Acquisition Timestamp", fontsize=11, fontweight="semibold")
        ax.set_title(
            f"All Features: Sensor {sensor}", fontsize=13, fontweight="bold", pad=12
        )
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="upper right", framealpha=0.9, fontsize=9)

        plt.tight_layout()

        if save_dir:
            safe_name = str(sensor).replace("/", "_").replace("\\", "_")
            out_file = os.path.join(save_dir, f"sensor_graph_{safe_name}.png")
            plt.savefig(out_file, dpi=150)
            saved_paths.append(out_file)
            print(f"   -> Saved: {out_file}")

        if show:
            plt.show()

        plt.close(fig)

    return saved_paths


session = requests.Session()
session.verify = False

try:
    # 1. Authenticate[cite: 1, 2, 15]
    print("[1/4] Authenticating with I-SENSE API...")
    res = session.post(
        f"{BASE_URL}/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    res.raise_for_status()
    token = res.json().get("token") or res.json()["data"]["token"]
    session.headers.update(
        {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    )

    # 2. Date Range Verification[cite: 3, 15]
    if not START_DATE or not END_DATE:
        now = datetime.now()
        END_DATE = now.strftime("%Y-%m-%d %H:%M:%S")
        START_DATE = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n[2/4] Fetching NV measurements from {START_DATE} to {END_DATE}...")
    all_rows = []

    # 3. Retrieve NV measurements per asset[cite: 3, 4, 15]
    for asset_id in ASSET_IDS:
        url = f"{BASE_URL}/tenant/assets/{asset_id}/nv-measurements"
        params = {"startDate": START_DATE, "endDate": END_DATE}

        response = session.get(url, params=params, timeout=30)
        if response.status_code != 200:
            print(f"   -> Asset {asset_id}: Failed (Status {response.status_code})")
            continue

        res_json = response.json()
        data = res_json.get("data", {})
        if not data:
            print(f"   -> Asset {asset_id}: No data points returned.")
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

        print(f"   -> Asset {asset_id}: Successfully processed.")

    if not all_rows:
        raise ValueError(
            "No measurement data could be retrieved. Verify date range and asset IDs."
        )

    # 4. Assemble and Export Datasets[cite: 1, 15]
    print("\n[3/4] Generating structured datasets...")
    df_final = pd.DataFrame(all_rows)
    df_final["timestamp"] = pd.to_datetime(df_final["timestamp"])
    df_final = df_final.sort_values(by=["timestamp", "sensor_position"])

    # Export combined master dataset[cite: 15]
    master_output_name = "ball_mill_ml_dataset1.csv"
    df_final.to_csv(master_output_name, index=False)
    print(f"✔ Saved combined master dataset to '{master_output_name}'")

    # Export individual CSV files per sensor
    os.makedirs(INDIVIDUAL_SENSOR_DIR, exist_ok=True)
    print(
        f"\n[Exporting] Writing individual sensor CSVs into '{INDIVIDUAL_SENSOR_DIR}/'..."
    )
    for sensor_id, sensor_df in df_final.groupby("sensor_position"):
        safe_sensor_id = (
            str(sensor_id).replace("/", "_").replace("\\", "_").replace(" ", "_")
        )
        sensor_csv_path = os.path.join(
            INDIVIDUAL_SENSOR_DIR, f"sensor_{safe_sensor_id}.csv"
        )
        sensor_df.to_csv(sensor_csv_path, index=False)
        print(f"   -> Saved: {sensor_csv_path} ({len(sensor_df)} rows)")

    # 5. Plot 2 Sensors Across All Features[cite: 15]
    print("\n[4/4] Executing Sensor Visualization...")
    plot_two_sensors(
        df=df_final,
        sensor_col="sensor_position",
        time_col="timestamp",
        sensor_ids=None,
        normalize=False,
        save_dir="two_graphs_output",
        show=False,
    )

except Exception as e:
    print(f"\n[Error]: {e}")
