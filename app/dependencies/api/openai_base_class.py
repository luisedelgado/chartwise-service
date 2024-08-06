from abc import ABC
from typing import AsyncIterable

from ...managers.auth_manager import AuthManager

class OpenAIBaseClass(ABC):

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
    metadata – the metadata to be used when logging.
    max_tokens – the max tokens allowed for the response output.
    user_prompt – the user prompt to be used.
    system_prompt – the system prompt to be used.
    auth_manager – the auth_manager to be leveraged internally.
    cache_configuration – the optional cache configuration.
    """
    async def stream_chat_completion(metadata: dict,
                                     max_tokens: int,
                                     user_prompt: str,
                                     system_prompt: str,
                                     auth_manager: AuthManager,
                                     cache_configuration: dict = None) -> AsyncIterable[str]:
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
