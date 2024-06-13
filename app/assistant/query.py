import os

from datetime import datetime
from fastapi import status
from llama_index.core import VectorStoreIndex
from llama_index.llms.openai import OpenAI as llama_index_OpenAI
from llama_index.vector_stores.pinecone import PineconeVectorStore
from openai import OpenAI
from pinecone import PineconeApiException
from pinecone.grpc import PineconeGRPC

from ..internal import library_clients, utilities
from . import message_templates

__llm_model = "gpt-3.5-turbo"

class QueryResult:
    def __init__(self, response_token, status_code):
        self.response_token = response_token
        self.status_code = status_code

"""
Queries the respective datastore with the incoming parameters.
Returns a QueryResult object with the query result.

Arguments:
index_id  – the index id that should be queried inside the datastore.
input  – the input for the query.
response_language_code  – the language code to be used in the response.
querying_user – the user that triggered the query.
session_id  – the session id.
endpoint_name  – the endpoint that was invoked.
"""
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

        is_portkey_reachable = library_clients.is_portkey_reachable()
        api_base = library_clients.PORTKEY_GATEWAY_URL if is_portkey_reachable else None
        headers = library_clients.create_portkey_headers(environment=utilities.get_current_environment(),
                                                         session_id=session_id,
                                                         user=querying_user,
                                                         llm_model=__llm_model,
                                                         cache_max_age=3600, # 1 hour
                                                         caching_shard_key=index_id,
                                                         endpoint_name=endpoint_name) if is_portkey_reachable else None

        llm = llama_index_OpenAI(model=__llm_model,
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

"""
Creates a greeting with the incoming values.
Returns a QueryResult object with the greeting result.

Arguments:
name  – the addressing name to be used in the greeting.
language_code  – the language_code to be used in the greeting.
tz_identifier  – the timezone identifier to be used for calculating the client's current time.
session_id  – the session id.
endpoint_name  – the endpoint that was invoked.
"""
def create_greeting(name: str,
                    language_code: str,
                    tz_identifier: str,
                    session_id: str,
                    endpoint_name: str,
                    ) -> QueryResult:
    try:
        is_portkey_reachable = library_clients.is_portkey_reachable()
        api_base = library_clients.PORTKEY_GATEWAY_URL if is_portkey_reachable else None
        caching_shard_key = (session_id + "-" + datetime.now().strftime("%d-%m-%Y"))
        headers = library_clients.create_portkey_headers(environment=utilities.get_current_environment(),
                                                         session_id=session_id,
                                                         llm_model=__llm_model,
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
