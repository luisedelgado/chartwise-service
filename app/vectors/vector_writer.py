import os, uuid
import tiktoken

from enum import Enum

from fastapi import HTTPException
from langchain.text_splitter import RecursiveCharacterTextSplitter
from llama_index.core import Document
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import ServerlessSpec, PineconeApiException
from pinecone.exceptions import NotFoundException
from pinecone.grpc import PineconeGRPC

from ..api.auth_base_class import AuthManagerBaseClass
from . import data_cleaner
from .embeddings import create_embeddings
from .vector_query import VectorQueryWorker, PRE_EXISTING_HISTORY_PREFIX

class VectorIntakeScenario(Enum):
    HISTORICAL_CONTEXT = "historical_context"
    NEW_SESSION = "NEW_SESSION"

"""
Inserts a new record to the datastore leveraging the incoming data.

Arguments:
index_id – the index name that should be used to insert the data.
namespace – the namespace that should be used for manipulating the index.
text – the text to be inserted in the record.
session_id – the session_id.
scenario – the scenario under which this request was made.
auth_manager – the auth manager to be leveraged internally.
therapy_session_date – the session_date to be used as metadata (only when scenario is NEW_SESSION).
"""
async def insert_session_vectors(index_id: str,
                                 namespace: str,
                                 text: str,
                                 session_id: str,
                                 scenario: VectorIntakeScenario,
                                 auth_manager: AuthManagerBaseClass,
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
                                                                      session_id=session_id)

            if scenario == VectorIntakeScenario.NEW_SESSION:
                vector_store.namespace = namespace
                doc.id_ = f"{therapy_session_date}-{chunk_index}-{uuid.uuid1()}"
                doc.metadata.update({
                    "session_date": therapy_session_date,
                    "chunk_summary": chunk_summary,
                    "chunk_text": chunk_text
                })
            elif scenario == VectorIntakeScenario.HISTORICAL_CONTEXT:
                vector_store.namespace = "".join([namespace,
                                                  "-",
                                                  PRE_EXISTING_HISTORY_PREFIX])
                doc.id_ = f"{PRE_EXISTING_HISTORY_PREFIX}-{uuid.uuid1()}"
                doc.metadata.update({
                    "pre_existing_history_summary": chunk_summary,
                    "pre_existing_history_text": chunk_text
                })
            else:
                raise Exception(f"Untracked scenario: {scenario.value}")

            doc.embedding = create_embeddings(text=chunk_summary,
                                              auth_manager=auth_manager)
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

        if date is None:
            # Delete all vectors inside namespace
            list_generator = index.list(namespace=namespace)
            ids_to_delete = list(list_generator)[0]
        else:
            # Delete the subset of data that matches the date prefix.
            list_generator = index.list(prefix=date, namespace=namespace)
            ids_to_delete = list(list_generator)[0]

        if len(ids_to_delete) > 0:
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
auth_manager – the auth manager to be leveraged internally.
"""
async def update_session_vectors(index_id: str,
                           namespace: str,
                           text: str,
                           date: str,
                           scenario: VectorIntakeScenario,
                           session_id: str,
                           auth_manager: AuthManagerBaseClass):
    try:
        # Delete the outdated data
        delete_session_vectors(index_id, namespace, date)

        # Insert the fresh data
        await insert_session_vectors(index_id=index_id,
                                     namespace=namespace,
                                     text=text,
                                     scenario=scenario,
                                     therapy_session_date=date,
                                     session_id=session_id,
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
