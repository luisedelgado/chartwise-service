import os

from .fake.fake_async_openai import FakeAsyncOpenAI
from .fake.fake_aws_cognito_client import FakeAwsCognitoClient
from .fake.fake_aws_db_client import FakeAwsDbClient
from .fake.fake_aws_kms_client import AwsKmsBaseClass, FakeAwsKmsClient
from .fake.fake_aws_s3_client import FakeAwsS3Client
from .fake.fake_aws_secret_manager_client import AwsSecretManagerBaseClass, FakeAwsSecretManagerClient
from .fake.fake_deepgram_client import FakeDeepgramClient
from .fake.fake_docupanda_client import FakeDocupandaClient
from .fake.fake_influx_client import FakeInfluxClient
from .fake.fake_pinecone_client import FakePineconeClient
from .fake.fake_resend_client import FakeResendClient
from .fake.fake_stripe_client import FakeStripeClient
from .implementation.aws_cognito_client import AwsCognitoBaseClass, AwsCognitoClient
from .implementation.aws_db_client import AwsDbBaseClass, AwsDbClient
from .implementation.aws_kms_client import AwsKmsClient
from .implementation.aws_s3_client import AwsS3BaseClass, AwsS3Client
from .implementation.aws_secret_manager_client import AwsSecretManagerClient
from .implementation.deepgram_client import DeepgramBaseClass, DeepgramClient
from .implementation.docupanda_client import DocupandaBaseClass, DocupandaClient
from .implementation.influx_client import InfluxBaseClass, InfluxClient
from .implementation.openai_client import OpenAIBaseClass, OpenAIClient
from .implementation.pinecone_client import PineconeBaseClass, PineconeClient
from .implementation.resend_client import ResendBaseClass, ResendClient
from .implementation.stripe_client import StripeBaseClass, StripeClient
from ..internal.schemas import PROD_ENVIRONMENT, STAGING_ENVIRONMENT, TESTING_ENVIRONMENT
from ..internal.security.chartwise_encryptor import ChartWiseEncryptor

class DependencyContainer:
    def __init__(self):
        self._environment = os.environ.get("ENVIRONMENT")
        self._testing_environment = (self._environment == TESTING_ENVIRONMENT)
        self._openai_client = None
        self._pinecone_client = None
        self._docupanda_client = None
        self._deepgram_client = None
        self._stripe_client = None
        self._resend_client = None
        self._influx_client = None
        self._aws_secret_manager_client = None
        self._aws_cognito_client = None
        self._aws_db_client = None
        self._aws_kms_client = None
        self._aws_s3_client = None
        self._chartwise_encryptor = None

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
            self._pinecone_client = FakePineconeClient() if self._testing_environment else PineconeClient(encryptor=self.inject_chartwise_encryptor())
        return self._pinecone_client

    def inject_docupanda_client(self) -> DocupandaBaseClass:
        if self._docupanda_client is None:
            self._docupanda_client = FakeDocupandaClient() if self._testing_environment else DocupandaClient()
        return self._docupanda_client

    def inject_stripe_client(self) -> StripeBaseClass:
        if self._stripe_client is None:
            self._stripe_client = FakeStripeClient() if self._testing_environment else StripeClient()
        return self._stripe_client

    def inject_resend_client(self) -> ResendBaseClass:
        if self._resend_client is not None:
            return self._resend_client

        environment = os.environ.get("ENVIRONMENT")
        if (environment == PROD_ENVIRONMENT or environment == STAGING_ENVIRONMENT):
            self._resend_client = ResendClient()
        else:
            self._resend_client = FakeResendClient()
        return self._resend_client

    def inject_influx_client(self) -> InfluxBaseClass:
        if self._influx_client is None:
            self._influx_client = FakeInfluxClient() if self._testing_environment else InfluxClient(environment=self._environment)
        return self._influx_client

    def inject_aws_cognito_client(self) -> AwsCognitoBaseClass:
        if self._aws_cognito_client is None:
            self._aws_cognito_client = FakeAwsCognitoClient() if self._testing_environment else AwsCognitoClient()
        return self._aws_cognito_client

    def inject_aws_db_client(self) -> AwsDbBaseClass:
        if self._aws_db_client is None:
            chartwise_encryptor = self.inject_chartwise_encryptor()
            self._aws_db_client: AwsDbBaseClass = FakeAwsDbClient() if self._testing_environment else AwsDbClient(encryptor=chartwise_encryptor)
        return self._aws_db_client

    def inject_aws_kms_client(self) -> AwsKmsBaseClass:
        if self._aws_kms_client is None:
            self._aws_kms_client = FakeAwsKmsClient() if self._testing_environment else AwsKmsClient()
        return self._aws_kms_client

    def inject_aws_s3_client(self) -> AwsS3BaseClass:
        if self._aws_s3_client is None:
            self._aws_s3_client = FakeAwsS3Client() if self._testing_environment else AwsS3Client()
        return self._aws_s3_client

    def inject_aws_secret_manager_client(self) -> AwsSecretManagerBaseClass:
        if self._aws_secret_manager_client is None:
            self._aws_secret_manager_client = FakeAwsSecretManagerClient() if self._testing_environment else AwsSecretManagerClient()
        return self._aws_secret_manager_client

    def inject_chartwise_encryptor(self) -> ChartWiseEncryptor:
        if self._chartwise_encryptor is None:
            self._chartwise_encryptor = ChartWiseEncryptor(
                aws_kms_client=self.inject_aws_kms_client(),
                resend_client=self.inject_resend_client(),
            )
        return self._chartwise_encryptor

dependency_container = DependencyContainer()
