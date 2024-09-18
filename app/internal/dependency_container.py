import os

from ..dependencies.fake.fake_deepgram_client import FakeDeepgramClient
from ..dependencies.fake.fake_docupanda_client import FakeDocupandaClient
from ..dependencies.fake.fake_async_openai import FakeAsyncOpenAI
from ..dependencies.fake.fake_pinecone_client import FakePineconeClient
from ..dependencies.fake.fake_supabase_client import FakeSupabaseClient
from ..dependencies.fake.fake_supabase_client_factory import FakeSupabaseClientFactory
from ..dependencies.implementation.deepgram_client import DeepgramBaseClass, DeepgramClient
from ..dependencies.implementation.docupanda_client import DocupandaBaseClass, DocupandaClient
from ..dependencies.implementation.openai_client import OpenAIBaseClass, OpenAIClient
from ..dependencies.implementation.pinecone_client import PineconeBaseClass, PineconeClient
from ..dependencies.implementation.supabase_client_factory import SupabaseFactoryBaseClass, SupabaseClientFactory

class DependencyContainer:
    def __init__(self):
        self._testing_environment = (os.environ.get("ENVIRONMENT") == "testing")
        self._openai_client = None
        self._pinecone_client = None
        self._docupanda_client = None
        self._deepgram_client = None
        self._supabase_client_factory = None

    def get_deepgram_client(self) -> DeepgramBaseClass:
        if self._deepgram_client is None:
            self._deepgram_client = FakeDeepgramClient() if self._testing_environment else DeepgramClient()
        return self._deepgram_client

    def get_openai_client(self) -> OpenAIBaseClass:
        if self._openai_client is None:
            self._openai_client = FakeAsyncOpenAI() if self._testing_environment else OpenAIClient()
        return self._openai_client

    def get_pinecone_client(self) -> PineconeBaseClass:
        if self._pinecone_client is None:
            self._pinecone_client = FakePineconeClient() if self._testing_environment else PineconeClient()
        return self._pinecone_client

    def get_docupanda_client(self) -> DocupandaBaseClass:
        if self._docupanda_client is None:
            self._docupanda_client = FakeDocupandaClient() if self._testing_environment else DocupandaClient()
        return self._docupanda_client

    def get_supabase_client_factory(self) -> SupabaseFactoryBaseClass:
        if self._supabase_client_factory is None:
            self._supabase_client_factory = FakeSupabaseClientFactory(FakeSupabaseClient(), FakeSupabaseClient()) if self._testing_environment else SupabaseClientFactory()
        return self._supabase_client_factory

dependency_container = DependencyContainer()
