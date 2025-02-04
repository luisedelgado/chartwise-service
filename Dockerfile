FROM --platform=linux/amd64 python:3.12.3-slim-bullseye

ENV PYTHONUNBUFFERED=True
ENV APP_HOME=/app
WORKDIR $APP_HOME

# Install ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements.txt separately for caching
COPY app/requirements.txt requirements.txt

# Install dependencies
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy entire project
COPY . ./

EXPOSE 8000
