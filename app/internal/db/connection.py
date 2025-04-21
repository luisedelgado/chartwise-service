import asyncpg
import os

from fastapi import FastAPI
from urllib.parse import quote_plus

from ...dependencies.api.aws_secret_manager_base_class import AwsSecretManagerBaseClass

CHARTWISE_USER = "chartwise_user"

async def connect_pool(app: FastAPI, secret_manager: AwsSecretManagerBaseClass):
    try:
        chartwise_user_secret_id = os.environ.get("AWS_SECRET_MANAGER_CHARTWISE_USER_ROLE")
        secret = secret_manager.get_secret(
            secret_id=chartwise_user_secret_id
        )
        password = quote_plus(secret.get(CHARTWISE_USER))
        endpoint = os.getenv("AWS_RDS_DATABASE_ENDPOINT")
        port = os.getenv("AWS_RDS_DB_PORT")
        database_name = os.getenv("AWS_RDS_DB_NAME")
        database_url = f"postgresql://{CHARTWISE_USER}:{password}@{endpoint}:{port}/{database_name}"

        app.state.pool = await asyncpg.create_pool(
            dsn=database_url,
            ssl='require',
            timeout=10
        )
    except Exception as e:
        raise RuntimeError(f"Invalid database URL: {e}") from e

async def disconnect_pool(app: FastAPI):
    await app.state.pool.close()
