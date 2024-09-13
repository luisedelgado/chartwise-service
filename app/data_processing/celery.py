import os

from celery import Celery

redis_url = os.getenv('CELERY_BROKER_URL')

celery_app = Celery(
    'chartwise',
    broker=redis_url,
    backend=redis_url
)

# example invocation in background add.delay(3, 4)
@celery_app.task
def add(x, y):
    return x + y
