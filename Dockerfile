# https://hub.docker.com/_/python
FROM python:3.12.3-slim-bullseye

ENV PYTHONUNBUFFERED True
ENV APP_HOME /app

WORKDIR $APP_HOME

# Copy only the requirements.txt file first for caching pip install step
COPY app/requirements.txt ./app/requirements.txt

# Install the dependencies
RUN pip install --no-cache-dir -r app/requirements.txt

# Now copy the rest of the application
COPY . ./

EXPOSE 8000
