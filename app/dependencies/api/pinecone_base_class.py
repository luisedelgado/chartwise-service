from abc import ABC, abstractmethod
from datetime import date
from fastapi import Request
from pinecone import Index
from typing import Callable

from .pinecone_session_date_override import PineconeQuerySessionDateOverride
from ..api.aws_db_base_class import AwsDbBaseClass
from ..api.openai_base_class import OpenAIBaseClass

class PineconeBaseClass(ABC):

    @abstractmethod
    async def insert_session_vectors(
        self,
        user_id: str,
        patient_id: str,
        text: str,
        session_report_id: str,
        openai_client: OpenAIBaseClass,
        summarize_chunk: Callable,
        therapy_session_date: date | None = None
    ) -> list[str]:
        """
        Inserts a new record to the store leveraging the incoming data.
        The record is associated with information about a session.

        Arguments:
        user_id – the user id associated with the data that will be inserted.
        patient_id – the patient id associated with the data to be inserted.
        text – the text to be inserted in the record.
        session_report_id – the session report id.
        openai_client – the openai client to be leveraged internally.
        summarize_chunk – a callable method used to summarize chunks.
        therapy_session_date – the session_date to be used as metadata (only when scenario is NEW_SESSION).
        """
        pass

    @abstractmethod
    async def insert_preexisting_history_vectors(
        self,
        user_id: str,
        patient_id: str,
        text: str,
        openai_client: OpenAIBaseClass,
        summarize_chunk: Callable,
    ):
        """
        Inserts a new record to the store leveraging the incoming data.
        The record is associated with information about pre-existing history.

        Arguments:
        user_id – the user id associated with the operation.
        patient_id – the patient id associated with the operation.
        text – the text to be inserted in the record.
        openai_client – the openai client to be leveraged internally.
        summarize_chunk – a callable method used to summarize chunks.
        """
        pass

    @abstractmethod
    def delete_session_vectors(
        self,
        user_id: str,
        patient_id: str,
        date: date | None = None,
    ):
        """
        Deletes session vectors. If the date param is None, it deletes everything inside the namespace.
        Otherwise it deletes the vectors that match the date filtering prefix.

        Arguments:
        user_id – the user id associated with the operation.
        patient_id – the patient id associated with the operation.
        date – the optional value to be used as a filtering prefix.
        """
        pass

    @abstractmethod
    def delete_preexisting_history_vectors(
        self,
        user_id: str,
        patient_id: str,
    ):
        """
        Deletes pre-existing history vectors.

        Arguments:
        user_id – the user id associated with the operation.
        patient_id – the patient id associated with the operation.
        """
        pass

    @abstractmethod
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
        """
        Updates a session record leveraging the incoming data.

        Arguments:
        user_id – the user id associated with the operation.
        patient_id – the patient id associated with the operation.
        old_date – the date associated with the old version of the record.
        new_date – the date associated with the new version of the record.
        session_report_id – the session report id.
        openai_client – the openai client to be leveraged internally.
        summarize_chunk – a callable method used to summarize chunks.
        """
        pass

    @abstractmethod
    async def update_preexisting_history_vectors(
        self,
        user_id: str,
        patient_id: str,
        text: str,
        openai_client: OpenAIBaseClass,
        summarize_chunk: Callable
    ):
        """
        Updates a pre-existig history record leveraging the incoming data.

        Arguments:
        user_id – the user id associated with the operation.
        patient_id – the patient id associated with the operation.
        text – the text to be inserted in the record.
        openai_client – the openai client to be leveraged internally.
        summarize_chunk – a callable method used to summarize chunks.
        """
        pass

    @abstractmethod
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
        """
        Retrieves the vector context associated with the incoming query_input.

        Arguments:
        openai_client – the openai client to be leveraged internally.
        aws_db_client – the AWS DB client to be leveraged internally.
        query_input – the query that was triggered by a user.
        user_id – the user id associated with the context.
        patient_id – the patient id associated with the context.
        query_top_k – the top k results that should be retrieved from the vector store.
        rerank_vectors – flag for determining whether vectors should get reranked.
        request – the FastAPI request associated with the operation.
        include_preexisting_history – flag determinig whether the context will include the patient's preexisting history.
        session_dates_overrides – the optional override for including session-date-specific vectors.
        """
        pass

    @abstractmethod
    async def fetch_historical_context(
        self,
        index: Index,
        namespace: str,
    ):
        """
        Retrieves the historical context associated with a patient, if exists.

        Arguments:
        index_id – the index that should be used to query the data.
        namespace – the namespace that should be used for querying the index.
        """
        pass
