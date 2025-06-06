import os
import redis
import time

# Initialize Redis client
redis_client = redis.StrictRedis(
    host=os.environ["REDIS_HOST"],
    port=int(os.environ["REDIS_PORT"]),
    password=os.environ["REDIS_AUTH_TOKEN"],
    db=0,
    decode_responses=True,
    ssl=True,
    ssl_cert_reqs=None,
    ssl_check_hostname=False,
    socket_connect_timeout=10,
    socket_timeout=10
)

def lambda_handler(event, context):
    try:
        # Extract data from the event
        records = event.get("Records", [])
        
        for record in records:
            event_name = record.get("eventName")
            image = (
                record.get("dynamodb", {}).get("NewImage", {})
                if event_name in ("INSERT", "MODIFY")
                else record.get("dynamodb", {}).get("OldImage", {})
            )

            therapist_id = image.get("therapist_id", {}).get("S")
            connection_id = image.get("connection_id", {}).get("S")

            if not connection_id or not therapist_id or therapist_id == "unauthenticated":
                continue

            redis_key = f"therapist:{therapist_id}:connection:{connection_id}"

            if event_name in ("INSERT", "MODIFY"):
                ttl_raw = int(image["ttl"]["N"]) if "ttl" in image else None
                ttl = ttl_raw if ttl_raw and ttl_raw > int(time.time()) else None
                redis_client.set(redis_key, 1, ex=ttl)
            elif event_name == "REMOVE":
                redis_client.delete(redis_key)

        return {
            "statusCode": 200,
            "body": "Successfully processed DynamoDB stream events"
        }

    except Exception as e:
        print(f"Error processing stream events: {e}")
        return {
            "statusCode": 500,
            "body": f"Error processing stream events: {str(e)}"
        }
