from abc import ABC

from pinecone import Index
from typing import Mapping

from .pinecone_session_date_override import PineconeQuerySessionDateOverride
from ..api.openai_base_class import OpenAIBaseClass

class PineconeBaseClass(ABC):

    """
    Inserts a new record to the datastore leveraging the incoming data.
    The record is associated with information about a session.

    Arguments:
    user_id – the user id associated with the data that will be inserted.
    patient_id – the patient id associated with the data to be inserted.
    text – the text to be inserted in the record.
    session_report_id – the session report id.
    openai_client – the openai client to be leveraged internally.
    use_monitoring_proxy – flag determining whether or not we should use the monitoring proxy.
    monitoring_proxy_url – the optional monitoring proxy url.
    monitoring_proxy_headers – the optional monitoring proxy headers.
    therapy_session_date – the session_date to be used as metadata (only when scenario is NEW_SESSION).
    """
    async def insert_session_vectors(user_id: str,
                                     patient_id: str,
                                     text: str,
                                     session_report_id: str,
                                     openai_client: OpenAIBaseClass,
                                     use_monitoring_proxy: bool,
                                     monitoring_proxy_headers: Mapping = None,
                                     monitoring_proxy_url: str = None,
                                     therapy_session_date: str = None):
        pass

    """
    Inserts a new record to the datastore leveraging the incoming data.
    The record is associated with information about pre-existing history.

    Arguments:
    user_id – the user id associated with the operation.
    patient_id – the patient id associated with the operation.
    text – the text to be inserted in the record.
    openai_client – the openai client to be leveraged internally.
    use_monitoring_proxy – flag determining whether or not we should use the monitoring proxy.
    monitoring_proxy_url – the optional monitoring proxy url.
    monitoring_proxy_headers – the optional monitoring proxy headers.
    """
    async def insert_preexisting_history_vectors(user_id: str,
                                                 patient_id: str,
                                                 text: str,
                                                 openai_client: OpenAIBaseClass,
                                                 use_monitoring_proxy: bool,
                                                 monitoring_proxy_url: str = None,
                                                 monitoring_proxy_headers: Mapping = None):
        pass

    """
    Deletes session vectors. If the date param is None, it deletes everything inside the namespace.
    Otherwise it deletes the vectors that match the date filtering prefix.

    Arguments:
    user_id – the user id associated with the operation.
    patient_id – the patient id associated with the operation.
    date – the optional value to be used as a filtering prefix.
    """
    def delete_session_vectors(user_id: str,
                               patient_id: str,
                               date: str = None):
        pass

    """
    Deletes pre-existing history vectors.

    Arguments:
    user_id – the user id associated with the operation.
    patient_id – the patient id associated with the operation.
    """
    def delete_preexisting_history_vectors(user_id: str, patient_id: str):
        pass

    """
    Updates a session record leveraging the incoming data.

    Arguments:
    user_id – the user id associated with the operation.
    patient_id – the patient id associated with the operation.
    old_date – the date associated with the old version of the record.
    new_date – the date associated with the new version of the record.
    session_report_id – the session report id.
    openai_client – the openai client to be leveraged internally.
    use_monitoring_proxy – flag determining whether or not we should use the monitoring proxy.
    monitoring_proxy_url – the optional monitoring proxy url.
    monitoring_proxy_headers – the optional monitoring proxy headers.
    """
    async def update_session_vectors(user_id: str,
                                     patient_id: str,
                                     text: str,
                                     old_date: str,
                                     new_date: str,
                                     session_report_id: str,
                                     openai_client: OpenAIBaseClass,
                                     use_monitoring_proxy: bool,
                                     monitoring_proxy_url: str = None,
                                     monitoring_proxy_headers: Mapping = None):
        pass

    """
    Updates a pre-existig history record leveraging the incoming data.

    Arguments:
    user_id – the user id associated with the operation.
    patient_id – the patient id associated with the operation.
    text – the text to be inserted in the record.
    openai_client – the openai client to be leveraged internally.
    use_monitoring_proxy – flag determining whether or not we should use the monitoring proxy.
    monitoring_proxy_url – the optional monitoring proxy url.
    monitoring_proxy_headers – the optional monitoring proxy headers.
    """
    async def update_preexisting_history_vectors(user_id: str,
                                                 patient_id: str,
                                                 text: str,
                                                 openai_client: OpenAIBaseClass,
                                                 use_monitoring_proxy: bool,
                                                 monitoring_proxy_url: str = None,
                                                 monitoring_proxy_headers: Mapping = None):
        pass

    """
    Retrieves the vector context associated with the incoming query_input.

    Arguments:
    openai_client – the openai client to be leveraged internally.
    query_input – the query that was triggered by a user.
    user_id – the user id associated with the context.
    patient_id – the patient id associated with the context.
    query_top_k – the top k results that should be retrieved from the vector store.
    rerank_top_n – the top n results that should be returned after reranking vectors.
    use_monitoring_proxy – flag determining whether or not we should use the monitoring proxy.
    monitoring_proxy_url – the optional monitoring proxy url.
    monitoring_proxy_headers – the optional monitoring proxy headers.
    include_preexisting_history – flag determinig whether the context will include the patient's preexisting history.
    session_date_override – the optional override for including session-date-specific vectors.
    """
    async def get_vector_store_context(openai_client: OpenAIBaseClass,
                                       query_input: str,
                                       user_id: str,
                                       patient_id: str,
                                       query_top_k: int,
                                       rerank_top_n: int,
                                       use_monitoring_proxy: bool,
                                       monitoring_proxy_url: str = None,
                                       monitoring_proxy_headers: Mapping = None,
                                       include_preexisting_history: bool = True,
                                       session_dates_override: list[PineconeQuerySessionDateOverride] = None) -> str:
        pass

    """
    Retrieves the historical context associated with a patient, if exists.

    Arguments:
    index_id – the index that should be used to query the data.
    namespace – the namespace that should be used for querying the index.
    """
    async def fetch_historical_context(index: Index,
                                       namespace: str):
        pass
