import os

from .dependencies.implementation.openai_client import OpenAIClient
from .dependencies.implementation.supabase_client_factory import SupabaseClientFactory
from .internal.model import RouterDependencies
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
supabase_client_factory = SupabaseClientFactory()
openai_client = OpenAIClient()

app = EndpointServiceCoordinator(routers=[
                                    AssistantRouter(environment=environment,
                                                    auth_manager=auth_manager,
                                                    assistant_manager=assistant_manager,
                                                    router_dependencies=RouterDependencies(openai_client=openai_client,
                                                                                           supabase_client_factory=supabase_client_factory)).router,
                                    AudioProcessingRouter(auth_manager=auth_manager,
                                                          assistant_manager=assistant_manager,
                                                          audio_processing_manager=audio_processing_manager,
                                                          router_dependencies=RouterDependencies(openai_client=openai_client,
                                                                                                 supabase_client_factory=supabase_client_factory)).router,
                                    SecurityRouter(auth_manager=auth_manager,
                                                   assistant_manager=assistant_manager,
                                                   router_dependencies=RouterDependencies(supabase_client_factory=supabase_client_factory)).router,
                                    ImageProcessingRouter(assistant_manager=assistant_manager,
                                                          auth_manager=auth_manager,
                                                          image_processing_manager=image_processing_manager,
                                                          router_dependencies=RouterDependencies(openai_client=openai_client,
                                                                                                 supabase_client_factory=supabase_client_factory)).router,
                                ],
                                 environment=environment).app
