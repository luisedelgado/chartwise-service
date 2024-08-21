import json, os, requests, ssl

from fastapi import BackgroundTasks, HTTPException, status
from speechmatics.models import ConnectionSettings
from speechmatics.batch_client import BatchClient

from ..api.speechmatics_base_class import SpeechmaticsBaseClass
from ..api.supabase_factory_base_class import SupabaseFactoryBaseClass
from ...internal.logging import Logger
from ...internal.utilities import general_utilities
from ...managers.auth_manager import AuthManager

class SpeechmaticsClient(SpeechmaticsBaseClass):

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

    async def diarize_audio(self,
                            therapist_id: str,
                            background_tasks: BackgroundTasks,
                            auth_manager: AuthManager,
                            session_id: str,
                            file_full_path: str,
                            supabase_client_factory: SupabaseFactoryBaseClass,
                            session_auth_token: str,
                            endpoint_url: str,
                            file_name: str) -> str:
        logger = Logger(supabase_client_factory=supabase_client_factory)
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

                file = {"data_file": (file_name,
                                      open(file_full_path, 'rb'))}

                response = requests.post(portkey_gateway_url + document_endpoint,
                                         headers=headers,
                                         data={"config": json.dumps(config)},
                                         files=file)

                assert response.status_code == 201, f"Got HTTP code {response.status_code} while uploading the audio file"
                json_response = response.json()
                job_id = json_response['id']
                logger.log_diarization_event(background_tasks=background_tasks,
                                             therapist_id=therapist_id,
                                             session_id=session_id,
                                             job_id=job_id)
                return job_id
            except Exception as e:
                status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
                raise HTTPException(status_code=status_code,
                                    detail=str(e))
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
                        audio=file_full_path,
                        transcription_config=config,
                    )
                    logger.log_diarization_event(background_tasks=background_tasks,
                                                 therapist_id=therapist_id,
                                                 session_id=session_id,
                                                 job_id=job_id)
                    return job_id
                except Exception as e:
                    status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
                    raise HTTPException(status_code=status_code,
                                        detail=str(e))
