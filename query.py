import os
import time
import message_templates as message_templates

from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone.grpc import PineconeGRPC

def query_model(input):
    load_dotenv('environment.env')

    # Initialize connection to Pinecone
    pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))
    index_name = 'patient-john-doe'

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

    llm = OpenAI(model="gpt-3.5-turbo", temperature=0)
    query_engine = vector_index.as_query_engine(
        text_qa_template=message_templates.qa_template,
        refine_template=message_templates.refine_template,
        llm=llm,
        streaming=True,
    )

    return str(query_engine.query(input))
