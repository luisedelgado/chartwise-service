# https://hub.docker.com/_/python
FROM python:3.12.3-slim-bullseye

ENV PYTHONUNBUFFERED True
ENV APP_HOME /app

# Create a non-root user (celeryuser)
RUN useradd -ms /bin/bash celeryuser

WORKDIR $APP_HOME
COPY . ./

RUN pip install --no-cache-dir -r app/requirements.txt

# Change ownership of the app directory to the non-root user
RUN chown -R celeryuser:celeryuser $APP_HOME

# Switch to the non-root user
USER celeryuser

EXPOSE 8000
