# Texas Covid Model
This model is an adaptation of the model from [Rt.live](https://github.com/rtcovidlive/covid-model) adapted for Texas metro areas.

## Setup Instructions
For raw case count data go to the [Texas DSHS](https://dshs.texas.gov/coronavirus/) webpage.

In order to run the model locally:
1. Install requirements with `pip install -r requirements.txt`
1. Launch the model with `python main.py`

To run the model locally with Docker:
1. Build the image with `docker build -t covid-model .`
1. Run the image with `docker run -it covid-model`

To deploy the docker image
1. Build with `docker build -t gcr.io/texas-covid/covid-model .`
1. Push with `docker push gcr.io/texas-covid/covid-model`
