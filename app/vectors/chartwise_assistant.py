import tiktoken

from datetime import datetime
from typing import AsyncIterable

from ..dependencies.dependency_container import dependency_container
from .message_templates import PromptCrafter, PromptScenario
from ..dependencies.api.openai_base_class import OpenAIBaseClass
from ..dependencies.api.supabase_base_class import SupabaseBaseClass
from ..dependencies.api.pinecone_session_date_override import PineconeQuerySessionDateOverride
from ..internal.utilities import datetime_handler

TOPICS_CONTEXT_SESSIONS_CAP = 6
QUESTION_SUGGESTIONS_CONTEXT_SESSIONS_CAP = 6
ATTENDANCE_CONTEXT_SESSIONS_CAP = 52
BRIEFING_CONTEXT_SESSIONS_CAP = 4
QUERY_ACTON_NAME = "assistant_query"
BRIEFING_ACTON_NAME = "briefing"
QUESTION_SUGGESTIONS_ACTION_NAME = "question_suggestions"
TOPICS_ACTION_NAME = "topics"
TOPICS_INSIGHTS_ACTION_NAME = "topics_insights"
ATTENDANCE_INSIGHTS_ACTION_NAME = "attendance_insights"
SOAP_REPORT_ACTION_NAME = "soap_report"
SUMMARIZE_CHUNK_ACTION_NAME = "summarize_chunk"
MINI_SUMMARY_ACTION_NAME = "mini_summary"

class ChartWiseAssistant:

    def __init__(self):
        self.namespace_used_for_streaming = None

    """
    Queries the respective store with the incoming parameters.
    Returns the query result.

    Arguments:
    user_id – the user id associated with the query operation.
    patient_id – the patient id associated with the query operation.
    patient_name – the name by which the patient should be addressed.
    patient_gender – the patient's gender.
    query_input – the user input for the query.
    response_language_code – the language code to be used in the response.
    session_id – the session id.
    environment – the current running environment.
    session_date_override – the optional override for including date-specific vectors.
    """
    async def query_store(self,
                          user_id: str,
                          patient_id: str,
                          patient_name: str,
                          patient_gender: str,
                          query_input: str,
                          response_language_code: str,
                          session_id: str,
                          environment: str,
                          session_date_override: PineconeQuerySessionDateOverride = None) -> AsyncIterable[str]:
        try:
            openai_client = dependency_container.inject_openai_client()
            metadata = {
                "environment": environment,
                "user_id": user_id,
                "patient_id": patient_id,
                "language_code": response_language_code,
                "session_id": str(session_id),
                "action": QUERY_ACTON_NAME,
            }

            # If the user is now querying another patient, let's clear any chat history.
            if self.namespace_used_for_streaming != patient_id:
                await openai_client.clear_chat_history()
                self.namespace_used_for_streaming = patient_id

            is_first_message_in_conversation = len(openai_client.chat_history) == 0

            # If there exists a chat history already, we should reformulate the latest user question
            # So that it can be understood standalone. This helps in cleaning the chat history, and helping the assistant be more efficient.
            if not is_first_message_in_conversation:
                prompt_crafter = PromptCrafter()
                reformulate_question_user_prompt = prompt_crafter.get_user_message_for_scenario(chat_history=(await openai_client.flatten_chat_history()),
                                                                                                query_input=query_input,
                                                                                                scenario=PromptScenario.REFORMULATE_QUERY)
                reformulate_question_system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.REFORMULATE_QUERY)
                prompt_tokens = len(tiktoken.get_encoding("o200k_base").encode(f"{reformulate_question_system_prompt}\n{reformulate_question_user_prompt}"))
                max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

                query_input = await openai_client.trigger_async_chat_completion(metadata=metadata,
                                                                                max_tokens=max_tokens,
                                                                                messages=[
                                                                                    {"role": "system", "content": reformulate_question_system_prompt},
                                                                                    {"role": "user", "content": reformulate_question_user_prompt},
                                                                                ],
                                                                                expects_json_response=False)

            context = await dependency_container.inject_pinecone_client().get_vector_store_context(query_input=query_input,
                                                                                                   user_id=user_id,
                                                                                                   patient_id=patient_id,
                                                                                                   openai_client=openai_client,
                                                                                                   query_top_k=6,
                                                                                                   rerank_vectors=True,
                                                                                                   session_dates_override=[session_date_override])

            last_session_date = None if session_date_override is None else session_date_override.session_date

            async for part in openai_client.stream_chat_completion(vector_context=context,
                                                                   language_code=response_language_code,
                                                                   query_input=query_input,
                                                                   is_first_message_in_conversation=is_first_message_in_conversation,
                                                                   patient_name=patient_name,
                                                                   patient_gender=patient_gender,
                                                                   metadata=metadata,
                                                                   last_session_date=last_session_date):
                yield part

        except Exception as e:
            raise Exception(e)

    """
    Creates and returns a briefing on the incoming patient id's data.

    Arguments:
    user_id – the user id associated with the briefing operation.
    patient_id – the patient id associated with the briefing operation.
    environment – the current running environment.
    language_code – the language code to be used in the response.
    session_id – the session id.
    patient_name – the name by which the patient should be referred to.
    therapist_name – the name by which the patient should be referred to.
    session_count – the count of sessions so far with this patient.
    supabase_client – the supabase client.
    """
    async def create_briefing(self,
                              user_id: str,
                              patient_id: str,
                              environment: str,
                              language_code: str,
                              session_id: str,
                              patient_name: str,
                              patient_gender: str,
                              therapist_name: str,
                              therapist_gender: str,
                              session_count: int,
                              supabase_client: SupabaseBaseClass) -> str:
        try:
            query_input = (f"I'm coming up to speed with {patient_name}'s session notes. "
            "What's most valuable for me to remember, and what would be good avenues to explore in our upcoming session?")

            session_dates_override = self._retrieve_n_most_recent_session_dates(supabase_client=supabase_client,
                                                                                patient_id=patient_id,
                                                                                n=BRIEFING_CONTEXT_SESSIONS_CAP)

            openai_client = dependency_container.inject_openai_client()
            context = await dependency_container.inject_pinecone_client().get_vector_store_context(query_input=query_input,
                                                                                                   user_id=user_id,
                                                                                                   patient_id=patient_id,
                                                                                                   openai_client=openai_client,
                                                                                                   query_top_k=0,
                                                                                                   rerank_vectors=False,
                                                                                                   session_dates_override=session_dates_override)

            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.PRESESSION_BRIEFING,
                                                                       language_code=language_code,
                                                                       patient_name=patient_name,
                                                                       query_input=query_input,
                                                                       context=context)

            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.PRESESSION_BRIEFING,
                                                                           language_code=language_code,
                                                                           therapist_name=therapist_name,
                                                                           therapist_gender=therapist_gender,
                                                                           patient_name=patient_name,
                                                                           patient_gender=patient_gender,
                                                                           session_count=session_count)
            prompt_tokens = len(tiktoken.get_encoding("o200k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            caching_shard_key = (patient_id + "-briefing-" + datetime.now().strftime(datetime_handler.DATE_FORMAT))
            metadata = {
                "environment": environment,
                "user_id": user_id,
                "patient_id": patient_id,
                "session_id": str(session_id),
                "caching_shard_key": caching_shard_key,
                "language_code": language_code,
                "action": BRIEFING_ACTON_NAME
            }

            return await openai_client.trigger_async_chat_completion(metadata=metadata,
                                                                     max_tokens=max_tokens,
                                                                     messages=[
                                                                         {"role": "system", "content": system_prompt},
                                                                         {"role": "user", "content": user_prompt},
                                                                     ],
                                                                     expects_json_response=False,
                                                                     cache_configuration={
                                                                         'cache_max_age': 86400, # 24 hours
                                                                         'caching_shard_key': caching_shard_key,
                                                                     })
        except Exception as e:
            raise Exception(e)

    """
    Fetches a set of questions to be suggested to the user for feeding the assistant.

    Arguments:
    user_id – the user id associated with the question suggestions operation.
    patient_id – the patient id associated with the question suggestions operation.
    environment – the current running environment.
    language_code – the language code to be used in the response.
    session_id – the session id.
    patient_name – the name by which the patient should be addressed.
    patient_gender – the patient gender.
    """
    async def create_question_suggestions(self,
                                          user_id: str,
                                          patient_id: str,
                                          environment: str,
                                          language_code: str,
                                          session_id: str,
                                          patient_name: str,
                                          patient_gender: str,
                                          supabase_client: SupabaseBaseClass) -> str:
        try:
            query_input = f"What are 2 questions about different topics that I could ask about {patient_name}'s session history?"

            session_dates_override = self._retrieve_n_most_recent_session_dates(supabase_client=supabase_client,
                                                                                patient_id=patient_id,
                                                                                n=QUESTION_SUGGESTIONS_CONTEXT_SESSIONS_CAP)

            openai_client = dependency_container.inject_openai_client()
            context = await dependency_container.inject_pinecone_client().get_vector_store_context(query_input=query_input,
                                                                                                   user_id=user_id,
                                                                                                   patient_id=patient_id,
                                                                                                   openai_client=openai_client,
                                                                                                   query_top_k=0,
                                                                                                   rerank_vectors=False,
                                                                                                   session_dates_override=session_dates_override)

            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.QUESTION_SUGGESTIONS,
                                                                       context=context,
                                                                       language_code=language_code,
                                                                       patient_gender=patient_gender,
                                                                       patient_name=patient_name,
                                                                       query_input=query_input)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.QUESTION_SUGGESTIONS,
                                                                           language_code=language_code)
            prompt_tokens = len(tiktoken.get_encoding("o200k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            caching_shard_key = (patient_id + "-questions-" + datetime.now().strftime(datetime_handler.DATE_FORMAT))
            metadata = {
                "environment": environment,
                "user_id": user_id,
                "patient_id": patient_id,
                "session_id": str(session_id),
                "caching_shard_key": caching_shard_key,
                "language_code": language_code,
                "action": QUESTION_SUGGESTIONS_ACTION_NAME
            }

            return await openai_client.trigger_async_chat_completion(metadata=metadata,
                                                                     max_tokens=max_tokens,
                                                                     messages=[
                                                                         {"role": "system", "content": system_prompt},
                                                                         {"role": "user", "content": user_prompt},
                                                                     ],
                                                                     cache_configuration={
                                                                         'cache_max_age': 86400, # 24 hours
                                                                         'caching_shard_key': caching_shard_key,
                                                                     },
                                                                     expects_json_response=True)
        except Exception as e:
            raise Exception(e)

    """
    Fetches a set of topics associated with the user along with respective density percentages.

    Arguments:
    user_id – the user id associated with the topics operation.
    patient_id – the patient id associated with the topics operation.
    environment – the current running environment.
    language_code – the language code to be used in the response.
    session_id – the session id.
    patient_name – the name by which the patient should be addressed.
    patient_gender – the patient gender.
    supabase_client – the supabase client to be leveraged internally.
    """
    async def fetch_recent_topics(self,
                                  user_id: str,
                                  patient_id: str,
                                  environment: str,
                                  language_code: str,
                                  session_id: str,
                                  patient_name: str,
                                  patient_gender: str,
                                  supabase_client: SupabaseBaseClass) -> str:
        try:
            query_input = f"What are the topics that have come up the most in {patient_name}'s most recent sessions?"

            session_dates_override = self._retrieve_n_most_recent_session_dates(supabase_client=supabase_client,
                                                                                patient_id=patient_id,
                                                                                n=TOPICS_CONTEXT_SESSIONS_CAP)

            openai_client = dependency_container.inject_openai_client()
            context = await dependency_container.inject_pinecone_client().get_vector_store_context(query_input=query_input,
                                                                                                   user_id=user_id,
                                                                                                   patient_id=patient_id,
                                                                                                   openai_client=openai_client,
                                                                                                   query_top_k=0,
                                                                                                   rerank_vectors=False,
                                                                                                   include_preexisting_history=False,
                                                                                                   session_dates_override=session_dates_override)

            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.TOPICS,
                                                                       context=context,
                                                                       language_code=language_code,
                                                                       patient_gender=patient_gender,
                                                                       patient_name=patient_name,
                                                                       query_input=query_input)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.TOPICS,
                                                                           language_code=language_code)
            prompt_tokens = len(tiktoken.get_encoding("o200k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            caching_shard_key = (patient_id + "-topics-" + datetime.now().strftime(datetime_handler.DATE_FORMAT))
            metadata = {
                "environment": environment,
                "user_id": user_id,
                "patient_id": patient_id,
                "session_id": str(session_id),
                "caching_shard_key": caching_shard_key,
                "language_code": language_code,
                "action": TOPICS_ACTION_NAME
            }

            return await openai_client.trigger_async_chat_completion(metadata=metadata,
                                                                     max_tokens=max_tokens,
                                                                     messages=[
                                                                         {"role": "system", "content": system_prompt},
                                                                         {"role": "user", "content": user_prompt},
                                                                     ],
                                                                     cache_configuration={
                                                                         'cache_max_age': 86400, # 24 hours
                                                                         'caching_shard_key': caching_shard_key,
                                                                     },
                                                                     expects_json_response=True)
        except Exception as e:
            raise Exception(e)

    """
    Create insight for a given set of recent topics.

    Arguments:
    recent_topics_json – the set of recent topics to be analyzed.
    user_id – the user id associated with the topics insights operation.
    patient_id – the patient id associated with the topics insights operation.
    environment – the current running environment.
    language_code – the language code to be used in the response.
    session_id – the session id.
    patient_name – the name by which the patient should be addressed.
    patient_gender – the patient gender.
    supabase_client – the supabase client to be leveraged internally.
    """
    async def generate_recent_topics_insights(self,
                                              recent_topics_json: str,
                                              user_id: str,
                                              patient_id: str,
                                              environment: str,
                                              language_code: str,
                                              session_id: str,
                                              patient_name: str,
                                              patient_gender: str,
                                              supabase_client: SupabaseBaseClass) -> str:
        try:
            query_input = f"Please help me analyze the following set of topics that have recently come up during my sessions with {patient_name}, my patient:\n{recent_topics_json}"

            session_dates_override = self._retrieve_n_most_recent_session_dates(supabase_client=supabase_client,
                                                                                patient_id=patient_id,
                                                                                n=TOPICS_CONTEXT_SESSIONS_CAP)

            openai_client = dependency_container.inject_openai_client()
            context = await dependency_container.inject_pinecone_client().get_vector_store_context(query_input=query_input,
                                                                                                   user_id=user_id,
                                                                                                   patient_id=patient_id,
                                                                                                   openai_client=openai_client,
                                                                                                   query_top_k=0,
                                                                                                   rerank_vectors=False,
                                                                                                   include_preexisting_history=False,
                                                                                                   session_dates_override=session_dates_override)

            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.TOPICS_INSIGHTS,
                                                                       context=context,
                                                                       language_code=language_code,
                                                                       patient_gender=patient_gender,
                                                                       patient_name=patient_name,
                                                                       query_input=query_input)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.TOPICS_INSIGHTS,
                                                                           language_code=language_code)
            prompt_tokens = len(tiktoken.get_encoding("o200k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            caching_shard_key = (patient_id + "-topics-insights-" + datetime.now().strftime(datetime_handler.DATE_FORMAT))
            metadata = {
                "environment": environment,
                "user_id": user_id,
                "patient_id": patient_id,
                "session_id": str(session_id),
                "caching_shard_key": caching_shard_key,
                "language_code": language_code,
                "action": TOPICS_INSIGHTS_ACTION_NAME
            }

            return await openai_client.trigger_async_chat_completion(metadata=metadata,
                                                                     max_tokens=max_tokens,
                                                                     messages=[
                                                                         {"role": "system", "content": system_prompt},
                                                                         {"role": "user", "content": user_prompt},
                                                                     ],
                                                                     cache_configuration={
                                                                         'cache_max_age': 86400, # 24 hours
                                                                         'caching_shard_key': caching_shard_key,
                                                                     },
                                                                     expects_json_response=False)
        except Exception as e:
            raise Exception(e)

    async def generate_attendance_insights(self,
                                           therapist_id: str,
                                           patient_id: str,
                                           environment: str,
                                           language_code: str,
                                           session_id: str,
                                           patient_name: str,
                                           patient_gender: str,
                                           supabase_client: SupabaseBaseClass) -> str:
        try:
            patient_session_dates = [date_wrapper.session_date for date_wrapper in self._retrieve_n_most_recent_session_dates(supabase_client=supabase_client,
                                                                                                                              patient_id=patient_id,
                                                                                                                              n=ATTENDANCE_CONTEXT_SESSIONS_CAP)]
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.ATTENDANCE_INSIGHTS,
                                                                       patient_session_dates=patient_session_dates,
                                                                       patient_name=patient_name,
                                                                       patient_gender=patient_gender)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.ATTENDANCE_INSIGHTS,
                                                                           language_code=language_code)
            prompt_tokens = len(tiktoken.get_encoding("o200k_base").encode(f"{system_prompt}\n{user_prompt}"))
            openai_client = dependency_container.inject_openai_client()
            max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            caching_shard_key = (patient_id + "-attendance-insights-" + datetime.now().strftime(datetime_handler.DATE_FORMAT))
            metadata = {
                "environment": environment,
                "user_id": therapist_id,
                "patient_id": patient_id,
                "session_id": str(session_id),
                "caching_shard_key": caching_shard_key,
                "language_code": language_code,
                "action": ATTENDANCE_INSIGHTS_ACTION_NAME
            }

            return await openai_client.trigger_async_chat_completion(metadata=metadata,
                                                                     max_tokens=max_tokens,
                                                                     messages=[
                                                                         {"role": "system", "content": system_prompt},
                                                                         {"role": "user", "content": user_prompt},
                                                                     ],
                                                                     cache_configuration={
                                                                         'cache_max_age': 86400, # 24 hours
                                                                         'caching_shard_key': caching_shard_key,
                                                                     },
                                                                     expects_json_response=False)
        except Exception as e:
            raise Exception(e)

    """
    Creates and returns a SOAP report with the incoming data.

    Arguments:
    text – the text to be adapted to a SOAP format.
    therapist_id – the therapist_id.
    session_id – the session id.
    """
    async def create_soap_report(self,
                                 text: str,
                                 therapist_id: str,
                                 session_id: str) -> str:
        try:
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.SOAP_TEMPLATE,
                                                                       session_notes=text)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.SOAP_TEMPLATE)
            prompt_tokens = len(tiktoken.get_encoding("o200k_base").encode(f"{system_prompt}\n{user_prompt}"))

            openai_client = dependency_container.inject_openai_client()
            max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            metadata = {
                "user_id": therapist_id,
                "session_id": str(session_id),
                "action": SOAP_REPORT_ACTION_NAME
            }

            return await openai_client.trigger_async_chat_completion(metadata=metadata,
                                                                     max_tokens=max_tokens,
                                                                     messages=[
                                                                         {"role": "system", "content": system_prompt},
                                                                         {"role": "user", "content": user_prompt},
                                                                     ],
                                                                     expects_json_response=False)
        except Exception as e:
            raise Exception(e)

    """
    Summarizes a chunk for faster fetching.

    Arguments:
    user_id – the user id.
    session_id – the session id.
    chunk_text – the text associated with the incoming chunk.
    openai_client – the openai client to be leveraged internally.
    """
    async def summarize_chunk(self,
                              user_id: str,
                              session_id: str,
                              chunk_text: str,
                              openai_client: OpenAIBaseClass) -> str:
        try:
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(PromptScenario.CHUNK_SUMMARY,
                                                                       chunk_text=chunk_text)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.CHUNK_SUMMARY)
            prompt_tokens = len(tiktoken.get_encoding("o200k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            metadata = {
                "user_id": user_id,
                "session_id": str(session_id),
                "action": SUMMARIZE_CHUNK_ACTION_NAME
            }
            return await openai_client.trigger_async_chat_completion(metadata=metadata,
                                                                     max_tokens=max_tokens,
                                                                     messages=[
                                                                         {"role": "system", "content": system_prompt},
                                                                         {"role": "user", "content": user_prompt},
                                                                     ],
                                                                     expects_json_response=False)
        except Exception as e:
            raise Exception(e)

    """
    Creates a 'mini' summary of the incoming session notes.

    Arguments:
    session_notes – the text associated with the session notes.
    therapist_id – the therapist_id.
    language_code – the language_code to be used for generating the response.
    session_id – the session id.
    patient_id – the patient id.
    """
    async def create_session_mini_summary(self,
                                          session_notes: str,
                                          therapist_id: str,
                                          language_code: str,
                                          session_id: str,
                                          patient_id: str) -> str:
        try:
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(PromptScenario.SESSION_MINI_SUMMARY,
                                                                       session_notes=session_notes)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.SESSION_MINI_SUMMARY,
                                                                           language_code=language_code)
            prompt_tokens = len(tiktoken.get_encoding("o200k_base").encode(f"{system_prompt}\n{user_prompt}"))

            openai_client = dependency_container.inject_openai_client()
            max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            metadata = {
                "patient_id": patient_id,
                "user_id": therapist_id,
                "session_id": str(session_id),
                "language_code": language_code,
                "action": MINI_SUMMARY_ACTION_NAME
            }

            return await openai_client.trigger_async_chat_completion(metadata=metadata,
                                                                     max_tokens=max_tokens,
                                                                     messages=[
                                                                         {"role": "system", "content": system_prompt},
                                                                         {"role": "user", "content": user_prompt},
                                                                     ],
                                                                     expects_json_response=False)
        except Exception as e:
            raise Exception(e)

    # Private

    def _retrieve_n_most_recent_session_dates(self,
                                              supabase_client: SupabaseBaseClass,
                                              patient_id: str,
                                              n: int) -> list[PineconeQuerySessionDateOverride]:
        try:
            dates_response = supabase_client.select(fields="session_date",
                                                    filters={
                                                        "patient_id": patient_id,
                                                    },
                                                    table_name="session_reports",
                                                    limit=n,
                                                    order_desc_column="session_date")
            dates_response_data = dates_response['data']

            overrides = []
            for date in dates_response_data:
                plain_date = date['session_date']
                overrides.append(
                    PineconeQuerySessionDateOverride(session_date=plain_date)
                )
            return overrides
        except Exception as e:
            raise Exception(e)
