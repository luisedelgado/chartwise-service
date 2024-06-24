import json, os, requests, shutil, ssl

from datetime import datetime

from deepgram import (
    DeepgramClient,
    PrerecordedOptions,
    FileSource,
)
from fastapi import (File, HTTPException, status, UploadFile)
from httpx import Timeout
from speechmatics.models import ConnectionSettings
from speechmatics.batch_client import BatchClient

from .auth_manager import AuthManager
from ..internal import utilities
from ..api.audio_processing_base_class import AudioProcessingManagerBaseClass

class AudioProcessingManager(AudioProcessingManagerBaseClass):

    async def transcribe_audio_file(self,
                                    audio_file: UploadFile = File(...)) -> str:
        try:
            _, file_extension = os.path.splitext(audio_file.filename)
            files_dir = 'app/files'
            audio_copy_bare_name = datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
            audio_copy_path = files_dir + '/' + audio_copy_bare_name + file_extension

            # Write incoming audio to our local volume for further processing
            with open(audio_copy_path, 'wb+') as buffer:
                shutil.copyfileobj(audio_file.file, buffer)

            assert os.path.exists(audio_copy_path), "Something went wrong while processing the file."
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=str(e))
        finally:
            await audio_file.close()

        # Process local copy with DeepgramClient
        try:
            deepgram = DeepgramClient(os.getenv("DG_API_KEY"))

            with open(audio_copy_path, "rb") as file:
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
        except HTTPException as e:
            raise HTTPException(status_code=e.status_code,
                                detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="The transcription operation failed.")
        finally:
            await utilities.clean_up_files([audio_copy_path])

        return transcript

    # Speechmatics

    """
    The set of IPs that Speechmatics may use to trigger a notification to our service.
    """
    def get_diarization_notifications_ips(self) -> list:
        return [
            "40.74.41.91",
            "52.236.157.154",
            "40.74.37.0",
            "20.73.209.153",
            "20.73.142.44",
            "20.105.89.153",
            "20.105.89.173",
            "20.105.89.184",
            "20.105.89.98",
            "20.105.88.228",
            "52.149.21.32",
            "52.149.21.10",
            "52.137.102.83",
            "40.64.107.92",
            "40.64.107.99",
            "52.146.58.224",
            "52.146.58.159",
            "52.146.59.242",
            "52.146.59.213",
            "52.146.58.64",
            "20.248.249.20",
            "20.248.249.47",
            "20.248.249.181",
            "20.248.249.119",
            "20.248.249.164",
        ]

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
                                 session_auth_token: str,
                                 endpoint_url: str,
                                 audio_file: UploadFile = File(...)) -> str:
        _, file_extension = os.path.splitext(audio_file.filename)
        files_dir = 'app/files'
        audio_copy_file_name = datetime.now().strftime("%d-%m-%Y-%H-%M-%S") + file_extension
        audio_copy_full_path = files_dir + '/' + audio_copy_file_name

        try:
            # Write incoming audio to our local volume for further processing
            with open(audio_copy_full_path, 'wb+') as buffer:
                shutil.copyfileobj(audio_file.file, buffer)

            assert os.path.exists(audio_copy_full_path), "Something went wrong while processing the file."
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=str(e))
        finally:
            await audio_file.close()

        config = self.diarization_config(auth_token=session_auth_token,
                                    endpoint_url=endpoint_url)

        auth_manager = AuthManager()
        if auth_manager.is_monitoring_proxy_reachable():
            try:
                base_url = os.environ.get("SPEECHMATICS_URL")
                document_endpoint = os.environ.get("SPEECHMATICS_JOBS_ENDPOINT")

                headers = {
                    "Authorization": "Bearer " + os.environ.get("SPEECHMATICS_API_KEY"),
                    "x-portkey-api-key": os.environ.get("PORTKEY_API_KEY"),
                    "x-portkey-custom-host": base_url + document_endpoint,
                    "x-portkey-virtual-key": os.environ.get("PORTKEY_SPEECHMATICS_VIRTUAL_KEY"),
                }

                file = {"data_file": (audio_copy_file_name, open(audio_copy_full_path, 'rb'))}
                response = requests.post(auth_manager.get_monitoring_proxy_url(), headers=headers, data={"config": json.dumps(config)}, files=file)

                assert response.status_code == 201, f"Got HTTP code {response.status} while uploading the audio file"
                json_response = response.json()
                job_id = json_response['id']
                return job_id
            except Exception as e:
                raise Exception(str(e))
            finally:
                await utilities.clean_up_files([audio_copy_full_path])
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
                    return client.submit_job(
                        audio=audio_copy_full_path,
                        transcription_config=config,
                    )
                except TimeoutError as e:
                    raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT)
                except HTTPException as e:
                    raise HTTPException(status_code=e.status_code, detail=str(e))
                except Exception as e:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                        detail=str(e))
                finally:
                    await utilities.clean_up_files([audio_copy_full_path])
