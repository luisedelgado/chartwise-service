import os

from .dependencies.implementation.openai_manager import OpenAIManager
from .dependencies.implementation.supabase_manager_factory import SupabaseManagerFactory
from .routers.assistant_router import AssistantRouter
from .routers.audio_processing_router import AudioProcessingRouter
from .routers.image_processing_router import ImageProcessingRouter
from .routers.security_router import SecurityRouter
from .service_coordinator import EndpointServiceCoordinator
from .managers.assistant_manager import AssistantManager
from .managers.audio_processing_manager import AudioProcessingManager
from .managers.auth_manager import AuthManager
from .managers.image_processing_manager import ImageProcessingManager

environment = os.environ.get("ENVIRONMENT")
auth_manager = AuthManager()
assistant_manager = AssistantManager()
audio_processing_manager = AudioProcessingManager()
image_processing_manager = ImageProcessingManager()
supabase_manager_factory = SupabaseManagerFactory()
openai_manager = OpenAIManager()

app = EndpointServiceCoordinator(routers=[
                                    AssistantRouter(environment=environment,
                                                    auth_manager=auth_manager,
                                                    assistant_manager=assistant_manager,
                                                    openai_manager=openai_manager,
                                                    supabase_manager_factory=supabase_manager_factory).router,
                                    AudioProcessingRouter(auth_manager=auth_manager,
                                                          assistant_manager=assistant_manager,
                                                          audio_processing_manager=audio_processing_manager,
                                                          openai_manager=openai_manager,
                                                          supabase_manager_factory=supabase_manager_factory).router,
                                    SecurityRouter(auth_manager=auth_manager,
                                                   assistant_manager=assistant_manager,
                                                   supabase_manager_factory=supabase_manager_factory).router,
                                    ImageProcessingRouter(assistant_manager=assistant_manager,
                                                          auth_manager=auth_manager,
                                                          image_processing_manager=image_processing_manager,
                                                          supabase_manager_factory=supabase_manager_factory,
                                                          openai_manager=openai_manager).router,
                                ],
                                 environment=environment).app
