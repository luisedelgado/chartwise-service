import asyncpg
import os

from fastapi import FastAPI
from urllib.parse import quote_plus

from ...dependencies.api.aws_secret_manager_base_class import AwsSecretManagerBaseClass
from ...dependencies.api.resend_base_class import ResendBaseClass

async def connect_pool(
    app: FastAPI,
    secret_manager: AwsSecretManagerBaseClass,
    resend_client: ResendBaseClass,
):
    try:
        chartwise_user_secret_id = os.environ.get("AWS_SECRET_MANAGER_CHARTWISE_USER_ROLE")
        secret = secret_manager.get_secret(
            secret_id=chartwise_user_secret_id,
            resend_client=resend_client,
        )
        username = secret.get("username")
        password = quote_plus(secret.get("password"))
        endpoint = secret.get("host") or os.getenv("AWS_RDS_DATABASE_ENDPOINT")
        port = secret.get("port") or os.getenv("AWS_RDS_DB_PORT")
        database_name = secret.get("dbname") or os.getenv("AWS_RDS_DB_NAME")
        database_url = f"postgresql://{username}:{password}@{endpoint}:{port}/{database_name}"

        app.state.pool = await asyncpg.create_pool(
            dsn=database_url,
            ssl='require',
            timeout=10
        )
    except Exception as e:
        raise RuntimeError(f"Invalid database URL: {e}") from e

async def disconnect_pool(
    app: FastAPI
):
    await app.state.pool.close()
