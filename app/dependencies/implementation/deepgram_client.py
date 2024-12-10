import json, os, requests

from deepgram import (
    DeepgramClient as DeepgramSDKClient,
    PrerecordedOptions,
    FileSource,
)
from fastapi import HTTPException, status
from httpx import Timeout

from ...internal.monitoring_proxy import get_monitoring_proxy_url, use_monitoring_proxy
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

    async def diarize_audio(self, file_full_path: str) -> str:
        # TODO: Revert check when Portkey fixes WAV bug
        if not use_monitoring_proxy():
            try:
                monitoring_proxy_url = get_monitoring_proxy_url()
                assert len(monitoring_proxy_url or '') > 0, "Missing monitoring proxy url param"

                custom_host_url = os.environ.get("DG_URL")
                listen_endpoint = os.environ.get("DG_LISTEN_ENDPOINT")
                portkey_gateway_url = monitoring_proxy_url

                headers = {
                    "x-portkey-forward-headers": "[\"authorization\", \"content-type\"]",
                    "Authorization": "Token " + os.environ.get("DG_API_KEY"),
                    "Content-type": "audio/wav",
                    "x-portkey-api-key": os.environ.get("PORTKEY_API_KEY"),
                    "x-portkey-custom-host": custom_host_url,
                    "x-portkey-provider": "openai",
                    "x-portkey-metadata": json.dumps({"hidden_provider": "deepgram"})
                }

                options = "&".join([self.DG_QUERY_PARAMS, "diarize=true"])

                endpoint_configuration = portkey_gateway_url + listen_endpoint + "?" + options

                with open(file_full_path, 'rb') as audio_file:
                    # Increase the timeout to 300 seconds (5 minutes).
                    response = requests.post(endpoint_configuration,
                                             headers=headers,
                                             data=audio_file,
                                             timeout=(self.CONNECT_TIMEOUT, self.DIARIZATION_READ_TIMEOUT))

                assert response.status_code == 200, f"{response.text}"
                response_body = json.loads(response.text)
                utterances = response_body['results']['utterances']
                diarization = DiarizationCleaner().clean_transcription(raw_diarization=utterances)
            except Exception as e:
                status_code = general_utilities.extract_status_code(exception=e, fallback=status.HTTP_417_EXPECTATION_FAILED)
                raise HTTPException(status_code=status_code,
                                    detail=str(e))
        else:
            # Process local copy with DeepgramSDK
            try:
                deepgram = DeepgramSDKClient(os.getenv("DG_API_KEY"))

                with open(file_full_path, "rb") as file:
                    buffer_data = file.read()

                payload: FileSource = {
                    "buffer": buffer_data,
                }

                options = PrerecordedOptions(
                    model="nova-2",
                    smart_format=True,
                    detect_language=True,
                    utterances=True,
                    numerals=True,
                    diarize=True
                )

                # Increase the timeout to 300 seconds (5 minutes).
                response = deepgram.listen.prerecorded.v("1").transcribe_file(payload,
                                                                              options,
                                                                              timeout=Timeout(connect=self.CONNECT_TIMEOUT,
                                                                                              read=self.DIARIZATION_READ_TIMEOUT,
                                                                                              write=self.DIARIZATION_WRITE_TIMEOUT,
                                                                                              pool=self.DIARIZATION_POOL_TIMEOUT))

                json_response = json.loads(response.to_json(indent=4))
                utterances = json_response.get('results').get('utterances')
                diarization = DiarizationCleaner().clean_transcription(raw_diarization=utterances)
            except Exception as e:
                status_code = general_utilities.extract_status_code(exception=e, fallback=status.HTTP_417_EXPECTATION_FAILED)
                raise HTTPException(status_code=status_code,
                                    detail=str(e))

        return diarization

    async def transcribe_audio(self,
                               file_full_path: str) -> str:
        # TODO: Revert check when Portkey fixes WAV bug
        if not use_monitoring_proxy():
            try:
                monitoring_proxy_url = get_monitoring_proxy_url()
                assert len(monitoring_proxy_url or '') > 0, "Missing monitoring proxy url param"

                custom_host_url = os.environ.get("DG_URL")
                listen_endpoint = os.environ.get("DG_LISTEN_ENDPOINT")
                portkey_gateway_url = monitoring_proxy_url

                headers = {
                    "x-portkey-forward-headers": "[\"authorization\", \"content-type\"]",
                    "Authorization": "Token " + os.environ.get("DG_API_KEY"),
                    "Content-type": "audio/wav",
                    "x-portkey-api-key": os.environ.get("PORTKEY_API_KEY"),
                    "x-portkey-custom-host": custom_host_url,
                    "x-portkey-provider": "openai",
                    "x-portkey-metadata": json.dumps({"hidden_provider": "deepgram"})
                }

                endpoint_configuration = portkey_gateway_url + listen_endpoint + "?" + self.DG_QUERY_PARAMS

                with open(file_full_path, 'rb') as audio_file:
                    # Increase the timeout to 300 seconds (5 minutes).
                    response = requests.post(endpoint_configuration,
                                             headers=headers,
                                             data=audio_file,
                                             timeout=(self.CONNECT_TIMEOUT, self.TRANSCRIPTION_READ_TIMEOUT))

                assert response.status_code == 200, f"{response.text}"
                response_body = json.loads(response.text)
                transcript = response_body['results']['channels'][0]['alternatives'][0]['transcript']
            except Exception as e:
                status_code = general_utilities.extract_status_code(exception=e, fallback=status.HTTP_417_EXPECTATION_FAILED)
                raise HTTPException(status_code=status_code,
                                    detail=str(e))
        else:
            # Process local copy with DeepgramSDK
            try:
                deepgram = DeepgramSDKClient(os.getenv("DG_API_KEY"))

                with open(file_full_path, "rb") as file:
                    buffer_data = file.read()

                payload: FileSource = {
                    "buffer": buffer_data,
                }

                options = PrerecordedOptions(
                    model="nova-2",
                    smart_format=True,
                    detect_language=True,
                    utterances=True,
                    numerals=True
                )

                # Increase the timeout to 300 seconds (5 minutes).
                response = deepgram.listen.prerecorded.v("1").transcribe_file(payload,
                                                                              options,
                                                                              timeout=Timeout(connect=self.CONNECT_TIMEOUT,
                                                                                              read=self.TRANSCRIPTION_READ_TIMEOUT,
                                                                                              write=self.TRANSCRIPTION_WRITE_TIMEOUT,
                                                                                              pool=self.TRANSCRIPTION_POOL_TIMEOUT))

                json_response = json.loads(response.to_json(indent=4))
                transcript = json_response.get('results').get('channels')[0]['alternatives'][0]['transcript']
            except Exception as e:
                status_code = general_utilities.extract_status_code(exception=e, fallback=status.HTTP_417_EXPECTATION_FAILED)
                raise HTTPException(status_code=status_code,
                                    detail=str(e))

        return transcript
