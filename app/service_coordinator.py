import asyncio, os, time

from fastapi import APIRouter, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from supabase import Client, create_client

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
        self.initialize_routes()

        try:
            assert len(routers) > 0, "Did not receive any routers"

            for router in routers:
                assert type(router) is APIRouter, "Received invalid object instead of router"
                self.app.include_router(router)

            self.datastore_client: Client = create_client(supabase_url=os.environ.get("SUPABASE_URL"),
                                                          supabase_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))

        except Exception as e:
            raise HTTPException(detail=str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def initialize_routes(self):
        self.app.middleware("http")(self.measure_latency)

    async def measure_latency(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        end_time = time.time()

        # We're not logging latency in environments other than prod.
        if self.environment != "prod":
            return response

        async def log_latency():
            latency_milliseconds = (end_time - start_time) * 1000
            latency_ms = f"{latency_milliseconds:.2f}"
            latency_payload = {
                "latency_ms": latency_ms,
                "request_url": str(request.url),
                "request_method": request.method
            }

            try:
                request_body = await request.json()
            except Exception:
                request_body = {}

            try:
                user_id = None if 'user_id' not in request_body else request_body['user_id']
                if user_id is not None:
                    latency_payload['user_id'] = user_id

                self.datastore_client.table('latency_logs').insert(latency_payload).execute()
            except Exception:
                # Fail silently
                pass

        # Schedule the background task
        asyncio.create_task(log_latency())
        return response
