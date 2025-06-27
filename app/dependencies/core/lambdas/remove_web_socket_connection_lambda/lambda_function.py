import os
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("TABLE_NAME")) # type: ignore[attr-defined]

def lambda_handler(event, context):
    connection_id = event["requestContext"]["connectionId"].strip()

    try:
        query = table.query(
            IndexName=os.environ.get("CONNECTION_ID_INDEX_NAME"),
            KeyConditionExpression=Key("connection_id").eq(connection_id)
        )

        items = query.get("Items", [])
        if not items:
            no_items_found_msg = f"No matching connection_id found in gsi_by_connection: {connection_id}"
            print(no_items_found_msg)
            return {"statusCode": 200, "body": no_items_found_msg}

        item = items[0]
        table.delete_item(
            Key={
                "therapist_id": item["therapist_id"],
                "connection_id": item["connection_id"]
            }
        )

        return {"statusCode": 200, "body": "Disconnected"}

    except Exception as e:
        print(f"Error deleting connection: {e}")
        return {"statusCode": 500, "body": "Failed to disconnect"}
