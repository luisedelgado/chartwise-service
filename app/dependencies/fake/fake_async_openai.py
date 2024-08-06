from typing import AsyncIterable

from ..api.openai_base_class import OpenAIBaseClass
from ...managers.auth_manager import AuthManager

class FakeOpenAICompletions:

    def __init__(self, create_returns_data: bool):
        self.create_returns_data = create_returns_data

    def create(self,
               model: str,
               messages: list,
               temperature: int,
               max_tokens: int):
        if not self.create_returns_data:
            return {}

        return {
            'choices': [
                {
                    'message': {
                        'content': 'fake content'
                    }
                }
            ]
        }

class FakeOpenAIChat:

    def __init__(self, completions_return_data: bool):
        self.completions = FakeOpenAICompletions(create_returns_data=completions_return_data)

class FakeAsyncOpenAI(OpenAIBaseClass):

    def __init__(self):
        self._chat = FakeOpenAIChat(completions_return_data=True)

    async def trigger_async_chat_completion(self,
                                            metadata: dict,
                                            max_tokens: int,
                                            messages: list,
                                            expects_json_response: bool,
                                            auth_manager: AuthManager,
                                            cache_configuration: dict = None):
        return {
            "summary": "my fake summary",
            "questions": ["question"],
            "topics": ["topic"]
        }

    async def stream_chat_completion(self,
                                     metadata: dict,
                                     max_tokens: int,
                                     user_prompt: str,
                                     system_prompt: str,
                                     auth_manager: AuthManager,
                                     cache_configuration: dict = None) -> AsyncIterable[str]:
        yield "my result"

    async def create_embeddings(self,
                                auth_manager: AuthManager,
                                text: str):
        return [""]

    @property
    def chat(self):
        return self._chat

    @chat.setter
    def chat(self, returns_data: bool):
        self._chat = FakeOpenAIChat(completions_return_data=returns_data)
