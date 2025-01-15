from abc import ABC, abstractmethod
from langchain.schema import BaseMessage
from typing import AsyncIterable

class OpenAIBaseClass(ABC):

    LLM_MODEL = "gpt-4o-mini"
    EMBEDDING_MODEL = "text-embedding-3-small"
    GPT_4O_MINI_MAX_OUTPUT_TOKENS = 16000
    chat_history: list[BaseMessage] = []

    """
    Invokes a chat completion asynchronously.

    Arguments:
    metadata – the metadata to be used when logging.
    max_tokens – the max tokens allowed for the response output.
    messages – the set of message prompts.
    expects_json_response – a flag representing whether or not the response is expected to be in json format.
    cache_configuration – the optional cache configuration.
    """
    @abstractmethod
    async def trigger_async_chat_completion(metadata: dict,
                                            max_tokens: int,
                                            messages: list,
                                            expects_json_response: bool,
                                            cache_configuration: dict = None):
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
    metadata – the metadata associated with the completion request.
    last_session_date – the optional last session date for further contextualizing the prompts.
    """
    @abstractmethod
    async def stream_chat_completion(vector_context: str,
                                     language_code: str,
                                     query_input: str,
                                     is_first_message_in_conversation: bool,
                                     patient_name: str,
                                     patient_gender: str,
                                     metadata: dict,
                                     last_session_date: str = None) -> AsyncIterable[str]:
        pass

    """
    Clears any existing chat history.
    """
    @abstractmethod
    async def clear_chat_history():
        pass

    """
    Returns a flattened version of the full chat history.
    """
    @abstractmethod
    async def flatten_chat_history() -> str:
        pass

    """
    Creates embeddings from the incoming text.

    Arguments:
    text – the text to be embedded.
    """
    @abstractmethod
    async def create_embeddings(text: str):
        pass
