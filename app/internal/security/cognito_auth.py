import time
import jwt
import os

from jwt import PyJWKClient
from fastapi import Header, HTTPException, status
from typing import Dict

COGNITO_ISSUER = f"https://cognito-idp.{os.environ.get('COGNITO_REGION')}.amazonaws.com/{os.environ.get('COGNITO_USER_POOL_ID')}"
JWKS_URL = f"{COGNITO_ISSUER}/.well-known/jwks.json"
JWKS_CACHE = None
JWKS_CACHE_EXPIRATION = 0
JWKS_CACHE_TTL_SECONDS = 86400 # 24 hours

def verify_cognito_token(auth_header: str = Header(..., description="Bearer Cognito ID token")) -> Dict:
    """FastAPI dependency that validates the Authorization header and returns user info."""
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identity authorization header missing or invalid",
        )

    cognito_token = auth_header.split(" ")[1]
    decoded_cognito_token = decode_cognito_token(cognito_token)

    return {
        "sub": decoded_cognito_token.get("sub"),
        "email": decoded_cognito_token.get("email"),
        "claims": decoded_cognito_token
    }

def decode_cognito_token(token: str) -> Dict:
    """Decode and verify a Cognito ID token."""
    try:
        signing_key = get_jwk_client().get_signing_key_from_jwt(token)
        decoded_token = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=os.environ.get("COGNITO_APP_CLIENT_ID"),
            issuer=COGNITO_ISSUER,
        )

        if decoded_token.get("token_use") != "id":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expected ID token")

        return decoded_token

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {str(e)}")

def get_jwk_client():
    global JWKS_CACHE, JWKS_CACHE_EXPIRATION

    now = time.time()
    if JWKS_CACHE is None or now >= JWKS_CACHE_EXPIRATION:
        JWKS_CACHE = PyJWKClient(JWKS_URL)
        JWKS_CACHE_EXPIRATION = now + JWKS_CACHE_TTL_SECONDS

    return JWKS_CACHE
