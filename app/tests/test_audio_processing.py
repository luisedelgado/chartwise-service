from fastapi.testclient import TestClient

from ..managers.manager_factory import ManagerFactory
from ..routers.assistant_router import AssistantRouter
from ..routers.audio_processing_router import AudioProcessingRouter
from ..routers.security_router import SecurityRouter
from ..service_coordinator import EndpointServiceCoordinator

FAKE_AUTH_COOKIE = "my-auth-cookie"
FAKE_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
FAKE_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
DUMMY_WAV_FILE_LOCATION = "app/tests/data/maluma.wav"
AUDIO_WAV_FILETYPE = "audio/wav"
ENVIRONMENT = "testing"

class TestingHarnessAudioProcessingRouter:

    def setup_method(self):
        self.auth_manager = ManagerFactory().create_auth_manager(ENVIRONMENT)
        self.auth_manager.auth_cookie = FAKE_AUTH_COOKIE

        self.assistant_manager = ManagerFactory.create_assistant_manager(ENVIRONMENT)
        self.audio_processing_manager = ManagerFactory.create_audio_processing_manager(ENVIRONMENT)

        coordinator = EndpointServiceCoordinator(routers=[AssistantRouter(environment=ENVIRONMENT,
                                                                          auth_manager=self.auth_manager,
                                                                          assistant_manager=self.assistant_manager).router,
                                                          AudioProcessingRouter(auth_manager=self.auth_manager,
                                                                                assistant_manager=self.assistant_manager,
                                                                                audio_processing_manager=self.audio_processing_manager).router,
                                                          SecurityRouter(auth_manager=self.auth_manager,
                                                                         assistant_manager=self.assistant_manager).router])
        self.client = TestClient(coordinator.service_app)

    def test_invoke_transcription_with_no_auth(self):
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.NOTES_TRANSCRIPTION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                               },
                               files=files)
        assert response.status_code == 401

    def test_invoke_transcription_with_valid_auth(self):
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.NOTES_TRANSCRIPTION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                               },
                               files=files,
                               cookies={
                                   "authorization": FAKE_AUTH_COOKIE,
                               })
        assert response.status_code == 200
        assert response.json() == {"transcript": self.audio_processing_manager.FAKE_TRANSCRIPTION_RESULT}
        assert response.cookies.get("authorization") == self.auth_manager.FAKE_AUTH_TOKEN
        assert response.cookies.get("session_id") == self.auth_manager.FAKE_SESSION_ID

    def test_invoke_diarization_with_no_auth(self):
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "session_date": "10-24-2020",
                               },
                               files=files)
        assert response.status_code == 401

    def test_invoke_diarization_with_valid_auth_token_but_invalid_date_format(self):
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "session_date": "10/24/2020",
                               },
                               files=files,
                               cookies={
                                   "authorization": FAKE_AUTH_COOKIE,
                               })
        assert response.status_code == 401

    def test_invoke_diarization_with_valid_tokens_but_invalid_date_format(self):
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "session_date": "10/24/2020",
                               },
                               files=files,
                               cookies={
                                   "authorization": FAKE_AUTH_COOKIE,
                                   "datastore_access_token": FAKE_AUTH_COOKIE,
                                   "datastore_refresh_token": FAKE_AUTH_COOKIE,
                               })
        assert response.status_code == 409

    def test_invoke_diarization_with_valid_auth_and_valid_date_format(self):
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "session_date": "10-24-2020",
                               },
                               files=files,
                               cookies={
                                   "authorization": FAKE_AUTH_COOKIE,
                                   "datastore_access_token": FAKE_AUTH_COOKIE,
                                   "datastore_refresh_token": FAKE_AUTH_COOKIE,
                               })
        assert response.status_code == 200
        assert response.json() == {"job_id": self.audio_processing_manager.FAKE_JOB_ID}
        assert response.cookies.get("authorization") == self.auth_manager.FAKE_AUTH_TOKEN
        assert response.cookies.get("session_id") == self.auth_manager.FAKE_SESSION_ID

    def test_diarization_notifications_with_invalid_auth(self):
        response = self.client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
                               headers={
                               })
        assert response.status_code == 401

    def test_diarization_notifications_with_valid_auth_but_no_status(self):
        response = self.client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
                               headers={
                                   "authorization": FAKE_AUTH_COOKIE
                               },
                               params={
                               })
        assert response.status_code == 417

    def test_diarization_notifications_with_valid_auth_and_failed_status(self):
        response = self.client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
                               headers={
                                   "authorization": FAKE_AUTH_COOKIE
                               },
                               params={
                                   "status": "failed"
                               })
        assert response.status_code == 417

    def test_diarization_notifications_with_valid_auth_and_success_status_but_no_job_id(self):
        response = self.client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
                               headers={
                                   "authorization": FAKE_AUTH_COOKIE
                               },
                               params={
                                   "status": "failed"
                               })
        assert response.status_code == 417

    # TODO: Uncomment when async testing is figured out
    # def test_diarization_notifications_with_valid_auth_and_successful_params(self):
    #     assert self.assistant_manager.fake_processed_diarization_result == None
    #     response = self.client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
    #                            headers={
    #                                "authorization": FAKE_AUTH_COOKIE
    #                            },
    #                            params={
    #                                "status": "success",
    #                                "id": self.audio_processing_manager.FAKE_JOB_ID
    #                            },
    #                            json=self.audio_processing_manager.FAKE_DIARIZATION_RESULT)
    #     assert response.status_code == 200
    #     assert self.assistant_manager.fake_processed_diarization_result == '[{"content": "Lo creo que es lo m\\u00e1s reciente.", "current_speaker": "S1", "start_time": 0.0, "end_time": 1.65}]'
