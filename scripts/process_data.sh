#!/bin/bash

# This BASH script will download the updated Texas case count data and process
eval "$(conda shell.bash hook)"
conda activate texas_covid

# Set proper working directory
cd "$(dirname $BASH_SOURCE)"
cd ".."

# Avoid over-writing old results if they exist
FILE=data/final_results.pkl
if test -f "$FILE"; then
    mv "$FILE" data/old_results.pkl
fi

# Run updates, upload and re-start site if successful
if python scripts/process_data.py; then
    # Upload to S3
    aws s3 cp data/final_results.pkl s3://texas-covid

    # Re-load site
    cd "../texas_covid"
    heroku run "/app/scripts/restart.sh"
fi