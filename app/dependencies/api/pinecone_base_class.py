from abc import ABC

from ..api.openai_base_class import OpenAIBaseClass
from ...managers.auth_manager import AuthManager

class PineconeBaseClass(ABC):

    """
    Inserts a new record to the datastore leveraging the incoming data.
    The record is associated with information about a session.

    Arguments:
    index_id – the index name that should be used to insert the data.
    namespace – the namespace that should be used for manipulating the index.
    text – the text to be inserted in the record.
    session_id – the session_id.
    auth_manager – the auth manager to be leveraged internally.
    openai_client – the openai client to be leveraged internally.
    therapy_session_date – the session_date to be used as metadata (only when scenario is NEW_SESSION).
    """
    async def insert_session_vectors(index_id: str,
                                     namespace: str,
                                     text: str,
                                     session_id: str,
                                     auth_manager: AuthManager,
                                     openai_client: OpenAIBaseClass,
                                     therapy_session_date: str = None):
        pass

    """
    Inserts a new record to the datastore leveraging the incoming data.
    The record is associated with information about pre-existing history.

    Arguments:
    index_id – the index name that should be used to insert the data.
    namespace – the namespace that should be used for manipulating the index.
    text – the text to be inserted in the record.
    session_id – the session_id.
    openai_client – the openai client to be leveraged internally.
    auth_manager – the auth manager to be leveraged internally.
    """
    async def insert_preexisting_history_vectors(index_id: str,
                                                 namespace: str,
                                                 text: str,
                                                 session_id: str,
                                                 openai_client: OpenAIBaseClass,
                                                 auth_manager: AuthManager):
        pass

    """
    Deletes session vectors. If the date param is None, it deletes everything inside the namespace.
    Otherwise it deletes the vectors that match the date filtering prefix.

    Arguments:
    index_id – the index where vectors will be deleted.
    namespace – the specific namespace where vectors will be deleted.
    date – the optional value to be used as a filtering prefix.
    """
    def delete_session_vectors(index_id, namespace, date=None):
        pass

    """
    Deletes pre-existing history vectors.

    Arguments:
    index_id – the index where vectors will be deleted.
    namespace – the specific namespace where vectors will be deleted.
    """
    def delete_preexisting_history_vectors(index_id, namespace):
        pass

    """
    Deletes a full index. This is an operation typically associated with a therapist wanting
    to leave the platform, and therefore delete all of their data.

    Arguments:
    index_id – the index where vectors will be deleted.
    """
    def delete_index(index_id):
        pass

    """
    Updates a session record leveraging the incoming data.

    Arguments:
    index_id – the index that should be used to update the data.
    namespace – the namespace that should be used for manipulating the index.
    text – the text to be inserted in the record.
    date – the session_date to be used as metadata.
    session_id – the session_id.
    openai_client – the openai client to be leveraged internally.
    auth_manager – the auth manager to be leveraged internally.
    """
    async def update_session_vectors(index_id: str,
                                     namespace: str,
                                     text: str,
                                     old_date: str,
                                     new_date: str,
                                     session_id: str,
                                     openai_client: OpenAIBaseClass,
                                     auth_manager: AuthManager):
        pass

    """
    Updates a pre-existig history record leveraging the incoming data.

    Arguments:
    index_id – the index that should be used to update the data.
    namespace – the namespace that should be used for manipulating the index.
    text – the text to be inserted in the record.
    session_id – the session_id.
    openai_client – the openai client to be leveraged internally.
    auth_manager – the auth manager to be leveraged internally.
    """
    async def update_preexisting_history_vectors(index_id: str,
                                                 namespace: str,
                                                 text: str,
                                                 session_id: str,
                                                 openai_client: OpenAIBaseClass,
                                                 auth_manager: AuthManager):
        pass
