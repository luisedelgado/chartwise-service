from datetime import timedelta

from fastapi.testclient import TestClient

from ..dependencies.fake.fake_async_openai import FakeAsyncOpenAI
from ..dependencies.fake.fake_supabase_factory_manager import FakeSupabaseManagerFactory
from ..dependencies.fake.fake_supabase_manager import FakeSupabaseManager
from ..managers.assistant_manager import AssistantManager
from ..managers.audio_processing_manager import AudioProcessingManager
from ..managers.auth_manager import AuthManager
from ..routers.assistant_router import AssistantRouter
from ..routers.security_router import SecurityRouter
from ..service_coordinator import EndpointServiceCoordinator

FAKE_AUTH_COOKIE = "my-auth-cookie"
FAKE_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
FAKE_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
FAKE_SESSION_REPORT_ID = "09b6da8d-a58e-45e2-9022-7d58ca02266b"
FAKE_REFRESH_TOKEN = "refreshToken"
FAKE_ACCESS_TOKEN = "accessToken"
FAKE_TZ_IDENTIFIER = "UTC"
ENVIRONMENT = "testing"

class TestingHarnessAssistantRouter:

    def setup_method(self):
        self.auth_manager = AuthManager()
        self.assistant_manager = AssistantManager()
        self.audio_processing_manager = AudioProcessingManager()
        self.fake_openai_manager = FakeAsyncOpenAI(create_completion_returns_data=True)
        self.fake_supabase_admin_manager = FakeSupabaseManager()
        self.fake_supabase_user_manager = FakeSupabaseManager()
        self.fake_supabase_manager_factory = FakeSupabaseManagerFactory(fake_supabase_admin_manager=self.fake_supabase_admin_manager,
                                                                        fake_supabase_user_manager=self.fake_supabase_user_manager)
        self.auth_cookie = self.auth_manager.create_access_token(data={"sub": FAKE_THERAPIST_ID},
                                                                 expires_delta=timedelta(minutes=5))

        coordinator = EndpointServiceCoordinator(routers=[AssistantRouter(environment=ENVIRONMENT,
                                                                          auth_manager=self.auth_manager,
                                                                          assistant_manager=self.assistant_manager,
                                                                          openai_manager=self.fake_openai_manager,
                                                                          supabase_manager_factory=self.fake_supabase_manager_factory).router,
                                                          SecurityRouter(auth_manager=self.auth_manager,
                                                                         assistant_manager=self.assistant_manager,
                                                                         supabase_manager_factory=self.fake_supabase_manager_factory).router],
                                                 environment="dev")
        self.client = TestClient(coordinator.app)

    def test_insert_new_session_with_missing_auth_token(self):
        response = self.client.post(AssistantRouter.SESSIONS_ENDPOINT,
                               json={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                   "date": "01-01-2020",
                                   "client_timezone_identifier": "UTC",
                                   "datastore_access_token": FAKE_ACCESS_TOKEN,
                                   "datastore_refresh_token": FAKE_REFRESH_TOKEN,
                                   "source": "manual_input"
                               })
        assert response.status_code == 401

    def test_insert_new_session_with_auth_token_but_supabase_returns_unathenticated_session(self):
        response = self.client.post(AssistantRouter.SESSIONS_ENDPOINT,
                               cookies={
                                    "authorization": self.auth_cookie,
                                    "datastore_access_token": FAKE_ACCESS_TOKEN,
                                    "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                },
                                json={
                                    "patient_id": FAKE_PATIENT_ID,
                                    "therapist_id": FAKE_THERAPIST_ID,
                                    "text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                    "date": "01-01-2020",
                                    "client_timezone_identifier": "UTC",
                                    "datastore_access_token": FAKE_ACCESS_TOKEN,
                                    "datastore_refresh_token": FAKE_REFRESH_TOKEN,
                                    "source": "manual_input"
                               })
        assert response.status_code == 401

    def test_insert_new_session_with_valid_authentication_but_invalid_date_format(self):
        self.fake_supabase_user_manager.return_authenticated_session = True
        self.fake_supabase_user_manager.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_manager.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "client_timezone_identifier": "UTC",
                                        "therapist_id": FAKE_THERAPIST_ID,
                                        "text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                        "date": "01/01/2020",
                                        "source": "manual_input"
                                    })
        assert response.status_code == 400

    def test_insert_new_session_with_valid_auth_but_undefined_source(self):
        self.fake_supabase_user_manager.return_authenticated_session = True
        self.fake_supabase_user_manager.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_manager.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "client_timezone_identifier": "UTC",
                                        "therapist_id": FAKE_THERAPIST_ID,
                                        "text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                        "date": "01-01-2020",
                                        "source": "undefined"
                                    })
        assert response.status_code == 400

    # def test_insert_new_session_success(self):
    #     self.fake_supabase_user_manager.return_authenticated_session = True
    #     self.fake_supabase_user_manager.fake_access_token = FAKE_ACCESS_TOKEN
    #     self.fake_supabase_user_manager.fake_refresh_token = FAKE_REFRESH_TOKEN
    #     self.fake_supabase_user_manager.select_returns_data = True

    #     assert self.fake_supabase_user_manager.fake_insert_text == None
    #     insert_text = "El jugador favorito de Lionel Andres siempre fue Aimar."
    #     response = self.client.post(AssistantRouter.SESSIONS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": self.auth_cookie,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 json={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                     "text": insert_text,
    #                                     "date": "01-01-2020",
    #                                     "client_timezone_identifier": "UTC",
    #                                     "source": "manual_input"
    #                                 })
    #     assert response.status_code == 200
    #     assert self.fake_supabase_user_manager.fake_insert_text == insert_text

    # def test_update_session_with_invalid_auth(self):
    #     response = self.client.put(AssistantRouter.SESSIONS_ENDPOINT,
    #                                 json={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                     "client_timezone_identifier": "UTC",
    #                                     "text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
    #                                     "date": "01-01-2020",
    #                                     "source": "manual_input",
    #                                     "session_notes_id": self.assistant_manager.FAKE_SESSION_NOTES_ID
    #                                 })
    #     assert response.status_code == 401

    # def test_update_session_with_valid_auth_but_invalid_date_format(self):
    #     response = self.client.put(AssistantRouter.SESSIONS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 json={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                     "client_timezone_identifier": "UTC",
    #                                     "text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
    #                                     "date": "01/01/2020",
    #                                     "source": "manual_input",
    #                                     "session_notes_id": self.assistant_manager.FAKE_SESSION_NOTES_ID
    #                                 })
    #     assert response.status_code == 400

    # def test_update_session_with_valid_auth_but_invalid_timezone(self):
    #     response = self.client.put(AssistantRouter.SESSIONS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 json={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                     "client_timezone_identifier": "fsrghshfsdhfsd",
    #                                     "text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
    #                                     "date": "01-01-2020",
    #                                     "source": "manual_input",
    #                                     "session_notes_id": self.assistant_manager.FAKE_SESSION_NOTES_ID
    #                                 })
    #     assert response.status_code == 400

    # def test_update_session_with_valid_auth_but_undefined_source(self):
    #     response = self.client.put(AssistantRouter.SESSIONS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 json={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                     "client_timezone_identifier": "UTC",
    #                                     "text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
    #                                     "date": "01-01-2020",
    #                                     "source": "undefined",
    #                                     "session_notes_id": self.assistant_manager.FAKE_SESSION_NOTES_ID
    #                                 })
    #     assert response.status_code == 400

    # def test_update_session_success(self):
    #     response = self.client.put(AssistantRouter.SESSIONS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 json={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": self.auth_manager.FAKE_USER_ID,
    #                                     "client_timezone_identifier": "UTC",
    #                                     "text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
    #                                     "date": "01-01-2020",
    #                                     "source": "manual_input",
    #                                     "session_notes_id": self.assistant_manager.FAKE_SESSION_NOTES_ID
    #                                 })
    #     assert response.status_code == 200

    # def test_delete_session_with_invalid_auth(self):
    #     response = self.client.delete(AssistantRouter.SESSIONS_ENDPOINT,
    #                                     params={
    #                                         "session_report_id": FAKE_SESSION_REPORT_ID,
    #                                     })
    #     assert response.status_code == 401

    # def test_delete_session_with_valid_auth_but_empty_session_notes_id(self):
    #     response = self.client.delete(AssistantRouter.SESSIONS_ENDPOINT,
    #                                     cookies={
    #                                         "authorization": FAKE_AUTH_COOKIE,
    #                                         "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                         "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                     },
    #                                     params={
    #                                         "session_report_id": "",
    #                                     })
    #     assert response.status_code == 400

    # def test_delete_session_with_valid_auth_but_invalid_session_notes_id(self):
    #     response = self.client.delete(AssistantRouter.SESSIONS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "session_report_id": "4123sdggsdgsdgdsgsdg",
    #                                 })
    #     assert response.status_code == 400

    # def test_delete_session_with_valid_auth_but_invalid_therapist_id(self):
    #     response = self.client.delete(AssistantRouter.SESSIONS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "session_report_id": FAKE_SESSION_REPORT_ID,
    #                                     "therapist_id": ""
    #                                 })
    #     assert response.status_code == 400

    # def test_delete_session_success(self):
    #     response = self.client.delete(AssistantRouter.SESSIONS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "session_report_id": FAKE_SESSION_REPORT_ID,
    #                                     "therapist_id": self.auth_manager.FAKE_USER_ID
    #                                 })
    #     assert response.status_code == 200

    # # TODO: Uncomment when figure out how to test streaming
    # # def test_session_query_with_missing_auth(self):
    # #     response = self.client.post(AssistantRouter.QUERIES_ENDPOINT,
    # #                                 json={
    # #                                     "patient_id": FAKE_PATIENT_ID,
    # #                                     "therapist_id": FAKE_THERAPIST_ID,
    # #                                     "text": "Quien es el jugador favorito de Lionel Andres?",
    # #                                 })
    # #     assert response.status_code == 401

    # # def test_session_query_with_auth_but_no_datastore_tokens(self):
    # #     response = self.client.post(AssistantRouter.QUERIES_ENDPOINT,
    # #                                 cookies={
    # #                                     "authorization": FAKE_AUTH_COOKIE,
    # #                                 },
    # #                                 json={
    # #                                     "patient_id": FAKE_PATIENT_ID,
    # #                                     "therapist_id": FAKE_THERAPIST_ID,
    # #                                     "text": "Quien es el jugador favorito de Lionel Andres?",
    # #                                 })
    # #     assert response.status_code == 401

    # # def test_session_query_with_valid_auth_but_empty_therapist_id(self):
    # #     response = self.client.post(AssistantRouter.QUERIES_ENDPOINT,
    # #                                 cookies={
    # #                                     "authorization": FAKE_AUTH_COOKIE,
    # #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    # #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    # #                                 },
    # #                                 json={
    # #                                     "patient_id": FAKE_PATIENT_ID,
    # #                                     "therapist_id": "",
    # #                                     "text": "Quien es el jugador favorito de Lionel Andres?",
    # #                                 })
    # #     assert response.status_code == 400

    # # def test_session_query_with_valid_auth_but_empty_patient_id(self):
    # #     response = self.client.post(AssistantRouter.QUERIES_ENDPOINT,
    # #                                 cookies={
    # #                                     "authorization": FAKE_AUTH_COOKIE,
    # #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    # #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    # #                                 },
    # #                                 json={
    # #                                     "patient_id": "",
    # #                                     "therapist_id": FAKE_THERAPIST_ID,
    # #                                     "text": "Quien es el jugador favorito de Lionel Andres?",
    # #                                 })
    # #     assert response.status_code == 400

    # # def test_session_query_with_valid_auth_but_empty_text(self):
    # #     response = self.client.post(AssistantRouter.QUERIES_ENDPOINT,
    # #                                 cookies={
    # #                                     "authorization": FAKE_AUTH_COOKIE,
    # #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    # #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    # #                                 },
    # #                                 json={
    # #                                     "patient_id": FAKE_PATIENT_ID,
    # #                                     "therapist_id": FAKE_THERAPIST_ID,
    # #                                     "text": "",
    # #                                 })
    # #     assert response.status_code == 400

    # # def test_session_query_success(self):
    # #     response = self.client.post(AssistantRouter.QUERIES_ENDPOINT,
    # #                                 cookies={
    # #                                     "authorization": FAKE_AUTH_COOKIE,
    # #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    # #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    # #                                 },
    # #                                 json={
    # #                                     "patient_id": FAKE_PATIENT_ID,
    # #                                     "therapist_id": self.auth_manager.FAKE_USER_ID,
    # #                                     "text": "Quien es el jugador favorito de Lionel?",
    # #                                 })
    # #     assert response.status_code == 200

    # def test_greeting_with_missing_auth(self):
    #     response = self.client.get(AssistantRouter.GREETINGS_ENDPOINT,
    #                                 params={
    #                                     "client_tz_identifier": FAKE_TZ_IDENTIFIER,
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 401

    # def test_greeting_with_auth_but_missing_datastore_tokens(self):
    #     response = self.client.get(AssistantRouter.GREETINGS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                 },
    #                                 params={
    #                                     "client_tz_identifier": FAKE_TZ_IDENTIFIER,
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 401

    # def test_greeting_with_invalid_tz_identifier(self):
    #     response = self.client.get(AssistantRouter.GREETINGS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "client_tz_identifier": "boom",
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 400

    # def test_greeting_with_invalid_therapist_id(self):
    #     response = self.client.get(AssistantRouter.GREETINGS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "client_tz_identifier": "boom",
    #                                     "therapist_id": "",
    #                                 })
    #     assert response.status_code == 400

    # def test_greeting_success(self):
    #     response = self.client.get(AssistantRouter.GREETINGS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "client_tz_identifier": "boom",
    #                                     "therapist_id": "",
    #                                 })
    #     assert response.status_code == 400

    # def test_presession_summary_with_missing_auth(self):
    #     response = self.client.get(AssistantRouter.PRESESSION_TRAY_ENDPOINT,
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": FAKE_THERAPIST_ID
    #                                 })
    #     assert response.status_code == 401

    # def test_presession_summary_with_auth_but_missing_datastore_tokens(self):
    #     response = self.client.get(AssistantRouter.PRESESSION_TRAY_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                 },
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": FAKE_THERAPIST_ID
    #                                 })
    #     assert response.status_code == 401

    # def test_presession_summary_with_invalid_therapist_id(self):
    #     response = self.client.get(AssistantRouter.PRESESSION_TRAY_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": ""
    #                                 })
    #     assert response.status_code == 400

    # def test_presession_summary_with_invalid_patient_id(self):
    #     response = self.client.get(AssistantRouter.PRESESSION_TRAY_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "patient_id": "",
    #                                     "therapist_id": FAKE_THERAPIST_ID
    #                                 })
    #     assert response.status_code == 400

    # def test_presession_summary_success(self):
    #     response = self.client.get(AssistantRouter.PRESESSION_TRAY_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": self.auth_manager.FAKE_USER_ID
    #                                 })
    #     assert response.status_code == 200

    # def test_question_suggestions_with_missing_auth(self):
    #     response = self.client.get(AssistantRouter.QUESTION_SUGGESTIONS_ENDPOINT,
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 401

    # def test_question_suggestions_with_auth_but_missing_datastore_tokens(self):
    #     response = self.client.get(AssistantRouter.QUESTION_SUGGESTIONS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                 },
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 401

    # def test_question_suggestions_with_invalid_therapist_id(self):
    #     response = self.client.get(AssistantRouter.QUESTION_SUGGESTIONS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": "",
    #                                 })
    #     assert response.status_code == 400

    # def test_question_suggestions_with_invalid_patient_id(self):
    #     response = self.client.get(AssistantRouter.QUESTION_SUGGESTIONS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "patient_id": "",
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 400

    # def test_question_suggestions_success(self):
    #     response = self.client.get(AssistantRouter.QUESTION_SUGGESTIONS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": self.auth_manager.FAKE_USER_ID,
    #                                 })
    #     assert response.status_code == 200

    # def test_add_patient_with_missing_auth(self):
    #     response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
    #                                 json={
    #                                     "first_name": "Pepito",
    #                                     "last_name": "Perez",
    #                                     "birth_date": "10-24-1991",
    #                                     "gender": "female",
    #                                     "email": "foo@foo.foo",
    #                                     "phone_number": "123",
    #                                     "consentment_channel": "verbal",
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 401

    # def test_add_patient_with_auth_but_missing_datastore_tokens(self):
    #     response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                 },
    #                                 json={
    #                                     "first_name": "Pepito",
    #                                     "last_name": "Perez",
    #                                     "birth_date": "10-24-1991",
    #                                     "gender": "female",
    #                                     "email": "foo@foo.foo",
    #                                     "phone_number": "123",
    #                                     "consentment_channel": "verbal",
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 401

    # def test_add_patient_with_undefined_gender(self):
    #     response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 json={
    #                                     "first_name": "Pepito",
    #                                     "last_name": "Perez",
    #                                     "birth_date": "10-24-1991",
    #                                     "gender": "undefined",
    #                                     "email": "foo@foo.foo",
    #                                     "phone_number": "123",
    #                                     "consentment_channel": "verbal",
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 400

    # def test_add_patient_with_undefined_consentment_channel(self):
    #     response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 json={
    #                                     "first_name": "Pepito",
    #                                     "last_name": "Perez",
    #                                     "birth_date": "10-24-1991",
    #                                     "gender": "male",
    #                                     "email": "foo@foo.foo",
    #                                     "phone_number": "123",
    #                                     "consentment_channel": "undefined",
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 400

    # def test_add_patient_with_invalid_date(self):
    #     response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 json={
    #                                     "first_name": "Pepito",
    #                                     "last_name": "Perez",
    #                                     "birth_date": "10/24/1991",
    #                                     "gender": "male",
    #                                     "email": "foo@foo.foo",
    #                                     "phone_number": "123",
    #                                     "consentment_channel": "verbal",
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 400

    # def test_add_patient_success(self):
    #     response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 json={
    #                                     "first_name": "Pepito",
    #                                     "last_name": "Perez",
    #                                     "birth_date": "10-24-1991",
    #                                     "gender": "male",
    #                                     "email": "foo@foo.foo",
    #                                     "phone_number": "123",
    #                                     "consentment_channel": "verbal",
    #                                     "therapist_id": self.auth_manager.FAKE_USER_ID,
    #                                 })
    #     assert response.status_code == 200

    # def test_update_patient_with_missing_auth(self):
    #     response = self.client.put(AssistantRouter.PATIENTS_ENDPOINT,
    #                                 json={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "first_name": "Pepito",
    #                                     "last_name": "Perez",
    #                                     "birth_date": "10-24-1991",
    #                                     "gender": "female",
    #                                     "email": "foo@foo.foo",
    #                                     "phone_number": "123",
    #                                     "consentment_channel": "verbal",
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 401

    # def test_update_patient_with_auth_but_missing_datastore_tokens(self):
    #     response = self.client.put(AssistantRouter.PATIENTS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                 },
    #                                 json={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "first_name": "Pepito",
    #                                     "last_name": "Perez",
    #                                     "birth_date": "10-24-1991",
    #                                     "gender": "female",
    #                                     "email": "foo@foo.foo",
    #                                     "phone_number": "123",
    #                                     "consentment_channel": "verbal",
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 401

    # def test_update_patient_with_empty_patient_id(self):
    #     response = self.client.put(AssistantRouter.PATIENTS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 json={
    #                                     "patient_id": "",
    #                                     "first_name": "Pepito",
    #                                     "last_name": "Perez",
    #                                     "birth_date": "10-24-1991",
    #                                     "gender": "female",
    #                                     "email": "foo@foo.foo",
    #                                     "phone_number": "123",
    #                                     "consentment_channel": "verbal",
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 400

    # def test_update_patient_with_empty_therapist_id(self):
    #     response = self.client.put(AssistantRouter.PATIENTS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 json={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "first_name": "Pepito",
    #                                     "last_name": "Perez",
    #                                     "birth_date": "10-24-1991",
    #                                     "gender": "female",
    #                                     "email": "foo@foo.foo",
    #                                     "phone_number": "123",
    #                                     "consentment_channel": "verbal",
    #                                     "therapist_id": "",
    #                                 })
    #     assert response.status_code == 400

    # def test_update_patient_success(self):
    #     response = self.client.put(AssistantRouter.PATIENTS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 json={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "first_name": "Pepito",
    #                                     "last_name": "Perez",
    #                                     "birth_date": "10-24-1991",
    #                                     "gender": "female",
    #                                     "email": "foo@foo.foo",
    #                                     "phone_number": "123",
    #                                     "consentment_channel": "verbal",
    #                                     "therapist_id": self.auth_manager.FAKE_USER_ID,
    #                                 })
    #     assert response.status_code == 200

    # def test_delete_patient_with_missing_auth(self):
    #     response = self.client.delete(AssistantRouter.PATIENTS_ENDPOINT,
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 401

    # def test_delete_patient_with_auth_but_missing_datastore_tokens(self):
    #     response = self.client.delete(AssistantRouter.PATIENTS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                 },
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 401

    # def test_delete_patient_with_empty_therapist_id(self):
    #     response = self.client.delete(AssistantRouter.PATIENTS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": "",
    #                                 })
    #     assert response.status_code == 400

    # def test_delete_patient_with_empty_patient_id(self):
    #     response = self.client.delete(AssistantRouter.PATIENTS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "patient_id": "",
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 400

    # def test_delete_patient_success(self):
    #     response = self.client.delete(AssistantRouter.PATIENTS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": self.auth_manager.FAKE_USER_ID,
    #                                 })
    #     assert response.status_code == 200

    # def test_frequent_topics_with_missing_auth(self):
    #     response = self.client.get(AssistantRouter.TOPICS_ENDPOINT,
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 401

    # def test_frequent_topics_with_auth_but_missing_datastore_tokens(self):
    #     response = self.client.get(AssistantRouter.TOPICS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                 },
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 401

    # def test_frequent_topics_with_missing_therapist_id(self):
    #     response = self.client.get(AssistantRouter.TOPICS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": "",
    #                                 })
    #     assert response.status_code == 400

    # def test_frequent_topics_with_missing_patient_id(self):
    #     response = self.client.get(AssistantRouter.TOPICS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "patient_id": "",
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                 })
    #     assert response.status_code == 400

    # def test_frequent_topics_success(self):
    #     response = self.client.get(AssistantRouter.TOPICS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                     "datastore_access_token": FAKE_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": FAKE_REFRESH_TOKEN
    #                                 },
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": self.auth_manager.FAKE_USER_ID,
    #                                 })
    #     assert response.status_code == 200

    # def test_transform_with_template_with_missing_auth(self):
    #     response = self.client.post(AssistantRouter.TEMPLATES_ENDPOINT,
    #                                 json={
    #                                     "template": "soap",
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                     "session_notes_text": "My fake session notes"
    #                                 })
    #     assert response.status_code == 401

    # def test_transform_with_template_with_empty_therapist_id(self):
    #     response = self.client.post(AssistantRouter.TEMPLATES_ENDPOINT,
    #                                 json={
    #                                     "template": "soap",
    #                                     "therapist_id": "",
    #                                     "session_notes_text": "My fake session notes"
    #                                 },
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                 },)
    #     assert response.status_code == 400

    # def test_transform_with_template_with_free_form_value(self):
    #     response = self.client.post(AssistantRouter.TEMPLATES_ENDPOINT,
    #                                 json={
    #                                     "template": "free_form",
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                     "session_notes_text": "My fake session notes"
    #                                 },
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                 },)
    #     assert response.status_code == 400

    # def test_transform_with_template_with_empty_notes(self):
    #     response = self.client.post(AssistantRouter.TEMPLATES_ENDPOINT,
    #                                 json={
    #                                     "template": "soap",
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                     "session_notes_text": ""
    #                                 },
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                 },)
    #     assert response.status_code == 400

    # def test_transform_with_template_success(self):
    #     response = self.client.post(AssistantRouter.TEMPLATES_ENDPOINT,
    #                                 json={
    #                                     "template": "soap",
    #                                     "therapist_id": self.auth_manager.FAKE_USER_ID,
    #                                     "session_notes_text": "My fake session notes"
    #                                 },
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                 },)
    #     assert response.status_code == 200
