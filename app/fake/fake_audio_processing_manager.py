from fastapi import File, UploadFile

from ..api.audio_processing_base_class import AudioProcessingManagerBaseClass

class FakeAudioProcessingManager(AudioProcessingManagerBaseClass):
    async def transcribe_audio_file(audio_file: UploadFile = File(...)) -> str:
        return ""

    def get_diarization_notifications_ips() -> list:
        return []

    def diarization_config(auth_token: str, endpoint_url: str):
        return {}

    async def diarize_audio_file(self,
                                 session_auth_token: str,
                                 endpoint_url: str,
                                 audio_file: UploadFile = File(...)) -> str:
        return ""
