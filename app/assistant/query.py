import os, requests, uuid

from datetime import datetime
from fastapi import status
from llama_index.core import VectorStoreIndex
from llama_index.llms.openai import OpenAI as llama_index_openai
from llama_index.vector_stores.pinecone import PineconeVectorStore
from openai import OpenAI
from pinecone import PineconeApiException
from pinecone.grpc import PineconeGRPC
from portkey_ai import PORTKEY_GATEWAY_URL, createHeaders
from pytz import timezone

from . import message_templates

__llm_model = "gpt-3.5-turbo"

class QueryResult:
    def __init__(self, response_token, status_code):
        self.response_token = response_token
        self.status_code = status_code

def __get_current_environment():
    return "prod"

def __is_portkey_reachable() -> bool:
    try:
        return requests.get(PORTKEY_GATEWAY_URL).status_code < status.HTTP_500_INTERNAL_SERVER_ERROR
    except:
        return False

def __create_portkey_config(cache_max_age):
    return {
        "provider": "openai",
        "virtual_key": os.environ.get("PORTKEY_OPENAI_VIRTUAL_KEY"),
        "cache": {
            "mode": "semantic",
            "max_age": cache_max_age,
        },
        "retry": {
            "attempts": 2,
        },
        "override_params": {
            "model": __llm_model,
            "temperature": 0,
        }
    }

def __create_portkey_headers(**kwargs):
    environment = None if "environment" not in kwargs else kwargs["environment"]
    session_id = None if "session_id" not in kwargs else kwargs["session_id"]
    user = None if "user" not in kwargs else kwargs["user"]
    caching_shard_key = None if "caching_shard_key" not in kwargs else kwargs["caching_shard_key"]
    cache_max_age = None if "cache_max_age" not in kwargs else kwargs["cache_max_age"]
    endpoint_name = None if "endpoint_name" not in kwargs else kwargs["endpoint_name"]
    return createHeaders(trace_id=uuid.uuid4(),
                         api_key=os.environ.get("PORTKEY_API_KEY"),
                         config=__create_portkey_config(cache_max_age),
                         cache_namespace=caching_shard_key,
                         debug=False, # Prevents prompts and responses from being logged.
                         metadata={
                            "environment": environment,
                            "user": user,
                            "vector_index": caching_shard_key,
                            "session_id": session_id,
                            "endpoint_name": endpoint_name,
                        })

def query_store(index_id,
                input,
                response_language_code,
                querying_user,
                session_id,
                endpoint_name,) -> QueryResult:
    try:
        # Initialize connection to Pinecone
        pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))
        assert pc.describe_index(index_id).status['ready']

        index = pc.Index(index_id)
        vector_store = PineconeVectorStore(pinecone_index=index)
        vector_index = VectorStoreIndex.from_vector_store(vector_store=vector_store, similarity_top_k=3)

        is_portkey_reachable = __is_portkey_reachable()
        api_base = PORTKEY_GATEWAY_URL if is_portkey_reachable else None
        headers = __create_portkey_headers(environment=__get_current_environment(),
                                           session_id=session_id,
                                           user=querying_user,
                                           cache_max_age=3600, # 1 hour
                                           caching_shard_key=index_id,
                                           endpoint_name=endpoint_name) if is_portkey_reachable else None

        llm = llama_index_openai(model=__llm_model,
                                 temperature=0,
                                 api_base=api_base,
                                 default_headers=headers)
        query_engine = vector_index.as_query_engine(
            text_qa_template=message_templates.create_chat_prompt_template(response_language_code),
            refine_template=message_templates.create_refine_prompt_template(response_language_code),
            llm=llm,
            streaming=True,
        )

        response = query_engine.query(input)
        return QueryResult(str(response), status.HTTP_200_OK)
    except PineconeApiException as e:
        # We expect HTTPCode 404 if the index does not exist - NOT_FOUND
        return QueryResult(str(e), e.status)
    except Exception as e:
        return QueryResult(str(e), status.HTTP_409_CONFLICT)

def create_greeting(name: str,
                    language_code: str,
                    tz_identifier: str,
                    session_id: str,
                    endpoint_name: str,
                    ) -> QueryResult:
    try:
        is_portkey_reachable = __is_portkey_reachable()
        api_base = PORTKEY_GATEWAY_URL if is_portkey_reachable else None
        caching_shard_key = (session_id + "-" + datetime.now().strftime("%d-%m-%Y"))
        headers = __create_portkey_headers(environment=__get_current_environment(),
                                           session_id=session_id,
                                           cache_max_age=86400, # 24 hours
                                           caching_shard_key=caching_shard_key,
                                           endpoint_name=endpoint_name) if is_portkey_reachable else None

        llm = OpenAI(base_url=api_base,
                     default_headers=headers)

        completion = llm.chat.completions.create(
            model=__llm_model,
            messages=[
                {"role": "system", "content": message_templates.create_system_greeting_message(name=name,
                                                                                               tz_identifier=tz_identifier,
                                                                                               language_code=language_code)},
                {"role": "user", "content": message_templates.create_user_greeting_message()}
            ]
        )

        greeting = completion.choices[0].message
        return QueryResult(greeting, status.HTTP_200_OK)
    except Exception as e:
        return QueryResult(str(e), status.HTTP_409_CONFLICT)
