from datetime import datetime

from llama_index.core.prompts import ChatPromptTemplate
from llama_index.core.llms import ChatMessage, MessageRole
from num2words import num2words
from pytz import timezone

# Text QA Prompt

def __create_system_qa_message() -> str:
    return '''A therapist is using you to ask questions about their patients' notes. 
If the question references a person that is not mentioned anywhere in the session notes, 
you should strictly say you can't provide an answer. For any information you reference, always outline the session date found in the metadata.'''

def __create_user_qa_message(language_code: str) -> str:
    message_content = (
    '''We have provided context information below. \n
    ---------------------\n
    {context_str}
    \n---------------------\n
    For any information you reference, please outline the session date found in the metadata. If you cannot provide an answer do not reference session dates.''')
    language_code_requirement = f"\nTo craft your response use language {language_code}."
    execution_statement = "\nGiven this information, please answer the question: {query_str}\n"
    return message_content + language_code_requirement + execution_statement

def create_chat_prompt_template(language_code: str) -> ChatPromptTemplate:
    qa_messages = [
        ChatMessage(
            role=MessageRole.SYSTEM,
            content=__create_system_qa_message(),
        ),
        ChatMessage(
            role=MessageRole.USER,
            content=__create_user_qa_message(language_code),
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
    language_code_requirement = f"\nTo craft your response use language {language_code}."
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

def create_system_greeting_message(name: str, tz_identifier: str, language_code: str) -> str | None:
    try:
        tz = timezone(tz_identifier)
        weekday = datetime.now(tz).strftime('%A')
        return f'''A mental health practitioner is entering our Practice Management Platform. Your job is to greet them into the experience.
        \nSend a cheerful message about today being {weekday}, and address them by their name, which is {name}. 
        \nTo craft your response use language {language_code}. Finish off with a short fragment on productivity.'''
    except Exception as e:
        raise Exception(str(e))

def create_user_greeting_message() -> str:
    return f'''Write a welcoming message for the user. Your response should not go over 180 characters.'''

# Summary Prompt

def create_system_summary_message() -> str | None:
    return f'''A mental health practitioner is entering our Practice Management Platform.
    They are about to meet with an existing patient, and need to quickly refreshen on the patient's history.
    Your job is to provide a useful summary of the patient's most recent sessions, as well as big themes that have come up historically during sessions.
    You may use the session date found in the metadata for navigating through the sessions' data. The output should be structured in bullet points.'''

def create_user_summary_message(therapist_name: str,
                                patient_name: str,
                                language_code: str,
                                session_number: int) -> str:
    try:
        ordinal_session_number = num2words(session_number, to='ordinal_num')
        return f'''Write a summary about the patient's session history.
        Address the therapist by their name, {therapist_name}, and the patient by their name, {patient_name}.
        Start by reminding the therapist that they are seeing {patient_name} for the {ordinal_session_number} time.
        To craft your response use language {language_code}. Your response should not go over 600 characters.'''
    except Exception as e:
        raise Exception(e)
