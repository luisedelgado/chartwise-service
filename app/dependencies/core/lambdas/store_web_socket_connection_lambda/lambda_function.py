import os
import time
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("TABLE_NAME"))

def lambda_handler(event, context):
    connection_id = event["requestContext"]["connectionId"].strip()

    try:
        ttl = int(time.time()) + int(os.environ.get("UNAUTHENTICATED_TTL_SECONDS", "60"))

        table.put_item(Item={
            "connection_id": connection_id,
            "authenticated": False,
            "ttl": ttl,
        })

        return {"statusCode": 200, "body": "Connected"}
    except Exception as e:
        print(f"Failed to connect: {e}")
        return {"statusCode": 500, "body": "Internal Server Error"}
