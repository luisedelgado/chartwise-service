from ..api.speechmatics_base_class import SpeechmaticsBaseClass
from ..api.supabase_factory_base_class import SupabaseFactoryBaseClass
from ...managers.auth_manager import AuthManager

class SpeechmaticsClient(SpeechmaticsBaseClass):

    async def diarize_audio(self,
                            auth_manager: AuthManager,
                            session_id: str,
                            file_full_path: str,
                            supabase_client_factory: SupabaseFactoryBaseClass,
                            session_auth_token: str,
                            endpoint_url: str,
                            file_name: str) -> str:
        pass
