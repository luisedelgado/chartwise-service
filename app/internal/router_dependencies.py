from ..dependencies.api.deepgram_base_class import DeepgramBaseClass
from ..dependencies.api.docupanda_base_class import DocupandaBaseClass
from ..dependencies.api.openai_base_class import OpenAIBaseClass
from ..dependencies.api.pinecone_base_class import PineconeBaseClass
from ..dependencies.api.speechmatics_base_class import SpeechmaticsBaseClass
from ..dependencies.api.supabase_factory_base_class import SupabaseFactoryBaseClass

class RouterDependencies:
    def __init__(self,
                 openai_client: OpenAIBaseClass = None,
                 pinecone_client: PineconeBaseClass = None,
                 deepgram_client: DeepgramBaseClass = None,
                 docupanda_client: DocupandaBaseClass = None,
                 speechmatics_client: SpeechmaticsBaseClass = None,
                 supabase_client_factory: SupabaseFactoryBaseClass = None):
        self.openai_client = openai_client
        self.pinecone_client = pinecone_client
        self.docupanda_client = docupanda_client
        self.deepgram_client = deepgram_client
        self.speechmatics_client = speechmatics_client
        self.supabase_client_factory = supabase_client_factory
