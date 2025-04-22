from fastapi.testclient import TestClient

from ..data_processing.diarization_cleaner import DiarizationCleaner
from ..dependencies.dependency_container import dependency_container
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
        # Clear out any old state between tests
        dependency_container._openai_client = None
        dependency_container._pinecone_client = None
        dependency_container._docupanda_client = None
        dependency_container._stripe_client = None
        dependency_container._deepgram_client = None
        dependency_container._resend_client = None
        dependency_container._influx_client = None
        dependency_container._testing_environment = "testing"

        self.fake_deepgram_client = dependency_container.inject_deepgram_client()
        self.fake_openai_client = dependency_container.inject_openai_client()
        self.fake_docupanda_client = dependency_container.inject_docupanda_client()
        self.fake_pinecone_client = dependency_container.inject_pinecone_client()
        self.auth_cookie, _ = AuthManager().create_auth_token(user_id=FAKE_THERAPIST_ID)

        coordinator = EndpointServiceCoordinator(routers=[AudioProcessingRouter(environment=ENVIRONMENT).router],
                                                 environment=ENVIRONMENT)
        self.client = TestClient(coordinator.app)

    def test_invoke_transcription_with_no_auth(self):
        response = self.client.post(AudioProcessingRouter.NOTES_TRANSCRIPTION_ENDPOINT,
                                    data={
                                        "template": "soap",
                                        "patient_id": FAKE_PATIENT_ID,
                                        "session_date": "04-04-2022",
                                        "client_timezone_identifier": "UTC",
                                        "file_path": FAKE_PATIENT_ID
                                    })
        assert response.status_code == 401

    def test_invoke_soap_transcription_success(self):
        self.fake_pinecone_client.vector_store_context_returns_data = True
        response = self.client.post(AudioProcessingRouter.NOTES_TRANSCRIPTION_ENDPOINT,
                                    data={
                                        "template": "soap",
                                        "patient_id": FAKE_PATIENT_ID,
                                        "session_date": "04-04-2022",
                                        "client_timezone_identifier": "UTC",
                                        "file_path": FAKE_SESSION_REPORT_ID
                                    },
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    },
                                    cookies={
                                        "authorization": self.auth_cookie
                                    })
        assert response.status_code == 200
        assert "session_report_id" in response.json()

    def test_invoke_free_form_transcription_success(self):
        self.fake_pinecone_client.vector_store_context_returns_data = True
        response = self.client.post(AudioProcessingRouter.NOTES_TRANSCRIPTION_ENDPOINT,
                               data={
                                    "template": "soap",
                                    "patient_id": FAKE_PATIENT_ID,
                                    "session_date": "04-04-2022",
                                    "client_timezone_identifier": "UTC",
                                    "file_path": FAKE_REFRESH_TOKEN
                                },
                                headers={
                                    "store-access-token": FAKE_ACCESS_TOKEN,
                                    "store-refresh-token": FAKE_REFRESH_TOKEN
                                },
                                cookies={
                                    "authorization": self.auth_cookie
                                })
        assert response.status_code == 200
        assert "session_report_id" in response.json()

    def test_invoke_diarization_with_no_auth(self):
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "session_date": "10-24-2020",
                                   "template": "soap",
                                   "client_timezone_identifier": "UTC",
                                   "file_path": DUMMY_WAV_FILE_LOCATION
                               })
        assert response.status_code == 401

    def test_invoke_diarization_with_valid_auth_but_empty_patient_id(self):
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": "",
                                   "session_date": "10-24-2020",
                                   "template": "soap",
                                   "client_timezone_identifier": "UTC",
                                   "file_path": DUMMY_WAV_FILE_LOCATION
                               },
                               headers={
                                   "store-access-token": FAKE_ACCESS_TOKEN,
                                   "store-refresh-token": FAKE_REFRESH_TOKEN
                               },
                               cookies={
                                   "authorization": self.auth_cookie,
                               })
        assert response.status_code == 422

    def test_invoke_diarization_with_valid_auth_but_invalid_date_format(self):
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "session_date": "10/24/2020",
                                   "template": "soap",
                                   "client_timezone_identifier": "UTC",
                                   "file_path": DUMMY_WAV_FILE_LOCATION
                               },
                               headers={
                                   "store-access-token": FAKE_ACCESS_TOKEN,
                                   "store-refresh-token": FAKE_REFRESH_TOKEN
                               },
                               cookies={
                                   "authorization": self.auth_cookie,
                               })
        assert response.status_code == 400

    def test_invoke_diarization_with_valid_tokens_but_invalid_timezone_identifier(self):
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "session_date": "10-24-2020",
                                   "template": "soap",
                                   "client_timezone_identifier": "gfhhfhdfhhs",
                                   "file_path": DUMMY_WAV_FILE_LOCATION
                               },
                               headers={
                                   "store-access-token": FAKE_ACCESS_TOKEN,
                                   "store-refresh-token": FAKE_REFRESH_TOKEN
                               },
                               cookies={
                                   "authorization": self.auth_cookie
                               })
        assert response.status_code == 400

    def test_invoke_diarization_success(self):
        self.fake_pinecone_client.vector_store_context_returns_data = True
        response = self.client.post(AudioProcessingRouter.DIARIZATION_ENDPOINT,
                               data={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "session_date": "10-24-2020",
                                   "template": "soap",
                                   "client_timezone_identifier": "UTC",
                                   "file_path": FAKE_SESSION_REPORT_ID
                               },
                               headers={
                                   "store-access-token": FAKE_ACCESS_TOKEN,
                                   "store-refresh-token": FAKE_REFRESH_TOKEN
                               },
                               cookies={
                                   "authorization": self.auth_cookie
                               })
        assert response.status_code == 200
        assert "session_report_id" in response.json()

    def test_diarization_cleaner_internal_formatting(self):
        clean_transcription = DiarizationCleaner().clean_transcription(raw_diarization=FAKE_DIARIZATION_RESULT)
        assert clean_transcription == '[{"content": "Lo creo que lo más reciente, los protectores, los iniciados, ¿no es cierto? Exacto, ahí vamos. Los iniciados que hacés de un periodista.", "current_speaker": 0, "start_time": 0.08, "end_time": 7.7}, {"content": "Periodista alcohólico, bipolar y drogadicto. Sí. Delicioso. Sí, así como Adifa suavecito. Suavecito.", "current_speaker": 1, "start_time": 8.08, "end_time": 15.54}]'
