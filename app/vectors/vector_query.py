import os

from datetime import datetime
from fastapi import status
from llama_index.core import VectorStoreIndex
from llama_index.llms.openai import OpenAI as llama_index_OpenAI
from llama_index.vector_stores.pinecone import PineconeVectorStore
from openai import OpenAI
from pinecone.grpc import PineconeGRPC

from . import message_templates
from ..api.auth_base_class import AuthManagerBaseClass
from ..internal.utilities import datetime_handler

LLM_MODEL = "gpt-3.5-turbo"

class VectorQueryWorker:

    """
    Queries the respective datastore with the incoming parameters.
    Returns the query result.

    Arguments:
    index_id – the index id that should be queried inside the datastore.
    namespace – the namespace within the index that should be queried.
    input – the input for the query.
    response_language_code – the language code to be used in the response.
    session_id – the session id.
    endpoint_name – the endpoint that was invoked.
    method – the API method that was invoked.
    environment – the current running environment.
    auth_manager – the auth manager to be leveraged internally.
    """
    def query_store(self,
                    index_id: str,
                    namespace: str,
                    input: str,
                    response_language_code: str,
                    session_id: str,
                    endpoint_name: str,
                    method: str,
                    environment: str,
                    auth_manager: AuthManagerBaseClass,
                    auth_entity: str) -> str:
        try:
            # Initialize connection to Pinecone
            pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))
            assert pc.describe_index(index_id).status['ready']

            index = pc.Index(index_id)
            vector_store = PineconeVectorStore(pinecone_index=index, namespace=namespace)
            vector_index = VectorStoreIndex.from_vector_store(vector_store=vector_store, similarity_top_k=3)

            is_monitoring_proxy_reachable = auth_manager.is_monitoring_proxy_reachable()
            api_base = auth_manager.get_monitoring_proxy_url() if is_monitoring_proxy_reachable else None

            metadata = {
                "environment": environment,
                "user": index_id,
                "vector_index": index_id,
                "namespace": namespace,
                "response_language_code": response_language_code,
                "session_id": str(session_id),
                "endpoint_name": endpoint_name,
                "method": method,
                "auth_entity": auth_entity,
            }

            cache_ttl = 300 # 5 minutes
            headers = auth_manager.create_monitoring_proxy_headers(metadata=metadata,
                                                                   caching_shard_key=index_id,
                                                                   llm_model=LLM_MODEL,
                                                                   cache_max_age=cache_ttl) if is_monitoring_proxy_reachable else None

            llm = llama_index_OpenAI(model=LLM_MODEL,
                                    temperature=0,
                                    api_base=api_base,
                                    default_headers=headers)
            query_engine = vector_index.as_query_engine(
                text_qa_template=message_templates.create_chat_prompt_template(response_language_code),
                refine_template=message_templates.create_refine_prompt_template(response_language_code),
                llm=llm,
                streaming=True,
            )

            response = query_engine.query(input)
            return str(response)
        except Exception as e:
            raise Exception(e)

    """
    Creates a greeting with the incoming values.
    Returns the greeting result.

    Arguments:
    name  – the addressing name to be used in the greeting.
    language_code  – the language_code to be used in the greeting.
    tz_identifier  – the timezone identifier to be used for calculating the client's current time.
    session_id  – the session id.
    endpoint_name  – the endpoint that was invoked.
    method – the API method that was invoked.
    environment – the current running environment.
    auth_manager – the auth manager to be leveraged internally.
    """
    def create_greeting(self,
                        name: str,
                        language_code: str,
                        tz_identifier: str,
                        session_id: str,
                        endpoint_name: str,
                        therapist_id: str,
                        method: str,
                        environment: str,
                        auth_manager: AuthManagerBaseClass,
                        auth_entity: str,
                        ) -> str:
        try:
            caching_shard_key = caching_shard_key = (therapist_id + "-" + datetime.now().strftime(datetime_handler.DATE_FORMAT))
            metadata = {
                "environment": environment,
                "user": therapist_id,
                "session_id": str(session_id),
                "caching_shard_key": caching_shard_key,
                "endpoint_name": endpoint_name,
                "method": method,
                "tz_identifier": tz_identifier,
                "language_code": language_code,
                "auth_entity": auth_entity,
            }

            cache_ttl = 86400 # 24 hours
            messages = [
                    {"role": "system", "content": message_templates.create_system_greeting_message(name=name,
                                                                                                   tz_identifier=tz_identifier,
                                                                                                   language_code=language_code)},
                    {"role": "user", "content": message_templates.create_user_greeting_message()}
            ]

            return self._execute_completions_request(caching_shard_key=caching_shard_key,
                                                     metadata=metadata,
                                                     cache_ttl=cache_ttl,
                                                     messages=messages,
                                                     auth_manager=auth_manager)
        except Exception as e:
            raise Exception(e)

    """
    Creates and returns a brief summary on the incoming patient id's data.

    Arguments:
    therapist_id – the therapist that is requesting a summary.
    patient_id – the patient whose data is being summarized.
    environment – the current running environment.
    session_id – the session id.
    endpoint_name – the endpoint that was invoked.
    api_method – the API method that was invoked.
    language_code – the language in which the response should be returned.
    therapist_name – the name by which the user should be addressed.
    patient_name – the name of the patient whose data is being summarized.
    session_number – the number of the current session within the patient history.
    auth_manager – the auth manager to be leveraged internally.
    """
    def create_summary(self,
                       therapist_id: str,
                       patient_id: str,
                       environment: str,
                       session_id: str,
                       endpoint_name: str,
                       api_method: str,
                       language_code: str,
                       therapist_name: str,
                       patient_name: str,
                       session_number: int,
                       auth_manager: AuthManagerBaseClass,
                       auth_entity: str) -> str:
        try:
            caching_shard_key = caching_shard_key = (therapist_id + "-" + datetime.now().strftime(datetime_handler.DATE_FORMAT))
            metadata = {
                "environment": environment,
                "user": therapist_id,
                "patient": patient_id,
                "session_id": str(session_id),
                "caching_shard_key": caching_shard_key,
                "endpoint_name": endpoint_name,
                "method": api_method,
                "language_code": language_code,
                "auth_entity": auth_entity,
            }

            cache_ttl = 86400 # 24 hours
            messages = [
                    {"role": "system", "content": message_templates.create_system_summary_message()},
                    {"role": "user", "content": message_templates.create_user_summary_message(therapist_name=therapist_name,
                                                                                              patient_name=patient_name,
                                                                                              language_code=language_code,
                                                                                              session_number=session_number)}
            ]

            return self._execute_completions_request(caching_shard_key=caching_shard_key,
                                                     metadata=metadata,
                                                     cache_ttl=cache_ttl,
                                                     messages=messages,
                                                     auth_manager=auth_manager)
        except Exception as e:
            raise Exception(e)

    # Private

    """
    Invokes OpenAI's Completion API with the incoming parameters.
    Returns the completion result.

    Arguments:
    caching_shard_key – the shard key to be used for caching purposes.
    metadata – the metadata to be used for logging purposes.
    cache_ttl – the cache ttl.
    messages – the message instructions to be given to the LLM.
    auth_manager – the auth manager to be leveraged internally.
    """
    def _execute_completions_request(self,
                                     caching_shard_key: str,
                                     metadata: dict,
                                     cache_ttl: int,
                                     messages: list,
                                     auth_manager: AuthManagerBaseClass) -> str:
        try:
            is_monitoring_proxy_reachable = auth_manager.is_monitoring_proxy_reachable()
            api_base = auth_manager.get_monitoring_proxy_url() if is_monitoring_proxy_reachable else None

            headers = auth_manager.create_monitoring_proxy_headers(metadata=metadata,
                                                                   caching_shard_key=caching_shard_key,
                                                                   llm_model=LLM_MODEL,
                                                                   cache_max_age=cache_ttl) if is_monitoring_proxy_reachable else None

            llm = OpenAI(base_url=api_base,
                        default_headers=headers)

            completion = llm.chat.completions.create(
                model=LLM_MODEL,
                messages=messages
            )

            return completion.choices[0].message
        except Exception as e:
            raise Exception(e)
