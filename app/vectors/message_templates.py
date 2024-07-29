from datetime import datetime
from enum import Enum

from num2words import num2words
from pytz import timezone

from ..internal.utilities.general_utilities import gender_has_default_pronouns
from ..internal.utilities.datetime_handler import convert_to_internal_date_format

class PromptScenario(Enum):
    CHUNK_SUMMARY = "chunk_summary"
    GREETING = "greeting"
    PRESESSION_BRIEFING = "presession_briefing"
    QUERY = "query"
    QUESTION_SUGGESTIONS = "question_suggestions"
    SESSION_MINI_SUMMARY = "session_mini_summary"
    SOAP_TEMPLATE = "soap_template"
    TOPICS = "frequent_topics"
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
        elif scenario == PromptScenario.GREETING:
            return self._create_greeting_user_message()
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
            return self._create_frequent_topics_user_message(language_code=language_code,
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
        else:
            raise Exception("Received untracked prompt scenario for retrieving the user message")

    def get_system_message_for_scenario(self, scenario: PromptScenario, **kwargs):
        if scenario == PromptScenario.UNDEFINED:
            raise Exception("Received undefined prompt scenario for retrieving the user message")

        if scenario == PromptScenario.QUERY:
            last_session_date = None if 'last_session_date' not in kwargs else kwargs['last_session_date']
            patient_name = None if 'patient_name' not in kwargs else kwargs['patient_name']
            patient_gender = None if 'patient_gender' not in kwargs else kwargs['patient_gender']
            return self._create_qa_system_message(last_session_date=last_session_date,
                                                  patient_name=patient_name,
                                                  patient_gender=patient_gender)
        elif scenario == PromptScenario.GREETING:
            language_code = None if 'language_code' not in kwargs else kwargs['language_code']
            tz_identifier = None if 'tz_identifier' not in kwargs else kwargs['tz_identifier']
            therapist_name = None if 'therapist_name' not in kwargs else kwargs['therapist_name']
            therapist_gender = None if 'therapist_gender' not in kwargs else kwargs['therapist_gender']
            return self._create_greeting_system_message(therapist_name=therapist_name,
                                                        therapist_gender=therapist_gender,
                                                        tz_identifier=tz_identifier,
                                                        language_code=language_code)
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
            return self._create_frequent_topics_system_message(language_code=language_code)
        elif scenario == PromptScenario.CHUNK_SUMMARY:
            return self._create_chunk_summary_system_message()
        elif scenario == PromptScenario.SOAP_TEMPLATE:
            return self._create_soap_template_system_message()
        elif scenario == PromptScenario.SESSION_MINI_SUMMARY:
            language_code = None if 'language_code' not in kwargs else kwargs['language_code']
            return self._create_session_mini_summary_system_message(language_code=language_code)
        else:
            raise Exception("Received untracked prompt scenario for retrieving the system message")

    # Text QA Prompt

    def _create_qa_system_message(self,
                                  patient_name: str,
                                  patient_gender: str,
                                  last_session_date: str = None) -> str:
        assert len(patient_gender or '') > 0, "Missing patient_gender param for building system message"
        assert len(patient_name or '') > 0, "Missing patient_name param for building system message"

        if gender_has_default_pronouns(patient_gender):
            patient_info = f"For reference, the patient is a {patient_gender}, and their name is {patient_name}."
        else:
            patient_info = f"For reference, the patient's name is {patient_name}."

        last_session_date_param = "" if len(last_session_date or '') == 0 else f"Keep in mind that {patient_name}'s last session was on {convert_to_internal_date_format(last_session_date)} (mm-dd-yyyy)."
        return (
            "A mental health practitioner is entering our Practice Management Platform, and is using you to ask questions about a patient's session history based on the practitioner's own session notes. "
            f"{patient_info} "
            "Your job is to answer the practitioner's questions based on the information context you find from the context data. "
            "When evaluating the context, for each session you should always look first at the chunk_summary value to understand whether a given document is related to the question. "
            "If the chunk_summary value is related to the question, you should use it along the chunk_text value to generate your response. "
            "Additionally, if you find values for pre_existing_history_text and pre_existing_history_summary, make use of them as well since they describe the patient's pre-existing history prior to being added to our platform. "
            f"{last_session_date_param} "
            "When answering a question, you should always outline the session_date associated with the information you are providing (mm-dd-yyyy). If no session information is found, do not mention any session dates. "
            "If the question references a person other than the patient, for whom you can't find information in the session notes, you should strictly say you can't provide an answer. "
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

    # Greeting Prompt

    def _create_greeting_system_message(self,
                                        therapist_name: str,
                                        tz_identifier: str,
                                        language_code: str,
                                        therapist_gender: str) -> str | None:

        try:
            assert len(therapist_name or '') > 0, "Missing therapist_name param for building system message"
            assert len(tz_identifier or '') > 0, "Missing tz_identifier param for building system message"
            assert len(language_code or '') > 0, "Missing language_code param for building system message"
            assert len(therapist_gender or '') > 0, "Missing therapist_gender param for building system message"

            tz = timezone(tz_identifier)
            weekday = datetime.now(tz).strftime('%A')
            gender_context = f"For context, {therapist_name} is a {therapist_gender}. " if gender_has_default_pronouns(therapist_gender) else ""
            return (
                f"A mental health practitioner is entering our Practice Management Platform. Your job is to greet them into the experience. "
                f"Send a cheerful message about today being {weekday}. Address the practitioner by their name, which is {therapist_name}. {gender_context} "
                f"It is very important that you craft your response using language code {language_code}. Finish off with a short fragment on productivity."
            )
        except Exception as e:
            raise Exception(str(e))

    def _create_greeting_user_message(self) -> str:
        return f"Write a welcoming message for the practitioner. Your response should not go over 180 characters."

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
            assert len(therapist_gender or '') > 0, "Missing therapist_gender param for building system message"
            assert len(patient_name or '') > 0, "Missing patient_name param for building system message"
            assert len(patient_gender or '') > 0, "Missing patient_gender param for building system message"
            assert session_number > 0, "Something went wrong when building system message"

            gender_params = ""
            if gender_has_default_pronouns(therapist_gender):
                gender_params += f"For reference, {therapist_name} is a {therapist_gender}. "
            if gender_has_default_pronouns(patient_gender):
                gender_params += f"For reference, {patient_name} is a {patient_gender}. "
            ordinal_session_number = num2words(session_number, to='ordinal_num')
            last_session_date_param = "" if len(last_session_date or '') == 0 else f"Additionally, keep in mind that {patient_name}'s last session was on {convert_to_internal_date_format(last_session_date)} (mm-dd-yyyy)."
            return (
                    "A mental health practitioner is entering our Practice Management Platform. "
                    "They are about to meet with an existing patient, and need to quickly refreshen on the patient's session history. "
                    f"Your job is to 'prep' the practitioner, {therapist_name}. "
                    f"It is very important that you start by saluting {therapist_name}, and reminding them that they are seeing {patient_name}, the patient, for the {ordinal_session_number} time. "
                    f"{gender_params}"
                    "\n\nOnce you've reminded the therapist about the session number, you should provide a summary of the patient's history broken down into two sections: Most Recent Sessions, and Historical Themes. "
                    "If you determine it's the first time the therapist will meet with the patient, ignore the summary categorization, and just suggest strategies on how to establish a solid foundation. "
                    "\nWhen populating Most Recent Sessions, use the session_date value found in the context to determine which are the most recent session(s). "
                    "You should double-check the session dates for precision. For reference, the date format for session_date is mm-dd-yyyy. "
                    f"{last_session_date_param} "
                    "\nIf you're generating a summary for a patient that has already met with the therapist, you should end it with suggestions on what would be good avenues to explore in the upcoming session. "
                    "\nUse only the information you find based on the chunk_summary and chunk_text values. "
                    "The total length of the summary may take up to 1600 characters. "
                    "Return only a JSON object with a single key, 'summary', written in English, and the summary response as its only value. "
                    f"It is very important that the summary response is written using language code {language_code}. "
                    "Do not add the literal word 'json' in the response. Simply return the object.\n"
                    r"For example, a response for language code es-419 would look like: {'summary': 'Sesiones más recientes:\nEn las últimas sesiones, Juan ha hablado sobre la dificultad para equilibrar su vida laboral y personal.\n\nTemas históricos:\nJuan ha luchado con problemas de autoexigencia y perfeccionismo.'}"
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
                "A mental health practitioner has entered our Practice Management Platform to look at their patient's dashboard. "
                "They have the opportunity to ask you a question about the patient's session history. "
                "Your job is to provide the practitioner with three questions that they could ask you about the patient, for which you'd have rich answers. "
                "It is very important that each question remains under 60 characters of length. "
                "Avoid vague questions like 'What happened during the session of 04/10/2022?', and instead aim for narrow-focused questions like 'What have we discussed about the patient's childhood?'"
                "\nReturn only a JSON object with a key titled 'questions', written in English, and the array of questions as its value. "
                "If based on the context, you determine that there is no data associated with the patient for whatever reason, the 'questions' array should be empty. "
                f"It is very important that the content of each question is written using language code {language_code}. "
                "Do not add the literal word 'json' in the response. Simply return the object.\n"
                r"For example, a response for language code es-419 would look like: {'questions': ['¿Cuándo fue la última vez que hablamos del divorcio?', '¿Qué fue lo último que revisamos en sesión?', '¿Qué tema sería beneficioso retomar con el paciente?']}"
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
            assert len(patient_gender or '') > 0, "Missing patient_gender param for building user message"
            assert len(query_input or '') > 0, "Missing query_input param for building user message"

            if gender_has_default_pronouns(patient_gender):
                patient_info = f"\nFor reference, the patient is a {patient_gender}, and their name is {patient_name}."
            else:
                patient_info = f"\nFor reference, the patient's name is {patient_name}."
            return (
                f"We have provided context information below.\n---------------------\n{context}\n---------------------\n"
                f"\n{patient_info} "
                f"It is very important that each question is written using language code {language_code}, and that it remains under 50 characters of length. "
                f"Given this information, please answer the practitioner's question:\n{query_input}"
            )
        except Exception as e:
            raise Exception(e)

    # Frequent Topics

    def _create_frequent_topics_system_message(self, language_code: str) -> str:
        try:
            assert len(language_code or '') > 0, "Missing language_code param for building system message"

            return (
                "A mental health practitioner has entered our Practice Management Platform to look at their patient's dashboard. "
                "They want to gain insight into what are the three topics that the patient brings up the most during sessions. "
                "Your job is to provide the practitioner with the set of frequent topics, as well as each topic's respective percentage. "
                "For example, for a patient that has spoken equally about three topics, each topic's percentage would be 33.3%. "
                "It is very important that the sum of the percentages add up 100%. It shouldn't be below nor above. Please double check the math. "
                "Additionally, the string value for each topic should remain under 25 characters of length. "
                "\nReturn only a JSON object with a single key titled 'topics', written in English, and its only value being an array containing up to three objects. "
                f"Each object should have two keys titled 'topic' and 'percentage', written in English, and the content of each key's value needs to be written in language code {language_code}. "
                "If based on the context, you determine that there is no data associated with the patient for whatever reason, the 'topics' array should be empty. "
                "Do not add the literal word 'json' in the response. Simply return the object.\n"
                r"For example, a response for language code es-419 where the patient spoke equally about the three topics would look like: {'topics':[{'topic': 'Ansiedad por el trabajo', 'percentage': '33%'},{'topic': 'Mejora en el matrimonio', 'percentage': '33%'},{'topic': 'Pensando en adoptar', 'percentage': '33%'}]}"
                "\n"
                r"Another example for language code en-us where the patient has spoken half of the time about a single topic, and the remaining time is broken into two other topics would look like: {'topics':[{'topic': 'Graduating from school', 'percentage': '50%'},{'topic': 'Substance abuse', 'percentage': '25%'},{'topic': 'Adopting a pet', 'percentage': '25%'}]}"
            )
        except Exception as e:
            raise Exception(e)

    def _create_frequent_topics_user_message(self,
                                             language_code: str,
                                             context: str,
                                             patient_name: str,
                                             query_input: str,
                                             patient_gender: str) -> str:
        try:
            assert len(language_code or '') > 0, "Missing language_code param for building user message"
            assert len(context or '') > 0, "Missing context param for building user message"
            assert len(patient_name or '') > 0, "Missing patient_name param for building user message"
            assert len(patient_gender or '') > 0, "Missing patient_gender param for building user message"
            assert len(query_input or '') > 0, "Missing query_input param for building user message"

            if gender_has_default_pronouns(patient_gender):
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
            "A mental health practitioner just met with a patient, and is ready to upload their session notes into our platform. "
            "We have implemented a Retrieval Augmented Generation system, for which we are using a chunking approach to break up the practitioner's session notes. "
            "The goal is to create embeddings out of each chunk, and insert it in a vector database. "
            "Your job is to come up with a short summary about the chunk you'll be given. "
            "Keep in mind the chunk may contain only a subset of the session notes' information. "
            "Your summary is meant to be used for enabling a quick retrieval whenever the practitioner searches for information that's contained in this chunk. "
            "Ideally, by just looking at your summary our platform's search retriever should know exactly what information is contained in the chunk. "
            "Your output should be generated in English, regardless of what language the chunk is written in. "
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
            "A mental health practitioner just met with a patient, and is ready to upload their session notes into our platform. "
            "Your job is to adapt their session notes into the SOAP format. The acronym SOAP stands for Subjective, Objective, Assessment, and Plan. "
            "'Subjective' is what brought the patient to the practitioner, including past history. "
            "'Objective' is the objective information that can be collected from the patient encounter. "
            "'Assessment' represents the practitioner's professional opinion in light of the subjective and objective findings. "
            "'Plan' is the set of actions proposed either by the practitioner or the patient for addressing the patient's problem(s). "
            "You should take what the practitioner wrote, and break it down into each of these sections. "
            "You may paraphrase information if you believe it will make it more readable. "
            "If there is a section that can't be populated because there isn't enough information from the session notes, just leave it blank. "
            "Do not discard any information from the original report. If it doesn't fit in any of the categories, add it at the end, outside of the SOAP breakdown "
            "Return the new SOAP session notes as a string, with double line breaks between each category (Subjective, Objective, Assessment, and Plan), "
            "and single line breaks between a category's header and its content. "
            "It is very important that category headers are written in English but the category's content should be generated in the same language in which the practitioner's session notes were written."
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
                "A mental health practitioner just met with a patient, and is ready to upload their session notes into our platform. "
                "Our platform includes a Sessions table that shows a 'preview' of every session notes' entry. "
                "This preview is essentially a 'mini summary' of the session notes, and should be no longer than 50 characters. "
                "Your job is to come up with this mini summary. "
                "\nWhile you only have 50 characters, the goal is that by reading the mini summary, the practitioner should have a clear idea of what information is contained in the full session notes. "
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
