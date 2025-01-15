import asyncio

from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.schema import HumanMessage
from langchain_core.messages.ai import AIMessage
from typing import AsyncIterable, Awaitable

from ..api.openai_base_class import OpenAIBaseClass

FAKE_ASSISTANT_RESPONSE = "This is my fake response"

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

    throws_exception = False

    def __init__(self):
        self._chat = FakeOpenAIChat(completions_return_data=True)

    async def trigger_async_chat_completion(self,
                                            metadata: dict,
                                            max_tokens: int,
                                            messages: list,
                                            expects_json_response: bool,
                                            cache_configuration: dict = None):
        if self.throws_exception:
            raise Exception("Fake exception")

        return {
            "summary": "my fake summary",
            "questions": ["question"],
            "topics": ["topic"]
        }

    async def stream_chat_completion(self,
                                     vector_context: str,
                                     language_code: str,
                                     query_input: str,
                                     is_first_message_in_conversation: bool,
                                     patient_name: str,
                                     patient_gender: str,
                                     metadata: dict,
                                     last_session_date: str = None) -> AsyncIterable[str]:
        async def wrap_done(fn: Awaitable, event: asyncio.Event):
                try:
                    await fn
                except Exception as e:
                    raise Exception(e)
                finally:
                    event.set()

        human_message = HumanMessage(content=f"{query_input}")
        callback = AsyncIteratorCallbackHandler()

        async def inline_coroutine():
                await asyncio.sleep(1)
                return "Hello from the inline coroutine!"

        task = asyncio.create_task(wrap_done(
            inline_coroutine(),
            callback.done),
        )

        yield FAKE_ASSISTANT_RESPONSE

        self.chat_history.append(human_message)
        self.chat_history.append(AIMessage(content=FAKE_ASSISTANT_RESPONSE))

        await task

    async def clear_chat_history(self):
        self.chat_history = []

    async def flatten_chat_history(self) -> str:
        pass

    async def create_embeddings(self,
                                text: str):
        return [""]

    @property
    def chat(self):
        return self._chat

    @chat.setter
    def chat(self, returns_data: bool):
        self._chat = FakeOpenAIChat(completions_return_data=returns_data)
