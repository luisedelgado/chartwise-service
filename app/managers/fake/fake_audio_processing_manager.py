from fastapi import File, UploadFile

from ...api.audio_processing_base_class import AudioProcessingManagerBaseClass

class FakeAudioProcessingManager(AudioProcessingManagerBaseClass):
    async def transcribe_audio_file(self,
                                    audio_file: UploadFile = File(...)) -> str:
        return ""

    def get_diarization_notifications_ips(self) -> list:
        return []

    def diarization_config(self,
                           auth_token: str,
                           endpoint_url: str):
        return {}

    async def diarize_audio_file(self,
                                 session_auth_token: str,
                                 endpoint_url: str,
                                 audio_file: UploadFile = File(...)) -> str:
        return ""
