import json

from datetime import timedelta

from fastapi.testclient import TestClient

from ..data_processing.diarization_cleaner import DiarizationCleaner
from ..dependencies.fake.fake_async_openai import FakeAsyncOpenAI
from ..dependencies.fake.fake_deepgram_client import FakeDeepgramClient
from ..dependencies.fake.fake_pinecone_client import FakePineconeClient
from ..dependencies.fake.fake_speechmatics_client import FakeSpeechmaticsClient
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
FAKE_JOB_ID = "9876"
FAKE_DIARIZATION_RESULT = {
    "job": {
        "id": "m38xavr1g4"
    },
    "results": [
        {
            "alternatives": [
                {
                    "confidence": 0.94,
                    "content": "Lo",
                    "language": "es",
                    "speaker": "S1"
                }
            ],
            "end_time": 0.24,
            "start_time": 0.0,
            "type": "word"
        },
        {
            "alternatives":
            [
                {
                    "confidence": 1.0,
                    "content": "creo",
                    "language": "es",
                    "speaker": "S1"
                }
            ],
            "end_time": 0.45,
            "start_time": 0.24,
            "type": "word"
        },
        {
            "alternatives":
            [
                {
                    "confidence": 1.0,
                    "content": "que",
                    "language": "es",
                    "speaker": "S1"
                }
            ],
            "end_time": 0.54,
            "start_time": 0.45,
            "type": "word"
        },
        {
            "alternatives":
            [
                {
                    "confidence": 0.86,
                    "content": "es",
                    "language": "es",
                    "speaker": "S1"
                }
            ],
            "end_time": 0.6,
            "start_time": 0.54,
            "type": "word"
        },
        {
            "alternatives":
            [
                {
                    "confidence": 1.0,
                    "content": "lo",
                    "language": "es",
                    "speaker": "S1"
                }
            ],
            "end_time": 0.69,
            "start_time": 0.6,
            "type": "word"
        },
        {
            "alternatives":
            [
                {
                    "confidence": 0.95,
                    "content": "más",
                    "language": "es",
                    "speaker": "S1"
                }
            ],
            "end_time": 0.87,
            "start_time": 0.69,
            "type": "word"
        },
        {
            "alternatives":
            [
                {
                    "confidence": 1.0,
                    "content": "reciente",
                    "language": "es",
                    "speaker": "S1"
                }
            ],
            "end_time": 1.65,
            "start_time": 0.87,
            "type": "word"
        },
        {
            "alternatives":
            [
                {
                    "confidence": 1.0,
                    "content": ".",
                    "language": "es",
                    "speaker": "S1"
                }
            ],
            "attaches_to": "previous",
            "end_time": 1.65,
            "is_eos": True,
            "start_time": 1.65,
            "type": "punctuation"
        }
    ],
    "summary":
    {
        "content": "Temas clave:\n- Interpretación de personajes\n"
    }
}

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
        self.fake_speechmatics_client = FakeSpeechmaticsClient()
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
                                                                                                                       speechmatics_client=self.fake_speechmatics_client,
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

    def test_invoke_diarization_with_no_auth(self):
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "session_date": "10-24-2020",
                                   "template": "soap",
                                   "client_timezone_identifier": "UTC"
                               },
                               files=files)
        assert response.status_code == 401

    def test_invoke_diarization_with_auth_token_but_supabase_returns_unathenticated_session(self):
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    data={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                        "session_date": "10-24-2020",
                                        "template": "soap",
                                        "client_timezone_identifier": "UTC"
                                    },
                                    files=files)
        assert response.status_code == 401

    def test_invoke_diarization_with_valid_auth_but_empty_therapist_id(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": "",
                                   "session_date": "10-24-2020",
                                   "template": "soap",
                                   "client_timezone_identifier": "UTC"
                               },
                               files=files,
                               cookies={
                                   "authorization": self.auth_cookie,
                               })
        assert response.status_code == 422

    def test_invoke_diarization_with_valid_auth_but_empty_patient_id(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": "",
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "session_date": "10-24-2020",
                                   "template": "soap",
                                   "client_timezone_identifier": "UTC"
                               },
                               files=files,
                               cookies={
                                   "authorization": self.auth_cookie,
                               })
        assert response.status_code == 422

    def test_invoke_diarization_with_valid_auth_but_invalid_date_format(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "session_date": "10/24/2020",
                                   "template": "soap",
                                   "client_timezone_identifier": "UTC"
                               },
                               files=files,
                               cookies={
                                   "authorization": self.auth_cookie,
                               })
        assert response.status_code == 401

    def test_invoke_diarization_with_valid_tokens_but_invalid_timezone_identifier(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "session_date": "10-24-2020",
                                   "template": "soap",
                                   "client_timezone_identifier": "gfhhfhdfhhs"
                               },
                               files=files,
                               cookies={
                                   "authorization": self.auth_cookie,
                                   "datastore_access_token": FAKE_ACCESS_TOKEN,
                                   "datastore_refresh_token": FAKE_REFRESH_TOKEN,
                               })
        assert response.status_code == 417

    def test_invoke_diarization_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "session_date": "10-24-2020",
                                   "template": "soap",
                                   "client_timezone_identifier": "UTC"
                               },
                               files=files,
                               cookies={
                                   "authorization": self.auth_cookie,
                                   "datastore_access_token": FAKE_ACCESS_TOKEN,
                                   "datastore_refresh_token": FAKE_REFRESH_TOKEN,
                               })
        assert response.status_code == 200
        assert "job_id" in response.json()

    def test_diarization_notifications_with_invalid_auth(self):
        response = self.client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
                               headers={
                               })
        assert response.status_code == 401

    def test_diarization_notifications_with_valid_auth_but_no_status(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
                               headers={
                                   "authorization": self.auth_cookie
                               },
                               params={
                               })
        assert response.status_code == 417

    def test_diarization_notifications_with_valid_auth_and_failed_status(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
                               headers={
                                   "authorization": self.auth_cookie
                               },
                               params={
                                   "status": "failed"
                               })
        assert response.status_code == 417

    def test_diarization_notifications_with_valid_auth_and_success_status_but_no_job_id(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
                               headers={
                                   "authorization": self.auth_cookie
                               },
                               params={
                                   "status": "success"
                               })
        assert response.status_code == 417

    def test_diarization_notifications_with_valid_auth_and_successful_params(self):
        self.fake_supabase_admin_client.return_authenticated_session = True
        self.fake_supabase_admin_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_admin_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_admin_client.select_returns_data = True

        assert self.fake_pinecone_client.fake_vectors_insertion is None
        assert self.fake_supabase_admin_client.fake_text is None

        response = self.client.post(AudioProcessingRouter.DIARIZATION_NOTIFICATION_ENDPOINT,
                               headers={
                                   "authorization": self.auth_cookie
                               },
                               params={
                                   "status": "success",
                                   "id": FAKE_JOB_ID
                               },
                               json=FAKE_DIARIZATION_RESULT)
        assert response.status_code == 200

        fake_diarization_summary = FAKE_DIARIZATION_RESULT['summary']['content']
        assert self.fake_supabase_admin_client.fake_text == fake_diarization_summary
        assert self.fake_pinecone_client.fake_vectors_insertion == fake_diarization_summary

    def test_diarization_cleaner_internal_formatting(self):
        clean_transcription = DiarizationCleaner().clean_transcription(input=FAKE_DIARIZATION_RESULT["results"],
                                                                       supabase_client_factory=self.fake_supabase_client_factory)
        assert clean_transcription == '[{"content": "Lo creo que es lo m\\u00e1s reciente.", "current_speaker": "S1", "start_time": 0.0, "end_time": 1.65}]'
