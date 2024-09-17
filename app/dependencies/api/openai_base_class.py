from abc import ABC
from langchain.schema import BaseMessage
from typing import AsyncIterable, Mapping

from ...managers.auth_manager import AuthManager

class OpenAIBaseClass(ABC):

    LLM_MODEL = "gpt-4o-mini"
    EMBEDDING_MODEL = "text-embedding-3-small"
    RERANK_ACTION_NAME = "rerank_vectors"
    GPT_4O_MINI_MAX_OUTPUT_TOKENS = 16000
    chat_history: list[BaseMessage] = []

    """
    Invokes a chat completion asynchronously.

    Arguments:
    max_tokens – the max tokens allowed for the response output.
    messages – the set of message prompts.
    expects_json_response – a flag representing whether or not the response is expected to be in json format.
    use_monitoring_proxy – flag to determine whether or not the monitoring proxy is used.
    monitoring_proxy_headers – the headers to be used by the monitoring proxy.
    monitoring_proxy_url – the optional url for the monitoring proxy.
    """
    async def trigger_async_chat_completion(max_tokens: int,
                                            messages: list,
                                            expects_json_response: bool,
                                            use_monitoring_proxy: bool,
                                            monitoring_proxy_headers: Mapping = None,
                                            monitoring_proxy_url: str = None):
        pass

    """
    Streams a chat completion asynchronously.

    Arguments:
    vector_context – the context found from the vector store.
    language_code – the language code in which the response should be streamed.
    query_input – the query input.
    is_first_message_in_conversation – flag tracking whether it's the first message being sent in the conversation.
    patient_name – the patient name.
    patient_gender – the patient gender.
    use_monitoring_proxy – flag determining whether to use the monitoring proxy.
    monitoring_proxy_url – the optional monitoring proxy url.
    monitoring_proxy_headers – the optional monitoring proxy headers.
    last_session_date – the optional last session date for further contextualizing the prompts.
    """
    async def stream_chat_completion(vector_context: str,
                                     language_code: str,
                                     query_input: str,
                                     is_first_message_in_conversation: bool,
                                     patient_name: str,
                                     patient_gender: str,
                                     use_monitoring_proxy: bool,
                                     monitoring_proxy_url: str = None,
                                     monitoring_proxy_headers: Mapping = None,
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
    text – the text to be embedded.
    use_monitoring_proxy – flag determining whether to use the monitoring proxy.
    """
    async def create_embeddings(text: str,
                                use_monitoring_proxy: bool):
        pass

    """
    Reranks documents based on similarity to the input query.

    Arguments:
    documents – the set of documents to be reranked.
    top_n – the top n documents that should be returned after reranking.
    query_input – the input query.
    use_monitoring_proxy – flag to determine whether or not the monitoring proxy is used.
    monitoring_proxy_url – the optional url for the monitoring proxy.
    monitoring_proxy_headers – the headers to be used for the monitoring proxy.
    """
    async def rerank_documents(documents: list,
                               top_n: int,
                               query_input: str,
                               use_monitoring_proxy: bool,
                               monitoring_proxy_url: str = None,
                               monitoring_proxy_headers: Mapping = None):
        pass
