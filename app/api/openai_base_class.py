from abc import ABC

from ..managers.implementations.auth_manager import AuthManager

class OpenAIBaseClass(ABC):

    async def trigger_async_chat_completion(metadata: dict,
                                            max_tokens: int,
                                            messages: list,
                                            expects_json_response: bool,
                                            auth_manager: AuthManager,
                                            cache_configuration: dict = None):
        pass

    async def stream_chat_completion_internal(metadata: dict,
                                              max_tokens: int,
                                              messages: list,
                                              auth_manager: AuthManager,
                                              cache_configuration: dict = None):
        pass

    async def create_embeddings(auth_manager: AuthManager,
                                text: str):
        pass
