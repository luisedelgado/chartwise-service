from llama_index.core.prompts import ChatPromptTemplate
from llama_index.core.llms import ChatMessage, MessageRole

# Text QA Prompt

qa_message_user_template = (
    '''We have provided context information below. \n
    ---------------------\n
    {context_str}
    \n---------------------\n
    If the question references a person other than the patient, and they are not mentioned in the session notes, you should 
    strictly say you can't provide an answer because you don't know who that person is. If you reference session notes, outline 
    all the respective session dates after your answer. Otherwise do not reference any session dates.\nGiven this information, please answer 
    the question: {query_str}\n'''
)

qa_chat_message_content = '''A mental health practitioner is using you to ask questions 
about their patient's session notes. These notes were written by the practitioner themselves, 
so they just need help freshening up on details that they may not remember. 
You must act as a professional agent, and support the practitioner in finding relevant data.'''

qa_messages = [
    ChatMessage(
        role=MessageRole.SYSTEM,
        content=qa_chat_message_content,
    ),
    ChatMessage(
        role=MessageRole.USER,
        content=qa_message_user_template,
    ),
]
qa_template = ChatPromptTemplate(qa_messages)

# Refine Prompt

refine_message_user_template = '''The original question is as follows: {query_str}\nWe have provided an 
existing answer: {existing_answer}\nWe have the opportunity to refine the existing answer (only if needed) 
with some more context below.\n------------\n{context_msg}\n------------\nUsing both the new context and 
your own knowledge, update or repeat the existing answer.\n'''

refine_chat_message_content = '''A mental health practitioner is using you to ask questions 
about their patient's session notes. When refining an answer you always integrate the new context 
into the original answer, and provide the resulting response. You should never reference the original 
answer or context directly in your answer. If you reference session notes, outline all session dates after your answer. 
Otherwise do not reference any session dates.'''

refine_messages = [
    ChatMessage(
        role=MessageRole.SYSTEM,
        content=(refine_chat_message_content),
    ),
    ChatMessage(
        role=MessageRole.USER,
        content=(refine_message_user_template),
    ),
]
refine_template = ChatPromptTemplate(refine_messages)
