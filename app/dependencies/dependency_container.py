import os

from .fake.fake_async_openai import FakeAsyncOpenAI
from .fake.fake_deepgram_client import FakeDeepgramClient
from .fake.fake_docupanda_client import FakeDocupandaClient
from .fake.fake_influx_client import FakeInfluxClient
from .fake.fake_pinecone_client import FakePineconeClient
from .fake.fake_resend_client import FakeResendClient
from .fake.fake_stripe_client import FakeStripeClient
from .fake.fake_supabase_client import FakeSupabaseClient, SupabaseBaseClass
from .fake.fake_supabase_client_factory import FakeSupabaseClientFactory
from .implementation.deepgram_client import DeepgramBaseClass, DeepgramClient
from .implementation.docupanda_client import DocupandaBaseClass, DocupandaClient
from .implementation.influx_client import InfluxBaseClass, InfluxClient
from .implementation.openai_client import OpenAIBaseClass, OpenAIClient
from .implementation.pinecone_client import PineconeBaseClass, PineconeClient
from .implementation.resend_client import ResendBaseClass, ResendClient
from .implementation.stripe_client import StripeBaseClass, StripeClient
from .implementation.supabase_client_factory import SupabaseFactoryBaseClass, SupabaseClientFactory

class DependencyContainer:
    def __init__(self):
        self._environment = os.environ.get("ENVIRONMENT")
        self._testing_environment = (self._environment == "testing")
        self._openai_client = None
        self._pinecone_client = None
        self._docupanda_client = None
        self._deepgram_client = None
        self._supabase_client_factory = None
        self._stripe_client = None
        self._resend_client = None
        self._influx_client = None

    def inject_deepgram_client(self) -> DeepgramBaseClass:
        if self._deepgram_client is None:
            self._deepgram_client = FakeDeepgramClient() if self._testing_environment else DeepgramClient()
        return self._deepgram_client

    def inject_openai_client(self) -> OpenAIBaseClass:
        if self._openai_client is None:
            self._openai_client = FakeAsyncOpenAI() if self._testing_environment else OpenAIClient()
        return self._openai_client

    def inject_pinecone_client(self) -> PineconeBaseClass:
        if self._pinecone_client is None:
            self._pinecone_client = FakePineconeClient() if self._testing_environment else PineconeClient()
        return self._pinecone_client

    def inject_docupanda_client(self) -> DocupandaBaseClass:
        if self._docupanda_client is None:
            self._docupanda_client = FakeDocupandaClient() if self._testing_environment else DocupandaClient()
        return self._docupanda_client

    def inject_supabase_client_factory(self) -> SupabaseFactoryBaseClass:
        if self._supabase_client_factory is None:
            fake_admin_client: SupabaseBaseClass = FakeSupabaseClient()
            fake_user_client: SupabaseBaseClass = FakeSupabaseClient()
            self._supabase_client_factory = FakeSupabaseClientFactory(fake_admin_client, fake_user_client) if self._testing_environment else SupabaseClientFactory(environment=os.environ.get("ENVIRONMENT"))
        return self._supabase_client_factory

    def inject_stripe_client(self) -> StripeBaseClass:
        if self._stripe_client is None:
            self._stripe_client = FakeStripeClient() if self._testing_environment else StripeClient()
        return self._stripe_client

    def inject_resend_client(self) -> ResendBaseClass:
        if self._resend_client is not None:
            return self._resend_client

        environment = os.environ.get("ENVIRONMENT")
        if (environment == "prod" or environment == "staging"):
            self._resend_client = ResendClient()
        else:
            self._resend_client = FakeResendClient()
        return self._resend_client

    def inject_influx_client(self) -> InfluxBaseClass:
        if self._influx_client is None:
            self._influx_client = FakeInfluxClient() if self._testing_environment else InfluxClient(environment=self._environment)
        return self._influx_client

dependency_container = DependencyContainer()
