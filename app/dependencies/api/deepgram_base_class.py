from abc import ABC

from .templates import SessionNotesTemplate
from ...dependencies.api.openai_base_class import OpenAIBaseClass
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
    template – the template to be applied to the output.
    """
    async def transcribe_audio(auth_manager: AuthManager,
                               therapist_id: str,
                               session_id: str,
                               file_full_path: str,
                               openai_client: OpenAIBaseClass,
                               assistant_manager: AssistantManager,
                               template: SessionNotesTemplate) -> str:
        pass
