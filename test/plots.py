import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ==================== SENSOR SELECTION ====================
# Option A: Plot all sensors across the ball mill
# SELECTED_SENSORS = "ALL"

# Option B: Pick specific sensors to compare (edit the list as needed)
SELECTED_SENSORS = ["1RV", "2RV", "3RV", "4RV","5RV", "6RV", "7RV", "8RV", "9RV", "10RV", "11RV", "12RV"]

# ==================== ADDITIONAL OPTIONS ====================
# Set to True to filter out mill downtime / stoppage events (Acceleration < 0.08g)
EXCLUDE_STOPPAGES = False

CSV_FILE = "ball_mill_ml_dataset.csv"
OUTPUT_DIR = "custom_sensor_plots"
BINS_ACC = 60
BINS_TEMP = 50
BINS_VEL = 50
# ============================================================


def load_dataset(csv_path):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Could not find '{csv_path}' in {os.getcwd()}")
        
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Ensure consistent sensor position labels
    if "sensor_position" not in df.columns:
        df = df.sort_values(by=["timestamp", "measure_id"]).reset_index(drop=True)
        df["sensor_idx"] = df.groupby("timestamp").cumcount()
        df["sensor_position"] = df["sensor_idx"].apply(lambda i: f"Sensor {i+1:02d}")

    return df


def resolve_sensor_selection(df, selection):
    """
    Validates and extracts requested sensors from the dataset.
    """
    all_available = sorted(df["sensor_position"].dropna().unique().tolist())
    
    if selection is None or str(selection).strip().upper() == "ALL":
        return all_available
        
    if isinstance(selection, (list, tuple, set)):
        valid = [s for s in selection if s in all_available]
        missing = [s for s in selection if s not in all_available]
        
        if missing:
            print(f"[Warning] Sensor(s) not found in dataset: {missing}")
            print(f"          Available sensors: {all_available}")
            
        if not valid:
            raise ValueError(f"None of the requested sensors {selection} were found in the dataset.")
            
        return valid

    raise ValueError("SELECTED_SENSORS must be 'ALL' or a list of names, e.g. ['Sensor 01', 'Sensor 02']")


def plot_comparative_histogram(df, sensors, feature_name, unit, output_path, n_bins=60):
    """
    Overlays stepped density distributions of all target sensors on a single graph.
    """
    fig, ax = plt.subplots(figsize=(14, 6.5))
    fig.patch.set_facecolor("white")

    subset = df[df["sensor_position"].isin(sensors)]
    clean_vals = subset[feature_name].dropna()

    if clean_vals.empty:
        print(f"[Warning] No data found for {feature_name}. Skipping plot.")
        plt.close(fig)
        return

    # Dynamic bins spanning only the selected sensors' min-to-max range
    bins = np.linspace(clean_vals.min(), clean_vals.max(), n_bins)
    cmap = plt.get_cmap("tab20", max(len(sensors), 2))

    for i, sensor in enumerate(sensors):
        sensor_data = df[df["sensor_position"] == sensor][feature_name].dropna()
        if sensor_data.empty:
            continue

        ax.hist(
            sensor_data,
            bins=bins,
            histtype="step",
            linewidth=1.9,
            density=True,
            label=f"{sensor} (n={len(sensor_data)})",
            color=cmap(i % 20),
            alpha=0.9
        )

    sensor_count_label = f"({len(sensors)} Sensors)" if len(sensors) > 1 else f"({sensors[0]})"
    ax.set_title(f"Comparative Distribution: {feature_name} {sensor_count_label}", fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel(f"{feature_name} [{unit}]", fontsize=11, fontweight="semibold")
    ax.set_ylabel("Probability Density (Normalized)", fontsize=11, fontweight="semibold")
    ax.grid(True, linestyle="--", alpha=0.5)

    ax.legend(
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        borderaxespad=0,
        frameon=True,
        fontsize=10,
        title="Active Sensors",
        title_fontsize=11
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"✔ Saved: {output_path}")


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df = load_dataset(CSV_FILE)

    # Optional filter to remove stopped mill states
    if EXCLUDE_STOPPAGES:
        print("[Info] Filtering out mill stoppage events (Acceleration < 0.08g)...")
        df = df[df["Acceleration (g)"] >= 0.08]

    target_sensors = resolve_sensor_selection(df, SELECTED_SENSORS)
    print(f"[Run] Plotting distributions for {len(target_sensors)} sensor(s): {target_sensors}")

    # Graph 1: Acceleration
    plot_comparative_histogram(
        df=df,
        sensors=target_sensors,
        feature_name="Acceleration (g)",
        unit="g",
        output_path=os.path.join(OUTPUT_DIR, "compare_acceleration.png"),
        n_bins=BINS_ACC
    )

    # Graph 2: Temperature
    plot_comparative_histogram(
        df=df,
        sensors=target_sensors,
        feature_name="Temperature (°C)",
        unit="°C",
        output_path=os.path.join(OUTPUT_DIR, "compare_temperature.png"),
        n_bins=BINS_TEMP
    )
    # Graph 2: VCC
    plot_comparative_histogram(
        df=df,
        sensors=target_sensors,
        feature_name="Velocity (mm/s)",
        unit="mm/s",
        output_path=os.path.join(OUTPUT_DIR, "compare_velocity.png"),
        n_bins=BINS_VEL
    )