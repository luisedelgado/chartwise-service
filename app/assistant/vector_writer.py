import os

from fastapi import HTTPException
from llama_index.core import Document, Settings
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from pinecone import ServerlessSpec, PineconeApiException
from pinecone.grpc import PineconeGRPC

from . import data_cleaner

def upload_session_vector(index_name, session_text, session_date):
    try:
        # Globals
        Settings.embed_model = OpenAIEmbedding()

        doc = Document()
        doc.set_content(data_cleaner.clean_up_text(session_text))

        metadata_additions = {
            "session_date": session_date
        }
        doc.metadata.update(metadata_additions)

        pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))
        
        # If index already exists, this will silently fail so we can continue writing to it
        __create_index_if_necessary(index_name)

        assert pc.describe_index(index_name).status['ready']

        index = pc.Index(index_name)
        vector_store = PineconeVectorStore(pinecone_index=index)
        embed_model = OpenAIEmbedding(api_key=os.environ.get('OPENAI_API_KEY'))

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

        pipeline.run(documents=[doc])
    except PineconeApiException as e:
        raise HTTPException(status_code=e.status, detail=str(e))
    except Exception as e:
        raise Exception(str(e))

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
        ...