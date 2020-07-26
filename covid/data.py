from datetime import datetime
import pandas as pd
import numpy as np
import arviz as az
import re


def get_tx_covid_data():
    ''' Download and parse Covid cases and test data from Texas
        Dept of Health

        Returns
        --------
        new_cases (pd.DataFrame) : Daily new cases by county
        new_tests (pd.DataFrame) : Daily new tests by county
        tx_data (pd.DataFrame) : Texas-wide data from Covid tracking project
    '''
    # Get raw case and test data
    county_cases = pd.read_excel(
        io='https://dshs.texas.gov/coronavirus/TexasCOVID19DailyCountyCaseCountData.xlsx',
        skiprows=2,
        nrows=254, 
        index_col=0
    )
    county_tests = pd.read_excel(
        io='https://dshs.texas.gov/coronavirus/TexasCOVID-19CumulativeTestsOverTimebyCounty.xlsx',
        skiprows=1,
        nrows=254, 
        index_col=0,
    )
    
    # Get Texas-wide data from covid tracking project
    tx_data = pd.read_csv('https://covidtracking.com/api/v1/states/tx/daily.csv')
    tx_data = tx_data.set_index(
        tx_data['date'].map(
            lambda x: datetime.strptime(str(x), '%Y%m%d'))
    ).sort_index()

    # Drop population column and parse date headers
    if 'Population' in county_cases.columns:
        county_cases = county_cases.drop('Population', axis=1)

    if county_cases.columns.dtype == 'O':
        county_cases.columns = [datetime.strptime(
                        '2020-'+re.search(r'[\r\n\s]+([\d\-]+)', c)[1],
                        '%Y-%m-%d'
                    )
                    for c in county_cases.columns]

    if county_tests.columns.dtype == 'O':
        county_tests.columns = [
            datetime.strptime(
                '2020 ' + re.search(r'Tests Through ([\w\s]+)', c)[1],
                '%Y %B %d'
            )
            for c in county_tests.columns
        ]

    # Get daily difference for new case counts
    new_cases = county_cases.diff(axis=1)

    # Drop dates with missing or nonsense values
    BAD_TEST_DATES = [
        pd.Timestamp('2020-05-01'),
        pd.Timestamp('2020-05-03'),
        pd.Timestamp('2020-05-05'),
        pd.Timestamp('2020-05-23'),
        pd.Timestamp('2020-06-03'),
        pd.Timestamp('2020-06-10'),
        pd.Timestamp('2020-06-12'),
        pd.Timestamp('2020-07-16'),
    ]

    county_tests = county_tests.drop(BAD_TEST_DATES, axis=1)
    new_tests = county_tests.diff(axis=1)

    # Drop April 21 as there is no prior data
    new_tests = new_tests.drop(pd.Timestamp('2020-04-21'), axis=1)

    new_tests = pd.concat([
        new_tests,
        pd.DataFrame(columns=BAD_TEST_DATES, dtype='float64')
    ])
    new_tests = new_tests.sort_index(axis=1)

    # Drop negative values and linearly interpolate
    new_tests[new_tests < 0] = np.nan
    new_tests = new_tests.interpolate(
        method='time', axis=1)

    # Fixing known errors in Bexar test reporting
    # Generative model ignores days with zero tests
    new_cases.loc['Bexar', pd.Timestamp('2020-07-15')] = 0
    new_tests.loc['Bexar', pd.Timestamp('2020-07-15')] = 0
    new_cases.loc['Bexar', pd.Timestamp('2020-07-17')] = 691

    return new_cases, new_tests, tx_data


def summarize_inference_data(inference_data: az.InferenceData):
    """ Summarizes an inference_data object into the form that we publish on
        rt.live """
    posterior = inference_data.posterior
    hdi_mass = 80
    hpdi = az.hdi(posterior.r_t, hdi_prob=hdi_mass / 100).r_t

    observed_positive = inference_data.constant_data.observed_positive.to_series()
    scale_to_positives = lambda data: observed_positive.mean() / np.mean(data) * data
    tests = inference_data.constant_data.tests.to_series()
    normalized_positive = observed_positive / tests.clip(0.1 * tests.max())

    summary = pd.DataFrame(
        data={
            "mean": posterior.r_t.mean(["draw", "chain"]),
            "median": posterior.r_t.median(["chain", "draw"]),
            f"lower_{hdi_mass}": hpdi[:, 0],
            f"upper_{hdi_mass}": hpdi[:, 1],
            "infections": scale_to_positives(
                posterior.infections.mean(["draw", "chain"])
            ),
            "test_adjusted_positive": scale_to_positives(
                posterior.test_adjusted_positive.mean(["draw", "chain"])
            ),
            "test_adjusted_positive_raw": scale_to_positives(normalized_positive),
            "positive": observed_positive,
            "tests": tests,
        },
        index=pd.Index(posterior.date.values, name="date"),
    )
    return summary
