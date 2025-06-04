import os
import json
import time
import boto3
import jwt
from jwt import PyJWKClient

# Cognito issuer and JWKS setup
COGNITO_ISSUER = f"https://cognito-idp.{os.environ['AWS_SERVICES_REGION']}.amazonaws.com/{os.environ['AWS_COGNITO_USER_POOL_ID']}"
JWKS_URL = f"{COGNITO_ISSUER}/.well-known/jwks.json"

# AWS clients
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

gatewayapi = boto3.client(
    "apigatewaymanagementapi",
    endpoint_url=f"https://{os.environ['WEBSOCKET_DOMAIN']}/{os.environ['WEBSOCKET_STAGE']}"
)

def lambda_handler(event, context):
    connection_id = event["requestContext"]["connectionId"].strip()
    body = json.loads(event.get("body", "{}"))
    token = body.get("token")

    if not token:
        return {"statusCode": 401, "body": "Missing token"}

    try:
        # Validate JWT
        jwk_client = PyJWKClient(JWKS_URL)
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=os.environ["COGNITO_APP_CLIENT_ID"],
            issuer=COGNITO_ISSUER
        )
        therapist_id = decoded["sub"]

        # Query all current connections for the therapist
        existing = table.query(
            IndexName="TherapistIdIndex",
            KeyConditionExpression=boto3.dynamodb.conditions.Key("therapist_id").eq(therapist_id)
        ).get("Items", [])

        # Remove any other authenticated connections
        for conn in existing:
            if conn["connection_id"] != connection_id and conn.get("authenticated") is True:
                table.delete_item(Key={"connection_id": conn["connection_id"]})

        # Update the unauthenticated record to mark as authenticated
        ttl = int(time.time()) + int(os.environ.get("AUTHENTICATED_TTL_SECONDS", "600"))
        table.update_item(
            Key={"connection_id": connection_id},
            UpdateExpression="SET therapist_id = :tid, authenticated = :auth, #ttl = :ttl",
            ExpressionAttributeValues={
                ":tid": therapist_id,
                ":auth": True,
                ":ttl": ttl
            },
            ExpressionAttributeNames={
                "#ttl": "ttl"
            },
            ConditionExpression="attribute_exists(connection_id)"
        )

        return {"statusCode": 200, "body": "Authenticated"}

    except Exception as e:
        print(f"Auth error: {e}")
        # Optionally close the connection if the record doesn't exist
        try:
            gatewayapi.delete_connection(ConnectionId=connection_id)
        except Exception as close_err:
            print(f"Failed to close connection: {close_err}")
        return {"statusCode": 401, "body": "Unauthorized"}
