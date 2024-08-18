import asyncio, os, time

from fastapi import APIRouter, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

class EndpointServiceCoordinator:

    origins = [
        # Daniel Daza Development
        "https://localhost:5173",
        # chartwise.ai
        "https://chartwise.ai",
        "https://api.chartwise.ai",
        # Speechmatics Notification Servers
        "40.74.41.91",
        "52.236.157.154",
        "40.74.37.0",
        "20.73.209.153",
        "20.73.142.44",
        "20.105.89.153",
        "20.105.89.173",
        "20.105.89.184",
        "20.105.89.98",
        "20.105.88.228",
        "52.149.21.32",
        "52.149.21.10",
        "52.137.102.83",
        "40.64.107.92",
        "40.64.107.99",
        "52.146.58.224",
        "52.146.58.159",
        "52.146.59.242",
        "52.146.59.213",
        "52.146.58.64",
        "20.248.249.20",
        "20.248.249.47",
        "20.248.249.181",
        "20.248.249.119",
        "20.248.249.164",
    ]

    def __init__(self, routers, environment):
        self.app = FastAPI()
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self.environment = environment

        try:
            assert len(routers) > 0, "Did not receive any routers"

            for router in routers:
                assert type(router) is APIRouter, "Received invalid object instead of router"
                self.app.include_router(router)

        except Exception as e:
            raise HTTPException(detail=str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
