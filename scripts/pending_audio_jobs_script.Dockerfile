FROM python:3.12.3-slim-bullseye

ENV PYTHONUNBUFFERED True
ENV APP_HOME /app
WORKDIR $APP_HOME

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch FIRST, and then transformers
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.6.0
RUN pip install --no-cache-dir transformers==4.48.0

# Copy only the requirements.txt file for caching pip install step
COPY app/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt \
    && rm -rf ~/.cache/pip

# REMOVE any pre-existing model cache in case it was accidentally baked into a previous layer
RUN rm -rf /app/model_cache

# Copy entire project
COPY . ./

# Just in case, wipe it again after copying files
RUN rm -rf /app/model_cache

# Set the command to run the script
CMD ["python3", "process_pending_jobs.py"]
