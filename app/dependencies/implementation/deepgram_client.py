import json, os, requests

from deepgram import (
    DeepgramClient as DeepgramSDKClient,
    PrerecordedOptions,
    FileSource,
)
from fastapi import HTTPException, status
from httpx import Timeout

from ..api.deepgram_base_class import DeepgramBaseClass
from ...data_processing.diarization_cleaner import DiarizationCleaner
from ...internal.utilities import general_utilities

class DeepgramClient(DeepgramBaseClass):

    CONNECT_TIMEOUT = 300
    DIARIZATION_READ_TIMEOUT = 900
    DIARIZATION_WRITE_TIMEOUT = 300
    DIARIZATION_POOL_TIMEOUT = 300
    TRANSCRIPTION_READ_TIMEOUT = 120
    TRANSCRIPTION_WRITE_TIMEOUT = 40
    TRANSCRIPTION_POOL_TIMEOUT = 100
    DG_QUERY_PARAMS = "model=nova-2&smart_format=true&detect_language=true&utterances=true&numerals=true"

    async def diarize_audio(
        self,
        audio_file_url: str
    ) -> str:
        try:
            deepgram = DeepgramSDKClient(os.getenv("DG_API_KEY"))
            options = PrerecordedOptions(
                model="nova-2",
                smart_format=True,
                detect_language=True,
                utterances=True,
                numerals=True,
                diarize=True
            )

            # Increase the timeout to 300 seconds (5 minutes).
            cls = type(self)
            response = await deepgram.listen.asyncrest.v("1").transcribe_url(
                source={"url": audio_file_url},
                options=options,
                timeout=Timeout(
                    connect=cls.CONNECT_TIMEOUT,
                    read=cls.DIARIZATION_READ_TIMEOUT,
                    write=cls.DIARIZATION_WRITE_TIMEOUT,
                    pool=cls.DIARIZATION_POOL_TIMEOUT
                )
            )

            json_response = json.loads(response.to_json(indent=4))
            utterances = json_response.get('results').get('utterances')
            diarization = DiarizationCleaner().clean_transcription(raw_diarization=utterances)
            return diarization
        except Exception as e:
            status_code = general_utilities.extract_status_code(
                exception=e,
                fallback=status.HTTP_417_EXPECTATION_FAILED
            )
            raise HTTPException(
                status_code=status_code,
                detail=str(e)
            )

    async def transcribe_audio(
        self,
        audio_file_url: str
    ) -> str:
        try:
            deepgram = DeepgramSDKClient(os.getenv("DG_API_KEY"))
            options = PrerecordedOptions(
                model="nova-2",
                smart_format=True,
                detect_language=True,
                utterances=True,
                numerals=True
            )

            # Increase the timeout to 300 seconds (5 minutes).
            cls = type(self)
            response = await deepgram.listen.asyncrest.v("1").transcribe_url(source={"url": audio_file_url},
                                                                                options=options,
                                                                                timeout=Timeout(connect=cls.CONNECT_TIMEOUT,
                                                                                                read=cls.TRANSCRIPTION_READ_TIMEOUT,
                                                                                                write=cls.TRANSCRIPTION_WRITE_TIMEOUT,
                                                                                                pool=cls.TRANSCRIPTION_POOL_TIMEOUT))

            json_response = json.loads(response.to_json(indent=4))
            transcript = json_response.get('results').get('channels')[0]['alternatives'][0]['transcript']
            return transcript
        except Exception as e:
            status_code = general_utilities.extract_status_code(
                exception=e,
                fallback=status.HTTP_417_EXPECTATION_FAILED
            )
            raise HTTPException(status_code=status_code,
                                detail=str(e))
