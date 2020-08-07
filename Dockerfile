# Official Ubuntu image
FROM python:3.7

# Allow statements and log messages to immediately appear in the Cloud Run logs
ENV PYTHONUNBUFFERED True

# Install BLAS and dev requirements
RUN apt-get update && apt-get install -y \
  build-essential \
  gfortran \
  liblapack-dev \
  libopenblas-dev \
  gcc \
  libc6-dev

# Copy application dependency manifests to the container image.
# Copying this separately prevents re-running pip install on every code change.
COPY requirements.txt ./

# Install production dependencies.
RUN pip install -r requirements.txt

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

# Run the model training script on startup
CMD exec python main.py