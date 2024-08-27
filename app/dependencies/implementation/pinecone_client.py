import hashlib, os, uuid
import tiktoken

from fastapi import HTTPException
from langchain.text_splitter import RecursiveCharacterTextSplitter
from llama_index.core import Document
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import Index, Pinecone, PineconeApiException
from pinecone.exceptions import NotFoundException
from pinecone.grpc import PineconeGRPC 
from typing import Tuple

from ...dependencies.api.openai_base_class import OpenAIBaseClass
from ...dependencies.api.pinecone_session_date_override import PineconeQuerySessionDateOverride
from ...dependencies.api.pinecone_base_class import PineconeBaseClass
from ...internal.utilities import datetime_handler
from ...managers.auth_manager import AuthManager
from ...vectors import data_cleaner
from ...vectors.chartwise_assistant import ChartWiseAssistant, PRE_EXISTING_HISTORY_PREFIX

class PineconeClient(PineconeBaseClass):

    NUM_INDEXES = 20

    async def insert_session_vectors(self,
                                     user_id: str,
                                     patient_id: str,
                                     text: str,
                                     session_id: str,
                                     auth_manager: AuthManager,
                                     openai_client: OpenAIBaseClass,
                                     therapy_session_date: str = None):
        try:
            pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))
            bucket_index = self._get_bucket_for_user(user_id)

            assert pc.describe_index(bucket_index).status['ready']
            index = pc.Index(bucket_index)
            vector_store = PineconeVectorStore(pinecone_index=index)

            enc = tiktoken.get_encoding("cl100k_base")
            splitter = RecursiveCharacterTextSplitter(
                separators=["\n\n", "\n", " ", ""],
                chunk_size=256,
                chunk_overlap=25,
                length_function=lambda text: len(enc.encode(text)),
            )
            chunks = splitter.split_text(text)

            chartwise_assistant = ChartWiseAssistant()
            vectors = []
            for chunk_index, chunk in enumerate(chunks):
                doc = Document()

                chunk_text = data_cleaner.clean_up_text(chunk)
                doc.set_content(chunk_text)

                chunk_summary = await chartwise_assistant.summarize_chunk(chunk_text=chunk_text,
                                                                          therapist_id=user_id,
                                                                          auth_manager=auth_manager,
                                                                          openai_client=openai_client,
                                                                          session_id=session_id)

                vector_store.namespace = self._get_namespace(user_id=user_id,
                                                             patient_id=patient_id)
                doc.id_ = f"{therapy_session_date}-{chunk_index}-{uuid.uuid1()}"
                doc.metadata.update({
                    "session_date": therapy_session_date,
                    "chunk_summary": chunk_summary,
                    "chunk_text": chunk_text
                })

                doc.embedding = await openai_client.create_embeddings(text=chunk_summary,
                                                                      auth_manager=auth_manager)
                vectors.append(doc)

            vector_store.add(vectors)

        except PineconeApiException as e:
            raise HTTPException(status_code=e.status, detail=str(e))
        except Exception as e:
            raise Exception(str(e))

    async def insert_preexisting_history_vectors(self,
                                                 user_id: str,
                                                 patient_id: str,
                                                 text: str,
                                                 session_id: str,
                                                 openai_client: OpenAIBaseClass,
                                                 auth_manager: AuthManager):
        try:
            pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))
            bucket_index = self._get_bucket_for_user(user_id)

            assert pc.describe_index(bucket_index).status['ready']
            index = pc.Index(bucket_index)
            vector_store = PineconeVectorStore(pinecone_index=index)

            enc = tiktoken.get_encoding("cl100k_base")
            splitter = RecursiveCharacterTextSplitter(
                separators=["\n\n", "\n", " ", ""],
                chunk_size=256,
                chunk_overlap=25,
                length_function=lambda text: len(enc.encode(text)),
            )
            chunks = splitter.split_text(text)

            chartwise_assistant = ChartWiseAssistant()
            vectors = []
            for chunk in chunks:
                doc = Document()

                chunk_text = data_cleaner.clean_up_text(chunk)
                doc.set_content(chunk_text)

                chunk_summary = await chartwise_assistant.summarize_chunk(chunk_text=chunk_text,
                                                                          therapist_id=user_id,
                                                                          auth_manager=auth_manager,
                                                                          openai_client=openai_client,
                                                                          session_id=session_id)

                namespace = self._get_namespace(user_id=user_id, patient_id=patient_id)
                vector_store.namespace = "".join([namespace,
                                                    "-",
                                                    PRE_EXISTING_HISTORY_PREFIX])
                doc.id_ = f"{PRE_EXISTING_HISTORY_PREFIX}-{uuid.uuid1()}"
                doc.embedding = await openai_client.create_embeddings(text=chunk_summary, auth_manager=auth_manager)
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

    def delete_session_vectors(self,
                               user_id: str,
                               patient_id: str,
                               date: str = None):
        try:
            pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))
            bucket_index = self._get_bucket_for_user(user_id)

            assert pc.describe_index(bucket_index).status['ready']
            index = pc.Index(bucket_index)

            namespace = self._get_namespace(user_id=user_id,
                                            patient_id=patient_id)
            ids_to_delete = []
            if len(date or '') == 0:
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

    def delete_preexisting_history_vectors(self,
                                           user_id: str,
                                           patient_id: str):
        try:
            pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))
            bucket_index = self._get_bucket_for_user(user_id)

            assert pc.describe_index(bucket_index).status['ready']
            index = pc.Index(bucket_index)

            namespace = self._get_namespace(user_id=user_id,
                                            patient_id=patient_id)
            namespace_with_suffix = "".join([namespace,
                                             "-",
                                             PRE_EXISTING_HISTORY_PREFIX])

            ids_to_delete = []
            for list_ids in index.list(namespace=namespace_with_suffix):
                ids_to_delete = list_ids

            if len(ids_to_delete or '') > 0:
                index.delete(ids=ids_to_delete, namespace=namespace_with_suffix)
        except NotFoundException as e:
            raise NotFoundException(e)
        except Exception as e:
            raise Exception(str(e))

    async def update_session_vectors(self,
                                     user_id: str,
                                     patient_id: str,
                                     text: str,
                                     old_date: str,
                                     new_date: str,
                                     session_id: str,
                                     openai_client: OpenAIBaseClass,
                                     auth_manager: AuthManager):
        try:
            # Delete the outdated data
            self.delete_session_vectors(user_id=user_id,
                                        patient_id=patient_id,
                                        date=old_date)

            # Insert the fresh data
            await self.insert_session_vectors(user_id=user_id,
                                              patient_id=patient_id,
                                              text=text,
                                              therapy_session_date=new_date,
                                              session_id=session_id,
                                              openai_client=openai_client,
                                              auth_manager=auth_manager)
        except PineconeApiException as e:
            raise HTTPException(status_code=e.status, detail=str(e))
        except Exception as e:
            raise Exception(str(e))

    async def update_preexisting_history_vectors(self,
                                                 user_id: str,
                                                 patient_id: str,
                                                 text: str,
                                                 session_id: str,
                                                 openai_client: OpenAIBaseClass,
                                                 auth_manager: AuthManager):
        try:
            # Delete the outdated data
            self.delete_preexisting_history_vectors(user_id=user_id,
                                                    patient_id=patient_id)

            # Insert the fresh data
            await self.insert_preexisting_history_vectors(user_id=user_id,
                                                          patient_id=patient_id,
                                                          text=text,
                                                          session_id=session_id,
                                                          openai_client=openai_client,
                                                          auth_manager=auth_manager)
        except PineconeApiException as e:
            raise HTTPException(status_code=e.status, detail=str(e))
        except Exception as e:
            raise Exception(str(e))

    async def get_vector_store_context(self,
                                       auth_manager: AuthManager,
                                       openai_client: OpenAIBaseClass,
                                       query_input: str,
                                       user_id: str,
                                       patient_id: str,
                                       query_top_k: int,
                                       rerank_top_n: int,
                                       session_id: str,
                                       session_dates_override: list[PineconeQuerySessionDateOverride] = None) -> str:
        pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))

        missing_session_data_error = ("There's no data from patient sessions. "
                                      "They may have not gone through their first session since the practitioner added them to the platform. ")

        bucket_index = self._get_bucket_for_user(user_id)
        assert pc.describe_index(bucket_index).status['ready'], "Failed to fetch vector data"
        index = pc.Index(bucket_index)
        namespace = self._get_namespace(user_id=user_id,
                                        patient_id=patient_id)

        # Fetch patient's historical context
        found_historical_context, historical_context = await self.fetch_historical_context(index=index, namespace=namespace)

        if found_historical_context:
            historical_context = ("Here's an outline of the patient's pre-existing history:\n" + historical_context)
            missing_session_data_error = (f"{historical_context}\nBeyond this pre-existing context, there's no data from actual patient sessions. "
                                          "They may have not gone through their first session since the practitioner added them to the platform. ")
        else:
            historical_context = ""

        # Check if caller wants us to fetch any vectors
        if query_top_k > 0:
            embeddings = await openai_client.create_embeddings(auth_manager=auth_manager,
                                                               text=query_input)
            query_result = index.query(vector=embeddings,
                                       top_k=query_top_k,
                                       namespace=namespace,
                                       include_metadata=True)
            query_matches = query_result.to_dict()['matches']

            # There's no session data, return a message explaining this, and offer the historical context, if exists.
            if len(query_matches or []) == 0:
                return missing_session_data_error

            retrieved_docs = []
            for match in query_matches:
                metadata = match['metadata']
                session_date = "".join(["`session_date` = ",f"{metadata['session_date']}\n"])
                chunk_summary = "".join(["`chunk_summary` = ",f"{metadata['chunk_summary']}\n"])
                session_full_context = "".join([session_date,
                                                chunk_summary,
                                                "\n"])
                retrieved_docs.append({"id": match['id'], "text": session_full_context})

        # Check if caller wants us to rerank any vectors
        if rerank_top_n > 0:
            reranked_response_results = await openai_client.rerank_documents(auth_manager=auth_manager,
                                                                             documents=retrieved_docs,
                                                                             top_n=rerank_top_n,
                                                                             query_input=query_input,
                                                                             session_id=session_id,
                                                                             user_id=user_id)
            reranked_context = ""
            reranked_documents = reranked_response_results['reranked_documents']
            dates_contained = []
            for doc in reranked_documents:
                dates_contained.append(doc['session_date'])
                formatted_date = datetime_handler.convert_to_date_format_spell_out_month(session_date=doc['session_date'],
                                                                                         incoming_date_format=datetime_handler.DATE_FORMAT)
                doc_session_date = "".join(["`session_date` = ", f"{formatted_date}\n"])
                doc_chunk_summary = "".join(["`chunk_summary` = ", f"{doc['chunk_summary']}"])
                doc_full_context = "".join([doc_session_date,
                                            doc_chunk_summary,
                                            "\n"])
                reranked_context = "\n".join([reranked_context, doc_full_context])
        else:
            reranked_context = ""
            dates_contained = []

        if found_historical_context:
            reranked_context = "\n".join([reranked_context, historical_context])

        # Check if caller wants us to fetch a specific set of vectors, other than
        # the ones that may have already been fetched.
        if session_dates_override is not None:
            for current_override in session_dates_override:
                formatted_session_date_override = datetime_handler.convert_to_date_format_mm_dd_yyyy(session_date=current_override.session_date,
                                                                                                     incoming_date_format=datetime_handler.DATE_FORMAT_YYYY_MM_DD)
                override_date_is_already_contained = any(
                    current_date.startswith(f"{formatted_session_date_override}")
                    for current_date in dates_contained
                )

                if override_date_is_already_contained:
                    return missing_session_data_error if len(reranked_context or '') == 0 else reranked_context

                # Add vectors associated with the session date override since they haven't been retrieved yet.
                session_date_override_vector_ids = []
                list_operation_prefix = datetime_handler.convert_to_date_format_mm_dd_yyyy(session_date=current_override.session_date,
                                                                                           incoming_date_format=datetime_handler.DATE_FORMAT_YYYY_MM_DD)
                for list_ids in index.list(namespace=namespace, prefix=list_operation_prefix):
                    session_date_override_vector_ids = list_ids

                # Didn't find any vectors for that day, return unchanged reranked_context
                if len(session_date_override_vector_ids) == 0:
                    return missing_session_data_error if len(reranked_context or '') == 0 else reranked_context

                session_date_override_fetch_result = index.fetch(ids=session_date_override_vector_ids,
                                                                 namespace=namespace)
                vectors = session_date_override_fetch_result['vectors']
                if len(vectors or []) == 0:
                    return missing_session_data_error if len(reranked_context or '') == 0 else reranked_context

                # Have vectors for session date override. Append them to current reranked_context value.
                for vector_id in vectors:
                    vector_data = vectors[vector_id]

                    metadata = vector_data['metadata']
                    formatted_date = datetime_handler.convert_to_date_format_spell_out_month(session_date=metadata['session_date'],
                                                                                             incoming_date_format=datetime_handler.DATE_FORMAT)
                    session_date = "".join(["`session_date` = ",f"{formatted_date}\n"])
                    chunk_summary = "".join(["`chunk_summary` = ",f"{metadata['chunk_summary']}\n"])
                    session_date_override_context = "".join([session_date,
                                                             chunk_summary,])

                    if current_override.output_prefix_override is not None:
                        session_date_override_context = "".join([current_override.output_prefix_override,
                                                                 session_date_override_context])
                    if current_override.output_suffix_override is not None:
                        session_date_override_context = "".join([session_date_override_context,
                                                                 current_override.output_suffix_override,
                                                                 "\n"])

                    reranked_context = "\n".join([reranked_context,
                                                  session_date_override_context])

        return missing_session_data_error if len(reranked_context or '') == 0 else reranked_context

    async def fetch_historical_context(self,
                                       index: Index,
                                       namespace: str):
        historial_context_namespace = ("".join([namespace,
                                                  "-",
                                                  PRE_EXISTING_HISTORY_PREFIX]))
        context_vector_ids = []
        for list_ids in index.list(namespace=historial_context_namespace):
            context_vector_ids = list_ids

        if len(context_vector_ids or '') == 0:
            return (False, None)

        fetch_result = index.fetch(ids=context_vector_ids,
                                   namespace=historial_context_namespace)

        context_docs = []
        vectors = fetch_result['vectors']
        for vector_id in vectors:
            vector_data = vectors[vector_id]
            metadata = vector_data['metadata']
            chunk_summary = "".join(["`pre_existing_history_summary` = ",f"{metadata['pre_existing_history_summary']}"])
            chunk_full_context = "".join([chunk_summary,
                                          "\n"])
            context_docs.append({
                "id": vector_data['id'],
                "text": chunk_full_context
            })

        if len(context_docs) > 0:
            return (True, "\n".join([doc['text'] for doc in context_docs]))
        return (False, None)

    # Private

    def _get_namespace(self,
                       user_id: str,
                       patient_id: str) -> str:
        return f"{user_id}-{patient_id}"

    def _get_bucket_for_user(self,
                             user_id: str) -> str:
        # Convert the user_id to an integer
        user_int = int(hashlib.md5(user_id.encode()).hexdigest(), 16)

        # Use modulo to determine the index
        index_number = user_int % self.NUM_INDEXES
        return str(index_number)
