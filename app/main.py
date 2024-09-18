import os

from .routers.assistant_router import AssistantRouter
from .routers.audio_processing_router import AudioProcessingRouter
from .routers.image_processing_router import ImageProcessingRouter
from .routers.security_router import SecurityRouter
from .service_coordinator import EndpointServiceCoordinator

environment = os.environ.get("ENVIRONMENT")

app = EndpointServiceCoordinator(routers=[
                                    AssistantRouter(environment=environment).router,
                                    AudioProcessingRouter(environment=environment).router,
                                    SecurityRouter().router,
                                    ImageProcessingRouter(environment=environment).router,
                                ],
                                 environment=environment).app
