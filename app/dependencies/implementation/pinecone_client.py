import base64
import hashlib, os, uuid
import tiktoken, torch

from datetime import date, datetime
from fastapi import HTTPException, Request, status
from langchain.text_splitter import RecursiveCharacterTextSplitter
from llama_index.core import Document
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import PineconeApiException
from pinecone.exceptions import NotFoundException
from pinecone.grpc import PineconeGRPC, GRPCIndex
from starlette.concurrency import run_in_threadpool
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from typing import Callable, Tuple

from ...data_processing.electra_model_data import ELECTRA_MODEL_CACHE_DIR, ELECTRA_MODEL_NAME
from ...dependencies.api.aws_db_base_class import AwsDbBaseClass
from ...dependencies.api.openai_base_class import OpenAIBaseClass
from ...dependencies.api.pinecone_session_date_override import (
    PineconeQuerySessionDateOverride,
    PineconeQuerySessionDateOverrideType,
)
from ...dependencies.api.pinecone_base_class import PineconeBaseClass
from ...internal.schemas import VECTORS_SESSION_MAPPINGS_TABLE_NAME
from ...internal.security.chartwise_encryptor import ChartWiseEncryptor
from ...internal.utilities import datetime_handler
from ...vectors import data_cleaner

class PineconeClient(PineconeBaseClass):

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
        user_id: str,
        patient_id: str,
        text: str,
        session_report_id: str,
        openai_client: OpenAIBaseClass,
        summarize_chunk: Callable,
        therapy_session_date: date | None = None
    ) -> list[str]:
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

                assert therapy_session_date is not None, "Cannot manipulate a null date"
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
            return vector_ids
        except PineconeApiException as e:
            raise HTTPException(
                status_code=status.HTTP_417_EXPECTATION_FAILED,
                detail=str(e)
            )
        except Exception as e:
            raise RuntimeError(e) from e

    async def insert_preexisting_history_vectors(
        self,
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
            raise HTTPException(status_code=status.HTTP_417_EXPECTATION_FAILED, detail=str(e))
        except Exception as e:
            raise RuntimeError(e) from e

    def delete_session_vectors(
        self,
        user_id: str,
        patient_id: str,
        date: date | None = None
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
                user_id=user_id,
                patient_id=patient_id,
                text=text,
                session_report_id=session_report_id,
                openai_client=openai_client,
                therapy_session_date=new_date,
                summarize_chunk=summarize_chunk
            )
        except PineconeApiException as e:
            raise HTTPException(
                status_code=status.HTTP_417_EXPECTATION_FAILED,
                detail=str(e)
            )
        except Exception as e:
            raise RuntimeError(e) from e

    async def update_preexisting_history_vectors(
        self,
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
                patient_id=patient_id,
                text=text,
                openai_client=openai_client,
                summarize_chunk=summarize_chunk
            )
        except PineconeApiException as e:
            raise HTTPException(
                status_code=status.HTTP_417_EXPECTATION_FAILED,
                detail=str(e)
            )
        except Exception as e:
            raise RuntimeError(e) from e

    async def get_vector_store_context(
        self,
        openai_client: OpenAIBaseClass,
        aws_db_client: AwsDbBaseClass,
        query_input: str,
        user_id: str,
        patient_id: str,
        query_top_k: int,
        rerank_vectors: bool,
        request: Request,
        include_preexisting_history: bool = True,
        session_dates_overrides: list[PineconeQuerySessionDateOverride] | None = None
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

            ids_contained = []
            retrieved_docs = []
            context = ""
            if query_top_k > 0:
                retrieved_docs, ids_contained = await self._query_vectors(
                    query_input=query_input,
                    query_top_k=query_top_k,
                    index=index,
                    namespace=namespace,
                    openai_client=openai_client,
                )

                if len(retrieved_docs or '') == 0:
                    return missing_session_data_error

            if rerank_vectors:
                assert query_top_k > 0, "query_top_k must be greater than 0 when reranking is enabled."
                context, ids_contained = self.get_reranked_context(
                    query_input=query_input,
                    retrieved_docs=retrieved_docs,
                    batch_size=query_top_k,
                )
            elif len(retrieved_docs or '') > 0:
                # If reranking is not enabled, we will use the retrieved documents as they are.
                for doc in retrieved_docs:
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
                    context = "\n".join(
                        [
                            context,
                            doc_full_context
                        ]
                    )

            if include_preexisting_history:
                found_historical_context, historical_context = await self.fetch_historical_context(
                    index=index,
                    namespace=namespace
                )

                if found_historical_context:
                    assert historical_context is not None, "Unexpected null historical context"

                    historical_context = "".join([
                        "Here's an outline of the patient's pre-existing history:",
                        "\n",
                        historical_context,
                    ])

                    missing_session_data_error = (
                        f"{historical_context}\nBeyond this pre-existing context, there's no data from actual patient sessions. "
                        "They may have not gone through their first session since the practitioner added them to the platform. "
                    )
                    context = "\n".join(
                        [
                            context,
                            historical_context
                        ]
                    )

            # Check if caller wants us to fetch a specific set of vectors, other than
            # the ones that may have already been fetched.
            if session_dates_overrides is not None:
                for session_date_override in session_dates_overrides:
                    if session_date_override.override_type == PineconeQuerySessionDateOverrideType.SINGLE_DATE:
                        context = self._append_context_from_single_date_vectors(
                            session_date_override=session_date_override,
                            index=index,
                            namespace=namespace,
                            current_context=context,
                            ids_contained_in_current_context=ids_contained,
                        )
                    elif session_date_override.override_type == PineconeQuerySessionDateOverrideType.DATE_RANGE:
                        assert session_date_override.session_date_end is not None, "Missing session date end"
                        context = await self._append_context_from_date_range_vectors(
                            current_context=context,
                            index=index,
                            namespace=namespace,
                            aws_db_client=aws_db_client,
                            therapist_id=user_id,
                            request=request,
                            query_input=query_input,
                            start_date=session_date_override.session_date_start,
                            end_date=session_date_override.session_date_end,
                            ids_contained_in_current_context=ids_contained,
                        )
            return missing_session_data_error if len(context or '') == 0 else context
        except Exception as e:
            raise RuntimeError(e) from e

    async def fetch_historical_context(
        self,
        index: GRPCIndex,
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

    def get_reranked_context(
        self,
        query_input: str,
        retrieved_docs: list,
        batch_size: int,
        include_all_docs: bool = False,
    ) -> Tuple[str, list]:
        """
        Reranks the retrieved documents based on their chunk summaries using a pre-trained model.
        Args:
            query_input (str): The input query to be used for reranking.
            retrieved_docs (list): A list of documents retrieved from the vector store.
            batch_size (int): The size of the batches to process the documents in.
        Returns:
            Tuple[str, list]:
            - str: The reranked context.
            - list: A list of vector ids contained in the reranked context.
        """
        # Create pairs using only the chunk_summary for ranking
        pairs = [[query_input, doc['chunk_summary']] for doc in retrieved_docs]
        scores = []
        ids_contained = []

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
        reranked_documents = [doc for doc, _ in sorted(doc_score_pairs, key=lambda x: x[1], reverse=True)]

        reranked_context = ""
        reranked_docs_count = type(self).RERANK_TOP_N if not include_all_docs else len(retrieved_docs)
        for doc in reranked_documents[:reranked_docs_count]:
            ids_contained.append(doc['id'])
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
        return reranked_context, ids_contained

    # Private

    async def _query_vectors(
        self,
        query_input: str,
        query_top_k: int,
        index: GRPCIndex,
        namespace: str,
        openai_client: OpenAIBaseClass,
    ) -> Tuple[list, list]:
        embeddings = await openai_client.create_embeddings(text=query_input)
        query_result = index.query(
            vector=embeddings,
            top_k=query_top_k,
            namespace=namespace,
            include_metadata=True
        )
        query_matches = query_result.to_dict()['matches']

        if len(query_matches or []) == 0:
            return [], []

        ids_contained = []
        retrieved_docs = []
        for match in query_matches:
            metadata = match['metadata']
            session_date = metadata['session_date']
            vector_id = match['id']
            ids_contained.append(vector_id)
            ciphertext = base64.b64decode(metadata['chunk_summary'])
            plaintext = self.encryptor.decrypt(ciphertext)
            retrieved_docs.append(
                {
                    "session_date": session_date,
                    "chunk_summary": plaintext,
                    "id": vector_id,
                }
            )
        return retrieved_docs, ids_contained

    def _create_context_from_vectors(
        self,
        index: GRPCIndex,
        namespace: str,
        vector_ids: list[str],
        query_input: str | None = None,
        rerank_vectors: bool = False
    ) -> str:
        fetch_result = index.fetch(
            ids=vector_ids,
            namespace=namespace
        )
        vectors = fetch_result['vectors']
        if len(vectors or []) == 0:
            return ""

        fetched_docs = []
        for vector_id in vectors:
            vector_data = vectors[vector_id]

            metadata = vector_data['metadata']
            ciphertext = base64.b64decode(metadata['chunk_summary'])
            plaintext = self.encryptor.decrypt(ciphertext)
            fetched_docs.append({
                "session_date": metadata['session_date'],
                "chunk_summary": plaintext,
                "id": vector_data['id'],
            })

        if rerank_vectors:
            assert query_input is not None, "query_input must be provided when reranking is enabled."
            context, _ = self.get_reranked_context(
                query_input=query_input,
                batch_size=len(fetched_docs),
                retrieved_docs=fetched_docs,
                include_all_docs=True,
            )
        else:
            # Build context in-order from the fetched documents.
            context = ""
            for doc in fetched_docs:
                formatted_date = datetime_handler.convert_to_date_format_spell_out_month(
                    session_date=doc['session_date'],
                    incoming_date_format=datetime_handler.DATE_FORMAT
                )
                doc_context = "".join([
                    "`session_date` = ",
                    formatted_date,
                    "\n",
                    "`chunk_summary` = ",
                    doc['chunk_summary'],
                    "\n"
                ])
                context = "".join([context, doc_context, "\n"])
        return context

    def _append_context_from_single_date_vectors(
        self,
        session_date_override: PineconeQuerySessionDateOverride,
        index: GRPCIndex,
        namespace: str,
        current_context: str,
        ids_contained_in_current_context: list[str]
    ) -> str:
        """
        Updates the context for a single session date override.
        """
        session_date_vector_ids = []
        for list_ids in index.list(
            namespace=namespace,
            prefix=session_date_override.session_date_start,
        ):
            session_date_vector_ids = list_ids

        if len(session_date_vector_ids) == 0:
            # If there are no db hits for the session date override, we will not modify the current context.
            return current_context

        filtered_vector_ids = [
            vector_id for vector_id in session_date_vector_ids if vector_id not in ids_contained_in_current_context
        ]

        if len(filtered_vector_ids) == 0:
            # If there are no new vectors to append, we will not modify the current context.
            return current_context

        session_date_override_context = self._create_context_from_vectors(
            index=index,
            namespace=namespace,
            vector_ids=filtered_vector_ids,
        )

        if session_date_override_context is not None:
            # If the session_date_override has an output prefix or suffix for formatting purposes,
            # apply it, and append the final result to the `context` value.
            if session_date_override.output_prefix_override is not None:
                session_date_override_context = "".join(
                    [
                        session_date_override.output_prefix_override,
                        session_date_override_context
                    ]
                )
            if session_date_override.output_suffix_override is not None:
                session_date_override_context = "".join(
                    [
                        session_date_override_context,
                        session_date_override.output_suffix_override,
                        "\n"
                    ]
                )
            return "\n".join(
                [
                    current_context,
                    session_date_override_context
                ]
            )

        # If no context was found for the session date override, we will not modify the current context.
        return current_context

    async def _append_context_from_date_range_vectors(
            self,
            current_context: str,
            index: GRPCIndex,
            namespace: str,
            aws_db_client: AwsDbBaseClass,
            therapist_id: str,
            request: Request,
            query_input: str,
            start_date: str,
            end_date: str,
            ids_contained_in_current_context: list[str],
        ):
        vector_ids_response = await aws_db_client.select(
            user_id=therapist_id,
            request=request,
            table_name=VECTORS_SESSION_MAPPINGS_TABLE_NAME,
            fields=["id"],
            filters={
                "therapist_id": therapist_id,
                "session_date__gte": datetime.strptime(start_date, datetime_handler.DATE_FORMAT).date(),
                "session_date__lte": datetime.strptime(end_date, datetime_handler.DATE_FORMAT).date(),
            },
        )

        if len(vector_ids_response) == 0:
            return current_context

        vector_ids = [
            item['id'] for item in vector_ids_response if item['id'] not in ids_contained_in_current_context
        ]

        if len(vector_ids) == 0:
            # If there are no new vectors to append, we will not modify the current context.
            return current_context

        date_range_context = self._create_context_from_vectors(
            index=index,
            namespace=namespace,
            vector_ids=vector_ids,
            query_input=query_input,
            rerank_vectors=True,
        )
        return "\n".join(
            [
                current_context,
                date_range_context,
            ]
        )

    def _get_namespace(
        self,
        user_id: str,
        patient_id: str
    ) -> str:
        return f"{user_id}-{patient_id}"

    def _get_bucket_for_user(self, user_id: str) -> str:
        user_int = int(hashlib.md5(user_id.encode()).hexdigest(), 16)

        bucket_count = 20
        offset = 1

        index_number = (user_int % bucket_count) + offset
        return str(index_number)
