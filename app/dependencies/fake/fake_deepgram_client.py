from typing import Tuple

from ..api.deepgram_base_class import DeepgramBaseClass
from ..api.templates import SessionNotesTemplate
from ...dependencies.api.openai_base_class import OpenAIBaseClass
from ...managers.assistant_manager import AssistantManager
from ...managers.auth_manager import AuthManager

class FakeDeepgramClient(DeepgramBaseClass):

    async def transcribe_audio(self,
                               auth_manager: AuthManager,
                               therapist_id: str,
                               session_id: str,
                               file_full_path: str,
                               openai_client: OpenAIBaseClass,
                               assistant_manager: AssistantManager,
                               template: SessionNotesTemplate,
                               diarize: bool = False) -> str:
        return "fake transcription"

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
        return ("fake summary", "fake diarization")
