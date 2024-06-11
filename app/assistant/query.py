import json, os, time, requests

from fastapi import status
from llama_index.core import VectorStoreIndex
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import PineconeApiException
from pinecone.grpc import PineconeGRPC

from . import message_templates

class QueryResult:
    def __init__(self, response_token, status_code):
        self.response_token = response_token
        self.status_code = status_code

def query_store(index_id, input, response_language_code) -> QueryResult:
    try:
        # Initialize connection to Pinecone
        pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))
        assert pc.describe_index(index_id).status['ready']

        index = pc.Index(index_id)
        vector_store = PineconeVectorStore(pinecone_index=index)

        vector_index = VectorStoreIndex.from_vector_store(vector_store=vector_store, similarity_top_k=3)

        llm = OpenAI(model="gpt-3.5-turbo", temperature=0)
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
            'model': 'gpt-3.5-turbo',
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
