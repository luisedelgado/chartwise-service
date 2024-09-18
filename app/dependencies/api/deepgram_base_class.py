from abc import ABC

class DeepgramBaseClass(ABC):

    """
    Transcribes an audio file, and returns the text.

    Arguments:
    file_full_path – the audio file's full path.
    """
    async def transcribe_audio(file_full_path: str) -> str:
        pass

    """
    Diarizes an audio file based on the incoming data.

    Arguments:
    file_full_path – the audio file's full path.
    """
    async def diarize_audio(file_full_path: str):
        pass
