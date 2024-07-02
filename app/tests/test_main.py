from fastapi.testclient import TestClient

from ..managers.manager_factory import ManagerFactory
from ..routers.assistant_router import AssistantRouter
from ..routers.audio_processing_router import AudioProcessingRouter
from ..routers.image_processing_router import ImageProcessingRouter
from ..routers.security_router import SecurityRouter
from ..service_coordinator import EndpointServiceCoordinator

DUMMY_AUTH_COOKIE = "my-auth-cookie"
DUMMY_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
DUMMY_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
DUMMY_PDF_FILE_LOCATION = "app/tests/data/test2.pdf"
DUMMY_WAV_FILE_LOCATION = "app/tests/data/maluma.wav"
IMAGE_PDF_FILETYPE = "application/pdf"
AUDIO_WAV_FILETYPE = "audio/wav"

environment = "testing"
auth_manager = ManagerFactory().create_auth_manager(environment)
auth_manager.auth_cookie = DUMMY_AUTH_COOKIE

assistant_manager = ManagerFactory.create_assistant_manager(environment)
audio_processing_manager = ManagerFactory.create_audio_processing_manager(environment)
image_processing_manager = ManagerFactory.create_image_processing_manager(environment)

coordinator = EndpointServiceCoordinator(environment=environment,
                                                    routers=[
                                                        AssistantRouter(environment=environment,
                                                                        auth_manager=auth_manager,
                                                                        assistant_manager=assistant_manager).router,
                                                        AudioProcessingRouter(auth_manager=auth_manager,
                                                                              assistant_manager=assistant_manager,
                                                                              audio_processing_manager=audio_processing_manager).router,
                                                        ImageProcessingRouter(auth_manager=auth_manager,
                                                                              image_processing_manager=image_processing_manager).router,
                                                        SecurityRouter(auth_manager=auth_manager).router,
                                                    ])
client = TestClient(coordinator.service_app)

class TestingHarnessImageProcessing:

    def test_invoke_image_upload_with_no_auth(self):
        files = {
            "image": (DUMMY_PDF_FILE_LOCATION, open(DUMMY_PDF_FILE_LOCATION, 'rb'), IMAGE_PDF_FILETYPE)
        }
        response = client.post(ImageProcessingRouter.IMAGE_UPLOAD_ENDPOINT,
                            data={"patient_id": DUMMY_PATIENT_ID, "therapist_id": DUMMY_THERAPIST_ID},
                            files=files)
        assert response.status_code == 401

    def test_invoke_image_upload_with_auth(self):
        files = {
            "image": (DUMMY_PDF_FILE_LOCATION, open(DUMMY_PDF_FILE_LOCATION, 'rb'), IMAGE_PDF_FILETYPE)
        }
        response = client.post(ImageProcessingRouter.IMAGE_UPLOAD_ENDPOINT,
                               data={"patient_id": DUMMY_PATIENT_ID, "therapist_id": DUMMY_THERAPIST_ID},
                               files=files,
                               cookies={
                                   "authorization": DUMMY_AUTH_COOKIE,
                               })
        assert response.status_code == 200
        assert response.json() == {"document_id": image_processing_manager.FAKE_DOCUMENT_ID}

    def test_invoke_textraction_with_no_auth(self):
        response = client.post(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
                               json={
                                   "patient_id": DUMMY_PATIENT_ID,
                                   "therapist_id": DUMMY_THERAPIST_ID,
                                   "document_id": "12345"
                                })
        assert response.status_code == 401

    def test_invoke_textraction_with_auth_but_empty_doc_id(self):
        response = client.post(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
                               json={
                                   "patient_id": DUMMY_PATIENT_ID,
                                   "therapist_id": DUMMY_THERAPIST_ID,
                                   "document_id": ""
                                },
                                cookies={
                                    "authorization": DUMMY_AUTH_COOKIE,
                                })
        assert response.status_code == 409

    def test_invoke_textraction_with_auth_but_invalid_doc_id(self):
        response = client.post(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
                               json={
                                   "patient_id": DUMMY_PATIENT_ID,
                                   "therapist_id": DUMMY_THERAPIST_ID,
                                   "document_id": "000"
                                },
                                cookies={
                                    "authorization": DUMMY_AUTH_COOKIE,
                                })
        assert response.status_code == 409

    def test_invoke_textraction_with_auth_and_valid_doc_id(self):
        response = client.post(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
                               json={
                                   "patient_id": DUMMY_PATIENT_ID,
                                   "therapist_id": DUMMY_THERAPIST_ID,
                                   "document_id": "12345"
                                },
                                cookies={
                                    "authorization": DUMMY_AUTH_COOKIE,
                                })
        assert response.status_code == 200
        assert response.json() == {"extraction": image_processing_manager.FAKE_TEXTRACT_RESULT}

class TestingHarnessAudioProcessing:

    def test_invoke_transcription_with_no_auth(self):
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = client.post(AudioProcessingRouter.NOTES_TRANSCRIPTION_ENDPOINT,
                               data={
                                   "patient_id": DUMMY_PATIENT_ID,
                                   "therapist_id": DUMMY_THERAPIST_ID,
                               },
                               files=files)
        assert response.status_code == 401

    def test_invoke_transcription_with_valid_auth(self):
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = client.post(AudioProcessingRouter.NOTES_TRANSCRIPTION_ENDPOINT,
                               data={
                                   "patient_id": DUMMY_PATIENT_ID,
                                   "therapist_id": DUMMY_THERAPIST_ID,
                               },
                               files=files,
                               cookies={
                                   "authorization": DUMMY_AUTH_COOKIE,
                               })
        assert response.status_code == 200
        assert response.json() == {"transcript": audio_processing_manager.FAKE_TRANSCRIPTION_RESULT}

    def test_invoke_diarization_with_no_auth(self):
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": DUMMY_PATIENT_ID,
                                   "therapist_id": DUMMY_THERAPIST_ID,
                                   "session_date": "10-24-2020",
                               },
                               files=files)
        assert response.status_code == 401

    def test_invoke_diarization_with_valid_auth_but_invalid_date_format(self):
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": DUMMY_PATIENT_ID,
                                   "therapist_id": DUMMY_THERAPIST_ID,
                                   "session_date": "10/24/2020",
                               },
                               files=files,
                               cookies={
                                   "authorization": DUMMY_AUTH_COOKIE,
                               })
        assert response.status_code == 409

    def test_invoke_diarization_with_valid_auth_and_valid_date_format(self):
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": DUMMY_PATIENT_ID,
                                   "therapist_id": DUMMY_THERAPIST_ID,
                                   "session_date": "10-24-2020",
                               },
                               files=files,
                               cookies={
                                   "authorization": DUMMY_AUTH_COOKIE,
                               })
        assert response.status_code == 200
        assert response.json() == {"job_id": audio_processing_manager.FAKE_JOB_ID}

    def test_diarization_notifications_with_invalid_auth(self):
        response = client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
                               headers={
                               })
        assert response.status_code == 401

    def test_diarization_notifications_with_valid_auth_but_no_status(self):
        response = client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
                               headers={
                                   "authorization": DUMMY_AUTH_COOKIE
                               },
                               params={
                               })
        assert response.status_code == 417

    def test_diarization_notifications_with_valid_auth_and_failed_status(self):
        response = client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
                               headers={
                                   "authorization": DUMMY_AUTH_COOKIE
                               },
                               params={
                                   "status": "failed"
                               })
        assert response.status_code == 417

    def test_diarization_notifications_with_valid_auth_and_success_status_but_no_job_id(self):
        response = client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
                               headers={
                                   "authorization": DUMMY_AUTH_COOKIE
                               },
                               params={
                                   "status": "failed"
                               })
        assert response.status_code == 417

    def test_diarization_notifications_with_valid_auth_and_successful_params(self):
        assert assistant_manager.fake_processed_diarization_result == None
        response = client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
                               headers={
                                   "authorization": DUMMY_AUTH_COOKIE
                               },
                               params={
                                   "status": "success",
                                   "id": audio_processing_manager.FAKE_JOB_ID
                               },
                               json=audio_processing_manager.FAKE_DIARIZATION_RESULT)
        assert response.status_code == 200
        assert assistant_manager.fake_processed_diarization_result == '[{"content": "Lo creo que es lo m\\u00e1s reciente.", "current_speaker": "S1", "start_time": 0.0, "end_time": 1.65}]'
