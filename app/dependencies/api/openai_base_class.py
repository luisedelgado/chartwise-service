from abc import ABC
from langchain.schema import BaseMessage
from typing import AsyncIterable

from ...managers.auth_manager import AuthManager

class OpenAIBaseClass(ABC):

    GPT_4O_MINI_MAX_OUTPUT_TOKENS = 16000
    chat_history: list[BaseMessage] = []

    """
    Invokes a chat completion asynchronously.

    Arguments:
    metadata – the metadata to be used when logging.
    max_tokens – the max tokens allowed for the response output.
    messages – the set of message prompts.
    expects_json_response – a flag representing whether or not the response is expected to be in json format.
    auth_manager – the auth_manager to be leveraged internally.
    cache_configuration – the optional cache configuration.
    """
    async def trigger_async_chat_completion(metadata: dict,
                                            max_tokens: int,
                                            messages: list,
                                            expects_json_response: bool,
                                            auth_manager: AuthManager,
                                            cache_configuration: dict = None):
        pass

    """
    Streams a chat completion asynchronously.

    Arguments:
    vector_context – the context found from the vector store.
    language_code – the language code in which the response should be streamed.
    query_input – the query input.
    patient_id – the patient id.
    patient_name – the patient name.
    patient_gender – the patient gender.
    metadata – the metadata to be used when logging.
    auth_manager – the auth_manager to be leveraged internally.
    last_session_date – the optional last session date for further contextualizing the prompts.
    """
    async def stream_chat_completion(vector_context: str,
                                     language_code: str,
                                     query_input: str,
                                     patient_id: str,
                                     patient_name: str,
                                     patient_gender: str,
                                     metadata: dict,
                                     auth_manager: AuthManager,
                                     last_session_date: str = None) -> AsyncIterable[str]:
        pass

    """
    Clears any existing chat history.
    """
    async def clear_chat_history():
        pass

    """
    Returns a flattened version of the full chat history.
    """
    async def flatten_chat_history() -> str:
        pass

    """
    Creates embeddings from the incoming text.

    Arguments:
    auth_manager – the auth_manager to be leveraged internally.
    text – the text to be embedded.
    """
    async def create_embeddings(auth_manager: AuthManager,
                                text: str):
        pass

    """
    Reranks documents based on similarity to the input query.

    Arguments:
    auth_manager – the auth_manager to be leveraged internally.
    documents – the set of documents to be reranked.
    top_n – the top n documents that should be returned after reranking.
    query_input – the input query.
    session_id – the session id.
    user_id – the user id.
    """
    async def rerank_documents(auth_manager: AuthManager,
                               documents: list,
                               top_n: int,
                               query_input: str,
                               session_id: str,
                               user_id: str):
        pass
