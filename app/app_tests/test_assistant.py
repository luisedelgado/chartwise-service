from datetime import timedelta

from fastapi.testclient import TestClient

from ..dependencies.fake.fake_async_openai import FakeAsyncOpenAI
from ..dependencies.fake.fake_pinecone_client import FakePineconeClient
from ..dependencies.fake.fake_supabase_client import FakeSupabaseClient
from ..dependencies.fake.fake_supabase_client_factory import FakeSupabaseClientFactory
from ..internal.router_dependencies import RouterDependencies
from ..internal.schemas import SessionUploadStatus
from ..managers.assistant_manager import AssistantManager
from ..managers.audio_processing_manager import AudioProcessingManager
from ..managers.auth_manager import AuthManager
from ..routers.assistant_router import AssistantRouter
from ..service_coordinator import EndpointServiceCoordinator

FAKE_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
FAKE_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
FAKE_SECOND_THERAPIST_ID = "3b0ca3b4-4d3e-42a1-94f8-59a7c141e162"
FAKE_SESSION_REPORT_ID = "09b6da8d-a58e-45e2-9022-7d58ca02266b"
FAKE_REFRESH_TOKEN = "3ac77394-86b5-42dc-be14-0b92414d8443"
FAKE_ACCESS_TOKEN = "884f507c-f391-4248-91c4-7c25a138633a"
TZ_IDENTIFIER = "UTC"
ENVIRONMENT = "testing"

class TestingHarnessAssistantRouter:

    def setup_method(self):
        self.auth_manager = AuthManager()
        self.assistant_manager = AssistantManager()
        self.audio_processing_manager = AudioProcessingManager()
        self.fake_openai_client = FakeAsyncOpenAI()
        self.fake_supabase_admin_client = FakeSupabaseClient()
        self.fake_supabase_user_client = FakeSupabaseClient()
        self.fake_pinecone_client = FakePineconeClient()
        self.fake_supabase_client_factory = FakeSupabaseClientFactory(fake_supabase_admin_client=self.fake_supabase_admin_client,
                                                                      fake_supabase_user_client=self.fake_supabase_user_client)
        self.auth_cookie, _ = self.auth_manager.create_access_token(user_id=FAKE_THERAPIST_ID)

        coordinator = EndpointServiceCoordinator(routers=[AssistantRouter(environment=ENVIRONMENT,
                                                                          auth_manager=self.auth_manager,
                                                                          assistant_manager=self.assistant_manager,
                                                                          router_dependencies=RouterDependencies(openai_client=self.fake_openai_client,
                                                                                                                 pinecone_client=self.fake_pinecone_client,
                                                                                                                 supabase_client_factory=self.fake_supabase_client_factory)).router],
                                                 environment=ENVIRONMENT)
        self.client = TestClient(coordinator.app)

    def test_insert_new_session_with_missing_auth_token(self):
        response = self.client.post(AssistantRouter.SESSIONS_ENDPOINT,
                               json={
                                   "insert_payload": {
                                        "patient_id": FAKE_PATIENT_ID,
                                        "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                        "session_date": "01-01-2020",
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN,
                                        "source": "manual_input"
                                   },
                                   "client_timezone_identifier": TZ_IDENTIFIER,
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
                                    "insert_payload": {
                                        "patient_id": FAKE_PATIENT_ID,
                                        "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                        "session_date": "01-01-2020",
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN,
                                        "source": "manual_input"
                                    },
                                    "client_timezone_identifier": TZ_IDENTIFIER,
                               })
        assert response.status_code == 401

    def test_insert_new_session_with_valid_authentication_but_invalid_date_format(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "insert_payload": {
                                            "patient_id": FAKE_PATIENT_ID,
                                            "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                            "session_date": "01/01/2020",
                                            "source": "manual_input"
                                        },
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                    })
        assert response.status_code == 400

    def test_insert_new_session_with_valid_auth_but_undefined_source(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "insert_payload": {
                                            "patient_id": FAKE_PATIENT_ID,
                                            "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                            "session_date": "01-01-2020",
                                            "source": "undefined"
                                        },
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                    })
        assert response.status_code == 400

    def test_insert_new_session_with_empty_patient_id(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True

        assert self.fake_supabase_user_client.fake_text == None
        insert_text = "El jugador favorito de Lionel Andres siempre fue Aimar."
        response = self.client.post(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "insert_payload": {
                                            "patient_id": "",
                                            "notes_text": insert_text,
                                            "session_date": "01-01-2020",
                                            "source": "manual_input"
                                        },
                                        "client_timezone_identifier": "gfsghfsdhgdsgs",
                                    })
        assert response.status_code == 400

    def test_insert_new_session_with_invalid_timezone(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True

        assert self.fake_supabase_user_client.fake_text == None
        insert_text = "El jugador favorito de Lionel Andres siempre fue Aimar."
        response = self.client.post(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "insert_payload": {
                                            "patient_id": FAKE_PATIENT_ID,
                                            "notes_text": insert_text,
                                            "session_date": "01-01-2020",
                                            "source": "manual_input"
                                        },
                                        "client_timezone_identifier": "gfsghfsdhgdsgs",
                                    })
        assert response.status_code == 400

    def test_insert_new_session_success(self):
        self.fake_pinecone_client.vector_store_context_returns_data = True
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True

        assert self.fake_supabase_user_client.fake_text == None
        insert_text = "El jugador favorito de Lionel Andres siempre fue Aimar."
        response = self.client.post(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "insert_payload": {
                                            "patient_id": FAKE_PATIENT_ID,
                                            "notes_text": insert_text,
                                            "session_date": "01-01-2020",
                                            "source": "manual_input"
                                        },
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                    })
        assert response.status_code == 200
        assert self.fake_supabase_user_client.fake_text == insert_text
        assert self.fake_supabase_user_client.session_upload_processing_status == SessionUploadStatus.SUCCESS.value

    def test_update_session_with_missing_auth_token(self):
        response = self.client.put(AssistantRouter.SESSIONS_ENDPOINT,
                                    json={
                                        "update_payload": {
                                            "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                            "session_date": "01-01-2020",
                                            "source": "manual_input",
                                            "id": FAKE_SESSION_REPORT_ID
                                        },
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                    })
        assert response.status_code == 401

    def test_update_session_with_auth_token_but_supabase_returns_unathenticated_session(self):
        response = self.client.put(AssistantRouter.SESSIONS_ENDPOINT,
                               cookies={
                                    "authorization": self.auth_cookie,
                                    "datastore_access_token": FAKE_ACCESS_TOKEN,
                                    "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                },
                                json={
                                    "update_payload": {
                                        "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                        "session_date": "01/01/2020",
                                        "source": "manual_input",
                                        "id": FAKE_SESSION_REPORT_ID
                                    },
                                    "client_timezone_identifier": TZ_IDENTIFIER,
                               })
        assert response.status_code == 401

    def test_update_session_with_valid_auth_but_invalid_date_format(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.put(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "update_payload": {
                                            "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                            "session_date": "01/01/2020",
                                            "source": "manual_input",
                                            "id": FAKE_SESSION_REPORT_ID
                                        },
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                    })
        assert response.status_code == 400

    def test_update_session_with_valid_auth_but_invalid_timezone(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.put(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "update_payload": {
                                            "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                            "session_date": "01-01-2020",
                                            "source": "manual_input",
                                            "id": FAKE_SESSION_REPORT_ID
                                        },
                                        "client_timezone_identifier": "fsrghshfsdhfsd",
                                    })
        assert response.status_code == 400

    def test_update_session_with_valid_auth_but_undefined_source(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.put(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "update_payload": {
                                            "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                            "session_date": "01-01-2020",
                                            "source": "undefined",
                                            "id": FAKE_SESSION_REPORT_ID
                                        },
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                    })
        assert response.status_code == 400

    def test_update_session_with_valid_auth_but_empty_session_notes_id(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.put(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "update_payload": {
                                            "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                            "session_date": "01-01-2020",
                                            "source": "undefined",
                                            "id": "",
                                        },
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                    })
        assert response.status_code == 400

    def test_update_session_with_valid_auth_but_undefined_source(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.put(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "update_payload": {
                                            "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                            "session_date": "01-01-2020",
                                            "source": "undefined",
                                            "id": FAKE_SESSION_REPORT_ID
                                        },
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                    })
        assert response.status_code == 400

    def test_update_session_with_different_text_success(self):
        self.fake_pinecone_client.vector_store_context_returns_data = True
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.fake_text = "initial text"
        self.fake_supabase_user_client.select_returns_data = True
        update_text = "new_text"
        response = self.client.put(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "update_payload": {
                                            "notes_text": update_text,
                                            "session_date": "01-01-2020",
                                            "source": "manual_input",
                                            "id": FAKE_SESSION_REPORT_ID
                                        },
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                    })
        assert response.status_code == 200
        assert self.fake_supabase_user_client.fake_text == update_text

    def test_update_session_with_same_text_success(self):
        self.fake_pinecone_client.vector_store_context_returns_data = True
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        update_text = "initial text"
        self.fake_supabase_user_client.fake_text = update_text
        self.fake_supabase_user_client.select_returns_data = True
        response = self.client.put(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "update_payload": {
                                            "notes_text": update_text,
                                            "session_date": "01-01-2020",
                                            "source": "manual_input",
                                            "id": FAKE_SESSION_REPORT_ID
                                        },
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                    })
        assert response.status_code == 200
        assert self.fake_supabase_user_client.fake_text == update_text

    def test_delete_session_with_invalid_auth(self):
        response = self.client.delete(AssistantRouter.SESSIONS_ENDPOINT,
                                        params={
                                            "session_report_id": FAKE_SESSION_REPORT_ID,
                                        })
        assert response.status_code == 401

    def test_delete_session_with_valid_auth_token_but_supabase_returns_unathenticated_session(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.delete(AssistantRouter.SESSIONS_ENDPOINT,
                                        cookies={
                                            "authorization": self.auth_cookie,
                                            "datastore_access_token": FAKE_ACCESS_TOKEN,
                                            "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                        },
                                        params={
                                            "session_report_id": FAKE_SESSION_REPORT_ID,
                                        })
        assert response.status_code == 400

    def test_delete_session_with_valid_auth_but_empty_session_notes_id(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.delete(AssistantRouter.SESSIONS_ENDPOINT,
                                        cookies={
                                            "authorization": self.auth_cookie,
                                            "datastore_access_token": FAKE_ACCESS_TOKEN,
                                            "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                        },
                                        params={
                                            "session_report_id": "",
                                        })
        assert response.status_code == 400

    def test_delete_session_with_valid_auth_but_garbage_session_notes_id(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.delete(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "session_report_id": "4123sdggsdgsdgdsgsdg",
                                    })
        assert response.status_code == 400

    def test_delete_session_with_valid_auth_but_nonexistent_but_valid_session_notes_id_uuid(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.delete(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "session_report_id": FAKE_SESSION_REPORT_ID,
                                    })
        assert response.status_code == 400

    def test_delete_session_success(self):
        self.fake_pinecone_client.vector_store_context_returns_data = True
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        response = self.client.delete(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "session_report_id": FAKE_SESSION_REPORT_ID,
                                    })
        assert response.status_code == 200

    def test_session_query_with_missing_auth(self):
        response = self.client.post(AssistantRouter.QUERIES_ENDPOINT,
                                    json={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "text": "Quien es el jugador favorito de Lionel Andres?",
                                    })
        assert response.status_code == 401

    def test_session_query_with_auth_token_but_supabase_returns_unauthenticated(self):
        response = self.client.post(AssistantRouter.QUERIES_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "text": "Quien es el jugador favorito de Lionel Andres?",
                                    })
        assert response.status_code == 401

    def test_session_query_with_auth_token_but_supabase_returns_unauthenticated(self):
        response = self.client.post(AssistantRouter.QUERIES_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "text": "Quien es el jugador favorito de Lionel Andres?",
                                    })
        assert response.status_code == 401

    def test_session_query_with_valid_auth_token_but_empty_patient_id(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(AssistantRouter.QUERIES_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "patient_id": "",
                                        "text": "Quien es el jugador favorito de Lionel Andres?",
                                    })
        assert response.status_code == 400

    def test_session_query_with_valid_auth_token_but_empty_text(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(AssistantRouter.QUERIES_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "text": "",
                                    })
        assert response.status_code == 400

    def test_session_query_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_pinecone_client.vector_store_context_returns_data = True
        response = self.client.post(AssistantRouter.QUERIES_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "text": "Quien es el jugador favorito de Lionel?",
                                    })
        assert response.status_code == 200

    def test_session_query_success_changing_patient_and_clearing_chat_history(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_pinecone_client.vector_store_context_returns_data = True

        MESSI_QUERY = "Quien es el jugador favorito de Lionel?"
        CRISTIANO_QUERY = "Quien es el jugador favorito de Cristiano?"

        assert len(self.fake_openai_client.chat_history) == 0
        response = self.client.post(AssistantRouter.QUERIES_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "text": MESSI_QUERY,
                                    })
        assert response.status_code == 200
        assert len(self.fake_openai_client.chat_history) == 2
        assert MESSI_QUERY == self.fake_openai_client.chat_history[0].content
        assert CRISTIANO_QUERY != self.fake_openai_client.chat_history[1].content

        # Now trigger a query for a different patient id
        response = self.client.post(AssistantRouter.QUERIES_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "patient_id": FAKE_SECOND_THERAPIST_ID,
                                        "text": CRISTIANO_QUERY,
                                    })
        assert response.status_code == 200

        # Previous chat history should get cleared, leaving us with the 2 new messages.
        assert len(self.fake_openai_client.chat_history) == 2
        assert CRISTIANO_QUERY == self.fake_openai_client.chat_history[0].content
        assert MESSI_QUERY != self.fake_openai_client.chat_history[1].content

    def test_add_patient_with_missing_auth(self):
        response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
                                    json={
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "pre_existing_history": "My history",
                                        "birth_date": "10-24-1991",
                                        "gender": "female",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 401

    def test_add_patient_with_auth_token_but_supabase_returns_unauthenticated(self):
        response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "birth_date": "10-24-1991",
                                        "gender": "female",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 401

    def test_add_patient_with_undefined_gender(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "birth_date": "10-24-1991",
                                        "gender": "undefined",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 400

    def test_add_patient_with_undefined_consentment_channel(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "birth_date": "10-24-1991",
                                        "gender": "male",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "undefined",
                                    })
        assert response.status_code == 400

    def test_add_patient_with_invalid_date(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "birth_date": "10/24/1991",
                                        "gender": "male",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 400

    def test_add_male_patient_without_pre_existing_history_and_different_gender_pronouns(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_supabase_user_client.select_default_briefing_has_different_pronouns = True
        response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "birth_date": "10-24-1991",
                                        "gender": "male",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 200
        assert "patient_id" in response.json()

    def test_add_male_patient_without_pre_existing_history_and_not_different_gender_pronouns(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_supabase_user_client.select_default_briefing_has_different_pronouns = False
        response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "birth_date": "10-24-1991",
                                        "gender": "male",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 200
        assert "patient_id" in response.json()

    def test_add_female_patient_without_pre_existing_history_and_different_gender_pronouns(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_supabase_user_client.select_default_briefing_has_different_pronouns = True
        response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "birth_date": "10-24-1991",
                                        "gender": "female",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 200
        assert "patient_id" in response.json()

    def test_add_female_patient_without_pre_existing_history_and_not_different_gender_pronouns(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_supabase_user_client.select_default_briefing_has_different_pronouns = False
        response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "birth_date": "10-24-1991",
                                        "gender": "female",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 200
        assert "patient_id" in response.json()

    def test_add_male_patient_with_pre_existing_history_and_different_gender_pronouns(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_supabase_user_client.select_default_briefing_has_different_pronouns = True
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 0
        response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "birth_date": "10-24-1991",
                                        "pre_existing_history": "my history",
                                        "gender": "male",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 200
        assert "patient_id" in response.json()
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 1

    def test_add_male_patient_with_pre_existing_history_and_not_different_gender_pronouns(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_supabase_user_client.select_default_briefing_has_different_pronouns = False
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 0
        response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "birth_date": "10-24-1991",
                                        "pre_existing_history": "my history",
                                        "gender": "male",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 200
        assert "patient_id" in response.json()
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 1

    def test_add_female_patient_with_pre_existing_history_and_different_gender_pronouns(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_supabase_user_client.select_default_briefing_has_different_pronouns = True
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 0
        response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "birth_date": "10-24-1991",
                                        "pre_existing_history": "my history",
                                        "gender": "female",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 200
        assert "patient_id" in response.json()
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 1

    def test_add_female_patient_with_pre_existing_history_and_not_different_gender_pronouns(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_supabase_user_client.select_default_briefing_has_different_pronouns = False
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 0
        response = self.client.post(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "birth_date": "10-24-1991",
                                        "pre_existing_history": "my history",
                                        "gender": "female",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 200
        assert "patient_id" in response.json()
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 1

    def test_update_patient_with_missing_auth(self):
        response = self.client.put(AssistantRouter.PATIENTS_ENDPOINT,
                                    json={
                                        "id": FAKE_PATIENT_ID,
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "birth_date": "10-24-1991",
                                        "gender": "female",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 401

    def test_update_patient_with_auth_token_but_supabase_returns_unauthenticated(self):
        response = self.client.put(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "id": FAKE_PATIENT_ID,
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "birth_date": "10-24-1991",
                                        "gender": "female",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 401

    def test_update_patient_with_empty_patient_id(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.put(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "id": "",
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "birth_date": "10-24-1991",
                                        "gender": "female",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 400

    def test_update_patient_with_same_preexisting_history_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True

        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 0
        response = self.client.put(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "id": FAKE_PATIENT_ID,
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "birth_date": "10-24-1991",
                                        "gender": "female",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 200
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 0

    def test_update_patient_with_new_preexisting_history_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True

        assert self.fake_pinecone_client.update_preexisting_history_num_invocations == 0
        response = self.client.put(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "id": FAKE_PATIENT_ID,
                                        "first_name": "Pepito",
                                        "last_name": "Perez",
                                        "birth_date": "10-24-1991",
                                        "gender": "female",
                                        "pre_existing_history": "Foo Fighters",
                                        "email": "foo@foo.foo",
                                        "phone_number": "123",
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 200
        assert self.fake_pinecone_client.update_preexisting_history_num_invocations == 1

    def test_delete_patient_with_missing_auth(self):
        response = self.client.delete(AssistantRouter.PATIENTS_ENDPOINT,
                                    params={
                                        "patient_id": FAKE_PATIENT_ID,
                                    })
        assert response.status_code == 401

    def test_delete_patient_with_auth_token_but_supabase_returns_unauthenticated(self):
        response = self.client.delete(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "patient_id": FAKE_PATIENT_ID,
                                    })
        assert response.status_code == 401

    def test_delete_patient_with_empty_patient_id(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.delete(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "patient_id": "",
                                    })
        assert response.status_code == 400

    def test_delete_patient_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        response = self.client.delete(AssistantRouter.PATIENTS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "patient_id": FAKE_PATIENT_ID,
                                    })
        assert response.status_code == 200

    def test_transform_with_template_with_missing_auth(self):
        response = self.client.post(AssistantRouter.TEMPLATES_ENDPOINT,
                                    json={
                                        "template": "soap",
                                        "session_notes_text": "My fake session notes"
                                    })
        assert response.status_code == 401

    def test_transform_with_template_with_empty_session_notes_text(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(AssistantRouter.TEMPLATES_ENDPOINT,
                                    json={
                                        "template": "soap",
                                        "session_notes_text": ""
                                    },
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },)
        assert response.status_code == 400

    def test_transform_with_template_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(AssistantRouter.TEMPLATES_ENDPOINT,
                                    json={
                                        "template": "soap",
                                        "session_notes_text": "My fake session notes"
                                    },
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },)
        assert response.status_code == 200
