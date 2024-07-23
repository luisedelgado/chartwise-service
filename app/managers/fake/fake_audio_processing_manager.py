from fastapi import File, UploadFile

from ...api.assistant_base_class import AssistantManagerBaseClass
from ...api.auth_base_class import AuthManagerBaseClass
from ...api.audio_processing_base_class import AudioProcessingManagerBaseClass
from ...internal.model import SessionNotesTemplate

class FakeAudioProcessingManager(AudioProcessingManagerBaseClass):

    async def transcribe_audio_file(self,
                                    assistant_manager: AssistantManagerBaseClass,
                                    auth_manager: AuthManagerBaseClass,
                                    template: SessionNotesTemplate,
                                    therapist_id: str,
                                    session_id: str,
                                    audio_file: UploadFile = File(...)) -> str:
        return self.FAKE_TRANSCRIPTION_RESULT

    def diarization_config(self,
                           auth_token: str,
                           endpoint_url: str):
        return {}

    async def diarize_audio_file(self,
                                 auth_manager: AuthManagerBaseClass,
                                 session_auth_token: str,
                                 endpoint_url: str,
                                 session_id: str,
                                 audio_file: UploadFile = File(...)) -> str:
        return self.FAKE_JOB_ID

    FAKE_DIARIZATION_SUMMARY = "Messi and Zidane had an inspiring talk reminiscing about their careers as elite players."
    FAKE_TRANSCRIPTION_RESULT = "A frog leaping upward off his lily pad is pulled downward by gravity..."
    FAKE_JOB_ID = "9876"
    FAKE_DIARIZATION_RESULT = {
        "job":
        {
            "id": "m38xavr1g4"
        },
        "results":
        [
            {
                "alternatives":
                [
                    {
                        "confidence": 0.94,
                        "content": "Lo",
                        "language": "es",
                        "speaker": "S1"
                    }
                ],
                "end_time": 0.24,
                "start_time": 0.0,
                "type": "word"
            },
            {
                "alternatives":
                [
                    {
                        "confidence": 1.0,
                        "content": "creo",
                        "language": "es",
                        "speaker": "S1"
                    }
                ],
                "end_time": 0.45,
                "start_time": 0.24,
                "type": "word"
            },
            {
                "alternatives":
                [
                    {
                        "confidence": 1.0,
                        "content": "que",
                        "language": "es",
                        "speaker": "S1"
                    }
                ],
                "end_time": 0.54,
                "start_time": 0.45,
                "type": "word"
            },
            {
                "alternatives":
                [
                    {
                        "confidence": 0.86,
                        "content": "es",
                        "language": "es",
                        "speaker": "S1"
                    }
                ],
                "end_time": 0.6,
                "start_time": 0.54,
                "type": "word"
            },
            {
                "alternatives":
                [
                    {
                        "confidence": 1.0,
                        "content": "lo",
                        "language": "es",
                        "speaker": "S1"
                    }
                ],
                "end_time": 0.69,
                "start_time": 0.6,
                "type": "word"
            },
            {
                "alternatives":
                [
                    {
                        "confidence": 0.95,
                        "content": "más",
                        "language": "es",
                        "speaker": "S1"
                    }
                ],
                "end_time": 0.87,
                "start_time": 0.69,
                "type": "word"
            },
            {
                "alternatives":
                [
                    {
                        "confidence": 1.0,
                        "content": "reciente",
                        "language": "es",
                        "speaker": "S1"
                    }
                ],
                "end_time": 1.65,
                "start_time": 0.87,
                "type": "word"
            },
            {
                "alternatives":
                [
                    {
                        "confidence": 1.0,
                        "content": ".",
                        "language": "es",
                        "speaker": "S1"
                    }
                ],
                "attaches_to": "previous",
                "end_time": 1.65,
                "is_eos": True,
                "start_time": 1.65,
                "type": "punctuation"
            }
        ],
        "summary":
        {
            "content": "Temas clave:\n- Interpretación de personajes\n"
        }
    }
