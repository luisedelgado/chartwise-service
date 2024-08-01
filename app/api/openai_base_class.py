from abc import ABC

from ..api.auth_base_class import AuthManagerBaseClass

class OpenAIBaseClass(ABC):

    async def trigger_async_chat_completion(metadata: dict,
                                            max_tokens: int,
                                            messages: list,
                                            expects_json_response: bool,
                                            auth_manager: AuthManagerBaseClass,
                                            cache_configuration: dict = None):
        pass

    async def stream_chat_completion_internal(metadata: dict,
                                              max_tokens: int,
                                              messages: list,
                                              auth_manager: AuthManagerBaseClass,
                                              cache_configuration: dict = None):
        pass

    async def create_embeddings(auth_manager: AuthManagerBaseClass,
                                text: str):
        pass
