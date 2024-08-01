import os

from .routers.assistant_router import AssistantRouter
from .routers.audio_processing_router import AudioProcessingRouter
from .routers.image_processing_router import ImageProcessingRouter
from .routers.security_router import SecurityRouter
from .service_coordinator import EndpointServiceCoordinator
from .managers.implementations.assistant_manager import AssistantManager
from .managers.implementations.audio_processing_manager import AudioProcessingManager
from .managers.implementations.auth_manager import AuthManager
from .managers.implementations.image_processing_manager import ImageProcessingManager
from .managers.implementations.supabase_manager_factory import SupabaseManagerFactory

environment = os.environ.get("ENVIRONMENT")
auth_manager = AuthManager()
assistant_manager = AssistantManager()
audio_processing_manager = AudioProcessingManager()
image_processing_manager = ImageProcessingManager()
supabase_manager_factory = SupabaseManagerFactory()

app = EndpointServiceCoordinator(routers=[
                                    AssistantRouter(environment=environment,
                                                    auth_manager=auth_manager,
                                                    assistant_manager=assistant_manager,
                                                    supabase_manager_factory=supabase_manager_factory).router,
                                    AudioProcessingRouter(auth_manager=auth_manager,
                                                          assistant_manager=assistant_manager,
                                                          audio_processing_manager=audio_processing_manager,
                                                          supabase_manager_factory=supabase_manager_factory).router,
                                    SecurityRouter(auth_manager=auth_manager,
                                                   assistant_manager=assistant_manager,
                                                   supabase_manager_factory=supabase_manager_factory).router,
                                    ImageProcessingRouter(assistant_manager=assistant_manager,
                                                          auth_manager=auth_manager,
                                                          image_processing_manager=image_processing_manager,
                                                          supabase_manager_factory=supabase_manager_factory).router,
                                ],
                                 environment=environment).app
