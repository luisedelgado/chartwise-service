from datetime import timedelta

from fastapi.testclient import TestClient

from ..dependencies.fake.fake_async_openai import FakeAsyncOpenAI
from ..dependencies.fake.fake_deepgram_client import FakeDeepgramClient
from ..dependencies.fake.fake_pinecone_client import FakePineconeClient
from ..dependencies.fake.fake_supabase_client import FakeSupabaseClient
from ..dependencies.fake.fake_supabase_client_factory import FakeSupabaseClientFactory
from ..internal.router_dependencies import RouterDependencies
from ..managers.assistant_manager import AssistantManager
from ..managers.audio_processing_manager import AudioProcessingManager
from ..managers.auth_manager import AuthManager
from ..routers.audio_processing_router import AudioProcessingRouter
from ..service_coordinator import EndpointServiceCoordinator

FAKE_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
FAKE_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
FAKE_SESSION_REPORT_ID = "09b6da8d-a58e-45e2-9022-7d58ca02266b"
FAKE_REFRESH_TOKEN = "3ac77394-86b5-42dc-be14-0b92414d8443"
FAKE_ACCESS_TOKEN = "884f507c-f391-4248-91c4-7c25a138633a"
TZ_IDENTIFIER = "UTC"
ENVIRONMENT = "testing"
DUMMY_WAV_FILE_LOCATION = "app/tests/data/maluma.wav"
AUDIO_WAV_FILETYPE = "audio/wav"
ENVIRONMENT = "testing"

class TestingHarnessAudioProcessingRouter:

    def setup_method(self):
        self.auth_manager = AuthManager()
        self.assistant_manager = AssistantManager()
        self.audio_processing_manager = AudioProcessingManager()
        self.fake_openai_client = FakeAsyncOpenAI()
        self.fake_deepgram_client = FakeDeepgramClient()
        self.fake_supabase_admin_client = FakeSupabaseClient()
        self.fake_supabase_user_client = FakeSupabaseClient()
        self.fake_pinecone_client = FakePineconeClient()
        self.fake_supabase_client_factory = FakeSupabaseClientFactory(fake_supabase_admin_client=self.fake_supabase_admin_client,
                                                                      fake_supabase_user_client=self.fake_supabase_user_client)
        self.auth_cookie = self.auth_manager.create_access_token(data={"sub": FAKE_THERAPIST_ID},
                                                                 expires_delta=timedelta(minutes=5))

        coordinator = EndpointServiceCoordinator(routers=[AudioProcessingRouter(auth_manager=self.auth_manager,
                                                                                assistant_manager=self.assistant_manager,
                                                                                audio_processing_manager=self.audio_processing_manager,
                                                                                router_dependencies=RouterDependencies(openai_client=self.fake_openai_client,
                                                                                                                       deepgram_client=self.fake_deepgram_client,
                                                                                                                       pinecone_client=self.fake_pinecone_client,
                                                                                                                       supabase_client_factory=self.fake_supabase_client_factory)).router],
                                                 environment=ENVIRONMENT)
        self.client = TestClient(coordinator.app)

    def test_invoke_transcription_with_no_auth(self):
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.NOTES_TRANSCRIPTION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "template": "soap"
                               },
                               files=files)
        assert response.status_code == 401

    def test_invoke_soap_transcription_success(self):
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.NOTES_TRANSCRIPTION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "template": "soap"
                               },
                               files=files,
                               cookies={
                                   "authorization": self.auth_cookie,
                               })
        assert response.status_code == 200
        assert "soap_transcript" in response.json()

    def test_invoke_free_form_transcription_success(self):
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.NOTES_TRANSCRIPTION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "template": "free_form"
                               },
                               files=files,
                               cookies={
                                   "authorization": self.auth_cookie,
                               })
        assert response.status_code == 200
        assert "transcript" in response.json()

    # def test_invoke_diarization_with_no_auth(self):
    #     files = {
    #         "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
    #     }
    #     response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
    #                            data={
    #                                "patient_id": FAKE_PATIENT_ID,
    #                                "therapist_id": FAKE_THERAPIST_ID,
    #                                "session_date": "10-24-2020",
    #                                "template": SOAP_TEMPLATE,
    #                                "client_timezone_identifier": "UTC"
    #                            },
    #                            files=files)
    #     assert response.status_code == 401

    # def test_invoke_diarization_with_valid_auth_token_but_invalid_date_format(self):
    #     files = {
    #         "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
    #     }
    #     response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
    #                            data={
    #                                "patient_id": FAKE_PATIENT_ID,
    #                                "therapist_id": FAKE_THERAPIST_ID,
    #                                "session_date": "10/24/2020",
    #                                "template": SOAP_TEMPLATE,
    #                                "client_timezone_identifier": "UTC"
    #                            },
    #                            files=files,
    #                            cookies={
    #                                "authorization": FAKE_AUTH_COOKIE,
    #                            })
    #     assert response.status_code == 401

    # def test_invoke_diarization_with_valid_tokens_but_invalid_date_format(self):
    #     files = {
    #         "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
    #     }
    #     response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
    #                            data={
    #                                "patient_id": FAKE_PATIENT_ID,
    #                                "therapist_id": self.auth_manager.FAKE_USER_ID,
    #                                "session_date": "10/24/2020",
    #                                "template": SOAP_TEMPLATE,
    #                                "client_timezone_identifier": "UTC"
    #                            },
    #                            files=files,
    #                            cookies={
    #                                "authorization": FAKE_AUTH_COOKIE,
    #                                "datastore_access_token": FAKE_AUTH_COOKIE,
    #                                "datastore_refresh_token": FAKE_AUTH_COOKIE,
    #                            })
    #     assert response.status_code == 417

    # def test_invoke_diarization_with_valid_tokens_but_invalid_timezone_identifier(self):
    #     files = {
    #         "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
    #     }
    #     response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
    #                            data={
    #                                "patient_id": FAKE_PATIENT_ID,
    #                                "therapist_id": self.auth_manager.FAKE_USER_ID,
    #                                "session_date": "10-24-2020",
    #                                "template": SOAP_TEMPLATE,
    #                                "client_timezone_identifier": "gfhhfhdfhhs"
    #                            },
    #                            files=files,
    #                            cookies={
    #                                "authorization": FAKE_AUTH_COOKIE,
    #                                "datastore_access_token": FAKE_AUTH_COOKIE,
    #                                "datastore_refresh_token": FAKE_AUTH_COOKIE,
    #                            })
    #     assert response.status_code == 417

    # def test_invoke_diarization_with_valid_auth_and_valid_date_format(self):
    #     files = {
    #         "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
    #     }
    #     response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
    #                            data={
    #                                "patient_id": FAKE_PATIENT_ID,
    #                                "therapist_id": self.auth_manager.FAKE_USER_ID,
    #                                "session_date": "10-24-2020",
    #                                "template": SOAP_TEMPLATE,
    #                                "client_timezone_identifier": "UTC"
    #                            },
    #                            files=files,
    #                            cookies={
    #                                "authorization": FAKE_AUTH_COOKIE,
    #                                "datastore_access_token": FAKE_AUTH_COOKIE,
    #                                "datastore_refresh_token": FAKE_AUTH_COOKIE,
    #                            })
    #     assert response.status_code == 200
    #     assert response.json() == {"job_id": self.audio_processing_manager.FAKE_JOB_ID}
    #     assert response.cookies.get("authorization") == self.auth_manager.FAKE_AUTH_TOKEN
    #     assert response.cookies.get("session_id") == self.auth_manager.FAKE_SESSION_ID

    # def test_diarization_notifications_with_invalid_auth(self):
    #     response = self.client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
    #                            headers={
    #                            })
    #     assert response.status_code == 401

    # def test_diarization_notifications_with_valid_auth_but_no_status(self):
    #     response = self.client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
    #                            headers={
    #                                "authorization": FAKE_AUTH_COOKIE
    #                            },
    #                            params={
    #                            })
    #     assert response.status_code == 417

    # def test_diarization_notifications_with_valid_auth_and_failed_status(self):
    #     response = self.client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
    #                            headers={
    #                                "authorization": FAKE_AUTH_COOKIE
    #                            },
    #                            params={
    #                                "status": "failed"
    #                            })
    #     assert response.status_code == 417

    # def test_diarization_notifications_with_valid_auth_and_success_status_but_no_job_id(self):
    #     response = self.client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
    #                            headers={
    #                                "authorization": FAKE_AUTH_COOKIE
    #                            },
    #                            params={
    #                                "status": "failed"
    #                            })
    #     assert response.status_code == 417

    # # TODO: Uncomment when async testing is figured out
    # # def test_diarization_notifications_with_valid_auth_and_successful_params(self):
    # #     assert self.assistant_manager.fake_processed_diarization_result == None
    # #     response = self.client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
    # #                            headers={
    # #                                "authorization": FAKE_AUTH_COOKIE
    # #                            },
    # #                            params={
    # #                                "status": "success",
    # #                                "id": self.audio_processing_manager.FAKE_JOB_ID
    # #                            },
    # #                            json=self.audio_processing_manager.FAKE_DIARIZATION_RESULT)
    # #     assert response.status_code == 200
    # #     assert self.assistant_manager.fake_processed_diarization_result == '[{"content": "Lo creo que es lo m\\u00e1s reciente.", "current_speaker": "S1", "start_time": 0.0, "end_time": 1.65}]'
