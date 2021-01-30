from covid.data import get_county_cases, get_county_tests, get_state_data, START_DATE
from datetime import datetime
import pandas as pd


def test_county_cases():
    df = get_county_cases()

    assert isinstance(df, pd.DataFrame)
    assert isinstance(df.columns, pd.DatetimeIndex)
    assert df.columns[0] == START_DATE


def test_county_tests():
    df = get_county_tests()

    assert isinstance(df, pd.DataFrame)
    assert isinstance(df.columns, pd.DatetimeIndex)
    assert df.columns[0] == START_DATE


def test_state_data():
    df = get_state_data()

    assert isinstance(df, pd.DataFrame)
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index[0] == START_DATE
