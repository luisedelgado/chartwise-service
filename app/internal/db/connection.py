import asyncpg
import os

from fastapi import FastAPI
from urllib.parse import quote_plus

from ...internal.schemas import PROD_ENVIRONMENT, STAGING_ENVIRONMENT
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

        if os.environ.get("ENVIRONMENT") not in [STAGING_ENVIRONMENT, PROD_ENVIRONMENT]:
            # Running locally, let's leverage Bastion's SSH tunnel
            endpoint = os.getenv("AWS_BASTION_RDS_DATABASE_ENDPOINT", "127.0.0.1")
            port = os.getenv("AWS_BASTION_RDS_DB_PORT", "5433")

        database_url = f"postgresql://{username}:{password}@{endpoint}:{port}/{database_name}"
        app.state.pool = await asyncpg.create_pool(
            dsn=database_url,
            ssl='require',
            timeout=30,
            command_timeout=30,
        )
    except Exception as e:
        raise RuntimeError(f"Invalid database URL: {e}") from e

async def disconnect_pool(
    app: FastAPI
):
    await app.state.pool.close()
