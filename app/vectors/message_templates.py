from enum import Enum

from ..internal.utilities.general_utilities import gender_has_default_pronouns
from ..internal.utilities.datetime_handler import convert_to_date_format_spell_out_month, DATE_FORMAT

class PromptScenario(Enum):
    # keep sorted A-Z
    ATTENDANCE_INSIGHTS = "attendance_insights"
    CHUNK_SUMMARY = "chunk_summary"
    DIARIZATION_SUMMARY = "diarization_summary"
    DIARIZATION_CHUNKS_GRAND_SUMMARY = "diarization_chunks_grand_summary"
    PRESESSION_BRIEFING = "presession_briefing"
    QUERY = "query"
    QUESTION_SUGGESTIONS = "question_suggestions"
    REFORMULATE_QUERY = "reformulate_query"
    SESSION_MINI_SUMMARY = "session_mini_summary"
    SOAP_TEMPLATE = "soap_template"
    TOPICS = "recent_topics"
    TOPICS_INSIGHTS = "recent_topics_insights"
    UNDEFINED = "undefined"

class PromptCrafter:

    def get_user_message_for_scenario(self, scenario: PromptScenario, **kwargs):
        if scenario == PromptScenario.UNDEFINED:
            raise Exception("Received undefined prompt scenario for retrieving the user message")

        if scenario == PromptScenario.QUERY:
            context = None if 'context' not in kwargs else kwargs['context']
            language_code = None if 'language_code' not in kwargs else kwargs['language_code']
            query_input = None if 'query_input' not in kwargs else kwargs['query_input']
            return self._create_qa_user_message(context=context,
                                                language_code=language_code,
                                                query_input=query_input)
        elif scenario == PromptScenario.PRESESSION_BRIEFING:
            language_code = None if 'language_code' not in kwargs else kwargs['language_code']
            patient_name = None if 'patient_name' not in kwargs else kwargs['patient_name']
            context = None if 'context' not in kwargs else kwargs['context']
            query_input = None if 'query_input' not in kwargs else kwargs['query_input']
            return self._create_briefing_user_message(language_code=language_code,
                                                      patient_name=patient_name,
                                                      query_input=query_input,
                                                      context=context)
        elif scenario == PromptScenario.QUESTION_SUGGESTIONS:
            language_code = None if 'language_code' not in kwargs else kwargs['language_code']
            context = None if 'context' not in kwargs else kwargs['context']
            patient_name = None if 'patient_name' not in kwargs else kwargs['patient_name']
            patient_gender = None if 'patient_gender' not in kwargs else kwargs['patient_gender']
            query_input = None if 'query_input' not in kwargs else kwargs['query_input']
            return self._create_question_suggestions_user_message(language_code=language_code,
                                                                  context=context,
                                                                  patient_name=patient_name,
                                                                  patient_gender=patient_gender,
                                                                  query_input=query_input)
        elif scenario == PromptScenario.TOPICS:
            language_code = None if 'language_code' not in kwargs else kwargs['language_code']
            context = None if 'context' not in kwargs else kwargs['context']
            patient_name = None if 'patient_name' not in kwargs else kwargs['patient_name']
            patient_gender = None if 'patient_gender' not in kwargs else kwargs['patient_gender']
            query_input = None if 'query_input' not in kwargs else kwargs['query_input']
            return self._create_recent_topics_user_message(language_code=language_code,
                                                           context=context,
                                                           patient_name=patient_name,
                                                           patient_gender=patient_gender,
                                                           query_input=query_input)
        elif scenario == PromptScenario.CHUNK_SUMMARY:
            chunk_text = None if 'chunk_text' not in kwargs else kwargs['chunk_text']
            return self._create_chunk_summary_user_message(chunk_text=chunk_text)
        elif scenario == PromptScenario.SOAP_TEMPLATE:
            session_notes = None if 'session_notes' not in kwargs else kwargs['session_notes']
            return self._create_soap_template_user_message(session_notes=session_notes)
        elif scenario == PromptScenario.SESSION_MINI_SUMMARY:
            session_notes = None if 'session_notes' not in kwargs else kwargs['session_notes']
            return self._create_session_mini_summary_user_message(session_notes=session_notes)
        elif scenario == PromptScenario.REFORMULATE_QUERY:
            query_input = None if 'query_input' not in kwargs else kwargs['query_input']
            chat_history = None if 'chat_history' not in kwargs else kwargs['chat_history']
            return self._create_reformulate_query_user_message(chat_history=chat_history,
                                                               query_input=query_input)
        elif scenario == PromptScenario.TOPICS_INSIGHTS:
            context = None if 'context' not in kwargs else kwargs['context']
            language_code = None if 'language_code' not in kwargs else kwargs['language_code']
            patient_gender = None if 'patient_gender' not in kwargs else kwargs['patient_gender']
            patient_name = None if 'patient_name' not in kwargs else kwargs['patient_name']
            query_input = None if 'query_input' not in kwargs else kwargs['query_input']
            return self._create_topics_insights_user_message(context=context,
                                                             language_code=language_code,
                                                             patient_gender=patient_gender,
                                                             patient_name=patient_name,
                                                             query_input=query_input)
        elif scenario == PromptScenario.ATTENDANCE_INSIGHTS:
            patient_session_dates = [] if 'patient_session_dates' not in kwargs else kwargs['patient_session_dates']
            patient_name = [] if 'patient_name' not in kwargs else kwargs['patient_name']
            patient_gender = [] if 'patient_gender' not in kwargs else kwargs['patient_gender']
            return self._create_attendance_insights_user_message(patient_session_dates=patient_session_dates,
                                                                 patient_gender=patient_gender,
                                                                 patient_name=patient_name)
        elif scenario == PromptScenario.DIARIZATION_SUMMARY:
            diarization = None if 'diarization' not in kwargs else kwargs['diarization']
            return self._summarize_diarization_user_message(diarization=diarization)
        elif scenario == PromptScenario.DIARIZATION_CHUNKS_GRAND_SUMMARY:
            diarization = None if 'diarization' not in kwargs else kwargs['diarization']
            return self._summarize_diarization_chunks_user_message(diarization=diarization)
        else:
            raise Exception("Received untracked prompt scenario for retrieving the user message")

    def get_system_message_for_scenario(self, scenario: PromptScenario, **kwargs):
        if scenario == PromptScenario.UNDEFINED:
            raise Exception("Received undefined prompt scenario for retrieving the user message")

        if scenario == PromptScenario.QUERY:
            last_session_date = None if 'last_session_date' not in kwargs else kwargs['last_session_date']
            patient_name = None if 'patient_name' not in kwargs else kwargs['patient_name']
            patient_gender = None if 'patient_gender' not in kwargs else kwargs['patient_gender']
            chat_history_included = False if 'chat_history_included' not in kwargs else kwargs['chat_history_included']
            return self._create_qa_system_message(last_session_date=last_session_date,
                                                  patient_name=patient_name,
                                                  patient_gender=patient_gender,
                                                  chat_history_included=chat_history_included)
        elif scenario == PromptScenario.PRESESSION_BRIEFING:
            language_code = None if 'language_code' not in kwargs else kwargs['language_code']
            patient_name = None if 'patient_name' not in kwargs else kwargs['patient_name']
            patient_gender = None if 'patient_gender' not in kwargs else kwargs['patient_gender']
            therapist_name = None if 'therapist_name' not in kwargs else kwargs['therapist_name']
            therapist_gender = None if 'therapist_gender' not in kwargs else kwargs['therapist_gender']
            session_count = None if 'session_count' not in kwargs else kwargs['session_count']
            return self._create_briefing_system_message(language_code=language_code,
                                                        therapist_name=therapist_name,
                                                        therapist_gender=therapist_gender,
                                                        patient_name=patient_name,
                                                        patient_gender=patient_gender,
                                                        session_count=session_count)
        elif scenario == PromptScenario.QUESTION_SUGGESTIONS:
            language_code = None if 'language_code' not in kwargs else kwargs['language_code']
            return self._create_question_suggestions_system_message(language_code=language_code)
        elif scenario == PromptScenario.TOPICS:
            language_code = None if 'language_code' not in kwargs else kwargs['language_code']
            return self._create_recent_topics_system_message(language_code=language_code)
        elif scenario == PromptScenario.CHUNK_SUMMARY:
            return self._create_chunk_summary_system_message()
        elif scenario == PromptScenario.SOAP_TEMPLATE:
            return self._create_soap_template_system_message()
        elif scenario == PromptScenario.SESSION_MINI_SUMMARY:
            language_code = None if 'language_code' not in kwargs else kwargs['language_code']
            return self._create_session_mini_summary_system_message(language_code=language_code)
        elif scenario == PromptScenario.REFORMULATE_QUERY:
            return self._create_reformulate_query_system_message()
        elif scenario == PromptScenario.TOPICS_INSIGHTS:
            language_code = None if 'language_code' not in kwargs else kwargs['language_code']
            return self._create_topics_insights_system_message(language_code=language_code)
        elif scenario == PromptScenario.ATTENDANCE_INSIGHTS:
            language_code = None if 'language_code' not in kwargs else kwargs['language_code']
            return self._create_attendance_insights_system_message(language_code=language_code)
        elif scenario == PromptScenario.DIARIZATION_SUMMARY:
            language_code = None if 'language_code' not in kwargs else kwargs['language_code']
            return self._summarize_diarization_system_message(language_code=language_code)
        elif scenario == PromptScenario.DIARIZATION_CHUNKS_GRAND_SUMMARY:
            language_code = None if 'language_code' not in kwargs else kwargs['language_code']
            return self._summarize_diarization_chunks_system_message(language_code=language_code)
        else:
            raise Exception("Received untracked prompt scenario for retrieving the system message")

    # Text QA Prompt

    def _create_qa_system_message(self,
                                  patient_name: str,
                                  patient_gender: str,
                                  chat_history_included: bool,
                                  last_session_date: str = None) -> str:
        assert len(patient_name or '') > 0, "Missing patient_name param for building system message"

        if patient_gender is not None and gender_has_default_pronouns(patient_gender):
            patient_gender_context = f", who is a {patient_gender}"
        else:
            patient_gender_context = ""

        if len(last_session_date or '') == 0:
            last_session_date_context = ""
        else:
            date_spell_out_month = convert_to_date_format_spell_out_month(session_date=last_session_date,
                                                                          incoming_date_format=DATE_FORMAT)
            last_session_date_context = f"\nNote that {patient_name}'s last session with the practitioner was on {date_spell_out_month}."

        if chat_history_included:
            chat_history_instruction = (
                "10. For coherence, consider the provided chat history to understand what the conversation has been so far. "
                "The `chunk_summary` fields still take precedence when you're looking for information with which to answer the user question.\n"
            )
        else:
            chat_history_instruction = ""

        return (
            f"A mental health practitioner is using our Practice Management Platform to inquire about a patient named {patient_name}{patient_gender_context}. "
            "The practitioner's session notes provide the available information. "
            "Your task is to answer the practitioner's questions based on these notes. "
            "Keep in mind that you should never attempt to diagnose the patient yourself. "
            "The practitioner relies on your support for organization and information retrieval, not for making clinical decisions. "
            "If the practitioner asks about the patient's session history, focus on providing objective data analysis rather than offering diagnostic recommendations."
            "\n\nInstructions:\n"
            "1. Evaluate the provided context documents.\n"
            "2. First, examine the `chunk_summary` to determine if the document is relevant to the question.\n"
            "3. If relevant, use the `chunk_summary` to formulate your response.\n"
            f"4. If there exists a `pre_existing_history_summary`, and **only** if it is relevant to the question, use it to build on your response. "
            "In that case, also mention the fact that you referenced the patient's pre-existing history. "
            "Otherwise, if the pre-existing history is not related to the question, ignore it.\n"
            f"5. When referencing a `chunk_summary`, always mention the session date associated with the information context. Use format '%b %d, %Y' (i.e: Oct 12, 2023).\n"
            "6. If no relevant session information is found, do not mention any dates.\n"
            "7. If the question is about future sessions or planning, and no relevant session notes exist, freely provide guidance to assist the practitioner.\n"
            "8. For questions directly related to the patient's session history, if the question cannot be answered based on the `chunk_summary` values, state that the information is not available in the session notes.\n"
            "9. For casual or non-informative inputs from the user (e.g.: 'Got it', 'Ok'), offer a simple acknowledgment or a brief, polite response that does not reference session context unless directly relevant.\n"
            f"{chat_history_instruction}"
            f"{last_session_date_context}"
        )

    def _create_qa_user_message(self,
                                context: str,
                                language_code: str,
                                query_input: str) -> str:
        try:
            assert len(context or '') > 0, "Missing context param for building user message"
            assert len(language_code or '') > 0, "Missing language_code param for building user message"
            assert len(query_input or '') > 0, "Missing query_input param for building user message"

            return (
                f"We have provided context information below.\n---------------------\n{context}\n---------------------\n"
                f"\nIt is very important that you craft your response using language code {language_code}.\n"
                f"\nGiven this information, please respond the user's input: {query_input}\n"
            )
        except Exception as e:
            raise RuntimeError(e) from e

    # Briefing Prompt

    def _create_briefing_system_message(self,
                                        language_code: str,
                                        therapist_name: str,
                                        therapist_gender: str,
                                        patient_name: str,
                                        patient_gender: str,
                                        session_count: int) -> str | None:
        try:
            assert len(language_code or '') > 0, "Missing language_code param for building system message"
            assert len(therapist_name or '') > 0, "Missing therapist_name param for building system message"
            assert len(patient_name or '') > 0, "Missing patient_name param for building system message"
            assert session_count >= 0, "Something went wrong when building system message"

            therapist_gender = ("" if (therapist_gender is None or not gender_has_default_pronouns(therapist_gender))
                                else f" ({therapist_gender})")
            patient_gender = ("" if (patient_gender is None or not gender_has_default_pronouns(patient_gender))
                              else f" ({patient_gender})")

            return (
                    f"A mental health practitioner, {therapist_name}{therapist_gender}, is about to meet with {patient_name}{patient_gender}, an existing patient. "
                    f"{therapist_name} is using our Practice Management Platform to quickly refreshen on {patient_name}'s session history. "
                    f"{therapist_name} has had {session_count} sessions with {patient_name} so far. "
                    f"The first thing you should do is say hi to {therapist_name}, and remind them that they have had {session_count} with {patient_name} **since the patient was onboarded onto our platform** (this distinction is very important). "
                    f"\n\nOnce you've said hi to {therapist_name}, your job is to provide a summary of {patient_name}'s session history in two sections: **Most Recent Sessions** and **Historical Themes**. "
                    "You should never attempt to diagnose the patient yourself. "
                    "The practitioner relies on your support for organization and information retrieval, not for making clinical decisions. Focus on providing objective data analysis rather than offering diagnostic recommendations.\n\n"
                    "• **Most Recent Sessions**: Base the summary strictly on the `chunk_summary` values you see as context. If you don't see any `chunk_summary` values, omit this section entirely without making up any details beyond what is explicitly available.\n"
                    "• **Historical Themes**: Use the `pre_existing_history_summary` as well as the `chunk_summary` values to determine a set of relevant, historical themes for the patient. "
                    "Use only information from the `pre_existing_history_summary` and `chunk_summary` values. Do not add nor make up any additional information. "
                    "If no `pre_existing_history_summary` value is available, attempt to identify historical themes from the available `chunk_summary` values. "
                    "However, if neither `pre_existing_history_summary` nor relevant `chunk_summary` values are available, omit this section entirely without adding or filling in any details beyond what's explicitly provided.\n\n"
                    "There are two specific scenarios to consider:\n\n"
                    f"1. **If both sections are omitted** due to lack of data, shift the focus to providing generic recommendations on how to approach the upcoming session with {patient_name}. "
                    "Offer strategies for guiding the conversation or establishing continuity from their previous meeting.\n\n"
                    f"2. **If this is {therapist_name}'s first time meeting with {patient_name}**, omit both sections, and instead suggest strategies on how to establish a solid foundation for their relationship.\n\n"
                    f"For **'Most Recent Sessions'** list the most recent sessions sorted by the most recent first. Ensure date precision. "
                    f"If {therapist_name} has previously met with {patient_name}, conclude with **'Suggestions for Next Session'**, offering discussion topics for their session that's about to start. "
                    "All sections should have at most 4 bullet points. "
                    f"It is very important that the summary is written using language code {language_code}. "
                    "As a reference point, aim for a total length of 1,600–2,000 characters. However, it's preferable to exceed this range rather than omit available information from a section. "
                    f"Ensure the headers for Most Recent Sessions, Historical Themes, and Suggestions for Next Session are bolded using appropriate mark-up, and that they also are written using language code {language_code}."
            )
        except Exception as e:
            raise RuntimeError(e) from e

    def _create_briefing_user_message(self,
                                      patient_name: str,
                                      query_input: str,
                                      language_code: str,
                                      context: str) -> str:
        try:
            assert len(patient_name or '') > 0, "Missing patient_name param for building user message"
            assert len(language_code or '') > 0, "Missing language_code param for building user message"

            return (
                f"We have provided context information below.\n---------------------\n{context}\n---------------------\n"
                f"\nIt is very important that your output is written using language code {language_code}. "
                f"Given this information, please answer the practitioner's question:\n{query_input}"
            )
        except Exception as e:
            raise RuntimeError(e) from e

    # Question Suggestions

    def _create_question_suggestions_system_message(self,
                                                    language_code: str) -> str:
        try:
            assert len(language_code or '') > 0, "Missing language_code param for building system message"

            return (
                "A mental health practitioner is viewing a patient's dashboard on our Practice Management Platform. "
                "They can ask you about the patient's session history. "
                "Your task is to generate two specific, objective questions that the practitioner might ask, based only on the factual information in the `chunk_summary` and `pre_existing_history_summary` values. "
                "The questions should be psychology-focused while ensuring that they don't add interpretations, assumptions, or diagnostic suggestions to what's exclusively available in the information context. "
                "The questions should also be under 60 characters in length. "
                "For example, a psychology-focused question would be 'What has the patient shared about his early childhood?' instead of 'When did the patient learn how to play the guitar?'\n\n"
                "Return a JSON object with a key titled `questions`, written in English, and an array of questions as its value. "
                f"Ensure that the questions are written in language code {language_code}. "
                "This is what the format should look like: {\"questions\": [..., ...]}\n"
                "Example output:\n"
                r"{'questions': ['When did we last talk about the divorce?', 'What was the last thing we discussed in session?']}"
            )
        except Exception as e:
            raise RuntimeError(e) from e

    def _create_question_suggestions_user_message(self,
                                                  language_code: str,
                                                  context: str,
                                                  patient_name: str,
                                                  query_input: str,
                                                  patient_gender: str) -> str:
        try:
            assert len(language_code or '') > 0, "Missing language_code param for building user message"
            assert len(context or '') > 0, "Missing context param for building user message"
            assert len(patient_name or '') > 0, "Missing patient_name param for building user message"
            assert len(query_input or '') > 0, "Missing query_input param for building user message"

            if patient_gender is not None and gender_has_default_pronouns(patient_gender):
                patient_info = f"\nFor reference, the patient is a {patient_gender}, and their name is {patient_name}."
            else:
                patient_info = f"\nFor reference, the patient's name is {patient_name}."
            return (
                f"We have provided context information below.\n---------------------\n{context}\n---------------------\n"
                f"\n{patient_info} "
                f"It is very important that each question is written using language code {language_code}, and that it remains under 60 characters of length. "
                f"Given this information, please answer the practitioner's question:\n{query_input}"
            )
        except Exception as e:
            raise RuntimeError(e) from e

    # Recent Topics

    def _create_recent_topics_system_message(self, language_code: str) -> str:
        try:
            assert len(language_code or '') > 0, "Missing language_code param for building system message"

            return (
                "A mental health practitioner is viewing a patient’s dashboard on our Practice Management Platform. "
                "They need to know what topics the patient has been discussing the most during the most recent sessions. "
                "Provide the following:\n\n"
                "1. A set of recent topics, each with its density percentage. There should not be more than 3 topics.\n"
                "2. Ensure the topics' percentages total up to exactly 100%. Double-check this, you should not return a set of percentages that do not add up to 100. \n"
                "3. Each topic's length should be under 25 characters.\n\n"
                "The topics must be extracted directly from the content in the session notes, exactly as they are presented, without any form of interpretation, rephrasing, or additional analysis. "
                "Do not infer or generate new topics beyond what is explicitly mentioned in the notes."
                "Return a JSON object with one key: `topics`, written in English. The value should be an array of up to three objects, each with:\n"
                f"* `topic`: Distinct topic written using language code {language_code}.\n"
                f"* `percentage`: Frequency percentage.\n\n"
                "If there are no `chunk_summary` values available, the array should be empty. "
                "Otherwise if there's at least one `chunk_summary`, the array should contain at least one topic, but up to three if possible. "
                "\n\nExample response where the patient spoke half of the time about a given topic, and the remaining time was split between two other topics:\n"
                r"{'topics':[{'topic': 'Graduating from school', 'percentage': '50%'},{'topic': 'Substance abuse', 'percentage': '25%'},{'topic': 'Adopting a pet', 'percentage': '25%'}]}"
            )
        except Exception as e:
            raise RuntimeError(e) from e

    def _create_recent_topics_user_message(self,
                                           language_code: str,
                                           context: str,
                                           patient_name: str,
                                           query_input: str,
                                           patient_gender: str) -> str:
        try:
            assert len(language_code or '') > 0, "Missing language_code param for building user message"
            assert len(context or '') > 0, "Missing context param for building user message"
            assert len(patient_name or '') > 0, "Missing patient_name param for building user message"
            assert len(query_input or '') > 0, "Missing query_input param for building user message"

            if patient_gender is not None and gender_has_default_pronouns(patient_gender):
                patient_info = f"\nFor reference, the patient is a {patient_gender}, and their name is {patient_name}. "
            else:
                patient_info = f"\nFor reference, the patient's name is {patient_name}. "
            return (
                f"We have provided context information below.\n---------------------\n{context}\n---------------------\n"
                f"{patient_info} "
                f"It is very important that each topic is written using language code {language_code}, and that it remain under 25 characters of length. "
                f"Given this information, please answer the practitioner's question:\n{query_input}"
            )
        except Exception as e:
            raise RuntimeError(e) from e

    # Session Entry Summary Prompt

    def _create_chunk_summary_system_message(self) -> str:
         return (
            "A mental health practitioner is uploading session notes to our platform. "
            "We use a Retrieval Augmented Generation system that involves chunking these notes. "
            "Each chunk will be converted into embeddings and stored in a vector database. "
            "Your task is to create a brief, informative summary of the chunk that will be provided. "
            "This summary must be directly based on the content in the chunk, without any interpretation, rephrasing, or additional analysis. "
            "It should only encapsulate the key information from the chunk for quick retrieval during searches. "
            "Ensure the summary accurately reflects the content and context of the chunk, exactly as presented in the original notes. "
            "Regardless of the original language, generate the summary in English."
        )

    def _create_chunk_summary_user_message(self,
                                           chunk_text: str) -> str:
        try:
            assert len(chunk_text or '') > 0, "Missing chunk_text param for building user message"
            return (f"Summarize the following chunk:\n\n{chunk_text}")
        except Exception as e:
            raise RuntimeError(e) from e

    # SOAP Template Prompt

    def _create_soap_template_system_message(self) -> str:
        return (
            "A mental health practitioner has uploaded session notes to our platform. "
            "Your task is to convert these notes into the SOAP format, which consists of the following sections:\n\n"
            "Subjective: What brought the patient to the practitioner, including their history and reasons for the visit.\n"
            "Objective: Factual information collected during the session.\n"
            "Assessment: The practitioner's professional analysis based on subjective and objective data."
            "Plan: The recommended actions or next steps from the practitioner or patient."
            "Organize the session notes under these headings. Paraphrase content if it enhances clarity or readability. "
            "If any section lacks sufficient detail, leave it blank, but ensure no original information is omitted. "
            "For any content that doesn’t fit within the SOAP structure, include it at the end, after the SOAP sections.\n\n"
            "Return the SOAP-formatted notes as a string with double line breaks between sections and single line breaks between each header and its content. "
            "Write the section headers in English, bolded with appropriate mark-up, while keeping the content in the same language as the original notes."
        )

    def _create_soap_template_user_message(self, session_notes: str) -> str:
        try:
            assert len(session_notes or '') > 0, "Missing session_notes param for building user message"
            return f"Adapt the following session notes into the SOAP format:\n\n{session_notes}."
        except Exception as e:
            raise RuntimeError(e) from e

    def _create_session_mini_summary_system_message(self, language_code: str):
        try:
            assert len(language_code or '') > 0, "Missing language_code param for building system message"
            return (
                "After a session with a patient, a mental health practitioner uploads their notes to our platform. "
                "Each session entry in the Sessions table includes a 'mini summary' of no more than 50 characters. "
                "Your task is to create this mini summary. "
                "It should be directly extracted from the content in the session notes, without any interpretation, rephrasing, or additional analysis. "
                "Ensure the summary conveys the core content of the session notes as clearly as possible. "
                "If the content provided does not contain any meaningful information to summarize, simply return the raw session notes unchanged. "
                f"It is very important that your output is generated using language code {language_code}. "
            )
        except Exception as e:
            raise RuntimeError(e) from e

    def _create_session_mini_summary_user_message(self, session_notes: str):
        try:
            assert len(session_notes or '') > 0, "Missing session_notes param for building user message"
            return (f"Summarize the following session notes:\n\n{session_notes}")
        except Exception as e:
            raise RuntimeError(e) from e

    # Reformulate query

    def _create_reformulate_query_system_message(self):
        return (
            "Given the chat history and the latest user input, which may reference previous context, reformulate the input into a standalone entry "
            "that can be understood without relying on the chat history. If the input is a question, do NOT provide an answer; only reformulate it if necessary, otherwise return it unchanged. "
            "For casual or non-informative inputs from the user (e.g.: 'Got it', 'Ok'), it's ok to return them unchanged. "
            "The output should be generated using the same language in which the user question is written."
        )

    def _create_reformulate_query_user_message(self, chat_history: str, query_input: str):
        try:
            assert len(chat_history or '') > 0, "Error while building user message: chat_history should be bigger than 0"
            assert len(query_input or '') > 0, "Error while building user message: query_input should be bigger than 0"

            return (
                "Please review the following chat history and the most recent user input. "
                "The user input might reference information from the chat history. "
                "Your task is to reformulate the user input into a standalone entry that can be understood without the chat history. "
                "If the input is a question, do NOT provide an answer; simply reformulate it if necessary, otherwise return it as is."
                "For casual or non-informative inputs from the user (e.g.: 'Got it', 'Ok'), it's ok to return them unchanged. "
                "The output should be generated using the same language in which the latest user question is written."
                f"\n---------------------\nChat History:\n{chat_history}\n---------------------\n"
                f"Latest User Input:\n{query_input}\n---------------------\n"
            )
        except Exception as e:
            raise RuntimeError(e) from e

    # Topics Insights

    def _create_topics_insights_system_message(self, language_code: str):
        assert len(language_code or '') > 0, "Missing language_code param for building system message"
        return (
            "You are a mental health assistant helping practitioners analyze their patients' session data. "
            "You will receive an array of topics, each with a corresponding frequency percentage, indicating how often the patient has spoken about these topics in their most recent sessions. "
            "Your task is to briefly analyze this information, strictly based on the provided data, and generate a concise paragraph that highlights any patterns, recurring themes, or notable insights. "
            "Ensure that the analysis is objective, avoiding interpretation or assumptions that are not explicitly supported by the data. "
            "Focus on rationalizing the data in a way that could assist the practitioner in understanding the patient's current focus or emotional state.\n"
            "\nIt is very important that the output meets the following criteria:\n"
            "1. Format the output as a single paragraph.\n"
            "2. Limit the output to 270 characters.\n"
            "3. Do not mention again each topic's frequency percentage (this is already highlighted to the user).\n"
            f"4. Ensure the output is generated using language code {language_code}.\n"
        )

    def _create_topics_insights_user_message(self,
                                             context: str,
                                             language_code: str,
                                             patient_gender: str,
                                             patient_name: str,
                                             query_input: str):
        try:
            assert len(patient_name or '') > 0, "Missing patient_name param for building user message"
            assert len(language_code or '') > 0, "Missing language_code param for building user message"

            gender_context = (". " if (patient_gender is None or not gender_has_default_pronouns(patient_gender))
                              else f" ({patient_gender}). ")

            return (
                f"We have provided context information below.\n---------------------\n{context}\n---------------------\n"
                f"\nIt is very important that your output is written using language code {language_code}. "
                f"Note that the patient name is {patient_name}{gender_context}"
                f"Given this information, please answer the practitioner's question:\n{query_input}"
            )
        except Exception as e:
            raise RuntimeError(e) from e

    # Attendance Insights

    def _create_attendance_insights_user_message(self,
                                                 patient_gender: str,
                                                 patient_name: str,
                                                 patient_session_dates: list[str]):
        try:
            assert len(patient_name or '') > 0, "Missing patient_name param for building user message"
            assert len(patient_session_dates or '') >= 0, "Missing patient_session_dates param for building user message"

            gender_context = (". " if (patient_gender is None or not gender_has_default_pronouns(patient_gender))
                              else f" ({patient_gender}). ")
            return ("Given the following dates of sessions that a patient has had with their therapist, provide an analysis of the patient's attendance pattern. "
                    "Highlight any trends, consistency, or notable gaps in the sessions. "
                    "Offer insights that might help understand the patient's commitment to therapy or any potential issues with regular attendance. "
                    "If the set of dates is empty, return only a 50-character sentence stating that the patient is yet to start attending sessions. "
                    f"Note that the patient name is {patient_name}{gender_context}"
                    "\n\n"
                    f"Here is the set of dates: {patient_session_dates}")
        except Exception as e:
            raise RuntimeError(e) from e

    def _create_attendance_insights_system_message(self,
                                                   language_code: str):
        try:
            assert len(language_code or '') > 0, "Missing language_code param for building system message"
            return ("You are a mental health assistant helping practitioners analyze their patients' attendance patterns. "
                    "You receive an array of dates (with format YYYY-MM-DD) representing the last N sessions a patient has had with their therapist. "
                    "Your task is to generate a brief, insightful paragraph that highlights trends or irregularities in the patient's attendance. "
                    "Consider factors such as consistency, gaps between sessions, and any changes in frequency over time. "
                    "Provide analytics that could help the therapist understand the patient's commitment, punctuality, or potential barriers to consistent attendance. "
                    "\n\nIt is very important that the output meets the following criteria:\n"
                    "1. Format the output as a single paragraph.\n"
                    "2. Limit the output to 290 characters.\n"
                    f"3. Ensure the output is generated using language code {language_code}.\n")
        except Exception as e:
            raise RuntimeError(e) from e

    # Summarize Diarization

    def _summarize_diarization_system_message(self, language_code: str) -> str:
        try:
            assert len(language_code or '') > 0, "Missing language_code param for building system message"
            return (
                "A mental health practitioner just met with a patient, and needs to summarize the content of the session. "
                f"We have a transcription of the full session in JSON format, and your task is to provide the summary using language code {language_code}. "
                "The summary must be based strictly on the content in the transcription and should not include any interpretation, rephrasing, or inferred insights beyond what is explicitly stated. "
                "The summary should concisely convey the key topics discussed, the emotions expressed, and any significant moments or changes in the patient's mood or behavior, exactly as presented in the transcription. "
                "Focus on the most relevant details that will help the therapist recall the session effectively. "
                "The JSON input consists of an array of objects where each object contains 4 attributes:\n"
                "1. 'content': A participant's spoken content.\n"
                "2. 'current_speaker': A unique identifier for the speaker associated with the content.\n"
                "3. 'start_time': The time at which the speaker's content began to be spoken.\n"
                "4. 'end_time': The time at which the speaker's content finished being spoken.\n\n"
                "------------\n\nExample Input:\n\n"
                r"[{'content': 'Hi, how are you feeling today?', 'current_speaker': 0, 'start_time': 0.0, 'end_time': 8.58}, {'content': 'Not so well.', 'current_speaker': 1, 'start_time': 9.0, 'end_time': 10.58}, {'content': 'Can you tell me more about what's been troubling you?', 'current_speaker': 0, 'start_time': 11.5, 'end_time': 14.58}, {'content': 'I've been feeling really anxious about work. I can't seem to relax, even at home.', 'current_speaker': 1, 'start_time': 15.5, 'end_time': 18.58}]"
                "\n\n------------\n\nExample Output:\n\n"
                "The patient expressed anxiety related to work, indicating difficulty in relaxing both at work and at home. "
                "The session focused on exploring these feelings and potential coping strategies."
            )
        except Exception as e:
            raise RuntimeError(e) from e

    def _summarize_diarization_user_message(self, diarization: str) -> str:
        try:
            assert len(diarization or '') > 0, "Missing diarization param for building user message"
            return (
                 "Please provide a concise summary of the following session transcription. "
                 "The summary should capture the key topics discussed, emotions expressed, and significant moments or changes in the session."
                 f"\n\n-----------------\n\nTranscription:\n\n{diarization}"
            )
        except Exception as e:
            raise RuntimeError(e) from e

    # Grand Summary of Diarization Chunks

    def _summarize_diarization_chunks_system_message(self, language_code: str) -> str:
        try:
            assert len(language_code or '') > 0, "Missing language_code param for building system message"
            return (
                "A mental health practitioner just met with a patient, and used our Practice Management Platform to listen to the session and generate a summary. "
                "Due to the session's lengthy duration, we have chunked its transcription, summarized each chunk independently, and merged all chunks together. "
                "The problem is that this merged version is bloated and has a lot of redundancy. "
                "Your task is to reword this grand summary to avoid redundancy, and make it cleaner and pleasant to read. "
                f"It is very important that this grand summary is written using language code {language_code}."
            )
        except Exception as e:
            raise RuntimeError(e) from e

    def _summarize_diarization_chunks_user_message(self, diarization: str) -> str:
        try:
            assert len(diarization or '') > 0, "Missing diarization param for building user message"
            return (
                 "Please clean up the following summary, which consists of a merged set of independent chunk summaries. "
                 f"\n\n-----------------\n\nTranscription:\n\n{diarization}"
            )
        except Exception as e:
            raise RuntimeError(e) from e
