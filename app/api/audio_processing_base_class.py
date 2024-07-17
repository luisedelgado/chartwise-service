from abc import ABC

from fastapi import File, UploadFile

from ..api.assistant_base_class import AssistantManagerBaseClass
from ..api.auth_base_class import AuthManagerBaseClass
from ..internal.model import SessionNotesTemplate

class AudioProcessingManagerBaseClass(ABC):
    """
    Returns the incoming audio's transcription.
    Arguments:
    auth_manager – the auth manager to be leveraged internally.
    assistant_manager – the assistant manager to be leveraged internally.
    template – the template to be used for returning the output.
    therapist_id – the therapist id associated with the audio file.
    endpoint_name – the name of the endpoint that triggered this flow.
    api_method – the method of the api that triggered this flow.
    audio_file – the audio file to be transcribed.
    """
    async def transcribe_audio_file(auth_manager: AuthManagerBaseClass,
                                    assistant_manager: AssistantManagerBaseClass,
                                    template: SessionNotesTemplate,
                                    therapist_id: str,
                                    endpoint_name: str,
                                    api_method: str,
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
    session_auth_token – the access_token associated with the current server session.
    endpoint_url – the endpoint url to be used for making the request.
    audio_file – the audio file to be diarized.
    """
    async def diarize_audio_file(auth_manager: AuthManagerBaseClass,
                                 session_auth_token: str,
                                 endpoint_url: str,
                                 audio_file: UploadFile = File(...)) -> str:
        pass
