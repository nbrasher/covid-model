#!/bin/bash

# This BASH script will download the updated Texas case count data and process
eval "$(conda shell.bash hook)"
conda activate texas_covid

# Set proper working directory
cd "$(dirname $BASH_SOURCE)"
cd ".."

# Run notebook with updated data
mv data/final_results.pkl data/old_results.pkl
python scripts/process_data.py

# Upload to S3
aws s3 cp data/final_results.pkl s3://texas-covid --profile personal

# Re-load site
cd "../texas_covid"
heroku run "/app/scripts/restart.sh"