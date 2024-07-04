from datetime import datetime

from llama_index.core.prompts import ChatPromptTemplate
from llama_index.core.llms import ChatMessage, MessageRole
from num2words import num2words
from pytz import timezone

from ..internal.utilities.general_utilities import gender_has_default_pronouns

# Text QA Prompt

def __create_system_qa_message() -> str:
    return '''A therapist is using you to ask questions about their patients' notes. 
    Your job is to answer the therapist's questions based on the information context you find from the sessions.
    For any information you reference, always outline the session date found in the metadata. 
    If the question references a person for whom you can't find information in the session notes, you should strictly say you can't provide an answer.'''

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

def __create_system_summary_message() -> str:
    return f'''A mental health practitioner is entering our Practice Management Platform.
    They are about to meet with an existing patient, and need to quickly refreshen on the patient's history.
    Your job is to provide a summary of the patient's most recent sessions, as well as big themes that have come up historically during sessions (if any).
    You may use the session date found in the metadata for navigating through the sessions' data. The output should be structured in bullet points.
    Particularly for patients with a short session history, use only the information you find from the metadata session dates (even if it results in a shorter summary).
    The "less is more" principle applies.'''

def __create_user_summary_message(therapist_name: str,
                                  therapist_gender: str,
                                  patient_name: str,
                                  patient_gender: str,
                                  language_code: str,
                                  session_number: int) -> str:
    try:
        ordinal_session_number = num2words(session_number, to='ordinal_num')
        context_paragraph =('''We have provided context information below. \n
                            ---------------------\n
                            {context_str}
                            \n---------------------\n''')
        instruction = "{query_str}"
        therapist_gender_context = f"For reference, {therapist_name} is a {therapist_gender}." if gender_has_default_pronouns(therapist_gender) else ""
        patient_gender_context = f"For reference, {patient_name} is a {patient_gender}." if gender_has_default_pronouns(patient_gender) else ""
        params = f'''\nAddress the therapist by their name, {therapist_name}, and the patient by theirs, which is {patient_name}.
        {therapist_gender_context}
        {patient_gender_context}
        Start by reminding the therapist that they are seeing {patient_name} for the {ordinal_session_number} time.
        It is very important that you craft your response using language code {language_code}. Your response should not go over 600 characters.'''
        return context_paragraph + instruction + params
    except Exception as e:
        raise Exception(e)

def create_summary_template(language_code: str,
                            patient_name: str,
                            patient_gender: str,
                            therapist_name: str,
                            therapist_gender: str,
                            session_number: int) -> ChatPromptTemplate:
    summary_message_templates = [
        ChatMessage(
            role=MessageRole.SYSTEM,
            content=__create_system_summary_message(),
        ),
        ChatMessage(
            role=MessageRole.USER,
            content=__create_user_summary_message(language_code=language_code,
                                                  patient_name=patient_name,
                                                  patient_gender=patient_gender,
                                                  therapist_name=therapist_name,
                                                  therapist_gender=therapist_gender,
                                                  session_number=session_number),
        ),
    ]
    return ChatPromptTemplate(summary_message_templates)

# Question Suggestions

def __create_system_question_suggestions_message() -> str:
    return f'''A mental health practitioner has entered our Practice Management Platform to look at their patient's dashboard. 
    They have the opportunity to ask you a question about the patient's session history.
    Your job is to provide the practitioner with three questions that they could ask you about the patient, for which you'd have rich answers.
    You may use the session date found in the metadata for navigating through the sessions' data. 
    The questions should be as concise as possible. Return a JSON array with a single key, "questions", and the array of questions as its value.'''

def __create_user_question_suggestions_message(language_code: str,
                                               patient_name: str,
                                               patient_gender: str) -> str:
    try:
        context_paragraph =('''We have provided context information below. \n
                            ---------------------\n
                            {context_str}
                            \n---------------------\n''')
        language_code_requirement = f"\nIt is very important that you craft your response using language code {language_code}."

        if gender_has_default_pronouns(patient_gender):
            patient_context = f"\nFor reference, the patient is a {patient_gender}, and their name is {patient_name}."
        else:
            patient_context = f"\nFor reference, the patient's name is {patient_name}."
        execution_statement = "\nGiven this information, please answer the question: {query_str}\n"
        return context_paragraph + language_code_requirement + patient_context + execution_statement
    except Exception as e:
        raise Exception(e)

def create_question_suggestions_template(language_code: str,
                                         patient_name: str,
                                         patient_gender: str) -> ChatPromptTemplate:
    question_suggestions_templates = [
        ChatMessage(
            role=MessageRole.SYSTEM,
            content=__create_system_question_suggestions_message(),
        ),
        ChatMessage(
            role=MessageRole.USER,
            content=__create_user_question_suggestions_message(language_code=language_code,
                                                               patient_name=patient_name,
                                                               patient_gender=patient_gender),
        ),
    ]
    return ChatPromptTemplate(question_suggestions_templates)
