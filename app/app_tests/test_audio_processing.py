from fastapi import BackgroundTasks
from fastapi.testclient import TestClient

from ..data_processing.diarization_cleaner import DiarizationCleaner
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
DUMMY_WAV_FILE_LOCATION = "app/app_tests/data/maluma.wav"
AUDIO_WAV_FILETYPE = "audio/wav"
ENVIRONMENT = "testing"
FAKE_JOB_ID = "9876"
FAKE_DIARIZATION_RESULT = [
    {
        "start": 0.08,
        "end": 1.38,
        "confidence": 0.8865234,
        "channel": 0,
        "transcript": "Lo creo que lo más",
        "words": [
        "..."
        ],
        "speaker": 0,
        "id": "d06d3c59-6674-4e55-8895-28ae7be274eb"
    },
    {
        "start": 1.92,
        "end": 7.7,
        "confidence": 0.9221734,
        "channel": 0,
        "transcript": "reciente, los protectores, los iniciados, ¿no es cierto? Exacto, ahí vamos. Los iniciados que hacés de un periodista.",
        "words": [
        "..."
        ],
        "speaker": 0,
        "id": "5eac57fd-f3fc-4f6a-9840-94c09f1c3c18"
    },
    {
        "start": 8.08,
        "end": 8.58,
        "confidence": 0.8144531,
        "channel": 0,
        "transcript": "Periodista",
        "words": [
        "..."
        ],
        "speaker": 1,
        "id": "7c9d3b40-d603-4aa7-a77c-0f66901c72aa"
    },
    {
        "start": 9.76,
        "end": 15.54,
        "confidence": 0.77842885,
        "channel": 0,
        "transcript": "alcohólico, bipolar y drogadicto. Sí. Delicioso. Sí, así como Adifa suavecito. Suavecito.",
        "words": [
        "..."
        ],
        "speaker": 1,
        "id": "17bc28e5-018f-4015-b799-fb0ac96580cf"
    }
]

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
        self.auth_cookie, _ = self.auth_manager.create_access_token(user_id=FAKE_THERAPIST_ID)

        coordinator = EndpointServiceCoordinator(routers=[AudioProcessingRouter(environment=ENVIRONMENT,
                                                                                auth_manager=self.auth_manager,
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
                                        "template": "soap",
                                        "patient_id": FAKE_PATIENT_ID,
                                        "session_date": "04-04-2022",
                                        "client_timezone_identifier": "UTC",
                                    },
                                    files=files)
        assert response.status_code == 401

    def test_invoke_soap_transcription_success(self):
        self.fake_pinecone_client.vector_store_context_returns_data = True
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.NOTES_TRANSCRIPTION_ENDPOINT,
                                    data={
                                        "template": "soap",
                                        "patient_id": FAKE_PATIENT_ID,
                                        "session_date": "04-04-2022",
                                        "client_timezone_identifier": "UTC",
                                    },
                                    files=files,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN,
                                    })
        assert response.status_code == 200
        assert "session_report_id" in response.json()

    def test_invoke_free_form_transcription_success(self):
        self.fake_pinecone_client.vector_store_context_returns_data = True
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.NOTES_TRANSCRIPTION_ENDPOINT,
                               data={
                                    "template": "soap",
                                    "patient_id": FAKE_PATIENT_ID,
                                    "session_date": "04-04-2022",
                                    "client_timezone_identifier": "UTC",
                                },
                               files=files,
                               cookies={
                                   "authorization": self.auth_cookie,
                                   "datastore_access_token": FAKE_ACCESS_TOKEN,
                                   "datastore_refresh_token": FAKE_REFRESH_TOKEN,
                               })
        assert response.status_code == 200
        assert "session_report_id" in response.json()

    def test_invoke_diarization_with_no_auth(self):
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
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
                                        "session_date": "10-24-2020",
                                        "template": "soap",
                                        "client_timezone_identifier": "UTC"
                                    },
                                    files=files)
        assert response.status_code == 401

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
        self.fake_pinecone_client.vector_store_context_returns_data = True
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        files = {
            "audio_file": (DUMMY_WAV_FILE_LOCATION, open(DUMMY_WAV_FILE_LOCATION, 'rb'), AUDIO_WAV_FILETYPE)
        }
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
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
        assert "session_report_id" in response.json()

    def test_diarization_cleaner_internal_formatting(self):
        clean_transcription = DiarizationCleaner().clean_transcription(raw_diarization=FAKE_DIARIZATION_RESULT)
        assert clean_transcription == '[{"content": "Lo creo que lo más reciente, los protectores, los iniciados, ¿no es cierto? Exacto, ahí vamos. Los iniciados que hacés de un periodista.", "current_speaker": 0, "start_time": 0.08, "end_time": 7.7}, {"content": "Periodista alcohólico, bipolar y drogadicto. Sí. Delicioso. Sí, así como Adifa suavecito. Suavecito.", "current_speaker": 1, "start_time": 8.08, "end_time": 15.54}]'
