import os

import cohere, tiktoken

from datetime import datetime
from pinecone import Pinecone, Index

from .message_templates import PromptCrafter, PromptScenario
from ..api.auth_base_class import AuthManagerBaseClass
from ..internal.utilities import datetime_handler
from ..managers.implementations.openai_manager import OpenAIManager

GPT_4O_MINI_MAX_OUTPUT_TOKENS = 16000
PRE_EXISTING_HISTORY_PREFIX = "pre-existing-history"

class IncludeSessionDateOverride:
    def __init__(self, output_prefix_override, output_suffix_override, session_date):
        self.output_prefix_override = output_prefix_override
        self.output_suffix_override = output_suffix_override
        self.session_date = session_date

class VectorQueryWorker:

    """
    Queries the respective datastore with the incoming parameters.
    Returns the query result.

    Arguments:
    index_id – the index id that should be queried inside the datastore.
    namespace – the namespace within the index that should be queried.
    patient_name – the name by which the patient should be addressed.
    patient_gender – the patient's gender.
    query_input – the user input for the query.
    response_language_code – the language code to be used in the response.
    session_id – the session id.
    endpoint_name – the endpoint that was invoked.
    method – the API method that was invoked.
    environment – the current running environment.
    auth_manager – the auth manager to be leveraged internally.
    openai_manager – the openai manager to be leveraged internally.
    last_session_date – the last session that the patient had (None if yet to have first session).
    """
    async def query_store(self,
                          index_id: str,
                          namespace: str,
                          patient_name: str,
                          patient_gender: str,
                          query_input: str,
                          response_language_code: str,
                          session_id: str,
                          endpoint_name: str,
                          method: str,
                          environment: str,
                          auth_manager: AuthManagerBaseClass,
                          openai_manager: OpenAIManager,
                          session_date_override: IncludeSessionDateOverride = None):
        try:
            context = await self._get_vector_store_context(auth_manager=auth_manager,
                                                           query_input=query_input,
                                                           index_id=index_id,
                                                           namespace=namespace,
                                                           openai_manager=openai_manager,
                                                           query_top_k=10,
                                                           rerank_top_n=3,
                                                           session_date_override=session_date_override)

            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.QUERY,
                                                                       context=context,
                                                                       language_code=response_language_code,
                                                                       query_input=query_input)

            last_session_date = None if session_date_override is None else session_date_override.session_date
            system_prompt = prompt_crafter.get_system_message_for_scenario(PromptScenario.QUERY,
                                                                           patient_gender=patient_gender,
                                                                           patient_name=patient_name,
                                                                           last_session_date=last_session_date)
            prompt_tokens = len(tiktoken.get_encoding("cl100k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            metadata = {
                "environment": environment,
                "user": index_id,
                "vector_index": index_id,
                "namespace": namespace,
                "language_code": response_language_code,
                "session_id": str(session_id),
                "endpoint_name": endpoint_name,
                "method": method,
            }

            async for part in self._stream_chat_completion_internal(metadata=metadata,
                                                                    max_tokens=max_tokens,
                                                                    messages=[
                                                                        {"role": "system", "content": system_prompt},
                                                                        {"role": "user", "content": user_prompt},
                                                                    ],
                                                                    auth_manager=auth_manager):
                yield part

        except Exception as e:
            raise Exception(e)

    """
    Creates a greeting with the incoming values.
    Returns the greeting result.

    Arguments:
    name – the addressing name to be used in the greeting.
    therapist_gender – the therapist gender.
    language_code – the language_code to be used in the greeting.
    tz_identifier – the timezone identifier to be used for calculating the client's current time.
    session_id – the session id.
    endpoint_name – the endpoint that was invoked.
    therapist_id – the therapist_id.
    method – the API method that was invoked.
    environment – the current running environment.
    auth_manager – the auth manager to be leveraged internally.
    """
    async def create_greeting(self,
                              therapist_name: str,
                              therapist_gender: str,
                              language_code: str,
                              tz_identifier: str,
                              session_id: str,
                              endpoint_name: str,
                              therapist_id: str,
                              method: str,
                              environment: str,
                              openai_manager: OpenAIManager,
                              auth_manager: AuthManagerBaseClass) -> str:
        try:
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.GREETING)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.GREETING,
                                                                           therapist_name=therapist_name,
                                                                           therapist_gender=therapist_gender,
                                                                           tz_identifier=tz_identifier,
                                                                           language_code=language_code)
            prompt_tokens = len(tiktoken.get_encoding("cl100k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            caching_shard_key = (therapist_id + "-greeting-" + datetime.now().strftime(datetime_handler.DATE_FORMAT))
            metadata = {
                "environment": environment,
                "user": therapist_id,
                "session_id": str(session_id),
                "caching_shard_key": caching_shard_key,
                "endpoint_name": endpoint_name,
                "method": method,
                "tz_identifier": tz_identifier,
                "language_code": language_code,
            }

            return await openai_manager.trigger_async_chat_completion(metadata=metadata,
                                                                     max_tokens=max_tokens,
                                                                     cache_configuration={
                                                                         'cache_max_age': 86400, # 24 hours
                                                                         'caching_shard_key': caching_shard_key,
                                                                     },
                                                                     messages=[
                                                                         {"role": "system", "content": system_prompt},
                                                                         {"role": "user", "content": user_prompt},
                                                                     ],
                                                                     expects_json_response=False,
                                                                     auth_manager=auth_manager)
        except Exception as e:
            raise Exception(e)

    """
    Creates and returns a briefing on the incoming patient id's data.

    Arguments:
    index_id – the index id that should be queried inside the datastore.
    namespace – the namespace within the index that should be queried.
    environment – the current running environment.
    language_code – the language code to be used in the response.
    session_id – the session id.
    endpoint_name – the endpoint that was invoked.
    method – the API method that was invoked.
    patient_name – the name by which the patient should be referred to.
    therapist_name – the name by which the patient should be referred to.
    session_number – the nth time on which the therapist is meeting with the patient.
    auth_manager – the auth manager to be leveraged internally.
    openai_manager – the openai manager to be leveraged internally.
    session_date_override – the optional session date override for including in the (vector) briefing context.
    """
    async def create_briefing(self,
                              index_id: str,
                              namespace: str,
                              environment: str,
                              language_code: str,
                              session_id: str,
                              endpoint_name: str,
                              method: str,
                              patient_name: str,
                              patient_gender: str,
                              therapist_name: str,
                              therapist_gender: str,
                              session_number: int,
                              auth_manager: AuthManagerBaseClass,
                              openai_manager: OpenAIManager,
                              session_date_override: IncludeSessionDateOverride = None) -> str:
        try:
            query_input = (f"I'm coming up to speed with {patient_name}'s session notes. "
            "What do I need to remember, and what would be good avenues to explore in our upcoming session?")

            context = await self._get_vector_store_context(auth_manager=auth_manager,
                                                           openai_manager=openai_manager,
                                                           query_input=query_input,
                                                           index_id=index_id,
                                                           namespace=namespace,
                                                           query_top_k=10,
                                                           rerank_top_n=4,
                                                           session_date_override=session_date_override)
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.PRESESSION_BRIEFING,
                                                                       language_code=language_code,
                                                                       patient_name=patient_name,
                                                                       query_input=query_input,
                                                                       context=context)

            last_session_date = None if session_date_override is None else session_date_override.session_date
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.PRESESSION_BRIEFING,
                                                                           language_code=language_code,
                                                                           therapist_name=therapist_name,
                                                                           therapist_gender=therapist_gender,
                                                                           patient_name=patient_name,
                                                                           patient_gender=patient_gender,
                                                                           session_number=session_number,
                                                                           last_session_date=last_session_date)
            prompt_tokens = len(tiktoken.get_encoding("cl100k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            caching_shard_key = (namespace + "-briefing-" + datetime.now().strftime(datetime_handler.DATE_FORMAT))
            metadata = {
                "environment": environment,
                "user": index_id,
                "patient": namespace,
                "session_id": str(session_id),
                "caching_shard_key": caching_shard_key,
                "endpoint_name": endpoint_name,
                "method": method,
                "language_code": language_code,
            }

            return await openai_manager.trigger_async_chat_completion(metadata=metadata,
                                                                      max_tokens=max_tokens,
                                                                      cache_configuration={
                                                                          'cache_max_age': 86400, # 24 hours
                                                                          'caching_shard_key': caching_shard_key,
                                                                      },
                                                                      messages=[
                                                                          {"role": "system", "content": system_prompt},
                                                                          {"role": "user", "content": user_prompt},
                                                                      ],
                                                                      expects_json_response=True,
                                                                      auth_manager=auth_manager)
        except Exception as e:
            raise Exception(e)

    """
    Fetches a set of questions to be suggested to the user for feeding the assistant.

    Arguments:
    index_id – the index id that should be queried inside the datastore.
    namespace – the namespace within the index that should be queried.
    environment – the current running environment.
    language_code – the language code to be used in the response.
    session_id – the session id.
    endpoint_name – the endpoint that was invoked.
    method – the API method that was invoked.
    patient_name – the name by which the patient should be addressed.
    patient_gender – the patient gender.
    openai_manager – the openai manager to be leveraged internally.
    auth_manager – the auth manager to be leveraged internally.
    """
    async def create_question_suggestions(self,
                                          index_id: str,
                                          namespace: str,
                                          environment: str,
                                          language_code: str,
                                          session_id: str,
                                          endpoint_name: str,
                                          method: str,
                                          patient_name: str,
                                          patient_gender: str,
                                          openai_manager: OpenAIManager,
                                          auth_manager: AuthManagerBaseClass) -> str:
        try:
            query_input = f"What are 3 questions that I could ask about {patient_name}'s session history?"
            context = await self._get_vector_store_context(auth_manager=auth_manager,
                                                           openai_manager=openai_manager,
                                                           query_input=query_input,
                                                           index_id=index_id,
                                                           namespace=namespace,
                                                           query_top_k=10,
                                                           rerank_top_n=5)

            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.QUESTION_SUGGESTIONS,
                                                                       context=context,
                                                                       language_code=language_code,
                                                                       patient_gender=patient_gender,
                                                                       patient_name=patient_name,
                                                                       query_input=query_input)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.QUESTION_SUGGESTIONS,
                                                                           language_code=language_code)
            prompt_tokens = len(tiktoken.get_encoding("cl100k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            caching_shard_key = (namespace + "-questions-" + datetime.now().strftime(datetime_handler.DATE_FORMAT))
            metadata = {
                "environment": environment,
                "user": index_id,
                "patient": namespace,
                "session_id": str(session_id),
                "caching_shard_key": caching_shard_key,
                "endpoint_name": endpoint_name,
                "method": method,
                "language_code": language_code,
            }

            return await openai_manager.trigger_async_chat_completion(metadata=metadata,
                                                                      max_tokens=max_tokens,
                                                                      cache_configuration={
                                                                          'cache_max_age': 86400, # 24 hours
                                                                          'caching_shard_key': caching_shard_key,
                                                                      },
                                                                      messages=[
                                                                          {"role": "system", "content": system_prompt},
                                                                          {"role": "user", "content": user_prompt},
                                                                      ],
                                                                      expects_json_response=True,
                                                                      auth_manager=auth_manager)
        except Exception as e:
            raise Exception(e)

    """
    Fetches a set of topics associated with the user along with respective density percentages.

    Arguments:
    index_id – the index id that should be queried inside the datastore.
    namespace – the namespace within the index that should be queried.
    environment – the current running environment.
    language_code – the language code to be used in the response.
    session_id – the session id.
    endpoint_name – the endpoint that was invoked.
    method – the API method that was invoked.
    patient_name – the name by which the patient should be addressed.
    patient_gender – the patient gender.
    openai_manager – the openai manager to be leveraged internally.
    auth_manager – the auth manager to be leveraged internally.
    """
    async def fetch_frequent_topics(self,
                                    index_id: str,
                                    namespace: str,
                                    environment: str,
                                    language_code: str,
                                    session_id: str,
                                    endpoint_name: str,
                                    method: str,
                                    patient_name: str,
                                    patient_gender: str,
                                    openai_manager: OpenAIManager,
                                    auth_manager: AuthManagerBaseClass) -> str:
        try:
            query_input = f"What are the 3 topics that come up the most in {patient_name}'s sessions?"
            context = await self._get_vector_store_context(auth_manager=auth_manager,
                                                           query_input=query_input,
                                                           openai_manager=openai_manager,
                                                           index_id=index_id,
                                                           namespace=namespace,
                                                           query_top_k=10,
                                                           rerank_top_n=5)

            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.TOPICS,
                                                                       context=context,
                                                                       language_code=language_code,
                                                                       patient_gender=patient_gender,
                                                                       patient_name=patient_name,
                                                                       query_input=query_input)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.TOPICS,
                                                                           language_code=language_code)
            prompt_tokens = len(tiktoken.get_encoding("cl100k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            caching_shard_key = (namespace + "-topics-" + datetime.now().strftime(datetime_handler.DATE_FORMAT))
            metadata = {
                "environment": environment,
                "user": index_id,
                "patient": namespace,
                "session_id": str(session_id),
                "caching_shard_key": caching_shard_key,
                "endpoint_name": endpoint_name,
                "method": method,
                "language_code": language_code,
            }

            return await openai_manager.trigger_async_chat_completion(metadata=metadata,
                                                                      max_tokens=max_tokens,
                                                                      cache_configuration={
                                                                          'cache_max_age': 86400, # 24 hours
                                                                          'caching_shard_key': caching_shard_key,
                                                                      },
                                                                      messages=[
                                                                          {"role": "system", "content": system_prompt},
                                                                          {"role": "user", "content": user_prompt},
                                                                      ],
                                                                      expects_json_response=True,
                                                                      auth_manager=auth_manager)
        except Exception as e:
            raise Exception(e)

    """
    Creates and returns a SOAP report with the incoming data.

    Arguments:
    text – the text to be adapted to a SOAP format.
    therapist_id – the therapist_id.
    auth_manager – the auth manager to be leveraged internally.
    openai_manager – the openai manager to be leveraged internally.
    session_id – the session id.
    """
    async def create_soap_report(self,
                                 text: str,
                                 therapist_id: str,
                                 auth_manager: AuthManagerBaseClass,
                                 openai_manager: OpenAIManager,
                                 session_id: str) -> str:
        try:
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.SOAP_TEMPLATE,
                                                                       session_notes=text)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.SOAP_TEMPLATE)
            prompt_tokens = len(tiktoken.get_encoding("cl100k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            metadata = {
                "user": therapist_id,
                "session_id": str(session_id),
            }

            return await openai_manager.trigger_async_chat_completion(metadata=metadata,
                                                                      max_tokens=max_tokens,
                                                                      messages=[
                                                                          {"role": "system", "content": system_prompt},
                                                                          {"role": "user", "content": user_prompt},
                                                                      ],
                                                                      expects_json_response=False,
                                                                      auth_manager=auth_manager)
        except Exception as e:
            raise Exception(e)

    """
    Summarizes a chunk for faster fetching.

    Arguments:
    chunk_text – the text associated with the incoming chunk.
    therapist_id – the therapist_id.
    auth_manager – the auth manager to be leveraged internally.
    openai_manager – the openai manager to be leveraged internally.
    session_id – the session id.
    """
    async def summarize_chunk(self,
                              chunk_text: str,
                              therapist_id: str,
                              auth_manager: AuthManagerBaseClass,
                              openai_manager: OpenAIManager,
                              session_id: str) -> str:
        try:
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(PromptScenario.CHUNK_SUMMARY,
                                                                       chunk_text=chunk_text)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.CHUNK_SUMMARY)
            prompt_tokens = len(tiktoken.get_encoding("cl100k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            metadata = {
                "user": therapist_id,
                "session_id": str(session_id)
            }

            return await openai_manager.trigger_async_chat_completion(metadata=metadata,
                                                                      max_tokens=max_tokens,
                                                                      messages=[
                                                                          {"role": "system", "content": system_prompt},
                                                                          {"role": "user", "content": user_prompt},
                                                                      ],
                                                                      expects_json_response=False,
                                                                      auth_manager=auth_manager)
        except Exception as e:
            raise Exception(e)

    """
    Creates a 'mini' summary of the incoming session notes.

    Arguments:
    session_notes – the text associated with the session notes.
    therapist_id – the therapist_id.
    language_code – the language_code to be used for generating the response.
    auth_manager – the auth manager to be leveraged internally.
    openai_manager – the openai manager to be leveraged internally.
    session_id – the session id.
    """
    async def create_session_mini_summary(self,
                                          session_notes: str,
                                          therapist_id: str,
                                          language_code: str,
                                          auth_manager: AuthManagerBaseClass,
                                          openai_manager: OpenAIManager,
                                          session_id: str) -> str:
        try:
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(PromptScenario.SESSION_MINI_SUMMARY,
                                                                       session_notes=session_notes)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.SESSION_MINI_SUMMARY,
                                                                           language_code=language_code)
            prompt_tokens = len(tiktoken.get_encoding("cl100k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            metadata = {
                "user": therapist_id,
                "session_id": str(session_id),
                "language_code": language_code,
            }

            return await openai_manager.trigger_async_chat_completion(metadata=metadata,
                                                                      max_tokens=max_tokens,
                                                                      messages=[
                                                                          {"role": "system", "content": system_prompt},
                                                                          {"role": "user", "content": user_prompt},
                                                                      ],
                                                                      expects_json_response=False,
                                                                      auth_manager=auth_manager)
        except Exception as e:
            raise Exception(e)

    # Private

    async def _get_vector_store_context(self,
                                        auth_manager: AuthManagerBaseClass,
                                        openai_manager: OpenAIManager,
                                        query_input: str,
                                        index_id: str,
                                        namespace: str,
                                        query_top_k: int,
                                        rerank_top_n: int,
                                        session_date_override: IncludeSessionDateOverride = None) -> str:
        pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))

        missing_session_data_error = ("There's no data from patient sessions. "
                                      "They may have not gone through their first session since the practitioner added them to the platform. ")
        if index_id not in pc.list_indexes().names():
            return missing_session_data_error

        index = pc.Index(index_id)
        embeddings = await openai_manager.create_embeddings(auth_manager=auth_manager,
                                                            text=query_input)

        # Fetch patient's historical context
        found_historical_context, historical_context = self._fetch_historical_context(index=index, namespace=namespace)

        if found_historical_context:
            historical_context = ("Here's an outline of the patient's pre-existing history, written by the therapist:\n" + historical_context)
            missing_session_data_error = (f"{historical_context}\nBeyond this pre-existing context, there's no data from actual patient sessions. "
                                          "They may have not gone through their first session since the practitioner added them to the platform. ")
        else:
            historical_context = ""

        query_result = index.query(vector=embeddings,
                                   top_k=query_top_k,
                                   namespace=namespace,
                                   include_metadata=True)
        query_matches = query_result.to_dict()['matches']

        # There's no session data, return a message explaining this, and offer the historical context, if exists.
        if len(query_matches or []) == 0:
            return missing_session_data_error

        query_matches_ids = []
        retrieved_docs = []
        for match in query_matches:
            query_matches_ids.append(match['id'])
            metadata = match['metadata']
            session_date = "".join(["session_date = ",f"{metadata['session_date']}\n"])
            chunk_summary = "".join(["chunk_summary = ",f"{metadata['chunk_summary']}\n"])
            chunk_text = "".join(["chunk_text = ",f"{metadata['chunk_text']}\n"])
            session_full_context = "".join([session_date,
                                            chunk_summary,
                                            chunk_text,
                                            "\n"])
            retrieved_docs.append({"id": match['id'], "text": session_full_context})

        cohere_client = cohere.AsyncClient(os.environ.get("COHERE_API_KEY"))
        rerank_response = await cohere_client.rerank(
            model="rerank-multilingual-v3.0",
            query=query_input,
            documents=retrieved_docs,
            return_documents=True,
            top_n=rerank_top_n,
        )

        reranked_response_results = rerank_response.results
        reranked_docs = "\n".join([result.document.text for result in reranked_response_results])

        if found_historical_context:
            reranked_docs = "\n".join([reranked_docs, historical_context])

        # Add vectors associated with the session date override if not already retrieved.
        formatted_session_date_override = datetime_handler.convert_to_internal_date_format(session_date_override.session_date)
        override_date_is_already_contained = any(
            str(result.document.id).startswith(f"{formatted_session_date_override}")
            for result in reranked_response_results
        )

        if not override_date_is_already_contained and session_date_override is not None:
            session_date_override_vector_ids = []
            list_operation_prefix = datetime_handler.convert_to_internal_date_format(session_date_override.session_date)
            for list_ids in index.list(namespace=namespace, prefix=list_operation_prefix):
                session_date_override_vector_ids = list_ids

            # Didn't find any vectors for that day, return unchanged reranked_docs
            if len(session_date_override_vector_ids) == 0:
                return reranked_docs

            session_date_override_fetch_result = index.fetch(ids=session_date_override_vector_ids,
                                                             namespace=namespace)
            vectors = session_date_override_fetch_result['vectors']
            if len(vectors or []) == 0:
                return reranked_docs

            # Have vectors for session date override. Append them to current reranked_docs value.
            for vector_id in vectors:
                vector_data = vectors[vector_id]

                metadata = vector_data['metadata']
                session_date = "".join(["session_date = ",f"{metadata['session_date']}\n"])
                chunk_summary = "".join(["chunk_summary = ",f"{metadata['chunk_summary']}\n"])
                chunk_text = "".join(["chunk_text = ",f"{metadata['chunk_text']}\n"])
                session_date_override_context = "".join([session_date_override.output_prefix_override,
                                                         session_date,
                                                         chunk_summary,
                                                         chunk_text,
                                                         session_date_override.output_suffix_override,
                                                         "\n"])
                reranked_docs = "\n".join([reranked_docs,
                                           session_date_override_context])

        return reranked_docs

    def _fetch_historical_context(self,
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
            chunk_summary = "".join(["pre_existing_history_summary = ",f"{metadata['pre_existing_history_summary']}"])
            chunk_text = "".join(["\npre_existing_history_text = ",f"{metadata['pre_existing_history_text']}\n"])
            chunk_full_context = "".join([chunk_summary,
                                          chunk_text,
                                          "\n"])
            context_docs.append({
                "id": vector_data['id'],
                "text": chunk_full_context
            })

        if len(context_docs) > 0:
            return (True, "\n".join([doc['text'] for doc in context_docs]))
        return (False, None)
