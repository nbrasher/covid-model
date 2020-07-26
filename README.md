# Texas Covid Model
This model is an adaptation of the model from [Rt.live](https://github.com/rtcovidlive/covid-model) adapted for Texas metro areas.

## Setup Instructions
For raw case count data go to the [Texas DSHS](https://dshs.texas.gov/coronavirus/) webpage.

In order to run the model locally:
1. Install requirements with `conda env create -f requirements.yml`
1. Launch the model with `scripts/process_data.sh`