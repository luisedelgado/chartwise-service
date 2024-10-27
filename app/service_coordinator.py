from fastapi import APIRouter, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

class EndpointServiceCoordinator:

    origins = [
        # Daniel Daza Development
        "https://localhost:5173",
        # chartwise.ai
        "https://chartwise.ai",
        "https://api.chartwise.ai",
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
