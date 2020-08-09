#!/usr/bin/env python
# coding: utf-8
import os
import sys
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from google.cloud.storage import Client

sys.path.append('.')
from covid.models.generative import GenerativeModel
from covid.data import get_tx_covid_data, summarize_inference_data

# Group county data into metro areas:
METROS = {
    'Houston': ['Harris', 'Montgomery', 'Fort Bend', 'Brazoria', 'Galveston'],
    'DFW': ['Dallas', 'Tarrant', 'Collin', 'Denton'],
    'Austin': ['Travis', 'Williamson'],
    'San Antonio': ['Bexar'],
    'San Marcos': ['Hays'],
    'El Paso': ['El Paso'],
    'Rio Grande Valley': ['Hidalgo', 'Cameron'],
    'Lubbock': ['Lubbock'],
}

# Output file, bucket and credntial file names
OUT_FILE = 'final_results.pkl'
OUT_FOLDER = '/tmp'
BUCKET = 'texas-covid.appspot.com'

if __name__ == '__main__':
    # Read in raw Daily data
    print('Downloading new data...', end='', flush=True)
    new_cases, new_tests, tx_data = get_tx_covid_data()
    print('complete')

    # Calculate models for all counties
    models = dict()
    results = dict()

    # Get start and end dates
    TX_DATA_START = pd.Timestamp('2020-03-17')
    TX_DATA_END = pd.Timestamp('2020-04-21')
    LAST_DAY = max(new_cases.columns[-1], new_tests.columns[-1])

    print('County data exists through', LAST_DAY.date())
    print('Covid tracking project data exists through', tx_data.index[-1].date())
    
    if (LAST_DAY.date() != tx_data.index[-1].date()):
        raise RuntimeError('Date mismatch, re-run when data is up-to-date')
    
    print('Running updates...')
    for region, counties in METROS.items():
        print(region)
        
        df = pd.concat(
            [new_cases.loc[counties].sum(), 
            new_tests.loc[counties].sum()],
            axis=1
        )
        df.columns = ['positive', 'total']

        # Fill-in missing test totals from state-wide data
        df.loc[TX_DATA_START:TX_DATA_END, 'total'] = tx_data.loc[
            TX_DATA_START:TX_DATA_END, 'total'] * df.loc[
            TX_DATA_END + pd.Timedelta(days=1), 'total'] / tx_data.loc[
            TX_DATA_END + pd.Timedelta(days=1), 'total']

        if np.isnan(df.loc[LAST_DAY, 'total']):
            df.loc[LAST_DAY, 'total'] = tx_data.loc[
                LAST_DAY, 'total'] * df.loc[(LAST_DAY - pd.Timedelta(days=7)):
                    (LAST_DAY - pd.Timedelta(days=1)), 'total'].sum() /\
                 tx_data.loc[(LAST_DAY - pd.Timedelta(days=7)):
                    (LAST_DAY - pd.Timedelta(days=1)), 'total'].sum()
        
        # If any mistaken values result in negatives, zero out so model ignores
        df['positive'] = np.where(
            df['positive'].values > 0,
            df['positive'].values,
            np.zeros_like(df['positive'].values)
        )

        gm = GenerativeModel(region, df.loc[TX_DATA_START: LAST_DAY])
        gm.sample()
        results[region] = summarize_inference_data(gm.inference_data)
        print('\n')

    # Add model run timestamp and save data
    results['timestamp'] = datetime.now(timezone.utc).astimezone()
    with open(os.path.join(OUT_FOLDER, OUT_FILE), 'wb') as f:
        pickle.dump(results, f)
    
    # Send to google cloud storage
    print('Writing results file to cloud storage...', end='', flush=True)
    bucket = Client().bucket(BUCKET)
    bucket.blob(OUT_FILE).upload_from_filename(
        os.path.join(OUT_FOLDER, OUT_FILE)
    )
    print('complete')
