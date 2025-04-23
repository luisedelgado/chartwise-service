import asyncio
import os
import tiktoken

from typing import AsyncIterable, Awaitable

from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.schema import HumanMessage, SystemMessage
from langchain_core.messages.ai import AIMessage
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI
from openai.types import Completion
from portkey_ai import Portkey

from ...internal.monitoring_proxy import get_monitoring_proxy_url, use_monitoring_proxy
from ...internal.utilities.general_utilities import create_monitoring_proxy_headers
from ...dependencies.api.openai_base_class import OpenAIBaseClass
from ...vectors.message_templates import PromptCrafter, PromptScenario

class OpenAIClient(OpenAIBaseClass):

    async def trigger_async_chat_completion(self,
                                            metadata: dict,
                                            max_tokens: int,
                                            messages: list,
                                            expects_json_response: bool,
                                            cache_configuration: dict = None):
        try:
            if use_monitoring_proxy():
                api_base = get_monitoring_proxy_url()
                cache_max_age = (None if (cache_configuration is None or 'cache_max_age' not in cache_configuration)
                                    else cache_configuration['cache_max_age'])
                caching_shard_key = (None if (cache_configuration is None or 'caching_shard_key' not in cache_configuration)
                                        else cache_configuration['caching_shard_key'])
                proxy_headers = create_monitoring_proxy_headers(metadata=metadata,
                                                                caching_shard_key=caching_shard_key,
                                                                cache_max_age=cache_max_age,
                                                                llm_model=type(self).LLM_MODEL)
            else:
                api_base = None
                proxy_headers = None

            openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"),
                                        default_headers=proxy_headers,
                                        base_url=api_base)

            response_format = "json_object" if expects_json_response else "text"
            response: Completion = await openai_client.chat.completions.create(
                model=type(self).LLM_MODEL,
                messages=messages,
                temperature=0,
                max_tokens=max_tokens,
                response_format={
                    "type": response_format
                }
            )

            response_message = response.choices[0].message
            assert ('refusal' not in response_message or response_message['refusal'] is None), response_message.refusal

            response_text = response_message.content.strip()
            return response_text if not expects_json_response else eval(response_text)
        except Exception as e:
            raise RuntimeError(e) from e

    async def stream_chat_completion(self,
                                     vector_context: str,
                                     language_code: str,
                                     query_input: str,
                                     is_first_message_in_conversation: bool,
                                     patient_name: str,
                                     patient_gender: str,
                                     metadata: dict,
                                     last_session_date: str = None) -> AsyncIterable[str]:
        try:
            if use_monitoring_proxy():
                monitoring_proxy_url = get_monitoring_proxy_url()
                assert len(monitoring_proxy_url or '') > 0, "Missing monitoring proxy url"

                api_base = monitoring_proxy_url
                proxy_headers = create_monitoring_proxy_headers(metadata=metadata,
                                                                llm_model=type(self).LLM_MODEL)
            else:
                api_base = None
                proxy_headers = None

            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.QUERY,
                                                                       context=vector_context,
                                                                       language_code=language_code,
                                                                       query_input=query_input)

            system_prompt = prompt_crafter.get_system_message_for_scenario(PromptScenario.QUERY,
                                                                           patient_gender=patient_gender,
                                                                           patient_name=patient_name,
                                                                           last_session_date=last_session_date,
                                                                           chat_history_included=(not is_first_message_in_conversation))

            input_window_content = "\n".join([system_prompt,
                                              (await self.flatten_chat_history()),
                                              user_prompt])
            prompt_tokens = len(tiktoken.get_encoding("o200k_base").encode(f"{input_window_content}"))
            max_tokens = self.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            callback = AsyncIteratorCallbackHandler()
            llm_client = ChatOpenAI(
                model=type(self).LLM_MODEL,
                temperature=0,
                streaming=True,
                default_headers=proxy_headers,
                base_url=api_base,
                verbose=True,
                max_tokens=max_tokens,
                callbacks=[callback],
            )

            """Wrap an awaitable with a event to signal when it's done or an exception is raised."""
            async def wrap_done(fn: Awaitable, event: asyncio.Event):
                try:
                    await fn
                except Exception as e:
                    raise RuntimeError(e) from e
                finally:
                    event.set()

            system_message = SystemMessage(content=f"{system_prompt}")
            human_message = HumanMessage(content=f"{user_prompt}")

            task = asyncio.create_task(wrap_done(
                llm_client.agenerate(messages=[
                    [
                        system_message,
                        *self.chat_history,
                        human_message
                    ]
                ]),
                callback.done),
            )

            model_output = ""
            async for token in callback.aiter():
                model_output = "".join([model_output, token])
                yield f"{token}"

            self.chat_history.append(HumanMessage(content=f"{query_input}\n"))
            self.chat_history.append(AIMessage(content=f"{model_output}\n"))

            await task

        except Exception as e:
            raise RuntimeError(e) from e

    async def clear_chat_history(self):
        self.chat_history = []

    async def flatten_chat_history(self) -> str:
        flattened_chat_history = ""
        for chat_message in self.chat_history:
            chat_message_formatted = ""
            if isinstance(chat_message, SystemMessage):
                chat_message_formatted = f"System:\n{chat_message}\n"
            elif isinstance(chat_message, HumanMessage):
                chat_message_formatted = f"User:\n{chat_message}\n"
            elif isinstance(chat_message, AIMessage):
                chat_message_formatted = f"Assistant:\n{chat_message}\n"
            else:
                raise Exception("Untracked message type.")
            flattened_chat_history = "\n".join([flattened_chat_history, chat_message_formatted])
        return flattened_chat_history

    async def create_embeddings(self,
                                text: str):
        if use_monitoring_proxy():
            portkey = Portkey(
                api_key=os.environ.get("PORTKEY_API_KEY"),
                virtual_key=os.environ.get("PORTKEY_OPENAI_VIRTUAL_KEY"),
            )

            query_data = portkey.embeddings.create(
                encoding_format='float',
                input=text,
                model=self.EMBEDDING_MODEL
            ).data
            embeddings = []
            for item in query_data:
                embeddings.extend(item.embedding)
            return embeddings
        else:
            openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            response = await openai_client.embeddings.create(input=[text],
                                                             model=self.EMBEDDING_MODEL)
            embeddings = []
            for item in response.model_dump()['data']:
                embeddings.extend(item['embedding'])
            return embeddings
