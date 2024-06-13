import json, os, requests, uuid

from fastapi import status
from llama_index.core import VectorStoreIndex
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import PineconeApiException
from pinecone.grpc import PineconeGRPC
from portkey_ai import PORTKEY_GATEWAY_URL, createHeaders

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

def __create_portkey_config():
    return {
        "provider": "openai",
        "virtual_key": os.environ.get("PORTKEY_OPENAI_VIRTUAL_KEY"),
        "cache": {
            "mode": "semantic",
            "max_age": 300, # 5 minutes
        },
        "retry": {
            "attempts": 2,
        },
        "override_params": {
            "model": __llm_model,
            "temperature": 0,
        }
    }

def query_store(index_id, input, response_language_code, querying_user, session_id) -> QueryResult:
    try:
        # Initialize connection to Pinecone
        pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))
        assert pc.describe_index(index_id).status['ready']

        index = pc.Index(index_id)
        vector_store = PineconeVectorStore(pinecone_index=index)
        vector_index = VectorStoreIndex.from_vector_store(vector_store=vector_store, similarity_top_k=3)

        is_portkey_reachable = __is_portkey_reachable()
        api_base = PORTKEY_GATEWAY_URL if is_portkey_reachable else None
        headers = createHeaders(trace_id=uuid.uuid4(),
                                api_key=os.environ.get("PORTKEY_API_KEY"),
                                config=__create_portkey_config(),
                                cache_namespace=index_id,
                                debug=False, # Prevents prompts and responses from being logged.
                                metadata={
                                    "environment": __get_current_environment(),
                                    "user": querying_user,
                                    "vector_index": index_id,
                                    "session_id": session_id,
                                }) if is_portkey_reachable else None

        llm = OpenAI(model=__llm_model,
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

def create_greeting(name: str, language_code: str, tz_identifier: str) -> QueryResult:
    try:
        api_key = os.environ.get('OPENAI_API_KEY')
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }

        data = {
            'model': __llm_model,
            'messages': [
                {'role': 'system', 'content': message_templates.create_system_greeting_message(name, tz_identifier)},
                {'role': 'user', 'content': message_templates.create_user_greeting_message(language_code)}
            ],
            'temperature': 0.7
        }

        response = requests.post('https://api.openai.com/v1/chat/completions',
                                headers=headers,
                                data=json.dumps(data))
        json_response = response.json()
        greeting = json_response.get('choices')[0]['message']['content']
        return QueryResult(greeting, status.HTTP_200_OK)
    except Exception as e:
        return QueryResult(str(e), status.HTTP_409_CONFLICT)
