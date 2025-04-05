import os
import requests
import datetime
from flask import Flask, Response
from prometheus_client import Gauge, generate_latest
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# Default to Vermilion River at Vermilion, OH
SITE_ID = os.environ.get("SITE_ID", "04199500")
PARAM_CODES = os.environ.get("PARAMS", "00060").split(",")

# Map USGS parameter codes to Prometheus-friendly names and descriptions
PARAM_MAP = {
    "00060": ("usgs_discharge_cfs", "Streamflow in cubic feet per second"),
    "00010": ("usgs_temp_celsius", "Water temperature in Celsius"),
    "00065": ("usgs_gage_height_ft", "Gage height in feet"),
    "00076": ("usgs_turbidity_ntu", "Turbidity in NTU"),
    # Add more as needed
}

# Create Prometheus gauges for each parameter
gauges = {}
for param in PARAM_CODES:
    metric_name, desc = PARAM_MAP.get(
        param, (f"usgs_param_{param}", f"USGS parameter {param}")
    )
    gauges[param] = Gauge(metric_name, desc, ["site", "site_name"])

site_name = None  # will populate from API response


def fetch_usgs():
    global site_name

    now = datetime.datetime.utcnow()
    start = now.replace(minute=0, second=0, microsecond=0)
    end = now
    url = (
        f"https://waterservices.usgs.gov/nwis/iv/?site={SITE_ID}"
        f"&parameterCd={','.join(PARAM_CODES)}"
        f"&startDT={start.isoformat()}Z"
        f"&endDT={end.isoformat()}Z"
        f"&format=json"
    )

    try:
        logging.info(
            f"Fetching USGS data for site {SITE_ID} and parameters {PARAM_CODES}"
        )
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        for series in data.get("value", {}).get("timeSeries", []):
            param = series["variable"]["variableCode"][0]["value"]
            values = series["values"][0]["value"]
            if not site_name:
                site_name = series["sourceInfo"]["siteName"]
            if values:
                val = float(values[-1]["value"])
                if param in gauges:
                    gauges[param].labels(site=SITE_ID, site_name=site_name).set(val)
                    logging.info(
                        f"Set {param} = {val} for site {SITE_ID} ({site_name})"
                    )
    except Exception as e:
        logging.error(f"Error fetching/parsing USGS data: {e}")


@app.route("/metrics")
def metrics():
    fetch_usgs()
    return Response(generate_latest(), mimetype="text/plain")


@app.route("/")
def home():
    return f"USGS Exporter is running for site {SITE_ID}. Visit /metrics for Prometheus data."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
