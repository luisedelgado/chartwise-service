from ..api.deepgram_base_class import DeepgramBaseClass

class FakeDeepgramClient(DeepgramBaseClass):

    diarize_audio_invoked = False
    transcribe_audio_invoked = False

    async def transcribe_audio(
        self,
        audio_file_url: str
    ) -> str:
        self.transcribe_audio_invoked = True
        return "fake transcription"

    async def diarize_audio(
        self,
        audio_file_url: str
    ) -> str:
        self.diarize_audio_invoked = True
        return "fake diarization"
