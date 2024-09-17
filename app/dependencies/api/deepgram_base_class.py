from abc import ABC

from .templates import SessionNotesTemplate
from ...dependencies.api.openai_base_class import OpenAIBaseClass

class DeepgramBaseClass(ABC):

    """
    Transcribes an audio file, and returns the text.

    Arguments:
    file_full_path – the audio file's full path.
    use_monitoring_proxy – flag to determine whether or not the monitoring proxy is used.
    monitoring_proxy_url – the optional url for the monitoring proxy.
    """
    async def transcribe_audio(file_full_path: str,
                               use_monitoring_proxy: bool,
                               monitoring_proxy_url: str = None) -> str:
        pass

    """
    Diarizes an audio file based on the incoming data.

    Arguments:
    file_full_path – the audio file's full path.
    use_monitoring_proxy – flag to determine whether or not the monitoring proxy is used.
    monitoring_proxy_url – the optional url for the monitoring proxy.
    """
    async def diarize_audio(file_full_path: str,
                            use_monitoring_proxy: bool,
                            monitoring_proxy_url: str = None):
        pass
