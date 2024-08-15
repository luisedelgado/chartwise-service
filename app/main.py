import os

from .dependencies.implementation.deepgram_client import DeepgramClient
from .dependencies.implementation.docupanda_client import DocupandaClient
from .dependencies.implementation.openai_client import OpenAIClient
from .dependencies.implementation.pinecone_client import PineconeClient
from .dependencies.implementation.speechmatics_client import SpeechmaticsClient
from .dependencies.implementation.supabase_client_factory import SupabaseClientFactory
from .internal.router_dependencies import RouterDependencies
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
speechmatics_client = SpeechmaticsClient()

app = EndpointServiceCoordinator(routers=[
                                    AssistantRouter(environment=environment,
                                                    auth_manager=auth_manager,
                                                    assistant_manager=assistant_manager,
                                                    router_dependencies=RouterDependencies(openai_client=openai_client,
                                                                                           pinecone_client=pinecone_client,
                                                                                           supabase_client_factory=supabase_client_factory)).router,
                                    AudioProcessingRouter(auth_manager=auth_manager,
                                                          assistant_manager=assistant_manager,
                                                          audio_processing_manager=audio_processing_manager,
                                                          router_dependencies=RouterDependencies(openai_client=openai_client,
                                                                                                 deepgram_client=deepgram_client,
                                                                                                 pinecone_client=pinecone_client,
                                                                                                 speechmatics_client=speechmatics_client,
                                                                                                 supabase_client_factory=supabase_client_factory)).router,
                                    SecurityRouter(auth_manager=auth_manager,
                                                   assistant_manager=assistant_manager,
                                                   router_dependencies=RouterDependencies(openai_client=openai_client,
                                                                                          supabase_client_factory=supabase_client_factory,
                                                                                          pinecone_client=pinecone_client)).router,
                                    ImageProcessingRouter(assistant_manager=assistant_manager,
                                                          auth_manager=auth_manager,
                                                          image_processing_manager=image_processing_manager,
                                                          router_dependencies=RouterDependencies(openai_client=openai_client,
                                                                                                 supabase_client_factory=supabase_client_factory,
                                                                                                 docupanda_client=docupanda_client)).router,
                                ],
                                 environment=environment).app
