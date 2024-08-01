import os, uuid
import tiktoken

from fastapi import HTTPException
from langchain.text_splitter import RecursiveCharacterTextSplitter
from llama_index.core import Document
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import ServerlessSpec, PineconeApiException
from pinecone.exceptions import NotFoundException
from pinecone.grpc import PineconeGRPC

from . import data_cleaner
from .vector_query import VectorQueryWorker, PRE_EXISTING_HISTORY_PREFIX
from ..api.auth_base_class import AuthManagerBaseClass
from ..managers.implementations.openai_manager import OpenAIManager

"""
Inserts a new record to the datastore leveraging the incoming data.
The record is associated with information about a session.

Arguments:
index_id – the index name that should be used to insert the data.
namespace – the namespace that should be used for manipulating the index.
text – the text to be inserted in the record.
session_id – the session_id.
auth_manager – the auth manager to be leveraged internally.
openai_manager – the openai manager to be leveraged internally.
therapy_session_date – the session_date to be used as metadata (only when scenario is NEW_SESSION).
"""
async def insert_session_vectors(index_id: str,
                                 namespace: str,
                                 text: str,
                                 session_id: str,
                                 auth_manager: AuthManagerBaseClass,
                                 openai_manager: OpenAIManager,
                                 therapy_session_date: str = None):
    try:
        pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))

        # If index already exists, this will silently fail so we can continue writing to it
        __create_index_if_necessary(index_id)

        assert pc.describe_index(index_id).status['ready']

        index = pc.Index(index_id)
        vector_store = PineconeVectorStore(pinecone_index=index)

        enc = tiktoken.get_encoding("cl100k_base")
        splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", " ", ""],
            chunk_size=256,
            chunk_overlap=25,
            length_function=lambda text: len(enc.encode(text)),
        )
        chunks = splitter.split_text(text)

        vector_query_worker = VectorQueryWorker()
        vectors = []
        for chunk_index, chunk in enumerate(chunks):
            doc = Document()

            chunk_text = data_cleaner.clean_up_text(chunk)
            doc.set_content(chunk_text)

            chunk_summary = await vector_query_worker.summarize_chunk(chunk_text=chunk_text,
                                                                      therapist_id=index_id,
                                                                      auth_manager=auth_manager,
                                                                      openai_manager=openai_manager,
                                                                      session_id=session_id)

            vector_store.namespace = namespace
            doc.id_ = f"{therapy_session_date}-{chunk_index}-{uuid.uuid1()}"
            doc.metadata.update({
                "session_date": therapy_session_date,
                "chunk_summary": chunk_summary,
                "chunk_text": chunk_text
            })

            doc.embedding = await openai_manager.create_embeddings(text=chunk_summary,
                                                                   auth_manager=auth_manager)
            vectors.append(doc)

        vector_store.add(vectors)

    except PineconeApiException as e:
        raise HTTPException(status_code=e.status, detail=str(e))
    except Exception as e:
        raise Exception(str(e))


"""
Inserts a new record to the datastore leveraging the incoming data.
The record is associated with information about pre-existing history.

Arguments:
index_id – the index name that should be used to insert the data.
namespace – the namespace that should be used for manipulating the index.
text – the text to be inserted in the record.
session_id – the session_id.
openai_manager – the openai manager to be leveraged internally.
auth_manager – the auth manager to be leveraged internally.
"""
async def insert_preexisting_history_vectors(index_id: str,
                                             namespace: str,
                                             text: str,
                                             session_id: str,
                                             openai_manager: OpenAIManager,
                                             auth_manager: AuthManagerBaseClass):
    try:
        pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))

        # If index already exists, this will silently fail so we can continue writing to it
        __create_index_if_necessary(index_id)

        assert pc.describe_index(index_id).status['ready']

        index = pc.Index(index_id)
        vector_store = PineconeVectorStore(pinecone_index=index)

        enc = tiktoken.get_encoding("cl100k_base")
        splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", " ", ""],
            chunk_size=256,
            chunk_overlap=25,
            length_function=lambda text: len(enc.encode(text)),
        )
        chunks = splitter.split_text(text)

        vector_query_worker = VectorQueryWorker()
        vectors = []
        for chunk in chunks:
            doc = Document()

            chunk_text = data_cleaner.clean_up_text(chunk)
            doc.set_content(chunk_text)

            chunk_summary = await vector_query_worker.summarize_chunk(chunk_text=chunk_text,
                                                                      therapist_id=index_id,
                                                                      auth_manager=auth_manager,
                                                                      openai_manager=openai_manager,
                                                                      session_id=session_id)

            vector_store.namespace = "".join([namespace,
                                                "-",
                                                PRE_EXISTING_HISTORY_PREFIX])
            doc.id_ = f"{PRE_EXISTING_HISTORY_PREFIX}-{uuid.uuid1()}"
            doc.embedding = await openai_manager.create_embeddings(text=chunk_summary, auth_manager=auth_manager)
            doc.metadata.update({
                "pre_existing_history_summary": chunk_summary,
                "pre_existing_history_text": chunk_text
            })
            vectors.append(doc)

        vector_store.add(vectors)

    except PineconeApiException as e:
        raise HTTPException(status_code=e.status, detail=str(e))
    except Exception as e:
        raise Exception(str(e))

"""
Deletes session vectors. If the date param is None, it deletes everything inside the namespace.
Otherwise it deletes the vectors that match the date filtering prefix.

Arguments:
index_id – the index where vectors will be deleted.
namespace – the specific namespace where vectors will be deleted.
date – the optional value to be used as a filtering prefix.
"""
def delete_session_vectors(index_id, namespace, date=None):
    try:
        pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))
        index = pc.Index(index_id)
        assert pc.describe_index(index_id).status['ready']

        ids_to_delete = []
        if date is None:
            # Delete all vectors inside namespace
            for list_ids in index.list(namespace=namespace):
                ids_to_delete = list_ids
        else:
            # Delete the subset of data that matches the date prefix.
            for list_ids in index.list(prefix=date, namespace=namespace):
                ids_to_delete = list_ids

        if len(ids_to_delete or '') > 0:
            index.delete(ids=ids_to_delete, namespace=namespace)
    except NotFoundException as e:
        raise NotFoundException(e)
    except Exception as e:
        raise Exception(str(e))

"""
Deletes pre-existing history vectors.

Arguments:
index_id – the index where vectors will be deleted.
namespace – the specific namespace where vectors will be deleted.
"""
def delete_preexisting_history_vectors(index_id, namespace):
    try:
        pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))
        index = pc.Index(index_id)
        assert pc.describe_index(index_id).status['ready']

        namespace = "".join([namespace,
                             "-",
                             PRE_EXISTING_HISTORY_PREFIX])
        ids_to_delete = []
        for list_ids in index.list(namespace=namespace):
            ids_to_delete = list_ids

        if len(ids_to_delete or '') > 0:
            index.delete(ids=ids_to_delete, namespace=namespace)
    except NotFoundException as e:
        raise NotFoundException(e)
    except Exception as e:
        raise Exception(str(e))

"""
Deletes a full index. This is an operation typically associated with a therapist wanting
to leave the platform, and therefore delete all of their data.

Arguments:
index_id – the index where vectors will be deleted.
"""
def delete_index(index_id):
    try:
        pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))
        pc.delete_index(index_id)
    except NotFoundException as e:
        # Index doesn't exist, failing silently. Therapist is deleting their profile prior to having any
        # data in our vector db
        pass
    except Exception as e:
        raise Exception(str(e))

"""
Updates a session record leveraging the incoming data.

Arguments:
index_id – the index that should be used to update the data.
namespace – the namespace that should be used for manipulating the index.
text – the text to be inserted in the record.
date – the session_date to be used as metadata.
session_id – the session_id.
openai_manager – the openai manager to be leveraged internally.
auth_manager – the auth manager to be leveraged internally.
"""
async def update_session_vectors(index_id: str,
                                 namespace: str,
                                 text: str,
                                 date: str,
                                 session_id: str,
                                 openai_manager: OpenAIManager,
                                 auth_manager: AuthManagerBaseClass):
    try:
        # Delete the outdated data
        delete_session_vectors(index_id, namespace, date)

        # Insert the fresh data
        await insert_session_vectors(index_id=index_id,
                                     namespace=namespace,
                                     text=text,
                                     therapy_session_date=date,
                                     session_id=session_id,
                                     openai_manager=openai_manager,
                                     auth_manager=auth_manager)
    except PineconeApiException as e:
        raise HTTPException(status_code=e.status, detail=str(e))
    except Exception as e:
        raise Exception(str(e))

"""
Updates a pre-existig history record leveraging the incoming data.

Arguments:
index_id – the index that should be used to update the data.
namespace – the namespace that should be used for manipulating the index.
text – the text to be inserted in the record.
session_id – the session_id.
openai_manager – the openai manager to be leveraged internally.
auth_manager – the auth manager to be leveraged internally.
"""
async def update_preexisting_history_vectors(index_id: str,
                                             namespace: str,
                                             text: str,
                                             session_id: str,
                                             openai_manager: OpenAIManager,
                                             auth_manager: AuthManagerBaseClass):
    try:
        # Delete the outdated data
        delete_preexisting_history_vectors(index_id, namespace)

        # Insert the fresh data
        await insert_preexisting_history_vectors(index_id=index_id,
                                                 namespace=namespace,
                                                 text=text,
                                                 session_id=session_id,
                                                 openai_manager=openai_manager,
                                                 auth_manager=auth_manager)
    except PineconeApiException as e:
        raise HTTPException(status_code=e.status, detail=str(e))
    except Exception as e:
        raise Exception(str(e))

# Private

"""
Creates an index in the datastore. If index name already exists, the method will fail silently.

Arguments:
index_name – the name that should be used to create the index.
"""
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
