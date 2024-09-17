import os

from .dependencies.implementation.deepgram_client import DeepgramClient
from .dependencies.implementation.docupanda_client import DocupandaClient
from .dependencies.implementation.openai_client import OpenAIClient
from .dependencies.implementation.pinecone_client import PineconeClient
from .dependencies.implementation.supabase_client_factory import SupabaseClientFactory
from .internal.dependency_container import DependencyContainer
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
pinecone_client = PineconeClient()
docupanda_client = DocupandaClient()
deepgram_client = DeepgramClient()

app = EndpointServiceCoordinator(routers=[
                                    AssistantRouter(environment=environment,
                                                    auth_manager=auth_manager,
                                                    assistant_manager=assistant_manager,
                                                    router_dependencies=DependencyContainer(openai_client=openai_client,
                                                                                           pinecone_client=pinecone_client,
                                                                                           supabase_client_factory=supabase_client_factory)).router,
                                    AudioProcessingRouter(environment=environment,
                                                          auth_manager=auth_manager,
                                                          assistant_manager=assistant_manager,
                                                          audio_processing_manager=audio_processing_manager,
                                                          router_dependencies=DependencyContainer(openai_client=openai_client,
                                                                                                 deepgram_client=deepgram_client,
                                                                                                 pinecone_client=pinecone_client,
                                                                                                 supabase_client_factory=supabase_client_factory)).router,
                                    SecurityRouter(auth_manager=auth_manager,
                                                   assistant_manager=assistant_manager,
                                                   router_dependencies=DependencyContainer(openai_client=openai_client,
                                                                                          supabase_client_factory=supabase_client_factory,
                                                                                          pinecone_client=pinecone_client)).router,
                                    ImageProcessingRouter(environment=environment,
                                                          assistant_manager=assistant_manager,
                                                          auth_manager=auth_manager,
                                                          image_processing_manager=image_processing_manager,
                                                          router_dependencies=DependencyContainer(openai_client=openai_client,
                                                                                                 pinecone_client=pinecone_client,
                                                                                                 supabase_client_factory=supabase_client_factory,
                                                                                                 docupanda_client=docupanda_client)).router,
                                ],
                                 environment=environment).app
