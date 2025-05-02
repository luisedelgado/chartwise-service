FROM python:3.13-slim

ENV PYTHONUNBUFFERED=True

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY listener.py .

ENTRYPOINT ["python", "listener.py"]
