import os
import json
import redis

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
            # Process each record
            if record.get("eventName") == "INSERT" or record.get("eventName") == "MODIFY":
                # Get the new image (the current state of the item)
                new_image = record.get("dynamodb", {}).get("NewImage", {})
                
                # Extract relevant fields
                therapist_id = new_image.get("therapist_id", {}).get("S")
                connection_id = new_image.get("connection_id", {}).get("S")
                
                if therapist_id and connection_id:
                    # Skip unauthenticated connections
                    if therapist_id == "unauthenticated":
                        continue
                        
                    # Store in Redis using a set
                    redis_key = f"therapist:{therapist_id}:connections"
                    redis_client.sadd(redis_key, connection_id)
                    
                    # Set TTL if specified in the DynamoDB record
                    if "ttl" in new_image:
                        ttl = int(new_image["ttl"].get("N", 0))
                        redis_client.expireat(redis_key, ttl)
                        
            elif record.get("eventName") == "REMOVE":
                # Get the old image (the previous state of the item)
                old_image = record.get("dynamodb", {}).get("OldImage", {})
                
                # Extract relevant fields
                therapist_id = old_image.get("therapist_id", {}).get("S")
                connection_id = old_image.get("connection_id", {}).get("S")
                
                if therapist_id and connection_id:
                    # Skip unauthenticated connections
                    if therapist_id == "unauthenticated":
                        continue
                        
                    # Remove from Redis set
                    redis_key = f"therapist:{therapist_id}:connections"
                    redis_client.srem(redis_key, connection_id)
                    
                    # If no more connections, remove the key
                    if redis_client.scard(redis_key) == 0:
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
