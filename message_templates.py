import calendar
from datetime import date
from llama_index.core.prompts import ChatPromptTemplate
from llama_index.core.llms import ChatMessage, MessageRole

# Text QA Prompt

def _create_system_qa_message() -> str:
    return '''A mental health practitioner is using you to ask questions 
    about their patient's session notes. These notes were written by the practitioner themselves, 
    so they just need help freshening up on details that they may not remember. 
    You must act as a professional agent, and support the practitioner by fetching data.'''

def _create_user_qa_message(language_code: str) -> str:
    message_content = (
    '''We have provided context information below. \n
    ---------------------\n
    {context_str}
    \n---------------------\n
    If the question references a person other than the patient, and they are not mentioned in the session notes, you should 
    strictly say you can't provide an answer because you don't know who that person is. If you do reference session notes, outline 
    all the respective session dates after your answer. Otherwise do not reference any session dates.''')
    language_code_requirement = f"\nTo craft your response use language {language_code}."
    execution_statement = "\nGiven this information, please answer the question: {query_str}\n"
    return message_content + language_code_requirement + execution_statement

def create_chat_prompt_template(language_code: str) -> ChatPromptTemplate:
    qa_messages = [
        ChatMessage(
            role=MessageRole.SYSTEM,
            content=_create_system_qa_message(),
        ),
        ChatMessage(
            role=MessageRole.USER,
            content=_create_user_qa_message(language_code),
        ),
    ]
    return ChatPromptTemplate(qa_messages)

# Refine Prompt

def _create_system_refine_message() -> str:
    return '''A mental health practitioner is using you to ask questions 
    about their patient's session notes. When refining an answer you always integrate the new context 
    into the original answer, and provide the resulting response. You should never reference the original 
    answer or context directly in your answer. If you reference session notes, outline all session dates after your answer. 
    Otherwise do not reference any session dates.'''

def _create_user_refine_message(language_code: str):
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
            content=(_create_system_refine_message()),
        ),
        ChatMessage(
            role=MessageRole.USER,
            content=(_create_user_refine_message(language_code)),
        ),
    ]
    return ChatPromptTemplate(refine_messages)

# Greeting Prompt

def create_system_greeting_message(name: str) -> str :
    today_date = date.today()
    weekday = calendar.day_name[today_date.weekday()]

    return f'''A mental health practitioner is using you to ask questions 
    about their patients' session notes. Your main job is to greet them while remaining professional: 
    Start by sending a cheerful message about today being {weekday}, and address them by their name, which is {name}. 
    Finish off with a short fragment on productivity.'''

def create_user_greeting_message(language_code: str) -> str:
    return f'''Write a welcoming message for the user. Remind them that you're here to help fetch anything from their session notes. 
    Your response should not go over 200 characters. To craft your response use language {language_code}.'''
