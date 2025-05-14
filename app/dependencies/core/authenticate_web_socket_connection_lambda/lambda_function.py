import os
import json
import time
import boto3
import jwt
from jwt import PyJWKClient
from boto3.dynamodb.conditions import Key

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

        # Lookup existing connection using GSI
        response = table.query(
            IndexName=os.environ["CONNECTION_ID_INDEX_NAME"],
            KeyConditionExpression=Key("connection_id").eq(connection_id)
        )
        items = response.get("Items", [])
        if not items:
            print(f"No record found for connection_id: {connection_id}")
            gatewayapi.delete_connection(ConnectionId=connection_id)
            return {"statusCode": 401, "body": "Connection not registered"}

        # Delete old (unauthenticated) record
        table.delete_item(
            Key={
                "therapist_id": items[0]["therapist_id"],
                "connection_id": connection_id
            }
        )

        # Put new authenticated record
        ttl = int(time.time()) + int(os.environ.get("AUTHENTICATED_TTL_SECONDS", "600"))
        table.put_item(Item={
            "therapist_id": therapist_id,
            "connection_id": connection_id,
            "authenticated": True,
            "ttl": ttl
        })

        return {"statusCode": 200, "body": "Authenticated"}

    except Exception as e:
        print(f"Auth error: {e}")
        return {"statusCode": 401, "body": "Unauthorized"}
