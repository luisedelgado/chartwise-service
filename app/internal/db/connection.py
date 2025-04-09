import asyncpg
import os

from fastapi import FastAPI
from urllib.parse import quote_plus

from ...dependencies.api.aws_secret_manager_base_class import AwsSecretManagerBaseClass

async def connect_pool(app: FastAPI, secret_manager: AwsSecretManagerBaseClass):
    try:
        secret = secret_manager.get_rds_secret()
        username = quote_plus(secret.get("username"))
        password = quote_plus(secret.get("password"))
        endpoint = os.getenv("AWS_RDS_DATABASE_ENDPOINT")
        port = os.getenv("AWS_RDS_DB_PORT")
        database_name = os.getenv("AWS_RDS_DB_NAME")
        database_url = f"postgresql://{username}:{password}@{endpoint}:{port}/{database_name}"

        app.state.pool = await asyncpg.create_pool(
            dsn=database_url,
            ssl='require',
            timeout=10
        )
    except Exception as e:
        raise Exception(f"Invalid database URL: {e}")

async def disconnect_pool(app: FastAPI):
    await app.state.pool.close()

async def get_conn(app: FastAPI):
    return await app.state.pool.acquire()
