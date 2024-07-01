from fastapi import File, UploadFile

from ...api.auth_base_class import AuthManagerBaseClass
from ...api.audio_processing_base_class import AudioProcessingManagerBaseClass

class FakeAudioProcessingManager(AudioProcessingManagerBaseClass):

    FAKE_TRANSCRIPTION_RESULT = "A frog leaping upward off his lily pad is pulled downward by gravity..."
    FAKE_JOB_ID = "9876"

    async def transcribe_audio_file(self,
                                    auth_manager: AuthManagerBaseClass,
                                    audio_file: UploadFile = File(...)) -> str:
        return self.FAKE_TRANSCRIPTION_RESULT

    def get_diarization_notifications_ips(self) -> list:
        return []

    def diarization_config(self,
                           auth_token: str,
                           endpoint_url: str):
        return {}

    async def diarize_audio_file(self,
                                 auth_manager: AuthManagerBaseClass,
                                 session_auth_token: str,
                                 endpoint_url: str,
                                 audio_file: UploadFile = File(...)) -> str:
        return self.FAKE_JOB_ID
