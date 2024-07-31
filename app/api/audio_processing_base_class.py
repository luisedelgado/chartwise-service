from abc import ABC

from fastapi import File, UploadFile

from ..api.assistant_base_class import AssistantManagerBaseClass
from ..api.auth_base_class import AuthManagerBaseClass
from ..api.supabase_factory_base_class import SupabaseFactoryBaseClass
from ..internal.model import SessionNotesTemplate

class AudioProcessingManagerBaseClass(ABC):
    """
    Returns the incoming audio's transcription.
    Arguments:
    auth_manager – the auth manager to be leveraged internally.
    assistant_manager – the assistant manager to be leveraged internally.
    template – the template to be used for returning the output.
    therapist_id – the therapist id associated with the audio file.
    session_id – the session id.
    audio_file – the audio file to be transcribed.
    """
    async def transcribe_audio_file(auth_manager: AuthManagerBaseClass,
                                    assistant_manager: AssistantManagerBaseClass,
                                    template: SessionNotesTemplate,
                                    therapist_id: str,
                                    session_id: str,
                                    audio_file: UploadFile = File(...)) -> str:
        pass

    """
    Returns the incoming audio's transcription.
    Arguments:
    auth_token – the auth_token to be used.
    endpoint_url – the endpoint url.
    """
    def diarization_config(auth_token: str, endpoint_url: str):
        pass

    """
    Queues a new job for a diarization transcription using the incoming audio file.
    Returns the job id that is processing.

    Arguments:
    auth_manager – the auth manager to be leveraged internally.
    supabase_manager_factory – the supabase factory to leverage internally.
    session_auth_token – the access_token associated with the current server session.
    endpoint_url – the endpoint url to be used for making the request.
    session_id – the session id.
    audio_file – the audio file to be diarized.
    """
    async def diarize_audio_file(auth_manager: AuthManagerBaseClass,
                                 supabase_manager_factory: SupabaseFactoryBaseClass,
                                 session_auth_token: str,
                                 endpoint_url: str,
                                 session_id: str,
                                 audio_file: UploadFile = File(...)) -> str:
        pass
