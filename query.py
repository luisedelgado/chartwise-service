import json
import message_templates as message_templates
import os
import time
import requests

from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone.grpc import PineconeGRPC

def query_store(index_name, input):
    load_dotenv('environment.env')

    # Initialize connection to Pinecone
    pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))

    # wait for index to be initialized  
    while not pc.describe_index(index_name).status['ready']:
        print("sleeping")
        time.sleep(1)
    
    #check index current stats
    index = pc.Index(index_name)

    # Initialize VectorStore
    vector_store = PineconeVectorStore(pinecone_index=index)

    # Instantiate VectorStoreIndex object from your vector_store object
    vector_index = VectorStoreIndex.from_vector_store(vector_store=vector_store, similarity_top_k=3)
    vector_index.storage_context.persist()
    
    llm = OpenAI(model="gpt-3.5-turbo", temperature=0)
    query_engine = vector_index.as_query_engine(
        text_qa_template=message_templates.qa_template,
        refine_template=message_templates.refine_template,
        llm=llm,
        streaming=True,
    )

    response = query_engine.query(input)
    return str(response)
    # response.print_response_stream()

def create_greeting():
    load_dotenv('environment.env')

    api_key = os.environ.get('OPENAI_API_KEY')
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    data = {
        'model': 'gpt-3.5-turbo',
        'messages': [
            {'role': 'system', 'content': message_templates.greeting_system_message_content},
            {'role': 'user', 'content': message_templates.greeting_user_message_content}
        ],
        'temperature': 0
    }

    response = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, data=json.dumps(data))
    json_response = response.json()
    greeting = json_response.get('choices')[0]['message']['content']
    return greeting
