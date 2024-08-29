from abc import ABC
from fastapi import BackgroundTasks
from typing import Tuple

from .templates import SessionNotesTemplate
from ...dependencies.api.openai_base_class import OpenAIBaseClass
from ...dependencies.api.supabase_factory_base_class import SupabaseFactoryBaseClass
from ...managers.assistant_manager import AssistantManager
from ...managers.auth_manager import AuthManager

class DeepgramBaseClass(ABC):

    """
    Transcribes an audio file, and returns the text.

    Arguments:
    auth_manager – the auth manager to be leveraged internally.
    therapist_id – the therapist id associated with the operation.
    session_id – the session id.
    file_full_path – the local file copy's full path.
    openai_client – the openai client to be used internally.
    assistant_manager – the assistant manager to be leveraged internally.
    template – the template to be applied to the output.
    diarize – flag indicating whether the audio should be diarized or not.
    """
    async def transcribe_audio(auth_manager: AuthManager,
                               therapist_id: str,
                               session_id: str,
                               file_full_path: str,
                               openai_client: OpenAIBaseClass,
                               assistant_manager: AssistantManager,
                               template: SessionNotesTemplate,
                               diarize: bool = False) -> str:
        pass

    """
    Diarizes an audio file based on the incoming data.

    Arguments:
    auth_manager – the auth manager to be leveraged internally.
    therapist_id – the therapist id associated with the operation.
    patient_id – the patient id associated with the operation.
    language_code – the language_code to be used for the diarization summary.
    session_id – the session id.
    file_full_path – the audio file's full path.
    openai_client – the openai client to be used internally.
    assistant_manager – the assistant manager to be leveraged internally.
    template – the template to be applied to the output.
    """
    async def diarize_audio(self,
                            auth_manager: AuthManager,
                            therapist_id: str,
                            patient_id: str,
                            language_code: str,
                            session_id: str,
                            file_full_path: str,
                            openai_client: OpenAIBaseClass,
                            assistant_manager: AssistantManager,
                            template: SessionNotesTemplate) -> Tuple[str, str]:
        pass
