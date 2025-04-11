from abc import ABC, abstractmethod

class DeepgramBaseClass(ABC):

    @abstractmethod
    async def transcribe_audio(audio_file_url: str) -> str:
        """
        Transcribes an audio file, and returns the text.

        Arguments:
        audio_file_url – the audio file's URL.
        """
        pass

    @abstractmethod
    async def diarize_audio(audio_file_url: str):
        """
        Diarizes an audio file based on the incoming data.

        Arguments:
        audio_file_url – the audio file's URL.
        """
        pass
