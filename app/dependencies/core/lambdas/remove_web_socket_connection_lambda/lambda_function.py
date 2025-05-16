import os
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("TABLE_NAME"))

def lambda_handler(event, context):
    connection_id = event["requestContext"]["connectionId"].strip()

    try:
        # Query the GSI to find the matching therapist_id
        response = table.query(
            IndexName=os.environ["CONNECTION_ID_INDEX_NAME"],
            KeyConditionExpression=boto3.dynamodb.conditions.Key("connection_id").eq(connection_id)
        )

        items = response.get("Items", [])
        if not items:
            print(f"No item found for connection_id: {connection_id}")
            return {"statusCode": 404, "body": "Connection not found"}

        therapist_id = items[0]["therapist_id"]

        # Delete the item by primary key
        table.delete_item(
            Key={
                "therapist_id": therapist_id,
                "connection_id": connection_id,
            }
        )

    except Exception as e:
        print(f"Error deleting connection: {e}")
        return {"statusCode": 500, "body": "Failed to disconnect"}

    return {"statusCode": 200, "body": "Disconnected"}
