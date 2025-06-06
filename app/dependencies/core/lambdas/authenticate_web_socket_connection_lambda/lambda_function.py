import os
import json
import time
import boto3
import jwt
from jwt import PyJWKClient
from boto3.dynamodb.conditions import Key

# Cognito issuer and JWKS setup
COGNITO_ISSUER = f"https://cognito-idp.{os.environ.get('AWS_SERVICES_REGION')}.amazonaws.com/{os.environ.get('AWS_COGNITO_USER_POOL_ID')}"
JWKS_URL = f"{COGNITO_ISSUER}/.well-known/jwks.json"

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("TABLE_NAME"))

gatewayapi = boto3.client(
    "apigatewaymanagementapi",
    endpoint_url=f"https://{os.environ.get('WEBSOCKET_DOMAIN')}/{os.environ.get('WEBSOCKET_STAGE')}"
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
            audience=os.environ.get("COGNITO_APP_CLIENT_ID"),
            issuer=COGNITO_ISSUER
        )
        therapist_id = decoded["sub"]
        ttl = int(time.time()) + int(os.environ.get("AUTHENTICATED_TTL_SECONDS", "600"))

        # Read the unauthenticated record
        unauth_key = {"therapist_id": "unauthenticated", "connection_id": connection_id}

        # Read the unauthenticated record with retries and exponential backoff
        record = table.get_item(Key=unauth_key, ConsistentRead=True).get("Item")

        if not record:
            raise ValueError("Unauthenticated connection not found")

        # Delete old authenticated connections for this therapist (optional)
        old_connections = table.query(
            KeyConditionExpression=Key("therapist_id").eq(therapist_id)
        ).get("Items", [])

        for conn in old_connections:
            if conn["connection_id"] != connection_id and conn.get("authenticated") is True:
                table.delete_item(Key={
                    "therapist_id": therapist_id,
                    "connection_id": conn["connection_id"]
                })

        # Write new record under authenticated therapist_id
        table.put_item(Item={
            "therapist_id": therapist_id,
            "connection_id": connection_id,
            "authenticated": True,
            "connected_at": record.get("connected_at", int(time.time())),
            "authenticated_at": int(time.time()),
            "ttl": ttl
        })

        # Delete the original unauthenticated record
        table.delete_item(Key=unauth_key)

        return {"statusCode": 200, "body": "Authenticated"}

    except Exception as e:
        print(f"Auth error: {e}")
        try:
            gatewayapi.delete_connection(ConnectionId=connection_id)
        except Exception as close_err:
            print(f"Failed to close connection: {close_err}")
        return {"statusCode": 401, "body": "Unauthorized"}
