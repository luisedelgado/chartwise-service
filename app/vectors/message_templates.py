from datetime import datetime

from llama_index.core.prompts import ChatPromptTemplate
from llama_index.core.llms import ChatMessage, MessageRole
from num2words import num2words
from pytz import timezone

from ..internal.model import BriefingConfiguration
from ..internal.utilities.general_utilities import gender_has_default_pronouns

# Text QA Prompt

def __create_system_qa_message() -> str:
    return '''A therapist is using you to ask questions about their patients' notes. 
    Your job is to answer the therapist's questions based on the information context you find from the sessions' data.
    You should always look first at the session_summary value found in the metadata to understand whether a given document is related to the question.
    If the session_summary value is related to the question, you should make use of that document to generate your response. 
    To answer a question in the best way possible, you should find the documents that are most related to the question. 
    For any information you reference, always outline the session_date value found in the metadata. If no session information is found, do not mention any session dates.
    If the question references a person other than the patient, for whom you can't find information in the session notes, you should strictly say you can't provide an answer.'''

def __create_user_qa_message(language_code: str, patient_gender: str, patient_name: str) -> str:
    message_content = (
    '''We have provided context information below. \n
    ---------------------\n
    {context_str}
    \n---------------------\n''')
    language_code_requirement = f"\nIt is very important that you craft your response using language code {language_code}."

    if gender_has_default_pronouns(patient_gender):
        patient_context = f"\nFor reference, the patient is a {patient_gender}, and their name is {patient_name}."
    else:
        patient_context = f"\nFor reference, the patient's name is {patient_name}."

    execution_statement = "\nGiven this information, please answer the question: {query_str}\n"
    return message_content + language_code_requirement + patient_context + execution_statement

def create_chat_prompt_template(language_code: str,
                                patient_name: str,
                                patient_gender: str) -> ChatPromptTemplate:
    qa_messages = [
        ChatMessage(
            role=MessageRole.SYSTEM,
            content=__create_system_qa_message(),
        ),
        ChatMessage(
            role=MessageRole.USER,
            content=__create_user_qa_message(patient_gender=patient_gender,
                                             language_code=language_code,
                                             patient_name=patient_name),
        ),
    ]
    return ChatPromptTemplate(qa_messages)

# Refine Prompt

def __create_system_refine_message() -> str:
    return '''A mental health practitioner is using you to ask questions 
    about their patient's session notes. When refining an answer you always integrate the new context 
    into the original answer, and provide the resulting response. You should never reference the original 
    answer or context directly in your answer. If you reference session notes, outline all session dates after your answer. 
    Otherwise do not reference any session dates.'''

def __create_user_refine_message(language_code: str):
    message_content = '''The original question is as follows: {query_str}\nWe have provided an 
    existing answer: {existing_answer}\nWe have the opportunity to refine the existing answer (only if needed) 
    with some more context below.\n------------\n{context_msg}\n------------'''
    language_code_requirement = f"\nIt is very important that you craft your response using language code {language_code}."
    execution_statement = '''\nUsing both the new context and 
    your own knowledge, update or repeat the existing answer.\n'''
    return message_content + language_code_requirement + execution_statement

def create_refine_prompt_template(language_code: str) -> ChatPromptTemplate:
    refine_messages = [
        ChatMessage(
            role=MessageRole.SYSTEM,
            content=(__create_system_refine_message()),
        ),
        ChatMessage(
            role=MessageRole.USER,
            content=(__create_user_refine_message(language_code)),
        ),
    ]
    return ChatPromptTemplate(refine_messages)

# Greeting Prompt

def create_system_greeting_message(therapist_name: str, tz_identifier: str, language_code: str, therapist_gender: str) -> str | None:
    try:
        tz = timezone(tz_identifier)
        weekday = datetime.now(tz).strftime('%A')
        gender_context = f"For context, {therapist_name} is a {therapist_gender}" if gender_has_default_pronouns(therapist_gender) else ""
        return f'''A mental health practitioner is entering our Practice Management Platform. Your job is to greet them into the experience.
        \nSend a cheerful message about today being {weekday}. Address the practitioner by their name, which is {therapist_name}. {gender_context}
        \nIt is very important that you craft your response using language code {language_code}. Finish off with a short fragment on productivity.'''
    except Exception as e:
        raise Exception(str(e))

def create_user_greeting_message() -> str:
    return f'''Write a welcoming message for the user. Your response should not go over 180 characters.'''

# Briefing Prompt

def __create_system_briefing_message(language_code: str, briefing_configuration: BriefingConfiguration) -> str:
    briefing_configuration_format_param = ", structured in bullet points" if briefing_configuration != BriefingConfiguration.FULL_SUMMARY else ""
    main_instruction = f'''A mental health practitioner is entering our Practice Management Platform.
    They are about to meet with an existing patient, and need to quickly refreshen on the patient's history.
    Your job is to provide a summary of the patient's history broken down into two sections: Most Recent Sessions, and Historical Themes. If there's no data for a particular section, simply omit it, and summarize the information that you do find.
    Each section may take up to 800 characters. You may use the session_date value found in the metadata for navigating through the sessions' data.
    Use only the information you find based on the metadata session_date values (even if it results in a shorter summary).
    We're aiming for accuracy and quality, not quantity. Return a JSON object with a single key, 'summary', written in English, and the summary response as its only value{briefing_configuration_format_param}.
    It is very important that the summary response is written using language code {language_code}.'''
    json_example = r'''\nFor example, a response for language code es-419 would look like: {{"summary": "Sesiones más recientes:\nEn las últimas sesiones, Juan ha hablado sobre la dificultad para equilibrar su vida laboral y personal.\n\nTemas históricos:\nJuan ha luchado con problemas de autoexigencia y perfeccionismo."}}'''
    return main_instruction + json_example

def __create_user_briefing_message(therapist_name: str,
                                  therapist_gender: str,
                                  patient_name: str,
                                  patient_gender: str,
                                  session_number: int,
                                  language_code: str,
                                  briefing_configuration: BriefingConfiguration) -> str:
    try:
        ordinal_session_number = num2words(session_number, to='ordinal_num')
        context_paragraph =('''We have provided context information below. \n
                            ---------------------\n
                            {context_str}
                            \n---------------------\n''')
        instruction = "{query_str}"
        name_params = f"\nAddress the therapist by their name, {therapist_name}, and the patient by theirs, which is {patient_name}.\n"
        gender_params = ""
        if gender_has_default_pronouns(therapist_gender):
            gender_params += f"For reference, {therapist_name} is a {therapist_gender}. "
        if gender_has_default_pronouns(patient_gender):
            gender_params += f"For reference, {patient_name} is a {patient_gender}. "

        content_params = f"\nIt is very important that the summary is written using language code {language_code}"
        message = context_paragraph + instruction + name_params + gender_params + content_params

        if briefing_configuration.value == "full_summary":
            message += f"\nStart by reminding the therapist that they are seeing {patient_name} for the {ordinal_session_number} time."

        return message
    except Exception as e:
        raise Exception(e)

def create_briefing_template(language_code: str,
                             patient_name: str,
                             patient_gender: str,
                             therapist_name: str,
                             therapist_gender: str,
                             session_number: int,
                             configuration: BriefingConfiguration) -> ChatPromptTemplate:
    briefing_message_templates = [
        ChatMessage(
            role=MessageRole.SYSTEM,
            content=__create_system_briefing_message(language_code=language_code,
                                                    briefing_configuration=configuration),
        ),
        ChatMessage(
            role=MessageRole.USER,
            content=__create_user_briefing_message(language_code=language_code,
                                                  patient_name=patient_name,
                                                  patient_gender=patient_gender,
                                                  therapist_name=therapist_name,
                                                  therapist_gender=therapist_gender,
                                                  session_number=session_number,
                                                  briefing_configuration=configuration),
        ),
    ]
    return ChatPromptTemplate(briefing_message_templates)

# Question Suggestions

def __create_system_question_suggestions_message(language_code: str) -> str:
    main_instruction = f'''A mental health practitioner has entered our Practice Management Platform to look at their patient's dashboard. 
    They have the opportunity to ask you a question about the patient's session history.
    Your job is to provide the practitioner with three questions that they could ask you about the patient, for which you'd have rich answers.
    You may use the session date found in the metadata for navigating through the sessions' data. 
    It is very important that each question remains under 60 characters of length. Avoid questions like "What happened during the session of 04/10/2022?" and instead aim for narrow-focused questions like "When has the patient talked about his childhood?"
    Return a JSON object with a key titled "questions", written in English, and the array of questions as its value.
    It is very important that the content of each question is written using language code {language_code}.'''
    json_example = r'''\nFor example, a response for language code es-419 would look like: {{"questions": ["¿Cuándo fue la última vez que hablamos del divorcio?", "¿Qué fue lo último que revisamos en sesión?", "¿Qué tema sería beneficioso retomar con el paciente?"]}}'''
    return main_instruction + json_example

def __create_user_question_suggestions_message(language_code: str,
                                               patient_name: str,
                                               patient_gender: str) -> str:
    try:
        context_paragraph =('''We have provided context information below. \n
                            ---------------------\n
                            {context_str}
                            \n---------------------\n''')
        if gender_has_default_pronouns(patient_gender):
            patient_context = f"\nFor reference, the patient is a {patient_gender}, and their name is {patient_name}."
        else:
            patient_context = f"\nFor reference, the patient's name is {patient_name}."
        execution_statement = "\nGiven this information, please answer the question: {query_str}\n"
        length_param = f"\nIt is very important that each question is written using language code {language_code}, and that it remains under 50 characters of length."
        return context_paragraph + patient_context + execution_statement + length_param
    except Exception as e:
        raise Exception(e)

def create_question_suggestions_template(language_code: str,
                                         patient_name: str,
                                         patient_gender: str) -> ChatPromptTemplate:
    question_suggestions_templates = [
        ChatMessage(
            role=MessageRole.SYSTEM,
            content=__create_system_question_suggestions_message(language_code),
        ),
        ChatMessage(
            role=MessageRole.USER,
            content=__create_user_question_suggestions_message(language_code=language_code,
                                                               patient_name=patient_name,
                                                               patient_gender=patient_gender),
        ),
    ]
    return ChatPromptTemplate(question_suggestions_templates)

# Frequent Topics

def __create_system_frequent_topics_message(language_code: str) -> str:
    main_instruction = f'''A mental health practitioner has entered our Practice Management Platform to look at their patient's dashboard. 
    They want to gain insight into what are the most frequent topics that the patient has spoken about in their whole session history.
    Your job is to provide the practitioner with the patient's three most frequent topics, as well as the topic's respective percentage.
    For example, for a patient that has spoken equally about three topics, each topic porcentage would be 33.3%. Do not return topics with 0%, instead return only the topics that have more than 0%.
    You may use the session date found in the metadata for navigating through the sessions' data. 
    It is very important that each topic remain under 25 characters of length.
    Return a JSON object with a single key titled "topics", written in English, and its only value being an array containing up to three objects. 
    Each object should have two keys titled "topic" and "percentage", written in English, and the content of each key's value needs to be written in language code {language_code}.'''
    json_example = r'''\nFor example, a response for language code es-419 where the patient spoke equally about the three topics would look like: {{"topics":[{{"topic": "Ansiedad por el trabajo", "percentage": "33%"}},{{"topic": "Mejora en el matrimonio", "percentage": "33%"}},{{"topic": "Pensando en adoptar", "percentage": "33%"}}]}}'''
    return main_instruction + json_example

def __create_user_frequent_topics_message(language_code: str,
                                          patient_name: str,
                                          patient_gender: str) -> str:
    try:
        context_paragraph =('''We have provided context information below. \n
                            ---------------------\n
                            {context_str}
                            \n---------------------\n''')

        if gender_has_default_pronouns(patient_gender):
            patient_context = f"\nFor reference, the patient is a {patient_gender}, and their name is {patient_name}."
        else:
            patient_context = f"\nFor reference, the patient's name is {patient_name}."
        execution_statement = "\nGiven this information, please answer the question: {query_str}\n"
        content_params = f"\nIt is very important that each topic is written using language code {language_code}, and that it remain under 25 characters of length."
        return context_paragraph + patient_context + execution_statement + content_params
    except Exception as e:
        raise Exception(e)

def create_frequent_topics_template(language_code: str,
                                    patient_name: str,
                                    patient_gender: str) -> ChatPromptTemplate:
    frequent_topics_templates = [
        ChatMessage(
            role=MessageRole.SYSTEM,
            content=__create_system_frequent_topics_message(language_code),
        ),
        ChatMessage(
            role=MessageRole.USER,
            content=__create_user_frequent_topics_message(language_code=language_code,
                                                          patient_name=patient_name,
                                                          patient_gender=patient_gender),
        ),
    ]
    return ChatPromptTemplate(frequent_topics_templates)

# Session Entry Summary Prompt

def create_system_session_summary_message() -> str:
    return '''A mental health practitioner just met with a patient, and is ready to upload their session notes into our platform.
    Your job is to come up with a short summary about the session notes to be used as a label for quick retrievals in the future.
    Ideally, by just looking at your summary one should know exactly what information is contained in the full set of notes.
    It is very important that you don't mention the patient's name inside the summary for privacy purposes. Refer to the patient as "the patient".
    When generating the output you should use a format that you consider ideal for navigating data quickly. Imagine you are going to be consuming the summary yourself.'''

def create_user_session_summary_message(session_notes: str, patient_name: str) -> str:
    return f'''Write a summary label for the session notes below.
    It is very important that you don't mention the patient's name, {patient_name}, inside the summary for privacy purposes.
    Refer to the patient as "the patient".
    Here are the raw notes:\n{session_notes}.'''

# SOAP Template Prompt

def create_system_soap_template_message() -> str:
    return '''A mental health practitioner just met with a patient, and is ready to upload their session notes into our platform.
    Your job is to adapt their session notes into the SOAP format. The acronym SOAP stands for Subjective, Objective, Assessment, and Plan.
    You should take what the practitioner wrote, and break it down into each of these sections.
    If there is a section that can't be populated because there isn't enough information from the session notes, just leave it blank.
    Return a JSON object with four keys, "subjective", "objective", "assessment", and "plan". The keys should be written in English.
    You should detect the language in which the session notes was written, and use the same language for generating each key's respective string value within the JSON object.'''

def create_user_soap_template_message(session_notes: str) -> str:
    return f'''Adapt the following session notes into the SOAP format:\n{session_notes}.'''
