"""
One-time script: delete all InfluxDB data written by the simulator.

Since simulator data and real ESP32 data share the same measurements and tags,
we delete by time range: everything from epoch to now = simulator data only.

Run once before connecting real ESP32 nodes:
    python scripts/purge_simulator_data.py
"""

import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from influxdb_client import InfluxDBClient

load_dotenv()

URL = os.getenv("INFLUXDB_URL", "")
TOKEN = os.getenv("INFLUXDB_TOKEN", "")
ORG = os.getenv("INFLUXDB_ORG", "Tameer")
BUCKET = os.getenv("INFLUXDB_BUCKET", "tameer")

MEASUREMENTS = [
    "soil_readings",
    "air_readings",
    "automation_events",
    "camera_data",
    "irrigation",
]

START = "1970-01-01T00:00:00Z"
STOP = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    if not URL or not TOKEN:
        print("ERROR: INFLUXDB_URL and INFLUXDB_TOKEN must be set in .env")
        sys.exit(1)

    print(f"\nTarget bucket : {ORG}/{BUCKET}")
    print(f"Delete range  : {START} → {STOP}")
    print(f"Measurements  : {', '.join(MEASUREMENTS)}")
    print("\nThis will permanently delete ALL simulator data from InfluxDB.")
    confirm = input("Type 'yes' to proceed: ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        sys.exit(0)

    with InfluxDBClient(url=URL, token=TOKEN, org=ORG) as client:
        delete_api = client.delete_api()
        for measurement in MEASUREMENTS:
            predicate = f'_measurement="{measurement}"'
            delete_api.delete(
                start=START,
                stop=STOP,
                predicate=predicate,
                bucket=BUCKET,
                org=ORG,
            )
            print(f"  Deleted: {measurement}")

    print("\nBucket is clean — ready for real ESP32 data.")


if __name__ == "__main__":
    main()
