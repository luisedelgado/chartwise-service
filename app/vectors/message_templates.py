from enum import Enum

from num2words import num2words

from ..internal.utilities.general_utilities import gender_has_default_pronouns
from ..internal.utilities.datetime_handler import convert_to_date_format_spell_out_month, DATE_FORMAT_YYYY_MM_DD

class PromptScenario(Enum):
    # keep sorted A-Z
    ATTENDANCE_INSIGHTS = "attendance_insights"
    CHUNK_SUMMARY = "chunk_summary"
    DIARIZATION_SUMMARY = "diarization_summary"
    PRESESSION_BRIEFING = "presession_briefing"
    QUERY = "query"
    QUESTION_SUGGESTIONS = "question_suggestions"
    REFORMULATE_QUERY = "reformulate_query"
    RERANKING = "reranking"
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
        elif scenario == PromptScenario.RERANKING:
            query_input = None if 'query_input' not in kwargs else kwargs['query_input']
            context = None if 'context' not in kwargs else kwargs['context']
            return self._create_reranking_user_message(query_input=query_input,
                                                       context=context)
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
            return self._create_attendance_insights_user_message(patient_session_dates=patient_session_dates)
        elif scenario == PromptScenario.DIARIZATION_SUMMARY:
            diarization = None if 'diarization' not in kwargs else kwargs['diarization']
            return self._summarize_diarization_user_message(diarization=diarization)
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
            session_number = None if 'session_number' not in kwargs else kwargs['session_number']
            last_session_date = None if 'last_session_date' not in kwargs else kwargs['last_session_date']
            return self._create_briefing_system_message(language_code=language_code,
                                                        therapist_name=therapist_name,
                                                        therapist_gender=therapist_gender,
                                                        patient_name=patient_name,
                                                        patient_gender=patient_gender,
                                                        session_number=session_number,
                                                        last_session_date=last_session_date)
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
        elif scenario == PromptScenario.RERANKING:
            top_n = None if 'top_n' not in kwargs else kwargs['top_n']
            return self._create_reranking_system_message(top_n=top_n)
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
                                                                          incoming_date_format=DATE_FORMAT_YYYY_MM_DD)
            last_session_date_context = f"\nNote that {patient_name}'s last session with the practitioner was on {date_spell_out_month}."

        if chat_history_included:
            chat_history_instruction = (
                "9. For coherence, consider the provided chat history to understand what the conversation has been so far. "
                "The `chunk_summary` fields still take precedence when you're looking for information with which to answer the user question.\n"
            )
        else:
            chat_history_instruction = ""

        return (
            f"A mental health practitioner is using our Practice Management Platform to inquire about a patient named {patient_name}{patient_gender_context}. "
            "The practitioner's session notes provide the available information. "
            "Your task is to answer the practitioner's questions based on these notes. "
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
            "8. For questions directly related to the patient's session history, if the question cannot be answered based on the session notes, state that the information is not available in the session notes.\n"
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
                f"\nGiven this information, please answer the question: {query_input}\n"
            )
        except Exception as e:
            raise Exception(e)

    # Briefing Prompt

    def _create_briefing_system_message(self,
                                        language_code: str,
                                        therapist_name: str,
                                        therapist_gender: str,
                                        patient_name: str,
                                        patient_gender: str,
                                        session_number: int,
                                        last_session_date: str = None) -> str | None:
        try:
            assert len(language_code or '') > 0, "Missing language_code param for building system message"
            assert len(therapist_name or '') > 0, "Missing therapist_name param for building system message"
            assert len(patient_name or '') > 0, "Missing patient_name param for building system message"
            assert session_number > 0, "Something went wrong when building system message"

            therapist_gender = ("" if (therapist_gender is None or not gender_has_default_pronouns(therapist_gender))
                                else f" ({therapist_gender})")
            patient_gender = ("" if (patient_gender is None or not gender_has_default_pronouns(patient_gender))
                              else f" ({patient_gender})")
            ordinal_session_number = num2words(session_number, to='ordinal_num')

            if len(last_session_date or '') == 0:
                last_session_date_context = ""
            else:
                date_spell_out_month = convert_to_date_format_spell_out_month(session_date=last_session_date,
                                                                              incoming_date_format=DATE_FORMAT_YYYY_MM_DD)
                last_session_date_context = f"Note that {patient_name}'s last session with the practitioner was on {date_spell_out_month}. "

            return (
                    f"A mental health practitioner, {therapist_name}{therapist_gender}, is about to meet with {patient_name}{patient_gender}, an existing patient. "
                    f"{therapist_name} is using our Practice Management Platform to quickly refreshen on {patient_name}'s session history. "
                    f"This will be their {ordinal_session_number} session together. "
                    f"The first thing you should do is say hi {therapist_name}, and remind them that they are going to be seeing {patient_name} for the {ordinal_session_number} time."
                    f"\n\nOnce you've said hi to {therapist_name}, provide a summary of {patient_name}'s session history in two sections: 'Most Recent Sessions' and 'Historical Themes'. "
                    f"If this is {therapist_name}'s first time meeting with {patient_name}, omit these sections and instead suggest strategies on how to establish a solid foundation. "
                    f"For 'Most Recent Sessions' list the most recent sessions sorted by most recent first. Ensure date precision. "
                    f"{last_session_date_context}"
                    f"If {therapist_name} has previously met with {patient_name}, conclude with suggestions for discussion topics for their session that's about to start. "
                    "Use only the information you find from the `chunk_summary` fields. "
                    f"It is very important that the summary doesn't go beyond 1600 characters, and that it's written using language code {language_code}. "
                    "Ensure the headers for 'Most Recent Sessions,' 'Historical Themes,' and 'Suggestions for Next Session' are bolded using appropriate mark-up."
            )
        except Exception as e:
            raise Exception(e)

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
            raise Exception(e)

    # Question Suggestions

    def _create_question_suggestions_system_message(self,
                                                    language_code: str) -> str:
        try:
            assert len(language_code or '') > 0, "Missing language_code param for building system message"

            return (
                "A mental health practitioner is viewing a patient's dashboard on our Practice Management Platform. "
                "They can ask you about the patient's session history. "
                "Your task is to generate two specific questions that the practitioner might ask, for which you have detailed answers based on the provided context documents. "
                "Each question should be under 60 characters in length and be focused on specific aspects of the patient's history. "
                "Avoid broad or vague questions like 'What happened during the session of Apr 10, 2022?' "
                "Instead, consider narrow-focused questions such as 'What have we discussed about the patient's childhood?'\n\n"
                "Return a JSON object with a key titled `questions`, written in English, and an array of questions as its value. "
                f"Ensure that the questions are written in language code {language_code}. "
                "This is what the format should look like: {\"questions\": [..., ...]}\n"
                "Example output using language code es-419:\n"
                r"{'questions': ['¿Cuándo fue la última vez que hablamos del divorcio?', '¿Qué fue lo último que revisamos en sesión?']}"
            )
        except Exception as e:
            raise Exception(e)

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
            raise Exception(e)

    # Recent Topics

    def _create_recent_topics_system_message(self, language_code: str) -> str:
        try:
            assert len(language_code or '') > 0, "Missing language_code param for building system message"

            return (
                "A mental health practitioner is viewing a patient’s dashboard on our Practice Management Platform. "
                "They need to see the top three topics the patient has discussed most frequently during sessions. Provide the following:\n\n"
                "1. Three frequent topics, each with its frequency percentage.\n"
                "2. Ensure the percentages sum to exactly 100%. Double-check the math.\n"
                "3. Each topic should be under 25 characters.\n\n"
                "Return a JSON object with one key: `topics`, written in English. The value should be an array of up to three objects, each with:\n"
                f"* `topic`: Distinct topic written using language code {language_code}.\n"
                f"* `percentage`: Frequency percentage.\n\n"
                "This is what the format should look like: {\"topics\": [{\"topic\": \"...\", \"percentage\": \"...\"}, {\"topic\": \"...\", \"percentage\": \"...\"}, {\"topic\": \"...\", \"percentage\": \"...\"}]}\n"
                "If no context data is available, the array should be empty. "
                "\n\nExample response for language code es-419 where the patient spoke half of the time about a given topic, and the remaining time was split between two other topics:\n"
                r"{'topics':[{'topic': 'Graduating from school', 'percentage': '50%'},{'topic': 'Substance abuse', 'percentage': '25%'},{'topic': 'Adopting a pet', 'percentage': '25%'}]}"
            )
        except Exception as e:
            raise Exception(e)

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
            raise Exception(e)

    # Session Entry Summary Prompt

    def _create_chunk_summary_system_message(self) -> str:
         return (
            "A mental health practitioner is uploading session notes to our platform. "
            "We use a Retrieval Augmented Generation system that involves chunking these notes. "
            "Each chunk will be converted into embeddings and stored in a vector database. "
            "Your task is to create a brief, informative summary of the chunk that will be provided. "
            "This summary should encapsulate the key information from the chunk, enabling quick retrieval when searching. "
            "Make sure the summary accurately reflects the content and context of the chunk. "
            "Regardless of the original language, generate the summary in English."
        )

    def _create_chunk_summary_user_message(self,
                                           chunk_text: str) -> str:
        try:
            assert len(chunk_text or '') > 0, "Missing chunk_text param for building user message"
            return (f"Summarize the following chunk:\n\n{chunk_text}")
        except Exception as e:
            raise Exception(e)

    # SOAP Template Prompt

    def _create_soap_template_system_message(self) -> str:
        return (
            "A mental health practitioner has uploaded session notes into our platform. "
            "Your task is to convert these notes into the SOAP format, which includes the following sections:\n\n"
            "Subjective: Describes what brought the patient to the practitioner, including their history and reasons for the visit.\n"
            "Objective: Contains objective information gathered during the patient encounter.\n"
            "Assessment: The practitioner's professional opinion based on the subjective and objective information.\n"
            "Plan: The actions proposed by the practitioner or the patient to address the issues discussed.\n\n"
            "Break down the session notes into these sections. Paraphrase information if it improves readability. "
            "Leave any section blank if there is insufficient information but do not discard any original content. "
            "If some information doesn't fit into the SOAP categories, place it at the end, outside the SOAP breakdown.\n\n"
            "Return the SOAP session notes formatted as a string, with double line breaks between sections (Subjective, Objective, Assessment, and Plan), and single line breaks between the category header and its content. "
            "Ensure category headers are written in English, while the content is written in the same language as the original notes."
        )

    def _create_soap_template_user_message(self, session_notes: str) -> str:
        try:
            assert len(session_notes or '') > 0, "Missing session_notes param for building user message"
            return f"Adapt the following session notes into the SOAP format:\n\n{session_notes}."
        except Exception as e:
            raise Exception(e)

    def _create_session_mini_summary_system_message(self, language_code: str):
        try:
            assert len(language_code or '') > 0, "Missing language_code param for building system message"
            return (
                "After a session with a patient, a mental health practitioner uploads their notes to our platform. "
                "Each session entry in the Sessions table includes a 'mini summary' of no more than 50 characters. "
                "Your task is to create this mini summary. "
                "It should clearly convey the essence of the session notes so that practitioners can quickly understand the content of each entry. "
                f"It is very important that your output is generated using language code {language_code}. "
            )
        except Exception as e:
            raise Exception(e)

    def _create_session_mini_summary_user_message(self, session_notes: str):
        try:
            assert len(session_notes or '') > 0, "Missing session_notes param for building user message"
            return (f"Summarize the following session notes:\n\n{session_notes}")
        except Exception as e:
            raise Exception(e)

    # Reranking

    def _create_reranking_system_message(self, top_n: int):
        try:
            assert top_n > 0, "Error while building user message: top_n should be bigger than 0"
            return (
                "A mental health practitioner is using our Practice Management Platform to ask questions about a patient. "
                "The available information about the patient's session history consists of the practitioner's own session notes. "
                "These session notes have been divided into chunks.\n\nYou will receive:\n\n"
                "1. The practitioner's question.\n2. A set of chunked session notes.\n\n"
                "Your task is to:\n\n1. Rerank the chunked documents based on their relevance to the practitioner's question.\n"
                "2. Ensure that the most relevant documents are ranked highest.\n\n"
                f"The top {top_n} documents will be used to answer the question, so they must contain all the necessary information to provide a comprehensive response.\n\n"
                "Return a JSON object with a single key, 'reranked_documents', written in English, and the array of reranked documents as its value. "
                "Each document object should have two keys titled 'session_date' and 'chunk_summary', each with their respective value from the context you were given. "
                "For the `session_date` use date format mm-dd-yyyy (i.e: 10-24-2020). "
                "It is very important that the documents' contents remain written in the language in which they were originally written.\n"
                r'Example output: {"reranked_documents": [{"session_date": "10-24-2022", "chunk_summary": "Umeko was born and raised in Venezuela."}, {"session_date": "02-24-2021", "chunk_summary": "Umeko had his first girlfriend when he was 17 years old."}, {"session_date": "06-24-2020", "chunk_summary": "Umeko enjoys soccer."}]}'
            )
        except Exception as e:
            raise Exception(e)

    def _create_reranking_user_message(self, query_input: str, context: str):
        try:
            assert len(context or '') > 0, "Missing context param for building user message"
            assert len(query_input or '') > 0, "Missing query_input param for building user message"
            return (
                f"We have provided the chunked documents below.\n---------------------\n{context}\n---------------------\n"
                f"\nGiven this information and the input question below, please rerank the chunked documents based on their relevance to the practitioner's question."
                f"\n\nInput question: {query_input}"
            )
        except Exception as e:
            raise Exception(e)

    # Reformulate query

    def _create_reformulate_query_system_message(self):
        return (
            "Given the chat history and the latest user question, which may reference previous context, reformulate the question into a standalone query "
            "that can be understood without relying on the chat history. Do NOT provide an answer; only reformulate the question if necessary, otherwise return it unchanged. "
            "The output should be generated using the same language in which the user question is written."
        )

    def _create_reformulate_query_user_message(self, chat_history: str, query_input: str):
        try:
            assert len(chat_history or '') > 0, "Error while building user message: chat_history should be bigger than 0"
            assert len(query_input or '') > 0, "Error while building user message: query_input should be bigger than 0"

            return (
                "Please review the following chat history and the most recent user question. "
                "The user question might reference information from the chat history. "
                "Your task is to reformulate the user question into a standalone query that can be understood without the chat history. "
                "Do NOT provide an answer; simply reformulate the question if necessary, otherwise return it as is."
                "The output should be generated using the same language in which the latest user question is written."
                f"\n---------------------\nChat History:\n{chat_history}\n---------------------\n"
                f"Latest User Question:\n{query_input}\n---------------------\n"
            )
        except Exception as e:
            raise Exception(e)

    # Topics Insights

    def _create_topics_insights_system_message(self, language_code: str):
        assert len(language_code or '') > 0, "Missing language_code param for building system message"
        return (
            "You are a mental health assistant helping practitioners analyze their patients' session data. "
            "You will receive an array of topics, each with a corresponding frequency percentage, indicating how often the patient has spoken about these topics in their most recent sessions. "
            "Your task is to briefly analyze this information and generate a concise paragraph that highlights any patterns, underlying themes, or notable insights. "
            "Focus on rationalizing the data in a way that could assist the practitioner in understanding the patient's current focus or emotional state.\n"
            "\nIt is very important that the output meets the following criteria:\n"
            "1. Format the output in bullet points.\n"
            "2. Limit the output to 500 characters.\n"
            f"3. Ensure the output is generated using language code {language_code}.\n"
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
            raise Exception(e)

    # Attendance Insights

    def _create_attendance_insights_user_message(self,
                                                 patient_session_dates: list[str]):
        try:
            assert len(patient_session_dates or '') >= 0, "Missing patient_session_dates param for building user message"
            return ("Given the following dates of sessions that a patient has had with their therapist, provide an analysis of the patient's attendance pattern. "
                    "Highlight any trends, consistency, or notable gaps in the sessions. "
                    "Offer insights that might help understand the patient's commitment to therapy or any potential issues with regular attendance. "
                    "If the set of dates is empty, return only a 50-character sentence stating that the patient is yet to start attending sessions.\n\n"
                    f"Here is the set of dates: {patient_session_dates}")
        except Exception as e:
            raise Exception(e)

    def _create_attendance_insights_system_message(self,
                                                   language_code: str):
        try:
            assert len(language_code or '') > 0, "Missing language_code param for building system message"
            return ("You are a mental health assistant helping practitioners analyze their patients' attendance patterns. "
                    "You receive an array of dates (with format YYYY-MM-DD) representing the last N sessions a patient has had with their therapist. "
                    "Your task is to generate a brief, insightful set of bullet points that highlights trends or irregularities in the patient's attendance. "
                    "Consider factors such as consistency, gaps between sessions, and any changes in frequency over time. "
                    "Provide analytics that could help the therapist understand the patient's commitment, punctuality, or potential barriers to consistent attendance. "
                    "\n\nIt is very important that the output meets the following criteria:\n"
                    "1. Format the output in bullet points.\n"
                    "2. Limit the output to 500 characters.\n"
                    f"3. Ensure the output is generated using language code {language_code}.\n")
        except Exception as e:
            raise Exception(e)

    # Summarize Diarization

    def _summarize_diarization_system_message(self, language_code: str) -> str:
        try:
            assert len(language_code or '') > 0, "Missing language_code param for building system message"
            return (
                "A mental health practitioner just met with a patient, and needs to summarize the content of the session. "
                f"We have a transcription of the full session in JSON format, and your task is to provide the summary using language code {language_code}. "
                "The summary should be concise and provide a clear overview of the key topics discussed, the emotions expressed, and any significant moments or changes in the patient's mood or behavior. "
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
            raise Exception(e)

    def _summarize_diarization_user_message(self, diarization: str) -> str:
        try:
            assert len(diarization or '') > 0, "Missing diarization param for building user message"
            return (
                 "Please provide a concise summary of the following session transcription. "
                 "The summary should capture the key topics discussed, emotions expressed, and significant moments or changes in the session."
                 f"\n\n-----------------\n\nTranscription:\n\n{diarization}"
            )
        except Exception as e:
            raise Exception(e)
