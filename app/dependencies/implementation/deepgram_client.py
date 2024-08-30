import json, os, requests
import tiktoken

from deepgram import (
    DeepgramClient as DeepgramSDKClient,
    PrerecordedOptions,
    FileSource,
)
from fastapi import HTTPException, status
from httpx import Timeout
from typing import Tuple

from ...vectors.chartwise_assistant import PromptCrafter, PromptScenario
from ..api.deepgram_base_class import DeepgramBaseClass
from ..api.templates import SessionNotesTemplate
from ...data_processing.diarization_cleaner import DiarizationCleaner
from ...dependencies.api.openai_base_class import OpenAIBaseClass
from ...internal.utilities import general_utilities
from ...managers.assistant_manager import AssistantManager
from ...managers.auth_manager import AuthManager

class DeepgramClient(DeepgramBaseClass):

    DIARIZATION_SUMMARY_ACTION_NAME = "diarization_summary"
    DG_QUERY_PARAMS = "model=nova-2&smart_format=true&detect_language=true&utterances=true&numerals=true"

    async def diarize_audio(self,
                            auth_manager: AuthManager,
                            therapist_id: str,
                            patient_id: str,
                            language_code: str,
                            session_id: str,
                            file_full_path: str,
                            openai_client: OpenAIBaseClass,
                            assistant_manager: AssistantManager,
                            template: SessionNotesTemplate) -> Tuple[str, str]:
        if auth_manager.is_monitoring_proxy_reachable():
            try:
                custom_host_url = os.environ.get("DG_URL")
                listen_endpoint = os.environ.get("DG_LISTEN_ENDPOINT")
                portkey_gateway_url = auth_manager.get_monitoring_proxy_url()

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
                                             timeout=(300.0, 20.0))

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
                                                                              timeout=Timeout(300.0, connect=20.0))

                json_response = json.loads(response.to_json(indent=4))
                utterances = json_response.get('results').get('utterances')
                diarization = DiarizationCleaner().clean_transcription(raw_diarization=utterances)
            except Exception as e:
                status_code = general_utilities.extract_status_code(exception=e, fallback=status.HTTP_417_EXPECTATION_FAILED)
                raise HTTPException(status_code=status_code,
                                    detail=str(e))

        metadata = {
            "user_id": therapist_id,
            "patient_id": patient_id,
            "session_id": str(session_id),
            "action": self.DIARIZATION_SUMMARY_ACTION_NAME
        }

        prompt_crafter = PromptCrafter()
        user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.DIARIZATION_SUMMARY,
                                                                   diarization=diarization)
        system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.DIARIZATION_SUMMARY,
                                                                       language_code=language_code)
        prompt_tokens = len(tiktoken.get_encoding("cl100k_base").encode(f"{system_prompt}\n{user_prompt}"))
        max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

        session_summary = await openai_client.trigger_async_chat_completion(metadata=metadata,
                                                                            max_tokens=max_tokens,
                                                                            messages=[
                                                                                {"role": "system", "content": system_prompt},
                                                                                {"role": "user", "content": user_prompt},
                                                                            ],
                                                                            expects_json_response=False,
                                                                            auth_manager=auth_manager)

        if template == SessionNotesTemplate.SOAP:
            session_summary = await assistant_manager.adapt_session_notes_to_soap(auth_manager=auth_manager,
                                                                                  openai_client=openai_client,
                                                                                  therapist_id=therapist_id,
                                                                                  session_notes_text=session_summary,
                                                                                  session_id=session_id)
        return (session_summary, diarization)

    async def transcribe_audio(self,
                               auth_manager: AuthManager,
                               therapist_id: str,
                               session_id: str,
                               file_full_path: str,
                               openai_client: OpenAIBaseClass,
                               assistant_manager: AssistantManager,
                               template: SessionNotesTemplate) -> str:
        if auth_manager.is_monitoring_proxy_reachable():
            try:
                custom_host_url = os.environ.get("DG_URL")
                listen_endpoint = os.environ.get("DG_LISTEN_ENDPOINT")
                portkey_gateway_url = auth_manager.get_monitoring_proxy_url()

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
                                             timeout=(300.0, 10.0))

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
                                                                              timeout=Timeout(300.0, connect=10.0))

                json_response = json.loads(response.to_json(indent=4))
                transcript = json_response.get('results').get('channels')[0]['alternatives'][0]['transcript']
            except Exception as e:
                status_code = general_utilities.extract_status_code(exception=e, fallback=status.HTTP_417_EXPECTATION_FAILED)
                raise HTTPException(status_code=status_code,
                                    detail=str(e))

        if template == SessionNotesTemplate.FREE_FORM:
            return transcript

        assert template == SessionNotesTemplate.SOAP, f"Unexpected template: {template}"
        return await assistant_manager.adapt_session_notes_to_soap(auth_manager=auth_manager,
                                                                   openai_client=openai_client,
                                                                   therapist_id=therapist_id,
                                                                   session_notes_text=transcript,
                                                                   session_id=session_id)
