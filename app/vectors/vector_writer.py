import os, uuid
import tiktoken

from fastapi import HTTPException
from langchain.text_splitter import RecursiveCharacterTextSplitter
from llama_index.core import Document
from llama_index.embeddings.openai import (OpenAIEmbedding, OpenAIEmbeddingMode, OpenAIEmbeddingModelType)
from llama_index.vector_stores.pinecone import PineconeVectorStore
from openai import OpenAI
from pinecone import ServerlessSpec, PineconeApiException
from pinecone.exceptions import NotFoundException
from pinecone.grpc import PineconeGRPC

from . import data_cleaner, message_templates
from .vector_query import LLM_MODEL
from ..api.auth_base_class import AuthManagerBaseClass
from ..internal.utilities import datetime_handler

"""
Inserts a new record to the datastore leveraging the incoming data.

Arguments:
index_id – the index name that should be used to insert the data.
namespace – the namespace that should be used for manipulating the index.
text – the text to be inserted in the record.
date – the session_date to be used as metadata.
endpoint_name – the endpoint_name that invoked this flow.
method – the api method that was used to invoke this flow.
patient_name – the patient's full name.
auth_manager – the auth manager to be leveraged internally.
kwargs – the optional set of parameters.
"""
def insert_session_vectors(index_id,
                           namespace,
                           text,
                           date,
                           endpoint_name,
                           method,
                           patient_name,
                           auth_manager,
                           **kwargs):
    try:
        assert datetime_handler.is_valid_date(date), "The incoming date is not in a valid format."

        session_id = None if "session_id" not in kwargs else kwargs["session_id"]
        environment = None if "environment" not in kwargs else kwargs["environment"]
        pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))
        
        # If index already exists, this will silently fail so we can continue writing to it
        __create_index_if_necessary(index_id)

        assert pc.describe_index(index_id).status['ready']

        index = pc.Index(index_id)
        vector_store = PineconeVectorStore(pinecone_index=index)
        vector_store.namespace = namespace

        embed_model = OpenAIEmbedding(mode=OpenAIEmbeddingMode.SIMILARITY_MODE,
                                      model=OpenAIEmbeddingModelType.TEXT_EMBED_3_SMALL,
                                      api_key=os.environ.get('OPENAI_API_KEY'))

        enc = tiktoken.get_encoding("cl100k_base")
        splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", " ", ""],
            chunk_size=256,
            chunk_overlap=25,
            length_function=lambda text: len(enc.encode(text)),
        )
        chunks = splitter.split_text(text)

        vectors = []
        for chunk_index, chunk in enumerate(chunks):
            doc = Document()
            doc.id_ = f"{date}-{chunk_index}-{uuid.uuid1()}"
            doc.set_content(data_cleaner.clean_up_text(chunk))

            session_summary = _summarize_session_entry(session_notes=chunk,
                                                       session_id=session_id,
                                                       endpoint_name=endpoint_name,
                                                       therapist_id=index_id,
                                                       method=method,
                                                       patient_name=patient_name,
                                                       environment=environment,
                                                       auth_manager=auth_manager)
            doc.metadata.update({
                "session_date": date,
                "session_summary": session_summary,
            })
            doc.embedding = embed_model.get_text_embedding(session_summary)
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
        if date is not None:
            assert datetime_handler.is_valid_date(date), "The incoming date is not in a valid format."

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
endpoint_name – the endpoint_name that invoked this flow.
method – the api method that was used to invoke this flow.
patient_name – the patient's full name.
auth_manager – the auth manager to be leveraged internally.
kwargs – the optional set of parameters.
"""
def update_session_vectors(index_id,
                           namespace,
                           text,
                           date,
                           endpoint_name,
                           method,
                           patient_name,
                           auth_manager,
                           **kwargs):
    try:
        assert datetime_handler.is_valid_date(date), "The incoming date is not in a valid format."

        # Delete the outdated data
        delete_session_vectors(index_id, namespace, date)

        # Insert the fresh data
        insert_session_vectors(index_id=index_id,
                               namespace=namespace,
                               text=text,
                               date=date,
                               endpoint_name=endpoint_name,
                               method=method,
                               patient_name=patient_name,
                               auth_manager=auth_manager,
                               kwargs=kwargs)
    except PineconeApiException as e:
        raise HTTPException(status_code=e.status, detail=str(e))
    except Exception as e:
        raise Exception(str(e))

# Private

"""
Summarizes a session entry for faster fetching.

Arguments:
session_text – the text associated with the session notes.
session_id – the session id.
endpoint_name – the endpoint that was invoked.
therapist_id – the therapist_id.
method – the API method that was invoked.
environment – the current running environment.
auth_manager – the auth manager to be leveraged internally.
patient_name – the patient's full name.
session_id – the session id.
"""
def _summarize_session_entry(session_notes: str,
                             endpoint_name: str,
                             therapist_id: str,
                             method: str,
                             environment: str,
                             auth_manager: AuthManagerBaseClass,
                             patient_name: str,
                             session_id: str = None,
                             ) -> str:
    try:
        metadata = {
            "environment": environment,
            "user": therapist_id,
            "endpoint_name": endpoint_name,
            "method": method,
        }
        if session_id is not None:
            metadata['session_id'] = str(session_id)

        messages = [
                {"role": "system", "content": message_templates.create_system_session_summary_message()},
                {"role": "user", "content": message_templates.create_user_session_summary_message(session_notes=session_notes, patient_name=patient_name)}
        ]

        is_monitoring_proxy_reachable = auth_manager.is_monitoring_proxy_reachable()
        api_base = auth_manager.get_monitoring_proxy_url() if is_monitoring_proxy_reachable else None
        headers = auth_manager.create_monitoring_proxy_headers(metadata=metadata,
                                                                llm_model=LLM_MODEL) if is_monitoring_proxy_reachable else None
        llm = OpenAI(base_url=api_base,
                    default_headers=headers)

        completion = llm.chat.completions.create(
            model=LLM_MODEL,
            messages=messages
        )
        return completion.choices[0].message.content
    except Exception as e:
        raise Exception(e)

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