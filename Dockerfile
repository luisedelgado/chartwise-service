# Use the specified Python base image
FROM python:3.12.3-slim-bullseye

ENV PYTHONUNBUFFERED True
ENV APP_HOME /app

WORKDIR $APP_HOME

# Install ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Copy only the requirements.txt file first for caching pip install step
COPY app/requirements.txt ./app/requirements.txt

# Install the Python dependencies
RUN pip install --no-cache-dir -r app/requirements.txt

# Now copy the rest of the application code
COPY . ./

EXPOSE 8000
