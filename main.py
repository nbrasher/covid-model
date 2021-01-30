import os
import pickle
import logging
import numpy as np
import pandas as pd
from pytz import timezone
from datetime import datetime
from google.cloud.storage import Client

from covid.model import GenerativeModel
from covid.data import get_tx_covid_data, summarize_inference_data

log = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

# Group county data into metro areas:
METROS = {
    "Houston": ["Harris", "Montgomery", "Fort Bend", "Brazoria", "Galveston"],
    "DFW": ["Dallas", "Tarrant", "Collin", "Denton"],
    "Austin": ["Travis", "Williamson"],
    "San Antonio": ["Bexar"],
    "San Marcos": ["Hays"],
    "El Paso": ["El Paso"],
    "Rio Grande Valley": ["Hidalgo", "Cameron"],
    "Lubbock": ["Lubbock"],
}

# Output file, bucket and credntial file names
OUT_FILE = "final_results.pkl"
OUT_FOLDER = "/tmp"
BUCKET = "texas-covid.appspot.com"


def main():
    # Read in raw Daily data
    log.info("Downloading new data...")
    new_cases, new_tests, tx_data = get_tx_covid_data()

    results = {}

    # Get start and end dates
    LAST_DAY = max(new_cases.columns[-1], new_tests.columns[-1])

    log.info(f"County data exists through {LAST_DAY.date()}")
    log.info(f"Covid tracking project data exists through {tx_data.index[-1].date()}")

    if LAST_DAY.date() != tx_data.index[-1].date():
        LAST_DAY = min(LAST_DAY, tx_data.index[-1])
        log.warning(f"Date mismatch, using {LAST_DAY.date()}")

    log.info("Running updates...")
    for region, counties in METROS.items():
        log.info(region)

        df = pd.concat(
            [new_cases.loc[counties].sum(), new_tests.loc[counties].sum()], axis=1
        )
        df.columns = ["positive", "total"]
        start_smooth = LAST_DAY - pd.Timedelta(days=7)
        end_smooth = LAST_DAY - pd.Timedelta(days=1)
        # Fill-in missing test totals from state-wide data
        if np.isnan(df.loc[LAST_DAY, "total"]):
            df.loc[LAST_DAY, "total"] = (
                tx_data.loc[LAST_DAY, "total"]
                * df.loc[start_smooth:end_smooth, "total"].sum()
                / tx_data.loc[start_smooth:end_smooth, "total"].sum()
            )

        # If any mistaken values result in negatives, zero out so model ignores
        df["positive"] = np.where(
            df["positive"].values > 0,
            df["positive"].values,
            np.zeros_like(df["positive"].values),
        )

        gm = GenerativeModel(region, df.loc[:LAST_DAY])
        gm.sample()
        results[region] = summarize_inference_data(gm.inference_data)

    # Add model run timestamp and save data
    results["timestamp"] = datetime.now(timezone("US/Central"))
    with open(os.path.join(OUT_FOLDER, OUT_FILE), "wb") as f:
        pickle.dump(results, f)

    # Send to google cloud storage
    # print('Writing results file to cloud storage...', end='', flush=True)
    # bucket = Client().bucket(BUCKET)
    # bucket.blob(OUT_FILE).upload_from_filename(
    #     os.path.join(OUT_FOLDER, OUT_FILE)
    # )
    # print('complete')


if __name__ == "__main__":
    main()
