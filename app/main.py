import os

from fastapi import (Cookie, FastAPI)
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated, Union

from .internal import security
from .managers.implementations.audio_processing_manager import AudioProcessingManager
from .routers import (assistant_router,
                      audio_processing_router,
                      image_processing_router,
                      security_router)

class EndpointServiceCoordinator():

    service_app = FastAPI()

    def __init__(self, environment=os.environ.get("ENVIRONMENT"), app=service_app):

        self.update_service_environment(environment)

        app.include_router(assistant_router.router)
        app.include_router(audio_processing_router.router)
        app.include_router(image_processing_router.router)
        app.include_router(security_router.router)

        origins = [
            # Daniel Daza development
            "https://localhost:5173",
            AudioProcessingManager().get_diarization_notifications_ips(),
        ]

        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    """
    Updates the current environment variable for all routers.

    Arguments:
    environment – The new environment to be set.
    """
    def update_service_environment(environment):
        for router in [assistant_router, audio_processing_router, image_processing_router, security_router]:
            router.environment = environment

    """
    Returns an OK status if the endpoint can be reached.

    Arguments:
    authorization – The authorization cookie, if exists.
    """
    @service_app.get("/v1/healthcheck")
    def read_healthcheck(authorization: Annotated[Union[str, None], Cookie()] = None):
        if not security.access_token_is_valid(authorization):
            raise security.TOKEN_EXPIRED_ERROR

        return {"status": "ok"}

app = EndpointServiceCoordinator().service_app
