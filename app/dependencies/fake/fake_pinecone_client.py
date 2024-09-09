from pinecone import Index

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
                                     user_id: str,
                                     patient_id: str,
                                     text: str,
                                     session_report_id: str,
                                     session_id: str,
                                     auth_manager: AuthManager,
                                     openai_client: OpenAIBaseClass,
                                     wait_for_availability: bool = False,
                                     therapy_session_date: str = None):
        self.fake_vectors_insertion = text

    async def insert_preexisting_history_vectors(self,
                                                 user_id: str,
                                                 patient_id: str,
                                                 text: str,
                                                 session_id: str,
                                                 openai_client: OpenAIBaseClass,
                                                 auth_manager: AuthManager):
        self.insert_preexisting_history_num_invocations = self.insert_preexisting_history_num_invocations + 1

    def delete_session_vectors(self,
                               user_id: str,
                               patient_id: str,
                               date: str = None):
        pass

    def delete_preexisting_history_vectors(self,
                                           user_id: str,
                                           patient_id: str):
        pass

    async def update_session_vectors(self,
                                     user_id: str,
                                     patient_id: str,
                                     text: str,
                                     old_date: str,
                                     new_date: str,
                                     session_id: str,
                                     session_report_id: str,
                                     openai_client: OpenAIBaseClass,
                                     auth_manager: AuthManager,
                                     wait_for_availability: bool = False):
        pass

    async def update_preexisting_history_vectors(self,
                                                 user_id: str,
                                                 patient_id: str,
                                                 text: str,
                                                 session_id: str,
                                                 openai_client: OpenAIBaseClass,
                                                 auth_manager: AuthManager):
        self.update_preexisting_history_num_invocations = self.update_preexisting_history_num_invocations + 1

    async def get_vector_store_context(self,
                                       auth_manager: AuthManager,
                                       openai_client: OpenAIBaseClass,
                                       query_input: str,
                                       user_id: str,
                                       patient_id: str,
                                       query_top_k: int,
                                       rerank_top_n: int,
                                       session_id: str,
                                       include_preexisting_history: bool = True,
                                       session_dates_override: list[PineconeQuerySessionDateOverride] = None) -> str:
        if not self.vector_store_context_returns_data:
            return ""
        return "This is my fake vector context"

    async def fetch_historical_context(self,
                                       index: Index,
                                       namespace: str):
        pass
