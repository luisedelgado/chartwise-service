from abc import ABC, abstractmethod
from langchain.schema import BaseMessage
from pydantic import BaseModel
from typing import AsyncIterable, Awaitable, Callable, Type

class OpenAIBaseClass(ABC):

    LLM_MODEL = "gpt-4o-mini"
    EMBEDDING_MODEL = "text-embedding-3-small"
    GPT_4O_MINI_MAX_OUTPUT_TOKENS = 16000
    GPT_4O_MINI_CONTEXT_WINDOW = 128000
    chat_history: list[BaseMessage] = []

    @abstractmethod
    async def trigger_async_chat_completion(
        self,
        max_tokens: int,
        messages: list,
        expected_output_model: Type[BaseModel] | None = None,
    ) -> BaseModel | str:
        """
        Invokes a chat completion asynchronously.

        Arguments:
        max_tokens – the max tokens allowed for the response output.
        messages – the set of message prompts.
        expected_output_model – the optional output model expected from the completion.
        """
        pass

    @abstractmethod
    async def stream_chat_completion(
        self,
        vector_context: str,
        language_code: str,
        query_input: str,
        is_first_message_in_conversation: bool,
        patient_name: str,
        patient_gender: str,
        calculate_max_tokens: Callable[[str, str], Awaitable[int]],
        last_session_date: str | None = None
    ) -> AsyncIterable[str]:
        """
        Streams a chat completion asynchronously.

        Arguments:
        vector_context – the context found from the vector store.
        language_code – the language code in which the response should be streamed.
        query_input – the query input.
        is_first_message_in_conversation – flag tracking whether it's the first message being sent in the conversation.
        patient_name – the patient name.
        patient_gender – the patient gender.
        last_session_date – the optional last session date for further contextualizing the prompts.
        """
        if False:
            yield  # type: ignore
        raise NotImplementedError

    @abstractmethod
    async def clear_chat_history(self):
        """
        Clears any existing chat history.
        """
        pass

    @abstractmethod
    async def flatten_chat_history(self) -> str:
        """
        Returns a flattened version of the full chat history.
        """
        pass

    @abstractmethod
    async def create_embeddings(
        self,
        text: str
    ):
        """
        Creates embeddings from the incoming text.

        Arguments:
        text – the text to be embedded.
        """
        pass
