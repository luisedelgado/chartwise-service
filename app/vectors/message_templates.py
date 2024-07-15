from datetime import datetime

from llama_index.core.prompts import ChatPromptTemplate
from llama_index.core.llms import ChatMessage, MessageRole
from num2words import num2words
from pytz import timezone

from ..internal.model import SummaryConfiguration
from ..internal.utilities.general_utilities import gender_has_default_pronouns

# Text QA Prompt

def __create_system_qa_message() -> str:
    return '''A therapist is using you to ask questions about their patients' notes. 
    Your job is to answer the therapist's questions based on the information context you find from the sessions' data.
    For any information you reference, always outline the session date found in the metadata. If no session information is found, do not mention any dates.
    If the question references a person other than the patient, for whom you can't find information in the session notes, you should strictly say you can't provide an answer.
    Responses with "There's no mention of that in the notes" or "Based on the context I don't have an answer" or no documents returned are considered poor responses.
    Responses where the question appears to be answered are considered good. Responses that contain detailed answers are considered the best.
    Also, use your own judgement in analyzing if the question asked is actually answered in the response.'''

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

# Summary Prompt

def __create_system_summary_message(language_code: str, summary_configuration: SummaryConfiguration) -> str:
    summary_configuration_format_param = ", structured in bullet points" if summary_configuration != SummaryConfiguration.FULL_SUMMARY else ""
    main_instruction = f'''A mental health practitioner is entering our Practice Management Platform.
    They are about to meet with an existing patient, and need to quickly refreshen on the patient's history.
    Your job is to provide a summary of the patient's history broken down into two sections: Most Recent Sessions, and Historical Themes. If there's no data for a particular section, simply omit it, and summarize the information that you do find.
    Each section may take up to 800 characters. You may use the session date found in the metadata for navigating through the sessions' data.
    Particularly for patients with a short session history, use only the information you find from the metadata session dates (even if it results in a shorter summary).
    The "less is more" principle applies. Return a JSON object with a single key, 'summary', written in English, and the summary response as its only value{summary_configuration_format_param}.
    It is very important that the summary response is written using language code {language_code}.'''
    json_example = r'''\nFor example, a response for language code es-419 would look like: {{"summary": "Sesiones más recientes:\nEn las últimas sesiones, Juan ha hablado sobre la dificultad para equilibrar su vida laboral y personal.\n\nTemas históricos:\nJuan ha luchado con problemas de autoexigencia y perfeccionismo."}}'''
    return main_instruction + json_example

def __create_user_summary_message(therapist_name: str,
                                  therapist_gender: str,
                                  patient_name: str,
                                  patient_gender: str,
                                  session_number: int,
                                  language_code: str,
                                  summary_configuration: SummaryConfiguration) -> str:
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

        if summary_configuration.value == "full_summary":
            message += f"\nStart by reminding the therapist that they are seeing {patient_name} for the {ordinal_session_number} time."

        return message
    except Exception as e:
        raise Exception(e)

def create_summary_template(language_code: str,
                            patient_name: str,
                            patient_gender: str,
                            therapist_name: str,
                            therapist_gender: str,
                            session_number: int,
                            configuration: SummaryConfiguration) -> ChatPromptTemplate:
    summary_message_templates = [
        ChatMessage(
            role=MessageRole.SYSTEM,
            content=__create_system_summary_message(language_code=language_code,
                                                    summary_configuration=configuration),
        ),
        ChatMessage(
            role=MessageRole.USER,
            content=__create_user_summary_message(language_code=language_code,
                                                  patient_name=patient_name,
                                                  patient_gender=patient_gender,
                                                  therapist_name=therapist_name,
                                                  therapist_gender=therapist_gender,
                                                  session_number=session_number,
                                                  summary_configuration=configuration),
        ),
    ]
    return ChatPromptTemplate(summary_message_templates)

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
