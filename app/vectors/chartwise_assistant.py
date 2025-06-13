import asyncio, inspect, json, tiktoken, logging

from fastapi import Request
from pydantic import BaseModel, Field
from typing import AsyncIterable

from .message_templates import PromptCrafter, PromptScenario
from ..dependencies.dependency_container import dependency_container
from ..dependencies.api.openai_base_class import OpenAIBaseClass
from ..dependencies.api.aws_db_base_class import AwsDbBaseClass
from ..dependencies.api.pinecone_session_date_override import (
    PineconeQuerySessionDateOverride,
    PineconeQuerySessionDateOverrideType,
)
from ..internal.alerting.internal_alert import EngineeringAlert
from ..internal.schemas import ENCRYPTED_SESSION_REPORTS_TABLE_NAME
from ..internal.session_container import session_container
from ..internal.utilities import datetime_handler

TOPICS_CONTEXT_SESSIONS_CAP = 4
QUESTION_SUGGESTIONS_CONTEXT_SESSIONS_CAP = 4
ATTENDANCE_CONTEXT_SESSIONS_CAP = 52
BRIEFING_CONTEXT_SESSIONS_CAP = 4

class ListQuestionSuggestionsSchema(BaseModel):
    questions: list[str] = Field(..., min_items=2, max_items=2)

class RecentTopicSchema(BaseModel):
    topic: str = Field(..., max_length=25)
    percentage: str = Field(..., pattern=r"^\d{1,3}%$")

class ListRecentTopicsSchema(BaseModel):
    topics: list[RecentTopicSchema]

class TimeTokensExtractionSchema(BaseModel):
    start_date: str
    end_date: str

class ChartWiseAssistant:

    def __init__(self):
        self.namespace_used_for_streaming = None

    async def query_store(
        self,
        user_id: str,
        patient_id: str,
        patient_name: str,
        patient_gender: str,
        query_input: str,
        response_language_code: str,
        request: Request,
        last_session_date_override: PineconeQuerySessionDateOverride = None
    ) -> AsyncIterable[str]:
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
        request – the upstream request object.
        last_session_date_override – the optional override for including date-specific vectors.
        """
        try:
            openai_client = dependency_container.inject_openai_client()

            # If the user is now querying another patient, let's clear any chat history.
            if self.namespace_used_for_streaming != patient_id:
                await openai_client.clear_chat_history()
                self.namespace_used_for_streaming = patient_id

            is_first_message_in_conversation = len(openai_client.chat_history) == 0
            prompt_crafter = PromptCrafter()

            async def reformulate_query_input_if_needed():
                if is_first_message_in_conversation:
                    return query_input

                # If there exists a chat history already, we should reformulate the latest user question
                # So that it can be understood standalone. This helps in cleaning the chat history, and helping the assistant be more accurate.
                reformulate_question_user_prompt = prompt_crafter.get_user_message_for_scenario(
                    chat_history=(await openai_client.flatten_chat_history()),
                    query_input=query_input,
                    scenario=PromptScenario.REFORMULATE_QUERY
                )
                reformulate_question_system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.REFORMULATE_QUERY)
                max_tokens = await self.calculate_max_tokens(
                    system_prompt=reformulate_question_system_prompt,
                    user_prompt=reformulate_question_user_prompt,
                )

                return await openai_client.trigger_async_chat_completion(
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": reformulate_question_system_prompt},
                        {"role": "user", "content": reformulate_question_user_prompt},
                    ],
                )

            async def extract_time_tokens_if_possible():
                # Extract any time-related tokens from the query input to determine if the completion
                # should be scoped to a time range.
                extract_time_tokens_user_prompt = prompt_crafter.get_user_message_for_scenario(
                    query_input=query_input,
                    scenario=PromptScenario.EXTRACT_TIME_TOKENS,
                )
                extract_time_tokens_system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.EXTRACT_TIME_TOKENS)
                max_tokens = await self.calculate_max_tokens(
                    system_prompt=extract_time_tokens_system_prompt,
                    user_prompt=extract_time_tokens_user_prompt,
                )

                return await openai_client.trigger_async_chat_completion(
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": extract_time_tokens_system_prompt},
                        {"role": "user", "content": extract_time_tokens_user_prompt},
                    ],
                    expected_output_model=TimeTokensExtractionSchema,
                )

            # Run the reformulation and time token extraction concurrently.
            reformulated_query_input, extracted_time_tokens = await asyncio.gather(
                reformulate_query_input_if_needed(),
                extract_time_tokens_if_possible(),
            )

            context = await self._fetch_context_based_on_query_input(
                query_input=reformulated_query_input,
                user_id=user_id,
                patient_id=patient_id,
                openai_client=openai_client,
                request=request,
                extracted_time_tokens=extracted_time_tokens,
                last_session_date_override=last_session_date_override,
            )
            last_session_date = None if last_session_date_override is None else last_session_date_override.session_date_start

            async for part in openai_client.stream_chat_completion(
                vector_context=context,
                language_code=response_language_code,
                query_input=reformulated_query_input,
                is_first_message_in_conversation=is_first_message_in_conversation,
                patient_name=patient_name,
                patient_gender=patient_gender,
                last_session_date=last_session_date,
                calculate_max_tokens=self.calculate_max_tokens
            ):
                yield part

        except Exception as e:
            raise RuntimeError(e) from e

    async def create_briefing(
        self,
        user_id: str,
        patient_id: str,
        language_code: str,
        patient_name: str,
        patient_gender: str,
        therapist_name: str,
        therapist_gender: str,
        session_count: int,
        request: Request
    ) -> str:
        """
        Creates and returns a briefing on the incoming patient id's data.

        Arguments:
        user_id – the user id associated with the briefing operation.
        patient_id – the patient id associated with the briefing operation.
        language_code – the language code to be used in the response.
        patient_name – the name by which the patient should be referred to.
        patient_gender – the patient gender.
        therapist_name – the name by which the patient should be referred to.
        therapist_gender – the therapist gender.
        session_count – the count of sessions so far with this patient.
        request – the upstream request object.
        """
        try:
            query_input = (
                f"I'm coming up to speed with {patient_name}'s session notes. "
                "What's most valuable for me to remember, and what would be good avenues "
                "to explore in our upcoming session?"
            )

            session_dates_override = await self._retrieve_n_most_recent_session_dates(
                request=request,
                therapist_id=user_id,
                patient_id=patient_id,
                n=BRIEFING_CONTEXT_SESSIONS_CAP
            )

            openai_client = dependency_container.inject_openai_client()
            context = await dependency_container.inject_pinecone_client().get_vector_store_context(
                query_input=query_input,
                user_id=user_id,
                patient_id=patient_id,
                openai_client=openai_client,
                aws_db_client=dependency_container.inject_aws_db_client(),
                request=request,
                query_top_k=0,
                rerank_vectors=False,
                session_dates_overrides=session_dates_override
            )

            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(
                scenario=PromptScenario.PRESESSION_BRIEFING,
                language_code=language_code,
                patient_name=patient_name,
                query_input=query_input,
                context=context
            )

            system_prompt = prompt_crafter.get_system_message_for_scenario(
                scenario=PromptScenario.PRESESSION_BRIEFING,
                language_code=language_code,
                therapist_name=therapist_name,
                therapist_gender=therapist_gender,
                patient_name=patient_name,
                patient_gender=patient_gender,
                session_count=session_count
            )
            max_tokens = await self.calculate_max_tokens(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            return await openai_client.trigger_async_chat_completion(
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as e:
            raise RuntimeError(e) from e

    async def create_question_suggestions(
        self,
        user_id: str,
        patient_id: str,
        language_code: str,
        patient_name: str,
        patient_gender: str,
        request: Request,
    ) -> BaseModel:
        """
        Fetches a set of questions to be suggested to the user for feeding the assistant.

        Arguments:
        user_id – the user id associated with the question suggestions operation.
        patient_id – the patient id associated with the question suggestions operation.
        language_code – the language code to be used in the response.
        patient_name – the name by which the patient should be addressed.
        patient_gender – the patient gender.
        request – the upstream request object.
        """
        try:
            query_input = (
                "What are 2 questions about different topics that I could ask "
                f"about {patient_name}'s session history?"
            )

            session_dates_override = await self._retrieve_n_most_recent_session_dates(
                request=request,
                therapist_id=user_id,
                patient_id=patient_id,
                n=QUESTION_SUGGESTIONS_CONTEXT_SESSIONS_CAP
            )

            openai_client = dependency_container.inject_openai_client()
            context = await dependency_container.inject_pinecone_client().get_vector_store_context(
                query_input=query_input,
                user_id=user_id,
                patient_id=patient_id,
                openai_client=openai_client,
                aws_db_client=dependency_container.inject_aws_db_client(),
                request=request,
                query_top_k=0,
                rerank_vectors=False,
                session_dates_overrides=session_dates_override
            )

            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(
                scenario=PromptScenario.QUESTION_SUGGESTIONS,
                context=context,
                language_code=language_code,
                patient_gender=patient_gender,
                patient_name=patient_name,
                query_input=query_input
            )
            system_prompt = prompt_crafter.get_system_message_for_scenario(
                scenario=PromptScenario.QUESTION_SUGGESTIONS,
                language_code=language_code
            )
            max_tokens = await self.calculate_max_tokens(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            return await openai_client.trigger_async_chat_completion(
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                expected_output_model=ListQuestionSuggestionsSchema,
            )
        except Exception as e:
            raise RuntimeError(e) from e

    async def fetch_recent_topics(
        self,
        user_id: str,
        patient_id: str,
        language_code: str,
        patient_name: str,
        patient_gender: str,
        request: Request,
    ) -> BaseModel:
        """
        Fetches a set of topics associated with the user along with respective density percentages.

        Arguments:
        user_id – the user id associated with the topics operation.
        patient_id – the patient id associated with the topics operation.
        language_code – the language code to be used in the response.
        patient_name – the name by which the patient should be addressed.
        patient_gender – the patient gender.
        request – the upstream request object.
        """
        try:
            query_input = (
                f"What are the topics that have come up the most in {patient_name}'s most recent sessions?"
            )

            session_dates_override = await self._retrieve_n_most_recent_session_dates(
                request=request,
                therapist_id=user_id,
                patient_id=patient_id,
                n=TOPICS_CONTEXT_SESSIONS_CAP
            )
            logging.info(f"[fetch_recent_topics] Session dates override: {session_dates_override}")

            openai_client = dependency_container.inject_openai_client()
            context = await dependency_container.inject_pinecone_client().get_vector_store_context(
                query_input=query_input,
                user_id=user_id,
                patient_id=patient_id,
                openai_client=openai_client,
                aws_db_client=dependency_container.inject_aws_db_client(),
                request=request,
                query_top_k=0,
                rerank_vectors=False,
                include_preexisting_history=False,
                session_dates_overrides=session_dates_override
            )
            logging.info(f"[fetch_recent_topics] Context length: {len(context)}")

            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(
                scenario=PromptScenario.TOPICS,
                context=context,
                language_code=language_code,
                patient_gender=patient_gender,
                patient_name=patient_name,
                query_input=query_input
            )
            system_prompt = prompt_crafter.get_system_message_for_scenario(
                scenario=PromptScenario.TOPICS,
                language_code=language_code
            )
            logging.info(f"[fetch_recent_topics] User prompt length: {len(user_prompt)}")
            logging.info(f"[fetch_recent_topics] System prompt length: {len(system_prompt)}")

            max_tokens = await self.calculate_max_tokens(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            logging.info(f"[fetch_recent_topics] Calculated max_tokens: {max_tokens}")

            return await openai_client.trigger_async_chat_completion(
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                expected_output_model=ListRecentTopicsSchema,
            )
        except Exception as e:
            logging.error(f"[fetch_recent_topics] Error occurred: {str(e)}")
            raise RuntimeError(e) from e

    async def generate_recent_topics_insights(
        self,
        recent_topics: ListRecentTopicsSchema,
        user_id: str,
        patient_id: str,
        language_code: str,
        patient_name: str,
        patient_gender: str,
        request: Request,
    ) -> str:
        """
        Create insight for a given set of recent topics.

        Arguments:
        recent_topics – the recent topics object to be analyzed.
        user_id – the user id associated with the topics insights operation.
        patient_id – the patient id associated with the topics insights operation.
        language_code – the language code to be used in the response.
        patient_name – the name by which the patient should be addressed.
        patient_gender – the patient gender.
        request – the upstream request object.
        """
        try:
            recent_topics_json_str = str(recent_topics.model_dump_json())
            query_input = (
                "Please help me analyze the following set of topics that have recently come up during "
                f"my sessions with {patient_name}, my patient:\n{recent_topics_json_str}"
            )
            logging.info(f"[generate_recent_topics_insights] Recent topics JSON length: {len(recent_topics_json_str)}")

            session_dates_override = await self._retrieve_n_most_recent_session_dates(
                request=request,
                therapist_id=user_id,
                patient_id=patient_id,
                n=TOPICS_CONTEXT_SESSIONS_CAP
            )
            logging.info(f"[generate_recent_topics_insights] Session dates override: {session_dates_override}")

            openai_client = dependency_container.inject_openai_client()
            context = await dependency_container.inject_pinecone_client().get_vector_store_context(
                query_input=query_input,
                user_id=user_id,
                patient_id=patient_id,
                openai_client=openai_client,
                aws_db_client=dependency_container.inject_aws_db_client(),
                request=request,
                query_top_k=0,
                rerank_vectors=False,
                include_preexisting_history=False,
                session_dates_overrides=session_dates_override
            )
            logging.info(f"[generate_recent_topics_insights] Context length: {len(context)}")

            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(
                scenario=PromptScenario.TOPICS_INSIGHTS,
                context=context,
                language_code=language_code,
                patient_gender=patient_gender,
                patient_name=patient_name,
                query_input=query_input
            )
            system_prompt = prompt_crafter.get_system_message_for_scenario(
                scenario=PromptScenario.TOPICS_INSIGHTS,
                language_code=language_code
            )
            logging.info(f"[generate_recent_topics_insights] User prompt length: {len(user_prompt)}")
            logging.info(f"[generate_recent_topics_insights] System prompt length: {len(system_prompt)}")

            max_tokens = await self.calculate_max_tokens(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            logging.info(f"[generate_recent_topics_insights] Calculated max_tokens: {max_tokens}")

            return await openai_client.trigger_async_chat_completion(
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as e:
            logging.error(f"[generate_recent_topics_insights] Error occurred: {str(e)}")
            raise RuntimeError(e) from e

    async def generate_attendance_insights(self,
                                           therapist_id: str,
                                           patient_id: str,
                                           language_code: str,
                                           patient_name: str,
                                           patient_gender: str,
                                           request: Request,) -> str:
        try:
            patient_session_dates = [
                date_override.session_date_start for date_override in (await self._retrieve_n_most_recent_session_dates(
                    request=request,
                    therapist_id=therapist_id,
                    patient_id=patient_id,
                    n=ATTENDANCE_CONTEXT_SESSIONS_CAP
                ))
            ]
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(
                scenario=PromptScenario.ATTENDANCE_INSIGHTS,
                patient_session_dates=patient_session_dates,
                patient_name=patient_name,
                patient_gender=patient_gender
            )
            system_prompt = prompt_crafter.get_system_message_for_scenario(
                scenario=PromptScenario.ATTENDANCE_INSIGHTS,
                language_code=language_code
            )
            max_tokens = await self.calculate_max_tokens(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            return await dependency_container.inject_openai_client().trigger_async_chat_completion(
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as e:
            raise RuntimeError(e) from e

    async def create_soap_report(
        self,
        text: str
    ) -> str:
        """
        Creates and returns a SOAP report with the incoming data.

        Arguments:
        text – the text to be adapted to a SOAP format.
        """
        try:
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(
                scenario=PromptScenario.SOAP_TEMPLATE,
                session_notes=text
            )
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.SOAP_TEMPLATE)
            max_tokens = await self.calculate_max_tokens(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            return await dependency_container.inject_openai_client().trigger_async_chat_completion(
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as e:
            raise RuntimeError(e) from e

    async def summarize_chunk(
        self,
        chunk_text: str,
        openai_client: OpenAIBaseClass
    ) -> str:
        """
        Summarizes a chunk for faster fetching.

        Arguments:
        chunk_text – the text associated with the incoming chunk.
        openai_client – the openai client to be leveraged internally.
        """
        try:
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(
                PromptScenario.CHUNK_SUMMARY,
                chunk_text=chunk_text
            )
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.CHUNK_SUMMARY)
            max_tokens = await self.calculate_max_tokens(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            return await openai_client.trigger_async_chat_completion(
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as e:
            raise RuntimeError(e) from e

    async def create_session_mini_summary(
        self,
        session_notes: str,
        language_code: str,
    ) -> str:
        """
        Creates a 'mini' summary of the incoming session notes.

        Arguments:
        session_notes – the text associated with the session notes.
        language_code – the language_code to be used for generating the response.
        """
        try:
            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(
                scenario=PromptScenario.SESSION_MINI_SUMMARY,
                session_notes=session_notes
            )
            system_prompt = prompt_crafter.get_system_message_for_scenario(
                scenario=PromptScenario.SESSION_MINI_SUMMARY,
                language_code=language_code
            )
            max_tokens = await self.calculate_max_tokens(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            return await dependency_container.inject_openai_client().trigger_async_chat_completion(
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as e:
            raise RuntimeError(e) from e

    # Private

    async def calculate_max_tokens(
        self,
        system_prompt: str,
        user_prompt: str) -> int:
        openai_client = dependency_container.inject_openai_client()
        prompt_tokens = len(tiktoken.get_encoding("o200k_base").encode(f"{system_prompt}\n{user_prompt}"))

        # Calculate how much space is left in the context window
        available_context = openai_client.GPT_4O_MINI_CONTEXT_WINDOW - prompt_tokens

        # Don't exceed OpenAI's max output limit
        max_tokens = min(available_context, openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS)
        return max_tokens

    async def _fetch_context_based_on_query_input(
        self,
        query_input: str,
        user_id: str,
        patient_id: str,
        openai_client: OpenAIBaseClass,
        request: Request,
        extracted_time_tokens: str | BaseModel,
        last_session_date_override: PineconeQuerySessionDateOverride = None
    ):
        start_date = None
        end_date = None
        if isinstance(extracted_time_tokens, BaseModel):
            extracted_time_tokens_json = json.loads(extracted_time_tokens.model_dump_json())
            if extracted_time_tokens_json.get("start_date") and extracted_time_tokens_json.get("end_date"):
                # If the time tokens were extracted, we should bound the query to the specified time range.
                start_date = extracted_time_tokens.start_date
                end_date = extracted_time_tokens.end_date

        if start_date is not None and end_date is not None:
            # Fetch the vector store context based on the extracted time range.
            return await dependency_container.inject_pinecone_client().get_vector_store_context(
                query_input=query_input,
                user_id=user_id,
                patient_id=patient_id,
                openai_client=openai_client,
                aws_db_client=dependency_container.inject_aws_db_client(),
                request=request,
                query_top_k=0,
                rerank_vectors=False,
                session_dates_overrides=[
                    PineconeQuerySessionDateOverride(
                        override_type=PineconeQuerySessionDateOverrideType.DATE_RANGE,
                        session_date_start=start_date,
                        session_date_end=end_date,
                    )
                ]
            )

        # Fetch the vector store context based on similarity search.
        return await dependency_container.inject_pinecone_client().get_vector_store_context(
            query_input=query_input,
            user_id=user_id,
            patient_id=patient_id,
            openai_client=openai_client,
            aws_db_client=dependency_container.inject_aws_db_client(),
            request=request,
            query_top_k=6,
            rerank_vectors=True,
            session_dates_overrides=[last_session_date_override]
        )

    async def _retrieve_n_most_recent_session_dates(
        self,
        request: Request,
        therapist_id: str,
        patient_id: str,
        n: int
    ) -> list[PineconeQuerySessionDateOverride]:
        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            dates_response_data = await aws_db_client.select(
                user_id=therapist_id,
                request=request,
                fields=["session_date"],
                filters={
                    "patient_id": patient_id,
                },
                table_name=ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
                limit=n,
                order_by=("session_date", "desc")
            )

            overrides = []
            for date in dates_response_data:
                date_obj = date['session_date']
                overrides.append(
                    PineconeQuerySessionDateOverride(
                        override_type=PineconeQuerySessionDateOverrideType.SINGLE_DATE,
                        session_date_start=date_obj.strftime(datetime_handler.DATE_FORMAT)
                    )
                )
            return overrides
        except Exception as e:
            raise RuntimeError(e) from e
