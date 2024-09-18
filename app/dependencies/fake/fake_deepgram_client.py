from ..api.deepgram_base_class import DeepgramBaseClass

class FakeDeepgramClient(DeepgramBaseClass):

    async def transcribe_audio(self,
                               file_full_path: str) -> str:
        return "fake transcription"

    async def diarize_audio(self,
                            file_full_path: str) -> str:
        return "fake diarization"
