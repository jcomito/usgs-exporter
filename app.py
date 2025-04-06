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
    "63680": ("usgs_turbidity_fnu", "Turbidity in FNU"),
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
    end = datetime.datetime.utcnow()
    start = end - datetime.timedelta(hours=2)

    url = (
        f"https://waterservices.usgs.gov/nwis/iv/?site={SITE_ID}"
        f"&parameterCd={','.join(PARAM_CODES)}"
        f"&startDT={start.isoformat()}Z"
        f"&endDT={end.isoformat()}Z"
        f"&format=json"
    )

    try:
        logging.info(f"Fetching USGS data for site {SITE_ID}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        series_list = data.get("value", {}).get("timeSeries", [])

        for series in series_list:
            param = str(series["variable"]["variableCode"][0]["value"])
            site_name = series["sourceInfo"].get("siteName", "unknown")

            values = []
            for value_block in series.get("values", []):
                values.extend(value_block.get("value", []))

            if values:
                val_str = values[-1].get("value")
                if val_str and val_str != "-999999":
                    try:
                        val = float(val_str)
                        if param in gauges:
                            gauges[param].labels(site=SITE_ID, site_name=site_name).set(
                                val
                            )
                            logging.info(
                                f"Set {param} = {val} for site {SITE_ID} ({site_name})"
                            )
                    except ValueError:
                        logging.warning(f"Invalid float value for {param}: {val_str}")
            else:
                logging.warning(f"No data for param {param}")

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
