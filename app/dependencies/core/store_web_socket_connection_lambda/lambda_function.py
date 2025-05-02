import os
import time
import boto3
import jwt

from jwt import PyJWKClient

COGNITO_ISSUER = f"https://cognito-idp.{os.environ.get('AWS_SERVICES_REGION')}.amazonaws.com/{os.environ.get('AWS_COGNITO_USER_POOL_ID')}"
JWKS_URL = f"{COGNITO_ISSUER}/.well-known/jwks.json"
JWKS_CACHE = None
JWKS_CACHE_EXPIRATION = 0
JWKS_CACHE_TTL_SECONDS = 86400 # 24 hours

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("TABLE_NAME"))

def get_jwk_client():
    global JWKS_CACHE, JWKS_CACHE_EXPIRATION
    now = time.time()
    if JWKS_CACHE is None or now >= JWKS_CACHE_EXPIRATION:
        JWKS_CACHE = PyJWKClient(JWKS_URL)
        JWKS_CACHE_EXPIRATION = now + JWKS_CACHE_TTL_SECONDS
    return JWKS_CACHE

def lambda_handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    auth_header = event["headers"].get("Authorization", "")

    try:
        token = auth_header.replace("Bearer ", "")
        signing_key = get_jwk_client().get_signing_key_from_jwt(token)
        print(f"signing_key: {signing_key}")
        decoded_token = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=os.environ.get("COGNITO_APP_CLIENT_ID"),
            issuer=COGNITO_ISSUER,
        )
        print(f"decoded_token: {decoded_token}")
        therapist_id = decoded_token["sub"]
    except Exception as e:
        print(f"Exception thrown: {e}")
        return {"statusCode": 401, "body": "Unauthorized"}

    try:
        ttl = int(time.time()) + int(os.environ.get("TTL_SECONDS", "600"))

        table.put_item(Item={
            "therapist_id": therapist_id,
            "connection_id": connection_id,
            "ttl": ttl,
        })
    except Exception as e:
        return {"statusCode": 417, "body": f"Unexpected failure: {str(e)}"}

    return {"statusCode": 200, "body": "Connected"}
