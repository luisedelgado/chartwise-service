import asyncpg
import os

from fastapi import FastAPI

DATABASE_URL = os.getenv("AWS_RDS_DATABASE_URL")

async def connect_pool(app: FastAPI):
    app.state.pool = await asyncpg.create_pool(DATABASE_URL)

async def disconnect_pool(app: FastAPI):
    await app.state.pool.close()

async def get_conn(app: FastAPI):
    return await app.state.pool.acquire()
