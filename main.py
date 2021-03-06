import os
import time
import logging
import numpy as np
import pandas as pd
from datetime import datetime

from covid.model import GenerativeModel
from covid.data import get_tx_covid_data, summarize_inference_data, to_firestore

log = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

# Group county data into metro areas:
METROS = {
    "houston": ["Harris", "Montgomery", "Fort Bend", "Brazoria", "Galveston"],
    "dallas_fort_worth": ["Dallas", "Tarrant", "Collin", "Denton"],
    "austin": ["Travis", "Williamson"],
    "san_antonio": ["Bexar"],
    "san_marcos": ["Hays"],
    "el_paso": ["El Paso"],
    "rio_grande_valley": ["Hidalgo", "Cameron"],
    "lubbock": ["Lubbock"],
}


def main():
    # Read in raw Daily data
    log.info("Downloading new data...")
    new_cases, new_tests, tx_data = get_tx_covid_data()

    # Get start and end dates
    LAST_DAY = max(new_cases.columns[-1], new_tests.columns[-1])

    log.info(f"County data exists through {LAST_DAY.date()}")
    log.info(f"Covid tracking project data exists through {tx_data.index[-1].date()}")

    if LAST_DAY.date() != tx_data.index[-1].date():
        LAST_DAY = min(LAST_DAY, tx_data.index[-1])
        log.warning(f"Date mismatch, using {LAST_DAY.date()}")

    # Firestore results keyed by time of model run
    fs_doc = datetime.now().strftime("%Y-%m-%d")

    log.info("Running regional models")
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
        to_firestore(fs_doc, {region: summarize_inference_data(gm.inference_data)})

    to_firestore(fs_doc, {"updated": time.time()})


if __name__ == "__main__":
    main()
