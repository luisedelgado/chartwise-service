from pinecone import Index

from ..api.openai_base_class import OpenAIBaseClass
from ..api.pinecone_base_class import PineconeBaseClass
from ...dependencies.api.pinecone_session_date_override import PineconeQuerySessionDateOverride
from ...managers.auth_manager import AuthManager

class FakePineconeClient(PineconeBaseClass):

    async def insert_session_vectors(self,
                                     index_id: str,
                                     namespace: str,
                                     text: str,
                                     session_id: str,
                                     auth_manager: AuthManager,
                                     openai_client: OpenAIBaseClass,
                                     therapy_session_date: str = None):
        pass

    async def insert_preexisting_history_vectors(self,
                                                 index_id: str,
                                                 namespace: str,
                                                 text: str,
                                                 session_id: str,
                                                 openai_client: OpenAIBaseClass,
                                                 auth_manager: AuthManager):
        pass

    def delete_session_vectors(self, index_id, namespace, date=None):
        pass

    def delete_preexisting_history_vectors(self, index_id, namespace):
        pass

    def delete_index(self, index_id):
        pass

    async def update_session_vectors(self,
                                     index_id: str,
                                     namespace: str,
                                     text: str,
                                     old_date: str,
                                     new_date: str,
                                     session_id: str,
                                     openai_client: OpenAIBaseClass,
                                     auth_manager: AuthManager):
        pass

    async def update_preexisting_history_vectors(self,
                                                 index_id: str,
                                                 namespace: str,
                                                 text: str,
                                                 session_id: str,
                                                 openai_client: OpenAIBaseClass,
                                                 auth_manager: AuthManager):
        pass

    async def get_vector_store_context(auth_manager: AuthManager,
                                       openai_client: OpenAIBaseClass,
                                       query_input: str,
                                       index_id: str,
                                       namespace: str,
                                       query_top_k: int,
                                       rerank_top_n: int,
                                       session_date_override: PineconeQuerySessionDateOverride = None) -> str:
        pass

    def fetch_historical_context(index: Index,
                                 namespace: str):
        pass
