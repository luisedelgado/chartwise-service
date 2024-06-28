import os

from fastapi import (Cookie, FastAPI)
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated, Union

from .internal import security
from .internal.utilities.lazy_loader import LazyLoader
from .managers.manager_factory import ManagerFactory
from .routers import (assistant_router,
                      audio_processing_router,
                      image_processing_router,
                      security_router)

class EndpointServiceCoordinator:

    service_app = FastAPI()

    def __init__(self, environment=os.environ.get("ENVIRONMENT"), app=service_app):

        self.update_routers_environment(environment)

        app.include_router(assistant_router.router)
        app.include_router(audio_processing_router.router)
        app.include_router(image_processing_router.router)
        app.include_router(security_router.router)

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

    """
    Updates the current environment variable for all routers.

    Arguments:
    environment – The new environment to be set.
    """
    def update_routers_environment(self, new_value):
        if isinstance(new_value, str):
            self._service_environment = new_value
            for router in [assistant_router, audio_processing_router, image_processing_router, security_router]:
                router.environment = new_value
        else:
            raise ValueError("Value must be a string")

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

app = LazyLoader(lambda: EndpointServiceCoordinator().service_app)
