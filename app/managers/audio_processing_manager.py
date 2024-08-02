import json, os, requests, ssl

from deepgram import (
    DeepgramClient,
    PrerecordedOptions,
    FileSource,
)
from fastapi import (File, HTTPException, status, UploadFile)
from httpx import Timeout
from speechmatics.models import ConnectionSettings
from speechmatics.batch_client import BatchClient

from ..dependencies.api.openai_base_class import OpenAIBaseClass
from ..dependencies.api.supabase_factory_base_class import SupabaseFactoryBaseClass
from ..internal.logging import Logger
from ..internal.model import SessionNotesTemplate
from ..internal.utilities import file_copiers
from ..managers.assistant_manager import AssistantManager
from ..managers.auth_manager import AuthManager

class AudioProcessingManager:

    async def transcribe_audio_file(self,
                                    auth_manager: AuthManager,
                                    assistant_manager: AssistantManager,
                                    openai_client: OpenAIBaseClass,
                                    template: SessionNotesTemplate,
                                    therapist_id: str,
                                    session_id: str,
                                    audio_file: UploadFile = File(...)) -> str:
        audio_copy_result: file_copiers.FileCopyResult = await file_copiers.make_file_copy(audio_file)

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

                options = "&".join(["model=nova-2",
                                    "smart_format=true",
                                    "detect_language=true",
                                    "utterances=true",
                                    "numerals=true"])
                endpoint_configuration = portkey_gateway_url + listen_endpoint + "?" + options

                with open(audio_copy_result.file_copy_full_path, 'rb') as audio_file:
                    response = requests.post(endpoint_configuration, headers=headers, data=audio_file)

                assert response.status_code == 200, f"{response.text}"
                response_body = json.loads(response.text)
                transcript = response_body['results']['channels'][0]['alternatives'][0]['transcript']
            except Exception as e:
                status_code = status.HTTP_417_EXPECTATION_FAILED if type(e) is not HTTPException else e.status_code
                raise HTTPException(status_code=status_code,
                                    detail=str(e))
            finally:
                await file_copiers.clean_up_files([audio_copy_result.file_copy_full_path])
        else:
            # Process local copy with DeepgramSDK
            try:
                deepgram = DeepgramClient(os.getenv("DG_API_KEY"))

                with open(audio_copy_result.file_copy_full_path, "rb") as file:
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

                # Increase the timeout to 300 seconds (5 minutes)
                response = deepgram.listen.prerecorded.v("1").transcribe_file(payload,
                                                                              options,
                                                                              timeout=Timeout(300.0, connect=10.0))

                json_response = json.loads(response.to_json(indent=4))
                transcript = json_response.get('results').get('channels')[0]['alternatives'][0]['transcript']
            except Exception as e:
                status_code = status.HTTP_417_EXPECTATION_FAILED if type(e) is not HTTPException else e.status_code
                raise HTTPException(status_code=status_code,
                                    detail=str(e))
            finally:
                await file_copiers.clean_up_files([audio_copy_result.file_copy_full_path])

        if template == SessionNotesTemplate.FREE_FORM:
            return transcript

        assert template == SessionNotesTemplate.SOAP, f"Unexpected template: {template}"
        return await assistant_manager.adapt_session_notes_to_soap(auth_manager=auth_manager,
                                                                   openai_client=openai_client,
                                                                   therapist_id=therapist_id,
                                                                   session_notes_text=transcript,
                                                                   session_id=session_id)

    # Speechmatics

    def diarization_config(self, auth_token: str, endpoint_url: str):
        return {
            "type": "transcription",
            "transcription_config": {
                "language": "auto",
                "operating_point": "enhanced",
                "diarization": "speaker",
                "enable_entities": True,
            },
            "notification_config": [
                {
                "url": endpoint_url,
                "method": "post",
                "contents": ["transcript"],
                "auth_headers": [f"Authorization: Bearer {auth_token}"]
                }
            ],
            "language_identification_config": {
                "expected_languages": ["en", "es"],
                "low_confidence_action": "allow"
            },
            "summarization_config": {
                "content_type": "conversational",
                "summary_length": "detailed",
                "summary_type": "bullets"
            },
        }

    async def diarize_audio_file(self,
                                 auth_manager: AuthManager,
                                 supabase_client_factory: SupabaseFactoryBaseClass,
                                 session_auth_token: str,
                                 endpoint_url: str,
                                 session_id: str,
                                 audio_file: UploadFile = File(...)) -> str:
        logger = Logger(supabase_client_factory=supabase_client_factory)
        audio_copy_result: file_copiers.FileCopyResult = await file_copiers.make_file_copy(audio_file)
        config = self.diarization_config(auth_token=session_auth_token,
                                         endpoint_url=endpoint_url)

        if auth_manager.is_monitoring_proxy_reachable():
            try:
                custom_host_url = os.environ.get("SPEECHMATICS_URL")
                document_endpoint = os.environ.get("SPEECHMATICS_JOBS_ENDPOINT")
                portkey_gateway_url = auth_manager.get_monitoring_proxy_url()

                headers = {
                    "x-portkey-forward-headers": "[\"authorization\"]",
                    "Authorization": "Bearer " + os.environ.get("SPEECHMATICS_API_KEY"),
                    "x-portkey-api-key": os.environ.get("PORTKEY_API_KEY"),
                    "x-portkey-custom-host": custom_host_url,
                    "x-portkey-provider": "openai",
                    "x-portkey-metadata": json.dumps({"hidden_provider": "speechmatics"})
                }

                file = {"data_file": (audio_copy_result.file_copy_name,
                                      open(audio_copy_result.file_copy_full_path, 'rb'))}

                response = requests.post(portkey_gateway_url + document_endpoint,
                                         headers=headers,
                                         data={"config": json.dumps(config)},
                                         files=file)

                assert response.status_code == 201, f"Got HTTP code {response.status_code} while uploading the audio file"
                json_response = response.json()
                job_id = json_response['id']
                logger.log_diarization_event(session_id=session_id,
                                             job_id=job_id)
                return job_id
            except Exception as e:
                status_code = status.HTTP_417_EXPECTATION_FAILED if type(e) is not HTTPException else e.status_code
                raise HTTPException(status_code=status_code,
                                    detail=str(e))
            finally:
                await file_copiers.clean_up_files([audio_copy_result.file_copy_full_path])
        else:
            ssl_context = (ssl.create_default_context()
                        if os.environ.get("ENVIRONMENT").lower() == "prod"
                        else ssl._create_unverified_context())
            settings = ConnectionSettings(
                url=os.getenv("SPEECHMATICS_URL"),
                auth_token=os.getenv("SPEECHMATICS_API_KEY"),
                ssl_context=ssl_context,
            )
            with BatchClient(settings) as client:
                try:
                    job_id = client.submit_job(
                        audio=audio_copy_result.file_copy_full_path,
                        transcription_config=config,
                    )
                    logger.log_diarization_event(session_id=session_id,
                                                 job_id=job_id)
                    return job_id
                except Exception as e:
                    status_code = status.HTTP_417_EXPECTATION_FAILED if type(e) is not HTTPException else e.status_code
                    raise HTTPException(status_code=status_code,
                                        detail=str(e))
                finally:
                    await file_copiers.clean_up_files([audio_copy_result.file_copy_full_path])
