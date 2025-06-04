import os
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("TABLE_NAME"))

def lambda_handler(event, context):
    connection_id = event["requestContext"]["connectionId"].strip()

    try:
        table.delete_item(
            Key={
                "connection_id": connection_id
            }
        )
        return {"statusCode": 200, "body": "Disconnected"}

    except Exception as e:
        print(f"Error deleting connection: {e}")
        return {"statusCode": 500, "body": "Failed to disconnect"}
