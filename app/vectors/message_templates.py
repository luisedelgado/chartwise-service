from datetime import datetime

from llama_index.core.prompts import ChatPromptTemplate
from llama_index.core.llms import ChatMessage, MessageRole
from num2words import num2words
from pytz import timezone

from ..internal.model import BriefingConfiguration
from ..internal.utilities.general_utilities import gender_has_default_pronouns

# Text QA Prompt

def create_qa_system_message() -> str:
    return '''A therapist is using you to ask questions about their patients' notes. 
    Your job is to answer the therapist's questions based on the information context you find from the sessions' data.
    You may use the session_date value found in the metadata for navigating through the sessions' data.
    You should always look first at the session_summary value found in the metadata to understand whether a given document is related to the question.
    If the session_summary value is related to the question, you should use it along session_text value to generate your response. 
    To answer a question in the best way possible, you should find the documents that are most related to the question. 
    For any information you reference, make sure you always outline the session_date value found in the metadata. If no session information is found, do not mention any session dates.
    If the question references a person other than the patient, for whom you can't find information in the session notes, you should strictly say you can't provide an answer.'''

def create_qa_user_message(context: str,
                           language_code: str,
                           patient_gender: str,
                           patient_name: str,
                           query_input: str) -> str:
    message_content = (
    f'''We have provided context information below. \n
    ---------------------\n
    {context}
    \n---------------------\n''')
    language_code_requirement = f"\nIt is very important that you craft your response using language code {language_code}."

    if gender_has_default_pronouns(patient_gender):
        patient_context = f"\nFor reference, the patient is a {patient_gender}, and their name is {patient_name}."
    else:
        patient_context = f"\nFor reference, the patient's name is {patient_name}."

    execution_statement = f"\nGiven this information, please answer the question: {query_input}\n"
    return message_content + language_code_requirement + patient_context + execution_statement

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

def create_system_message_briefing(language_code: str,
                                   therapist_name: str,
                                   therapist_gender: str,
                                   patient_name: str,
                                   patient_gender: str,
                                   session_number: int) -> str | None:
    try:
        ordinal_session_number = num2words(session_number, to='ordinal_num')
        main_instruction = f'''A mental health practitioner is entering our Practice Management Platform.
        They are about to meet with an existing patient, and need to quickly refreshen on the patient's history.
        Your job is to provide a summary of the patient's history broken down into two sections: Most Recent Sessions, and Historical Themes.
        If there's no data for a particular section, simply omit it, and summarize the information that you do find.
        Each section may take up to 800 characters. You may use the session_date value found in the metadata for navigating through the sessions' data.
        Use only the information you find based on the metadata session_date and session_text values (even if it results in a shorter summary).
        We're aiming for accuracy and quality, not quantity.
        Address the therapist by their name, {therapist_name}, and the patient by theirs, which is {patient_name}.
        Start by reminding the therapist that they are seeing {patient_name} for the {ordinal_session_number} time.'''
        gender_params = ""
        if gender_has_default_pronouns(therapist_gender):
            gender_params += f"For reference, {therapist_name} is a {therapist_gender}. "
        if gender_has_default_pronouns(patient_gender):
            gender_params += f"For reference, {patient_name} is a {patient_gender}. "
        output_format = f'''\nReturn only a JSON object with a single key, 'summary', written in English, and the summary response as its only value.
        It is very important that the summary response is written using language code {language_code}.'''
        output_example = r'''\nFor example, a response for language code es-419 would look like: {{"summary": "Sesiones más recientes:\nEn las últimas sesiones, Juan ha hablado sobre la dificultad para equilibrar su vida laboral y personal.\n\nTemas históricos:\nJuan ha luchado con problemas de autoexigencia y perfeccionismo."}}'''
        return main_instruction + gender_params + output_format + output_example
    except Exception as e:
        raise Exception(e)

def create_user_briefing_message(patient_name: str,
                                 language_code: str,
                                 configuration: BriefingConfiguration) -> str:
    try:
        instruction = ""
        if configuration == BriefingConfiguration.FULL_SUMMARY:
            instruction = f'''I'm coming up to speed with {patient_name}'s session notes.
            What do I need to remember, and what would be good avenues to explore in our upcoming session?'''
        elif configuration == BriefingConfiguration.PRIMARY_TOPICS:
            instruction = f'''I'm coming up to speed with {patient_name}'s session notes.
            What are the three primary topics associated with {patient_name}'s session history?
            Each bullet point should not take more than 50 characters.'''
        else:
            raise Exception("Invalid briefing configuration.")

        language_params = f"\n It is very important that your output is written using language code {language_code}"
        return (instruction + language_params)
    except Exception as e:
        raise Exception(e)

# Question Suggestions

def create_question_suggestions_system_message(language_code: str) -> str:
    main_instruction = f'''A mental health practitioner has entered our Practice Management Platform to look at their patient's dashboard. 
    They have the opportunity to ask you a question about the patient's session history.
    Your job is to provide the practitioner with three questions that they could ask you about the patient, for which you'd have rich answers.
    You may use the session date and session text found in the metadata for navigating through the sessions' data. 
    It is very important that each question remains under 60 characters of length. Avoid questions like "What happened during the session of 04/10/2022?" and instead aim for narrow-focused questions like "When has the patient talked about his childhood?"
    Return only a JSON object with a key titled "questions", written in English, and the array of questions as its value.
    It is very important that the content of each question is written using language code {language_code}.'''
    json_example = r'''\nFor example, a response for language code es-419 would look like: {{"questions": ["¿Cuándo fue la última vez que hablamos del divorcio?", "¿Qué fue lo último que revisamos en sesión?", "¿Qué tema sería beneficioso retomar con el paciente?"]}}'''
    return main_instruction + json_example

def create_question_suggestions_user_message(language_code: str,
                                             context: str,
                                             patient_name: str,
                                             query_input: str,
                                             patient_gender: str) -> str:
    try:
        context_paragraph =(f'''We have provided context information below. \n---------------------\n{context}\n---------------------\n''')
        if gender_has_default_pronouns(patient_gender):
            patient_context = f"\nFor reference, the patient is a {patient_gender}, and their name is {patient_name}."
        else:
            patient_context = f"\nFor reference, the patient's name is {patient_name}."
        execution_statement = f"\nGiven this information, please answer the user's question: {query_input}"
        length_param = f"\nIt is very important that each question is written using language code {language_code}, and that it remains under 50 characters of length."
        return context_paragraph + patient_context + execution_statement + length_param
    except Exception as e:
        raise Exception(e)

# Frequent Topics

def create_frequent_topics_system_message(language_code: str) -> str:
    main_instruction = f'''A mental health practitioner has entered our Practice Management Platform to look at their patient's dashboard. 
    They want to gain insight into what are the most frequent topics that the patient has spoken about in their whole session history.
    Your job is to provide the practitioner with the patient's three most frequent topics, as well as the topic's respective percentage.
    For example, for a patient that has spoken equally about three topics, each topic porcentage would be 33.3%. Do not return topics with 0%, instead return only the topics that have more than 0%.
    You may use the values for session date and session text found in the metadata for navigating through the sessions' data. 
    It is very important that each topic remain under 25 characters of length.
    Return only a JSON object with a single key titled "topics", written in English, and its only value being an array containing up to three objects. 
    Each object should have two keys titled "topic" and "percentage", written in English, and the content of each key's value needs to be written in language code {language_code}.'''
    json_example = r'''\nFor example, a response for language code es-419 where the patient spoke equally about the three topics would look like: {{"topics":[{{"topic": "Ansiedad por el trabajo", "percentage": "33%"}},{{"topic": "Mejora en el matrimonio", "percentage": "33%"}},{{"topic": "Pensando en adoptar", "percentage": "33%"}}]}}'''
    return main_instruction + json_example

def create_user_frequent_topics_message(language_code: str,
                                        context: str,
                                        patient_name: str,
                                        query_input: str,
                                        patient_gender: str) -> str:
    try:
        context_paragraph =(f'''We have provided context information below. \n
                            ---------------------\n
                            {context}
                            \n---------------------\n''')

        if gender_has_default_pronouns(patient_gender):
            patient_context = f"\nFor reference, the patient is a {patient_gender}, and their name is {patient_name}."
        else:
            patient_context = f"\nFor reference, the patient's name is {patient_name}."
        execution_statement = f"\nGiven this information, please answer the question: {query_input}\n"
        content_params = f"\nIt is very important that each topic is written using language code {language_code}, and that it remain under 25 characters of length."
        return context_paragraph + patient_context + execution_statement + content_params
    except Exception as e:
        raise Exception(e)

# Session Entry Summary Prompt

def create_system_session_summary_message() -> str:
    return '''A mental health practitioner just met with a patient, and is ready to upload their session notes into our platform.
    Your job is to come up with a short summary about the session notes to be used as a label for quick retrievals in the future.
    Ideally, by just looking at your summary one should know exactly what information is contained in the full set of notes.
    When generating the output you should use a format that you consider ideal for navigating data quickly. Imagine you are going to be consuming the summary yourself.
    You may use the values for session date and session text found in the metadata for navigating through the sessions notes' data.'''

def create_user_session_summary_message(session_notes: str, patient_name: str) -> str:
    return f'''Write a summary label for the session notes below. Here are the raw notes:\n\n{session_notes}.'''

# SOAP Template Prompt

def create_system_soap_template_message() -> str:
    return '''A mental health practitioner just met with a patient, and is ready to upload their session notes into our platform.
    Your job is to adapt their session notes into the SOAP format. The acronym SOAP stands for Subjective, Objective, Assessment, and Plan.
    "Subjective" is what brought the patient to the practitioner, including past history.
    "Objective" is the objective information that can be collected from the patient encounter.
    "Assessment" represents the practitioner's professional opinion in light of the subjective and objective findings.
    "Plan" is the set of actions proposed either by the practitioner or the patient for addressing the patient's problem(s).
    You should take what the practitioner wrote, and break it down into each of these sections. You may paraphrase information if you believe it will make it more readable.
    If there is a section that can't be populated because there isn't enough information from the session notes, just leave it blank.
    Return the new SOAP session notes as a string, with double line breaks between each category (Subjective, Objective, Assessment, and Plan), and single line breaks between a category's header and its content.
    It is very important that category headers are written in English but the category's content should be generated in the same language in which the practitioner's session notes were written.'''

def create_user_soap_template_message(session_notes: str) -> str:
    return f'''Adapt the following session notes into the SOAP format:\n{session_notes}.'''
