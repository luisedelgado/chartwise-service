# Use the specified Python base image
FROM python:3.12.3-slim-bullseye

# Set environment variables
ENV PYTHONUNBUFFERED True
ENV APP_HOME /app

# Set the working directory inside the container
WORKDIR $APP_HOME

# Copy only the requirements.txt file for caching pip install step
COPY app/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the application code
COPY app/ ./app/
COPY scripts/process_pending_jobs.py ./

# Set the command to run the script
CMD ["python", "process_pending_jobs.py"]
