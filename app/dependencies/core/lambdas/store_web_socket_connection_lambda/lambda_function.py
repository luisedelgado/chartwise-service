import os
import time
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("TABLE_NAME")) # type: ignore[attr-defined]

def lambda_handler(event, context):
    connection_id = event["requestContext"]["connectionId"].strip()

    try:
        print(f"[$connect] Writing item: therapist_id=unauthenticated, connection_id={connection_id}")
        ttl = int(time.time()) + int(os.environ.get("UNAUTHENTICATED_TTL_SECONDS", "60"))
        table.put_item(Item={
            "therapist_id": f"unauthenticated" ,
            "connection_id": connection_id,
            "authenticated": False,
            "connected_at": int(time.time()),
            "ttl": ttl
        })

        return {"statusCode": 200, "body": "Connected"}
    except Exception as e:
        print(f"Failed to connect: {e}")
        return {"statusCode": 500, "body": "Internal Server Error"}
