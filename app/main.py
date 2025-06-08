import logging
import os

from .routers.assistant_router import AssistantRouter
from .routers.audio_processing_router import AudioProcessingRouter
from .routers.image_processing_router import ImageProcessingRouter
from .routers.payment_processing_router import PaymentProcessingRouter
from .routers.security_router import SecurityRouter
from .service_coordinator import EndpointServiceCoordinator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

if os.environ.get("DEBUG_MODE") == "true":
    import debugpy
    print("Debugger is enabled. Waiting for client to attach...")
    debugpy.listen(("0.0.0.0", 5678))
    debugpy.wait_for_client()  # Pause execution until debugger attaches
    print("Debugger attached, resuming execution...")

environment = os.environ.get("ENVIRONMENT")

app = EndpointServiceCoordinator(routers=[
                                    AssistantRouter(environment=environment).router,
                                    AudioProcessingRouter(environment=environment).router,
                                    PaymentProcessingRouter(environment=environment).router,
                                    SecurityRouter().router,
                                    ImageProcessingRouter(environment=environment).router,
                                ],
                                 environment=environment).app
