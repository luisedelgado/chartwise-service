import os

from openai import AsyncOpenAI
from openai.types import Completion
from portkey_ai import Portkey

from ...dependencies.api.openai_base_class import OpenAIBaseClass
from ...managers.auth_manager import AuthManager

class OpenAIClient(OpenAIBaseClass):

    LLM_MODEL = "gpt-4o-mini"
    EMBEDDING_MODEL = "text-embedding-3-small"

    async def trigger_async_chat_completion(self,
                                            metadata: dict,
                                            max_tokens: int,
                                            messages: list,
                                            expects_json_response: bool,
                                            auth_manager: AuthManager,
                                            cache_configuration: dict = None):
        try:
            is_monitoring_proxy_reachable = auth_manager.is_monitoring_proxy_reachable()

            if is_monitoring_proxy_reachable:
                api_base = auth_manager.get_monitoring_proxy_url()
                cache_max_age = None if (cache_configuration is None or 'cache_max_age' not in cache_configuration) else cache_configuration['cache_max_age']
                caching_shard_key = None if (cache_configuration is None or 'caching_shard_key' not in cache_configuration) else cache_configuration['caching_shard_key']
                proxy_headers = auth_manager.create_monitoring_proxy_headers(metadata=metadata,
                                                                             caching_shard_key=caching_shard_key,
                                                                             cache_max_age=cache_max_age,
                                                                             llm_model=self.LLM_MODEL)
            else:
                api_base = None
                proxy_headers = None

            openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"),
                                        default_headers=proxy_headers,
                                        base_url=api_base)

            response: Completion = await openai_client.chat.completions.create(
                model=self.LLM_MODEL,
                messages=messages,
                temperature=0,
                max_tokens=max_tokens
            )

            response_text = response.choices[0].message.content.strip()
            return response_text if not expects_json_response else eval(str(response_text))
        except Exception as e:
            raise Exception(e)

    async def stream_chat_completion(self,
                                     metadata: dict,
                                     max_tokens: int,
                                     messages: list,
                                     auth_manager: AuthManager,
                                     cache_configuration: dict = None):
        try:
            is_monitoring_proxy_reachable = auth_manager.is_monitoring_proxy_reachable()

            if is_monitoring_proxy_reachable:
                api_base = auth_manager.get_monitoring_proxy_url()
                cache_max_age = None if (cache_configuration is None or 'cache_max_age' not in cache_configuration) else cache_configuration['cache_max_age']
                caching_shard_key = None if (cache_configuration is None or 'caching_shard_key' not in cache_configuration) else cache_configuration['caching_shard_key']
                proxy_headers = auth_manager.create_monitoring_proxy_headers(metadata=metadata,
                                                                             caching_shard_key=caching_shard_key,
                                                                             cache_max_age=cache_max_age,
                                                                             llm_model=self.LLM_MODEL)
            else:
                api_base = None
                proxy_headers = None

            openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"),
                                        default_headers=proxy_headers,
                                        base_url=api_base)

            response: Completion = await openai_client.chat.completions.create(
                model=self.LLM_MODEL,
                messages=messages,
                temperature=0,
                stream=True,
                max_tokens=max_tokens
            )

            async for part in response:
                if 'choices' in part:
                    yield part["choices"][0]["text"]

        except Exception as e:
            raise Exception(e)

    async def create_embeddings(self,
                                auth_manager: AuthManager,
                                text: str):
        if auth_manager.is_monitoring_proxy_reachable():
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
            for item in response.dict()['data']:
                embeddings.extend(item['embedding'])
            return embeddings
