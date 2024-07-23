import os

import cohere, tiktoken

from datetime import datetime
from openai import OpenAI
from openai.types import Completion
from pinecone import Pinecone

from ..internal.model import BriefingConfiguration
from .message_templates import PromptCrafter, PromptScenario
from .embeddings import create_embeddings
from ..api.auth_base_class import AuthManagerBaseClass
from ..internal.utilities import datetime_handler

LLM_MODEL = "gpt-4o-mini"
GPT_4O_MINI_MAX_OUTPUT_TOKENS = 16000

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
                          auth_manager: AuthManagerBaseClass) -> str:
        try:
            context = await self._get_context_from_semantically_matching_vectors(auth_manager=auth_manager,
                                                                                 query_input=query_input,
                                                                                 index_id=index_id,
                                                                                 namespace=namespace,
                                                                                 query_top_k=10,
                                                                                 rerank_top_n=3)

            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.QUERY,
                                                                       context=context,
                                                                       language_code=response_language_code,
                                                                       patient_gender=patient_gender,
                                                                       patient_name=patient_name,
                                                                       query_input=query_input)
            system_prompt = prompt_crafter.get_system_message_for_scenario(PromptScenario.QUERY)
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

            return self._trigger_chat_completion_internal(metadata=metadata,
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
    def create_greeting(self,
                        therapist_name: str,
                        therapist_gender: str,
                        language_code: str,
                        tz_identifier: str,
                        session_id: str,
                        endpoint_name: str,
                        therapist_id: str,
                        method: str,
                        environment: str,
                        auth_manager: AuthManagerBaseClass,
                        ) -> str:
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

            return self._trigger_chat_completion_internal(metadata=metadata,
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
    configuration – the configuration to be used for creating the summary.
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
                              configuration: BriefingConfiguration) -> str:
        try:
            query_input = ""
            if configuration == BriefingConfiguration.FULL_SUMMARY:
                query_input = f'''I'm coming up to speed with {patient_name}'s session notes.
                What do I need to remember, and what would be good avenues to explore in our upcoming session?'''
            elif configuration == BriefingConfiguration.PRIMARY_TOPICS:
                query_input = f'''I'm coming up to speed with {patient_name}'s session notes.
                What are the three primary topics associated with {patient_name}'s session history?
                Each bullet point should not take more than 50 characters.'''
            else:
                raise Exception("Invalid briefing configuration.")

            context = await self._get_context_from_semantically_matching_vectors(auth_manager=auth_manager,
                                                                                 query_input=query_input,
                                                                                 index_id=index_id,
                                                                                 namespace=namespace,
                                                                                 query_top_k=10,
                                                                                 rerank_top_n=3)
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
                                                                           session_number=session_number)
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

            return self._trigger_chat_completion_internal(metadata=metadata,
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
                                          auth_manager: AuthManagerBaseClass) -> str:
        try:
            query_input = f"What are 3 questions that I could ask about {patient_name}'s session history?"
            context = await self._get_context_from_semantically_matching_vectors(auth_manager=auth_manager,
                                                                                 query_input=query_input,
                                                                                 index_id=index_id,
                                                                                 namespace=namespace,
                                                                                 query_top_k=10,
                                                                                 rerank_top_n=3)

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

            return self._trigger_chat_completion_internal(metadata=metadata,
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
                                    auth_manager: AuthManagerBaseClass) -> str:
        try:
            query_input = f"What are the 3 topics that come up the most during {patient_name}'s sessions?"
            context = await self._get_context_from_semantically_matching_vectors(auth_manager=auth_manager,
                                                                                 query_input=query_input,
                                                                                 index_id=index_id,
                                                                                 namespace=namespace,
                                                                                 query_top_k=10,
                                                                                 rerank_top_n=3)

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

            return self._trigger_chat_completion_internal(metadata=metadata,
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
    """
    def create_soap_report(self,
                           text: str,
                           therapist_id: str,
                           auth_manager: AuthManagerBaseClass,
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

            return self._trigger_chat_completion_internal(metadata=metadata,
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
    Summarizes a session entry for faster fetching.

    Arguments:
    session_text – the text associated with the session notes.
    therapist_id – the therapist_id.
    auth_manager – the auth manager to be leveraged internally.
    session_date – the session date.
    session_id – the session id.
    """
    def summarize_session_entry(self,
                                session_text: str,
                                therapist_id: str,
                                auth_manager: AuthManagerBaseClass,
                                session_date: str,
                                session_id: str) -> str:
        try:
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(PromptScenario.SESSION_SUMMARY,
                                                                       session_notes=session_text,
                                                                       session_date=session_date)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.SESSION_SUMMARY)
            prompt_tokens = len(tiktoken.get_encoding("cl100k_base").encode(f"{system_prompt}\n{user_prompt}"))
            max_tokens = GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            metadata = {
                "user": therapist_id,
                "session_id": str(session_id)
            }

            return self._trigger_chat_completion_internal(metadata=metadata,
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

    async def _get_context_from_semantically_matching_vectors(self,
                                                              auth_manager: AuthManagerBaseClass,
                                                              query_input: str,
                                                              index_id: str,
                                                              namespace: str,
                                                              query_top_k: int,
                                                              rerank_top_n: int,) -> str:
        pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
        assert index_id in pc.list_indexes().names(), "Index not found"

        index = pc.Index(index_id)
        embeddings = create_embeddings(auth_manager=auth_manager,
                                       text=query_input)

        query_result = index.query(vector=embeddings,
                                   top_k=query_top_k,
                                   namespace=namespace,
                                   include_metadata=True)

        matches = query_result.to_dict()['matches']
        if len(matches) == 0:
            return "There is no session data associated with the patient. They may have not gone through their first session yet."

        retrieved_docs = []
        for match in matches:
            metadata = match['metadata']
            text = metadata['session_text']
            retrieved_docs.append({"id": match['id'], "text": text})

        cohere_client = cohere.AsyncClient(os.environ.get("COHERE_API_KEY"))
        rerank_response = await cohere_client.rerank(
            model="rerank-multilingual-v3.0",
            query=query_input,
            documents=[{"text": doc['text'], "id": doc['id']} for doc in retrieved_docs],
            return_documents=True,
            top_n=rerank_top_n,
        )
        return "\n".join([result.document.text for result in rerank_response.results])

    def _trigger_chat_completion_internal(self,
                                          metadata: dict,
                                          max_tokens: int,
                                          messages: list,
                                          expects_json_response: bool,
                                          auth_manager: AuthManagerBaseClass,
                                          cache_configuration: dict = None):
        try:
            is_monitoring_proxy_reachable = auth_manager.is_monitoring_proxy_reachable()

            if is_monitoring_proxy_reachable:
                assert (cache_configuration is None or
                        ('cache_max_age' in cache_configuration and
                         'caching_shard_key' in cache_configuration), "Missing expected values in caching configuration")

                api_base = auth_manager.get_monitoring_proxy_url()
                cache_max_age = None if (cache_configuration is None or 'cache_max_age' not in cache_configuration) else cache_configuration['cache_max_age']
                caching_shard_key = None if (cache_configuration is None or 'caching_shard_key' not in cache_configuration) else cache_configuration['caching_shard_key']
                proxy_headers = auth_manager.create_monitoring_proxy_headers(metadata=metadata,
                                                                             caching_shard_key=caching_shard_key,
                                                                             cache_max_age=cache_max_age,
                                                                             llm_model=LLM_MODEL)
            else:
                api_base = None
                proxy_headers = None

            openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"),
                                   default_headers=proxy_headers,
                                   base_url=api_base)

            response: Completion = openai_client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                temperature=0,
                max_tokens=max_tokens
            )

            response_text = response.choices[0].message.content.strip()
            return response_text if not expects_json_response else eval(str(response_text))
        except Exception as e:
            raise Exception(e)
