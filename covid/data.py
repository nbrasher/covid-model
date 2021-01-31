from google.cloud import firestore
from datetime import datetime
import pandas as pd
import numpy as np
import arviz as az
import warnings
import time
import re

warnings.simplefilter("ignore", category=FutureWarning)

START_DATE = pd.Timestamp("2020-06-01")

# Known days of bad test data in historical Texas records
BAD_TEST_DATES = [
    pd.Timestamp("2020-06-03"),
    pd.Timestamp("2020-06-10"),
    pd.Timestamp("2020-06-12"),
    pd.Timestamp("2020-07-16"),
    pd.Timestamp("2020-07-28"),
]


def get_county_cases() -> pd.DataFrame:
    """ Texas state case data by county
    """
    county_cases = pd.read_excel(
        io="https://dshs.texas.gov/coronavirus/TexasCOVID19DailyCountyCaseCountData.xlsx",
        skiprows=2,
        nrows=254,
        index_col=0,
    )

    county_cases.columns = [
        datetime.strptime(re.search(r"[\r\n\s]+([\d\-]+)", c)[1], "%m-%d-%Y")
        for c in county_cases.columns
    ]

    return county_cases.loc[:, START_DATE:]


def get_county_tests() -> pd.DataFrame:
    """ Texas state total test data by county
    """
    county_tests = pd.read_excel(
        io="https://dshs.texas.gov/coronavirus/TexasCOVID-19CumulativeTestsOverTimebyCounty.xlsx",
        skiprows=1,
        nrows=254,
        index_col=0,
    )
    county_tests2 = pd.read_excel(
        io="https://dshs.texas.gov/coronavirus/TexasCOVID-19CumulativeTestsbyCounty.xlsx",
        skiprows=1,
        nrows=254,
        index_col=0,
    )
    county_tests.columns = [
        datetime.strptime(
            "2020 " + re.search(r"Tests Through ([\w\s]+)", c)[1], "%Y %B %d"
        )
        for c in county_tests.columns
    ]
    county_tests = pd.concat([county_tests, county_tests2], axis=1)
    return county_tests.loc[:, START_DATE:]


def get_state_data() -> pd.DataFrame:
    """ Texas state-wide data from Covid Tracking project
    """
    tx_data = pd.read_csv("https://covidtracking.com/api/v1/states/tx/daily.csv")
    tx_data = tx_data.set_index(
        tx_data["date"].map(lambda x: datetime.strptime(str(x), "%Y%m%d"))
    ).sort_index()
    return tx_data.loc[START_DATE:]


def get_tx_covid_data():
    """ Clean and parse Texas state data

        Returns
        --------
        new_cases (pd.DataFrame) : Daily new cases by county
        new_tests (pd.DataFrame) : Daily new tests by county
        tx_data (pd.DataFrame) : Texas-wide data from Covid tracking project
    """
    # Get raw case and test data
    county_cases = get_county_cases()
    county_tests = get_county_tests()

    # Get Texas-wide data from covid tracking project
    tx_data = get_state_data()

    # Get daily difference for new case counts
    new_cases = county_cases.diff(axis=1)

    # Drop dates with missing or nonsense values
    county_tests = county_tests.drop(BAD_TEST_DATES, axis=1)
    new_tests = county_tests.diff(axis=1)
    new_tests = pd.concat(
        [new_tests, pd.DataFrame(columns=BAD_TEST_DATES, dtype="float64")]
    )
    new_tests = new_tests.sort_index(axis=1)

    # Drop negative values and linearly interpolate
    new_tests[new_tests < 0] = np.nan
    new_tests = new_tests.interpolate(method="time", axis=1)

    # Fixing known errors in Bexar test reporting
    # Generative model ignores days with zero tests
    new_cases.loc["Bexar", pd.Timestamp("2020-07-15")] = 0
    new_tests.loc["Bexar", pd.Timestamp("2020-07-15")] = 0
    new_cases.loc["Bexar", pd.Timestamp("2020-07-17")] = 691

    return new_cases, new_tests, tx_data


def scale_to_positives(data, observed_mean):
    return observed_mean / np.mean(data) * data


def summarize_inference_data(inference_data: az.InferenceData):
    """ Summarizes an inference_data object into the form that we publish on
        rt.live """
    posterior = inference_data.posterior
    hdi_mass = 80
    hpdi = az.hdi(posterior.r_t, hdi_prob=hdi_mass / 100).r_t

    observed_positive = inference_data.constant_data.observed_positive.to_series()
    tests = inference_data.constant_data.tests.to_series()
    normalized_positive = observed_positive / tests.clip(0.1 * tests.max())

    summary = pd.DataFrame(
        data={
            "date": posterior.date.values,
            "mean": posterior.r_t.mean(["draw", "chain"]),
            "median": posterior.r_t.median(["chain", "draw"]),
            f"lower_{hdi_mass}": hpdi[:, 0],
            f"upper_{hdi_mass}": hpdi[:, 1],
            "infections": scale_to_positives(
                posterior.infections.mean(["draw", "chain"]), observed_positive.mean()
            ),
            "test_adjusted_positive": scale_to_positives(
                posterior.test_adjusted_positive.mean(["draw", "chain"]),
                observed_positive.mean(),
            ),
            "test_adjusted_positive_raw": scale_to_positives(
                normalized_positive, observed_positive.mean()
            ),
            "positive": observed_positive,
            "tests": tests,
        }
    )
    return summary.to_dict(orient="list")


def to_firestore(doc: str, data: dict):
    """ Upload model results to Cloud Firestore
    """
    db = firestore.Client(project="texas-covid")
    doc_ref = db.collection("model-results").document(doc)

    if not doc_ref.get().exists:
        doc_ref.create({"created": time.time()})

    doc_ref.update(data)
