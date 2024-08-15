import json
import tiktoken

from datetime import datetime
from typing import AsyncIterable

from .message_templates import PromptCrafter, PromptScenario
from ..dependencies.api.openai_base_class import OpenAIBaseClass
from ..dependencies.api.pinecone_base_class import PineconeBaseClass
from ..dependencies.api.supabase_base_class import SupabaseBaseClass
from ..dependencies.api.pinecone_session_date_override import PineconeQuerySessionDateOverride
from ..internal.utilities import datetime_handler
from ..managers.auth_manager import AuthManager

PRE_EXISTING_HISTORY_PREFIX = "pre-existing-history"

class ChartWiseAssistant:

    def __init__(self):
        self.namespace_used_for_streaming = None

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
    openai_client – the openai client to be leveraged internally.
    pinecone_client – the pinecone client to be leveraged internally.
    session_date_override – the optional override for including date-specific vectors.
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
                          auth_manager: AuthManager,
                          openai_client: OpenAIBaseClass,
                          pinecone_client: PineconeBaseClass,
                          session_date_override: PineconeQuerySessionDateOverride = None) -> AsyncIterable[str]:
        try:
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

            # If the user is now querying another namespace, let's clear any chat history.
            if self.namespace_used_for_streaming != namespace:
                await openai_client.clear_chat_history()
                self.namespace_used_for_streaming = namespace
                is_first_message_in_conversation = True
            else:
                is_first_message_in_conversation = False

            # If there exists a chat history already, we should reformulate the latest user question
            # So that it can be understood standalone. This helps in cleaning the chat history, and helping the assistant be more efficient.
            if not is_first_message_in_conversation:
                prompt_crafter = PromptCrafter()
                reformulate_question_user_prompt = prompt_crafter.get_user_message_for_scenario(chat_history=(await openai_client.flatten_chat_history()),
                                                                                                query_input=query_input,
                                                                                                scenario=PromptScenario.REFORMULATE_QUERY)
                reformulate_question_system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.REFORMULATE_QUERY)
                prompt_tokens = len(tiktoken.get_encoding("cl100k_base").encode(f"{reformulate_question_system_prompt}\n{reformulate_question_user_prompt}"))
                max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens
                query_input = await openai_client.trigger_async_chat_completion(metadata=metadata,
                                                                                max_tokens=max_tokens,
                                                                                messages=[
                                                                                    {"role": "system", "content": reformulate_question_system_prompt},
                                                                                    {"role": "user", "content": reformulate_question_user_prompt},
                                                                                ],
                                                                                auth_manager=auth_manager,
                                                                                expects_json_response=False)

            _, context = await pinecone_client.get_vector_store_context(auth_manager=auth_manager,
                                                                        query_input=query_input,
                                                                        index_id=index_id,
                                                                        namespace=namespace,
                                                                        openai_client=openai_client,
                                                                        query_top_k=10,
                                                                        rerank_top_n=3,
                                                                        endpoint_name=endpoint_name,
                                                                        session_id=session_id,
                                                                        session_date_override=session_date_override)

            last_session_date = None if session_date_override is None else session_date_override.session_date
            async for part in openai_client.stream_chat_completion(vector_context=context,
                                                                   language_code=response_language_code,
                                                                   query_input=query_input,
                                                                   is_first_message_in_conversation=is_first_message_in_conversation,
                                                                   patient_name=patient_name,
                                                                   patient_gender=patient_gender,
                                                                   metadata=metadata,
                                                                   auth_manager=auth_manager,
                                                                   last_session_date=last_session_date):
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
    openai_client – the openai client.
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
                              openai_client: OpenAIBaseClass,
                              auth_manager: AuthManager) -> str:
        try:
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.GREETING)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.GREETING,
                                                                           therapist_name=therapist_name,
                                                                           therapist_gender=therapist_gender,
                                                                           tz_identifier=tz_identifier,
                                                                           language_code=language_code)
            prompt_tokens = len(tiktoken.get_encoding("cl100k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

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

            return await openai_client.trigger_async_chat_completion(metadata=metadata,
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
    openai_client – the openai client to be leveraged internally.
    pinecone_client – the pinecone client to be leveraged internally.
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
                              auth_manager: AuthManager,
                              openai_client: OpenAIBaseClass,
                              pinecone_client: PineconeBaseClass,
                              session_date_override: PineconeQuerySessionDateOverride = None) -> str:
        try:
            query_input = (f"I'm coming up to speed with {patient_name}'s session notes. "
            "What do I need to remember, and what would be good avenues to explore in our upcoming session?")

            _, context = await pinecone_client.get_vector_store_context(auth_manager=auth_manager,
                                                                        openai_client=openai_client,
                                                                        query_input=query_input,
                                                                        index_id=index_id,
                                                                        namespace=namespace,
                                                                        query_top_k=10,
                                                                        rerank_top_n=4,
                                                                        session_id=session_id,
                                                                        endpoint_name=endpoint_name,
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
            max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

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

            return await openai_client.trigger_async_chat_completion(metadata=metadata,
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
    openai_client – the openai client to be leveraged internally.
    pinecone_client – the pinecone client to be leveraged internally.
    supabase_client – the supabase client to be leveraged internally.
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
                                          openai_client: OpenAIBaseClass,
                                          pinecone_client: PineconeBaseClass,
                                          supabase_client: SupabaseBaseClass,
                                          auth_manager: AuthManager) -> str:
        try:
            query_input = f"What are 3 questions about different topics that I could ask about {patient_name}'s session history?"
            found_context, context = await pinecone_client.get_vector_store_context(auth_manager=auth_manager,
                                                                                    openai_client=openai_client,
                                                                                    query_input=query_input,
                                                                                    index_id=index_id,
                                                                                    endpoint_name=endpoint_name,
                                                                                    namespace=namespace,
                                                                                    session_id=session_id,
                                                                                    query_top_k=10,
                                                                                    rerank_top_n=4)

            # If there's no patient data, we'll return 3 static questions as default.
            if not found_context:
                default_question_suggestions = self._default_question_suggestions_ids_for_new_patient(language_code)
                strings_query = supabase_client.select_either_or_from_column(fields="*",
                                                                             table_name="user_interface_strings",
                                                                             column_name="id",
                                                                             possible_values=default_question_suggestions)
                assert (0 != len((strings_query).data)), "Did not find any strings data for the current scenario."
                default_question_suggestions = [item['value'] for item in strings_query.dict()['data']]
                response_dict = {
                    "questions": default_question_suggestions
                }
                return eval(json.dumps(response_dict, ensure_ascii=False))

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
            max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

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

            return await openai_client.trigger_async_chat_completion(metadata=metadata,
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
    openai_client – the openai client to be leveraged internally.
    pinecone_client – the pinecone client to be leveraged internally.
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
                                    openai_client: OpenAIBaseClass,
                                    pinecone_client: PineconeBaseClass,
                                    auth_manager: AuthManager) -> str:
        try:
            query_input = f"What are the 3 topics that come up the most in {patient_name}'s sessions?"
            _, context = await pinecone_client.get_vector_store_context(auth_manager=auth_manager,
                                                                        query_input=query_input,
                                                                        openai_client=openai_client,
                                                                        index_id=index_id,
                                                                        endpoint_name=endpoint_name,
                                                                        namespace=namespace,
                                                                        session_id=session_id,
                                                                        query_top_k=10,
                                                                        rerank_top_n=4)

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
            max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

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

            return await openai_client.trigger_async_chat_completion(metadata=metadata,
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
    openai_client – the openai client to be leveraged internally.
    session_id – the session id.
    """
    async def create_soap_report(self,
                                 text: str,
                                 therapist_id: str,
                                 auth_manager: AuthManager,
                                 openai_client: OpenAIBaseClass,
                                 session_id: str) -> str:
        try:
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.SOAP_TEMPLATE,
                                                                       session_notes=text)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.SOAP_TEMPLATE)
            prompt_tokens = len(tiktoken.get_encoding("cl100k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            metadata = {
                "user": therapist_id,
                "session_id": str(session_id),
            }

            return await openai_client.trigger_async_chat_completion(metadata=metadata,
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
    openai_client – the openai client to be leveraged internally.
    session_id – the session id.
    """
    async def summarize_chunk(self,
                              chunk_text: str,
                              therapist_id: str,
                              auth_manager: AuthManager,
                              openai_client: OpenAIBaseClass,
                              session_id: str) -> str:
        try:
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(PromptScenario.CHUNK_SUMMARY,
                                                                       chunk_text=chunk_text)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.CHUNK_SUMMARY)
            prompt_tokens = len(tiktoken.get_encoding("cl100k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            metadata = {
                "user": therapist_id,
                "session_id": str(session_id)
            }

            return await openai_client.trigger_async_chat_completion(metadata=metadata,
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
    openai_client – the openai client to be leveraged internally.
    session_id – the session id.
    """
    async def create_session_mini_summary(self,
                                          session_notes: str,
                                          therapist_id: str,
                                          language_code: str,
                                          auth_manager: AuthManager,
                                          openai_client: OpenAIBaseClass,
                                          session_id: str) -> str:
        try:
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(PromptScenario.SESSION_MINI_SUMMARY,
                                                                       session_notes=session_notes)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.SESSION_MINI_SUMMARY,
                                                                           language_code=language_code)
            prompt_tokens = len(tiktoken.get_encoding("cl100k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            metadata = {
                "user": therapist_id,
                "session_id": str(session_id),
                "language_code": language_code,
            }

            return await openai_client.trigger_async_chat_completion(metadata=metadata,
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

    def _default_question_suggestions_ids_for_new_patient(self, language_code: str):
        if language_code.startswith('es-'):
            # Spanish
            return [
                'question_suggestions_no_data_default_es_1',
                'question_suggestions_no_data_default_es_2',
                'question_suggestions_no_data_default_es_3'
            ] 
        elif language_code.startswith('en-'):
            # English
            return [
                'question_suggestions_no_data_default_en_1',
                'question_suggestions_no_data_default_en_2',
                'question_suggestions_no_data_default_en_3'
            ]
        else:
            raise Exception("Unsupported language code")
