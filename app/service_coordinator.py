from fastapi import APIRouter, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .managers.manager_factory import ManagerFactory

class EndpointServiceCoordinator:

    service_app = FastAPI()

    def __init__(self, environment, routers, app=service_app):
        try:
            assert len(routers) > 0, "Did not receive any routers"

            for router in routers:
                assert type(router) is APIRouter, "Received invalid object instead of router"
                app.include_router(router)

            origins = [
                # Daniel Daza development
                "https://localhost:5173"
            ]
            origins.extend(ManagerFactory().create_audio_processing_manager(environment).get_diarization_notifications_ips())

            app.add_middleware(
                CORSMiddleware,
                allow_origins=origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        except Exception as e:
            raise HTTPException(detail=str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
