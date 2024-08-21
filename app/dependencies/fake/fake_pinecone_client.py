from pinecone import Index
from typing import Tuple

from ..api.openai_base_class import OpenAIBaseClass
from ..api.pinecone_base_class import PineconeBaseClass
from ...dependencies.api.pinecone_session_date_override import PineconeQuerySessionDateOverride
from ...managers.auth_manager import AuthManager

class FakePineconeClient(PineconeBaseClass):

    def __init__(self):
        self.vector_store_context_returns_data = False
        self.insert_preexisting_history_num_invocations = 0
        self.update_preexisting_history_num_invocations = 0
        self.fake_vectors_insertion = None

    async def insert_session_vectors(self,
                                     index_id: str,
                                     namespace: str,
                                     text: str,
                                     session_id: str,
                                     auth_manager: AuthManager,
                                     openai_client: OpenAIBaseClass,
                                     therapy_session_date: str = None):
        self.fake_vectors_insertion = text

    async def insert_preexisting_history_vectors(self,
                                                 index_id: str,
                                                 namespace: str,
                                                 text: str,
                                                 session_id: str,
                                                 openai_client: OpenAIBaseClass,
                                                 auth_manager: AuthManager):
        self.insert_preexisting_history_num_invocations = self.insert_preexisting_history_num_invocations + 1

    async def create_index(self, index_id):
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
        self.update_preexisting_history_num_invocations = self.update_preexisting_history_num_invocations + 1

    async def get_vector_store_context(self,
                                       auth_manager: AuthManager,
                                       openai_client: OpenAIBaseClass,
                                       query_input: str,
                                       index_id: str,
                                       namespace: str,
                                       query_top_k: int,
                                       rerank_top_n: int,
                                       session_id: str,
                                       session_dates_override: list[PineconeQuerySessionDateOverride] = None) -> Tuple[bool, str]:
        if not self.vector_store_context_returns_data:
            return (False, "")
        return (True, "This is my fake vector context")

    async def fetch_historical_context(self,
                                       index: Index,
                                       namespace: str):
        pass
