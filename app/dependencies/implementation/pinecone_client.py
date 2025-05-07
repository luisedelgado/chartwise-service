import base64
import hashlib, os, uuid
import tiktoken, torch

from datetime import date
from fastapi import HTTPException
from langchain.text_splitter import RecursiveCharacterTextSplitter
from llama_index.core import Document
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import Index, PineconeApiException
from pinecone.exceptions import NotFoundException
from pinecone.grpc import PineconeGRPC
from starlette.concurrency import run_in_threadpool
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from typing import Callable

from ...data_processing.electra_model_data import ELECTRA_MODEL_CACHE_DIR, ELECTRA_MODEL_NAME
from ...dependencies.api.openai_base_class import OpenAIBaseClass
from ...dependencies.api.pinecone_session_date_override import PineconeQuerySessionDateOverride
from ...dependencies.api.pinecone_base_class import PineconeBaseClass
from ...internal.security.chartwise_encryptor import ChartWiseEncryptor
from ...internal.utilities import datetime_handler
from ...vectors import data_cleaner

class PineconeClient(PineconeBaseClass):

    NUM_INDEXES = 20
    RERANK_TOP_N = 4
    PRE_EXISTING_HISTORY_PREFIX = "pre-existing-history"
    MAX_CHUNK_SIZE = 512

    def __init__(
        self,
        encryptor: ChartWiseEncryptor
    ):
        self._pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))
        self._tokenizer = AutoTokenizer.from_pretrained(
            ELECTRA_MODEL_NAME,
            cache_dir=ELECTRA_MODEL_CACHE_DIR
        )
        self._model = AutoModelForSequenceClassification.from_pretrained(
            ELECTRA_MODEL_NAME,
            cache_dir=ELECTRA_MODEL_CACHE_DIR
        )
        self._device = torch.device("cpu")
        self._model.to(self._device)
        self.encryptor = encryptor

    async def insert_session_vectors(
        self,
        session_id: str,
        user_id: str,
        patient_id: str,
        text: str,
        session_report_id: str,
        openai_client: OpenAIBaseClass,
        summarize_chunk: Callable,
        therapy_session_date: date = None
    ):
        try:
            bucket_index = self._get_bucket_for_user(user_id)
            index = self._pc.Index(bucket_index)
            vector_store = PineconeVectorStore(pinecone_index=index)
            namespace = self._get_namespace(
                user_id=user_id,
                patient_id=patient_id
            )

            enc = tiktoken.get_encoding("o200k_base")
            splitter = RecursiveCharacterTextSplitter(
                separators=["\n\n", "\n", " ", ""],
                chunk_size=256,
                chunk_overlap=25,
                length_function=lambda text: len(enc.encode(text)),
            )
            chunks = splitter.split_text(text)

            vector_ids = []
            vectors = []
            for chunk_index, chunk in enumerate(chunks):
                doc = Document()

                chunk_text = data_cleaner.clean_up_text(chunk)
                encrypted_chunk_text = self.encryptor.encrypt(chunk_text)
                encoded_chunk_ciphertext = base64.b64encode(encrypted_chunk_text).decode("utf-8")
                doc.set_content(encoded_chunk_ciphertext)

                chunk_summary = await summarize_chunk(
                    chunk_text=chunk_text,
                    openai_client=openai_client
                )
                encrypted_chunk_summary = self.encryptor.encrypt(chunk_summary)
                encoded_chunk_summary_ciphertext = base64.b64encode(encrypted_chunk_summary).decode("utf-8")

                vector_store.namespace = namespace
                therapy_session_date_formatted = therapy_session_date.strftime(datetime_handler.DATE_FORMAT)
                doc_id = f"{therapy_session_date_formatted}-{chunk_index}-{uuid.uuid1()}"
                vector_ids.append(doc_id)
                doc.id_ = doc_id
                doc.metadata.update({
                    "session_date": therapy_session_date_formatted,
                    "chunk_summary": encoded_chunk_summary_ciphertext,
                    "chunk_text": encoded_chunk_ciphertext,
                    "session_report_id": str(session_report_id)
                })

                doc.embedding = await openai_client.create_embeddings(text=chunk_summary)
                vectors.append(doc)

            await run_in_threadpool(vector_store.add, vectors)

        except PineconeApiException as e:
            raise HTTPException(status_code=e.status, detail=str(e))
        except Exception as e:
            raise RuntimeError(e) from e

    async def insert_preexisting_history_vectors(
        self,
        session_id: str,
        user_id: str,
        patient_id: str,
        text: str,
        openai_client: OpenAIBaseClass,
        summarize_chunk: Callable
    ):
        try:
            bucket_index = self._get_bucket_for_user(user_id)
            index = self._pc.Index(bucket_index)
            vector_store = PineconeVectorStore(pinecone_index=index)

            enc = tiktoken.get_encoding("o200k_base")
            splitter = RecursiveCharacterTextSplitter(
                separators=["\n\n", "\n", " ", ""],
                chunk_size=256,
                chunk_overlap=25,
                length_function=lambda text: len(enc.encode(text)),
            )
            chunks = splitter.split_text(text)

            vectors = []
            for chunk in chunks:
                doc = Document()

                chunk_text = data_cleaner.clean_up_text(chunk)
                encrypted_chunk_text = self.encryptor.encrypt(chunk_text)
                encoded_chunk_ciphertext = base64.b64encode(encrypted_chunk_text).decode("utf-8")
                doc.set_content(encoded_chunk_ciphertext)

                chunk_summary = await summarize_chunk(
                    chunk_text=chunk_text,
                    openai_client=openai_client
                )
                encrypted_chunk_summary = self.encryptor.encrypt(chunk_summary)
                encoded_chunk_summary_ciphertext = base64.b64encode(encrypted_chunk_summary).decode("utf-8")

                namespace = self._get_namespace(
                    user_id=user_id,
                    patient_id=patient_id
                )
                cls = type(self)
                vector_store.namespace = "".join([namespace,
                                                    "-",
                                                    cls.PRE_EXISTING_HISTORY_PREFIX])
                doc.id_ = f"{cls.PRE_EXISTING_HISTORY_PREFIX}-{uuid.uuid1()}"
                doc.embedding = await openai_client.create_embeddings(text=chunk_summary)
                doc.metadata.update({
                    "pre_existing_history_summary": encoded_chunk_summary_ciphertext,
                    "pre_existing_history_text": encoded_chunk_ciphertext
                })
                vectors.append(doc)

            await run_in_threadpool(vector_store.add, vectors)

        except PineconeApiException as e:
            raise HTTPException(status_code=e.status, detail=str(e))
        except Exception as e:
            raise RuntimeError(e) from e

    def delete_session_vectors(
        self,
        user_id: str,
        patient_id: str,
        date: date = None
    ):
        try:
            bucket_index = self._get_bucket_for_user(user_id)
            index = self._pc.Index(bucket_index)

            namespace = self._get_namespace(
                user_id=user_id,
                patient_id=patient_id
            )
            ids_to_delete = []
            if date is None:
                # Delete all vectors inside namespace
                for list_ids in index.list(namespace=namespace):
                    ids_to_delete = list_ids
            else:
                # Delete the subset of data that matches the date prefix.
                date_formatted = date.strftime(datetime_handler.DATE_FORMAT)
                for list_ids in index.list(prefix=date_formatted, namespace=namespace):
                    ids_to_delete = list_ids

            if len(ids_to_delete or '') > 0:
                index.delete(ids=ids_to_delete, namespace=namespace)
        except NotFoundException as e:
            raise NotFoundException(e)
        except Exception as e:
            raise RuntimeError(e) from e

    def delete_preexisting_history_vectors(
        self,
        user_id: str,
        patient_id: str
    ):
        try:
            bucket_index = self._get_bucket_for_user(user_id)
            index = self._pc.Index(bucket_index)

            namespace = self._get_namespace(
                user_id=user_id,
                patient_id=patient_id
            )
            namespace_with_suffix = "".join([namespace,
                                             "-",
                                             type(self).PRE_EXISTING_HISTORY_PREFIX])

            ids_to_delete = []
            for list_ids in index.list(namespace=namespace_with_suffix):
                ids_to_delete = list_ids

            if len(ids_to_delete or '') > 0:
                index.delete(ids=ids_to_delete, namespace=namespace_with_suffix)
        except NotFoundException as e:
            raise NotFoundException(e)
        except Exception as e:
            raise RuntimeError(e) from e

    async def update_session_vectors(
        self,
        session_id: str,
        user_id: str,
        patient_id: str,
        text: str,
        old_date: date,
        new_date: date,
        session_report_id: str,
        openai_client: OpenAIBaseClass,
        summarize_chunk: Callable
    ):
        try:
            # Delete the outdated data
            self.delete_session_vectors(
                user_id=user_id,
                patient_id=patient_id,
                date=old_date
            )

            # Insert the fresh data
            await self.insert_session_vectors(
                session_id=session_id,
                user_id=user_id,
                patient_id=patient_id,
                text=text,
                session_report_id=session_report_id,
                openai_client=openai_client,
                therapy_session_date=new_date,
                summarize_chunk=summarize_chunk
            )
        except PineconeApiException as e:
            raise HTTPException(status_code=e.status, detail=str(e))
        except Exception as e:
            raise RuntimeError(e) from e

    async def update_preexisting_history_vectors(
        self,
        session_id: str,
        user_id: str,
        patient_id: str,
        text: str,
        openai_client: OpenAIBaseClass,
        summarize_chunk: Callable
    ):
        try:
            # Delete the outdated data
            self.delete_preexisting_history_vectors(
                user_id=user_id,
                patient_id=patient_id
            )

            # Insert the fresh data
            await self.insert_preexisting_history_vectors(
                user_id=user_id,
                session_id=session_id,
                patient_id=patient_id,
                text=text,
                openai_client=openai_client,
                summarize_chunk=summarize_chunk
            )
        except PineconeApiException as e:
            raise HTTPException(status_code=e.status, detail=str(e))
        except Exception as e:
            raise RuntimeError(e) from e

    async def get_vector_store_context(
        self,
        openai_client: OpenAIBaseClass,
        query_input: str,
        user_id: str,
        patient_id: str,
        query_top_k: int,
        rerank_vectors: bool,
        include_preexisting_history: bool = True,
        session_dates_override: list[PineconeQuerySessionDateOverride] = None
    ) -> str:
        try:
            missing_session_data_error = (
                "There's no data from patient sessions. "
                "They may have not gone through their first session since the practitioner added them to the platform. "
            )

            bucket_index = self._get_bucket_for_user(user_id)
            index = self._pc.Index(bucket_index)
            namespace = self._get_namespace(
                user_id=user_id,
                patient_id=patient_id
            )

            if include_preexisting_history:
                # Fetch patient's historical context
                found_historical_context, historical_context = await self.fetch_historical_context(
                    index=index,
                    namespace=namespace
                )

                if found_historical_context:
                    historical_context = (
                        "Here's an outline of the patient's pre-existing history:\n" + historical_context
                    )
                    missing_session_data_error = (
                        f"{historical_context}\nBeyond this pre-existing context, there's no data from actual patient sessions. "
                        "They may have not gone through their first session since the practitioner added them to the platform. "
                    )
                else:
                    historical_context = ""
            else:
                historical_context = ""
                found_historical_context = False

            # Check if caller wants us to fetch any vectors
            if query_top_k > 0:
                embeddings = await openai_client.create_embeddings(text=query_input)
                query_result = index.query(
                    vector=embeddings,
                    top_k=query_top_k,
                    namespace=namespace,
                    include_metadata=True
                )
                query_matches = query_result.to_dict()['matches']

                # There's no session data, return a message explaining this, and offer the historical context, if exists.
                if len(query_matches or []) == 0:
                    return missing_session_data_error

                retrieved_docs = []
                for match in query_matches:
                    metadata = match['metadata']
                    ciphertext = base64.b64decode(metadata['chunk_summary'])
                    plaintext = self.encryptor.decrypt(ciphertext)
                    retrieved_docs.append(
                        {"session_date": metadata['session_date'],
                        "chunk_summary": plaintext}
                    )

            # Check if caller wants us to rerank vectors
            if rerank_vectors:
                reranked_documents = self.rerank_docs(
                    query_input=query_input,
                    retrieved_docs=retrieved_docs,
                    batch_size=query_top_k
                )

                reranked_context = ""
                dates_contained = []
                for doc in reranked_documents[:type(self).RERANK_TOP_N]:
                    dates_contained.append(doc['session_date'])
                    formatted_date = datetime_handler.convert_to_date_format_spell_out_month(
                        session_date=doc['session_date'],
                        incoming_date_format=datetime_handler.DATE_FORMAT
                    )
                    doc_session_date = "".join(["`session_date` = ", f"{formatted_date}\n"])
                    doc_chunk_summary = "".join(["`chunk_summary` = ", f"{doc['chunk_summary']}"])
                    doc_full_context = "".join(
                        [doc_session_date,
                        doc_chunk_summary,
                        "\n"]
                    )
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
                    override_date_is_already_contained = any(
                        current_date.startswith(f"{current_override.session_date}")
                        for current_date in dates_contained
                    )

                    if override_date_is_already_contained:
                        return missing_session_data_error if len(reranked_context or '') == 0 else reranked_context

                    # Add vectors associated with the session date override since they haven't been retrieved yet.
                    session_date_override_vector_ids = []
                    list_operation_prefix = current_override.session_date
                    for list_ids in index.list(
                        namespace=namespace,
                        prefix=list_operation_prefix
                    ):
                        session_date_override_vector_ids = list_ids

                    # Didn't find any vectors for that day, return unchanged reranked_context
                    if len(session_date_override_vector_ids) == 0:
                        return missing_session_data_error if len(reranked_context or '') == 0 else reranked_context

                    session_date_override_fetch_result = index.fetch(
                        ids=session_date_override_vector_ids,
                        namespace=namespace
                    )
                    vectors = session_date_override_fetch_result['vectors']
                    if len(vectors or []) == 0:
                        return missing_session_data_error if len(reranked_context or '') == 0 else reranked_context

                    # Have vectors for session date override. Append them to current reranked_context value.
                    for vector_id in vectors:
                        vector_data = vectors[vector_id]

                        metadata = vector_data['metadata']
                        ciphertext = base64.b64decode(metadata['chunk_summary'])
                        plaintext = self.encryptor.decrypt(ciphertext)
                        formatted_date = datetime_handler.convert_to_date_format_spell_out_month(
                            session_date=metadata['session_date'],
                            incoming_date_format=datetime_handler.DATE_FORMAT
                        )
                        session_date = "".join(["`session_date` = ",f"{formatted_date}\n"])
                        chunk_summary = "".join(["`chunk_summary` = ",f"{plaintext}\n"])
                        session_date_override_context = "".join(
                            [session_date,
                            chunk_summary,]
                        )

                        if current_override.output_prefix_override is not None:
                            session_date_override_context = "".join(
                                [current_override.output_prefix_override,
                                session_date_override_context]
                            )
                        if current_override.output_suffix_override is not None:
                            session_date_override_context = "".join(
                                [session_date_override_context,
                                current_override.output_suffix_override,
                                "\n"]
                            )

                        reranked_context = "\n".join(
                            [reranked_context,
                            session_date_override_context]
                        )
            return missing_session_data_error if len(reranked_context or '') == 0 else reranked_context
        except Exception as e:
            raise RuntimeError(e) from e

    async def fetch_historical_context(
        self,
        index: Index,
        namespace: str
    ):
        historial_context_namespace = ("".join([
                    namespace,
                    "-",
                    type(self).PRE_EXISTING_HISTORY_PREFIX
                ]
            )
        )
        context_vector_ids = []
        for list_ids in index.list(namespace=historial_context_namespace):
            context_vector_ids = list_ids

        if len(context_vector_ids or '') == 0:
            return (False, None)

        fetch_result = index.fetch(
            ids=context_vector_ids,
            namespace=historial_context_namespace
        )

        context_docs = []
        vectors = fetch_result['vectors']
        for vector_id in vectors:
            vector_data = vectors[vector_id]
            metadata = vector_data['metadata']
            ciphertext = base64.b64decode(metadata['pre_existing_history_summary'])
            plaintext = self.encryptor.decrypt(ciphertext)
            decrypted_chunk_summary = "".join(["`pre_existing_history_summary` = ",
                                               f"{plaintext}"])
            decrypted_chunk_full_context = "".join([decrypted_chunk_summary, "\n"])
            context_docs.append({
                "id": vector_data['id'],
                "text": decrypted_chunk_full_context
            })

        if len(context_docs) > 0:
            return (True, "\n".join([doc['text'] for doc in context_docs]))
        return (False, None)

    # Private

    def rerank_docs(
        self,
        query_input: str,
        retrieved_docs: list,
        batch_size: int
    ) -> list:
        """
        Re-ranks a list of documents based on their relevance to a query input, using a
        cross-encoder model to compute relevance scores.

        Args:
            query_input (str): The query string used to rank the documents.
            retrieved_docs (list): A list of documents (each represented as a dictionary) that are retrieved
                                   for the query. Each document must contain at least the key 'chunk_summary',
                                   which will be used for ranking.
            batch_size (int): The number of document pairs to process in each batch. This controls memory usage
                            and batch processing efficiency.

        Returns: The list of documents from `retrieved_docs` sorted by their relevance score in descending order.
        """
        # Create pairs using only the chunk_summary for ranking
        pairs = [[query_input, doc['chunk_summary']] for doc in retrieved_docs]
        scores = []

        # Process in batches
        for i in range(0, len(pairs), batch_size):
            batch = pairs[i:i + batch_size]
            inputs = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                return_tensors='pt',
                max_length=type(self).MAX_CHUNK_SIZE
            ).to(self._device)

            with torch.no_grad():
                batch_scores = self._model(**inputs).logits.squeeze(-1)
                scores.extend(batch_scores.cpu().numpy())

        # Sort the original objects based on scores
        doc_score_pairs = list(zip(retrieved_docs, scores))
        return [doc for doc, _ in sorted(doc_score_pairs, key=lambda x: x[1], reverse=True)]

    def _get_namespace(
        self,
        user_id: str,
        patient_id: str
    ) -> str:
        return f"{user_id}-{patient_id}"

    def _get_bucket_for_user(
        self,
        user_id: str
    ) -> str:
        # Convert the user_id to an integer
        user_int = int(hashlib.md5(user_id.encode()).hexdigest(), 16)

        # Use modulo to determine the index
        index_number = user_int % type(self).NUM_INDEXES
        return str(index_number)
