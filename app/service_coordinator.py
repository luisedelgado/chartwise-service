from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .managers.manager_factory import ManagerFactory

class EndpointServiceCoordinator:

    service_app = FastAPI()

    def __init__(self, environment, routers, app=service_app):

        for router in routers:
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
