import data_cleaner as data_cleaner
import os
import time

from dotenv import load_dotenv
from llama_index.core import Document, Settings
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from pinecone import ServerlessSpec, PineconeApiException
from pinecone.grpc import PineconeGRPC

def upload_session_vector(index_name, session_text, session_date):
    load_dotenv('environment.env')

    # Globals
    Settings.embed_model = OpenAIEmbedding()

    doc = Document() 
    doc.set_content(data_cleaner.clean_up_text(session_text))

    # Add metadata
    metadata_additions = {
        "session_date": session_date
    }
    doc.metadata.update(metadata_additions)

    # Initialize connection to Pinecone
    pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))
    
    # Create index if necessary
    __create_index_if_necessary(index_name)

    # wait for index to be initialized
    while not pc.describe_index(index_name).status['ready']:
        print("sleeping")
        time.sleep(1)

    #check index current stats
    index = pc.Index(index_name)

    # Initialize VectorStore
    vector_store = PineconeVectorStore(pinecone_index=index)

    # This will be the model we use both for Node parsing and for vectorization
    embed_model = OpenAIEmbedding(api_key=os.environ.get('OPENAI_API_KEY'))

    # Define the initial pipeline
    pipeline = IngestionPipeline(
        transformations=[
            SemanticSplitterNodeParser(
                buffer_size=1,
                breakpoint_percentile_threshold=95, 
                embed_model=embed_model,
                ),
            embed_model,
            ],
            vector_store=vector_store
        )

    # Now we run our pipeline!
    pipeline.run(documents=[doc])
    
# Private functions

def __create_index_if_necessary(index_name: str):
    try:
        pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))
        pc.create_index(
            name=index_name,
            dimension=1536,
            spec=ServerlessSpec(
                cloud='aws',
                region='us-west-2')
        )
    except PineconeApiException as e:
        # We expect HTTPCode 409 if index already exists - ALREADY_EXISTS 
        print(e.status)

