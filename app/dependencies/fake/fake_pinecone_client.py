from datetime import date
from fastapi import Request
from pinecone import Index
from typing import Callable

from ..api.aws_db_base_class import AwsDbBaseClass
from ..api.openai_base_class import OpenAIBaseClass
from ..api.pinecone_base_class import PineconeBaseClass
from ...dependencies.api.pinecone_session_date_override import PineconeQuerySessionDateOverride

class FakePineconeClient(PineconeBaseClass):

    def __init__(self):
        self.vector_store_context_returns_data = False
        self.insert_preexisting_history_num_invocations = 0
        self.update_preexisting_history_num_invocations = 0
        self.fake_vectors_insertion = None
        self.insert_session_vectors_invoked = False
        self.insert_preexisting_history_vectors_invoked = False
        self.update_session_vectors_invoked = False
        self.update_preexisting_history_vectors_invoked = False
        self.delete_session_vectors_invoked = False
        self.delete_preexisting_history_vectors_invoked = False
        self.get_vector_store_context_invoked = False
        self.fetch_historical_context_invoked = False

    async def insert_session_vectors(
        self,
        user_id: str,
        patient_id: str,
        text: str,
        session_report_id: str,
        openai_client: OpenAIBaseClass,
        summarize_chunk: Callable,
        therapy_session_date: date = None
    ) -> list[str]:
        self.fake_vectors_insertion = text
        self.insert_session_vectors_invoked = True
        return ["vector1", "vector2"]

    async def insert_preexisting_history_vectors(
        self,
        user_id: str,
        patient_id: str,
        text: str,
        openai_client: OpenAIBaseClass,
        summarize_chunk: Callable
    ):
        self.insert_preexisting_history_num_invocations = self.insert_preexisting_history_num_invocations + 1
        self.insert_preexisting_history_vectors_invoked = True

    def delete_session_vectors(
        self,
        user_id: str,
        patient_id: str,
        date: date = None
    ):
        self.delete_session_vectors_invoked = True

    def delete_preexisting_history_vectors(
        self,
        user_id: str,
        patient_id: str
    ):
        self.delete_preexisting_history_vectors_invoked = True

    async def update_session_vectors(
        self,
        user_id: str,
        patient_id: str,
        text: str,
        old_date: date,
        new_date: date,
        session_report_id: str,
        openai_client: OpenAIBaseClass,
        summarize_chunk: Callable
    ):
        self.update_session_vectors_invoked = True

    async def update_preexisting_history_vectors(
        self,
        user_id: str,
        patient_id: str,
        text: str,
        openai_client: OpenAIBaseClass,
        summarize_chunk: Callable
    ):
        self.update_preexisting_history_num_invocations = self.update_preexisting_history_num_invocations + 1
        self.update_preexisting_history_vectors_invoked = True

    async def get_vector_store_context(
        self,
        openai_client: OpenAIBaseClass,
        aws_db_client: AwsDbBaseClass,
        query_input: str,
        user_id: str,
        patient_id: str,
        query_top_k: int,
        rerank_vectors: bool,
        request: Request,
        include_preexisting_history: bool = True,
        session_dates_overrides: list[PineconeQuerySessionDateOverride] | None = None
    ) -> str:
        self.get_vector_store_context_invoked = True
        if not self.vector_store_context_returns_data:
            return ""
        return "This is my fake vector context"

    async def fetch_historical_context(
        self,
        index: Index,
        namespace: str
    ):
        self.fetch_historical_context_invoked = True
