from abc import ABC

from fastapi import BackgroundTasks

from ..api.supabase_factory_base_class import SupabaseFactoryBaseClass
from ...managers.auth_manager import AuthManager

class SpeechmaticsBaseClass(ABC):

    """
    Diarizes an audio file based on the incoming data.

    Arguments:
    auth_manager – the auth manager to be leveraged internally.
    therapist_id – the therapist id associated with the operation.
    background_tasks – the object to schedule concurrent tasks.
    session_id – the session id.
    file_full_path – the audio file's full path.
    file_name – the audio's file name.
    supabase_client_factory – the supabase client factory to be leveraged internally.
    session_auth_token – the session auth token.
    endpoint url – the endpoint's url.
    """
    def diarize_audio(auth_manager: AuthManager,
                      therapist_id: str,
                      background_tasks: BackgroundTasks,
                      session_id: str,
                      file_full_path: str,
                      supabase_client_factory: SupabaseFactoryBaseClass,
                      session_auth_token: str,
                      endpoint_url: str,
                      file_name: str) -> str:
        pass
