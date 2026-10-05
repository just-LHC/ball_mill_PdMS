MILL_UNITS = ("Mill 1", "Mill 4", "Mill 5", "Mill 6")


def _sensor(name: str, kind: str, unit: str, location: str, source_label: str | None = None, component: str | None = None):
    return {
        "name": name,
        "kind": kind,
        "unit": unit,
        "location": location,
        "tag": None,
        "source_label": source_label,
        "component": component,
    }


def _bearing_sensors(equipment: str, kinds: tuple[str, ...], source_label: str | None, component: str | None = None):
    units = {"temperature": "°C", "vibration": "mm/s"}
    labels = {"temperature": "Temperature", "vibration": "Vibration"}
    sensors = []
    for position in ("IN", "OUT"):
        location = f"{equipment} {position} bearing"
        for kind in kinds:
            sensors.append(_sensor(
                f"{location.title()} {labels[kind]}",
                kind,
                units[kind],
                location,
                source_label,
                component,
            ))
    return sensors


def _numbered_sensors(equipment: str, kind: str, count: int, source_label: str | None = None, component: str | None = None):
    unit = "°C" if kind == "temperature" else "mm/s"
    label = "Temperature" if kind == "temperature" else "Vibration"
    return [
        _sensor(
            f"{equipment} {label} Sensor {index}",
            kind,
            unit,
            f"{equipment} {label} channel {index}",
            source_label,
            component,
        )
        for index in range(1, count + 1)
    ]


MILL_ASSETS = {
    "Mill 1": {
        "Mill Main Control": (
            _bearing_sensors("Mill Main Control", ("vibration",), None)
            + _numbered_sensors("Mill Main Control", "temperature", 1)
        ),
    },
    "Mill 4": {
        "Mill Main Control": (
            _bearing_sensors("Mill Main Control", ("vibration",), None)
            + _numbered_sensors("Mill Main Control", "temperature", 1)
        ),
    },
    "Mill 5": {
        "Mill Main Control": (
            _numbered_sensors("Gearbox 1 Bearing", "temperature", 10, "LHC", "Gearbox 1")
            + _numbered_sensors("Gearbox 1 Bearing", "vibration", 10, "OCP", "Gearbox 1")
            + _numbered_sensors("Gearbox 2 Bearing", "temperature", 4, "LHC", "Gearbox 2")
            + _numbered_sensors("Gearbox 2 Bearing", "vibration", 4, "OCP", "Gearbox 2")
            + _numbered_sensors("Gearbox 1 Motor Bearing", "vibration", 2, component="Gearbox 1")
            + _numbered_sensors("Gearbox 2 Motor Winding", "temperature", 2, component="Gearbox 2")
        ),
        "Separator Filter Fan": _bearing_sensors("Separator Filter Fan", ("temperature", "vibration"), None),
    },
    "Mill 6": {
        "Mill Main Control": (
            _bearing_sensors("Motor", ("temperature", "vibration"), "OCP")
            + _numbered_sensors("Gearbox", "temperature", 9, "OCP")
            + _numbered_sensors("Gearbox", "vibration", 9, "OCP")
        ),
        "Slide Shoe Bearing": _numbered_sensors("Slide Shoe Bearing", "temperature", 8, "HLC"),
        "Main Filter Fan": _bearing_sensors("Main Filter Fan", ("vibration",), "HCL"),
        "Separator Filter Fan": _bearing_sensors("Separator Filter Fan", ("temperature", "vibration"), None),
        "Dynamic Separator": _bearing_sensors("Dynamic Separator", ("vibration",), None),
    },
}
MILL_DISPLAY_NAMES = {"Mill 1": "Mill 1 (White Cement)"}


def get_mill_inventory(mill: str):
    assets = MILL_ASSETS.get(mill)
    if assets is None:
        return {
            "mill": mill,
            "display_name": MILL_DISPLAY_NAMES.get(mill, mill),
            "status": "NOT_CONFIGURED",
            "equipment": [],
        }

    return {
        "mill": mill,
        "display_name": MILL_DISPLAY_NAMES.get(mill, mill),
        "status": "PARTIALLY_CONFIGURED",
        "equipment": [
            {
                "name": name,
                "sensors": [
                    {**sensor, "channel_key": f"channel-{index + 1}"}
                    for index, sensor in enumerate(sensors)
                ],
            }
            for name, sensors in assets.items()
        ],
    }


def get_equipment_for_mill(mill: str):
    return [asset["name"] for asset in get_mill_inventory(mill)["equipment"]]