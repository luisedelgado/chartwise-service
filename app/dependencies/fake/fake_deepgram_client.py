from ..api.deepgram_base_class import DeepgramBaseClass

class FakeDeepgramClient(DeepgramBaseClass):

    async def transcribe_audio(self,
                               audio_file_url: str) -> str:
        return "fake transcription"

    async def diarize_audio(self,
                            audio_file_url: str) -> str:
        return "fake diarization"
