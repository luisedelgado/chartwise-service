from datetime import timedelta

from fastapi.testclient import TestClient

from ..dependencies.fake.fake_async_openai import FakeAsyncOpenAI
from ..dependencies.fake.fake_pinecone_client import FakePineconeClient
from ..dependencies.fake.fake_supabase_client import FakeSupabaseClient
from ..dependencies.fake.fake_supabase_client_factory import FakeSupabaseClientFactory
from ..internal.router_dependencies import RouterDependencies
from ..managers.assistant_manager import AssistantManager
from ..managers.audio_processing_manager import AudioProcessingManager
from ..managers.auth_manager import AuthManager
from ..routers.assistant_router import AssistantRouter
from ..service_coordinator import EndpointServiceCoordinator

FAKE_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
FAKE_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
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
        self.auth_cookie = self.auth_manager.create_access_token(data={"sub": FAKE_THERAPIST_ID},
                                                                 expires_delta=timedelta(minutes=5))

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
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                   "session_date": "01-01-2020",
                                   "client_timezone_identifier": TZ_IDENTIFIER,
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
                                    "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                    "session_date": "01-01-2020",
                                    "client_timezone_identifier": TZ_IDENTIFIER,
                                    "datastore_access_token": FAKE_ACCESS_TOKEN,
                                    "datastore_refresh_token": FAKE_REFRESH_TOKEN,
                                    "source": "manual_input"
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
                                        "patient_id": FAKE_PATIENT_ID,
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                        "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                        "session_date": "01/01/2020",
                                        "source": "manual_input"
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
                                        "patient_id": FAKE_PATIENT_ID,
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                        "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                        "session_date": "01-01-2020",
                                        "source": "undefined"
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
                                        "patient_id": "",
                                        "therapist_id": FAKE_THERAPIST_ID,
                                        "notes_text": insert_text,
                                        "session_date": "01-01-2020",
                                        "client_timezone_identifier": "gfsghfsdhgdsgs",
                                        "source": "manual_input"
                                    })
        assert response.status_code == 400

    def test_insert_new_session_with_empty_therapist_id(self):
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
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": "",
                                        "notes_text": insert_text,
                                        "session_date": "01-01-2020",
                                        "client_timezone_identifier": "gfsghfsdhgdsgs",
                                        "source": "manual_input"
                                    })
        assert response.status_code == 401

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
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                        "notes_text": insert_text,
                                        "session_date": "01-01-2020",
                                        "client_timezone_identifier": "gfsghfsdhgdsgs",
                                        "source": "manual_input"
                                    })
        assert response.status_code == 400

    def test_insert_new_session_success(self):
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
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                        "notes_text": insert_text,
                                        "session_date": "01-01-2020",
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                        "source": "manual_input"
                                    })
        assert response.status_code == 200
        assert self.fake_supabase_user_client.fake_text == insert_text

    def test_update_session_with_missing_auth_token(self):
        response = self.client.put(AssistantRouter.SESSIONS_ENDPOINT,
                                    json={
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                        "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                        "session_date": "01-01-2020",
                                        "source": "manual_input",
                                        "id": FAKE_SESSION_REPORT_ID
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
                                    "client_timezone_identifier": TZ_IDENTIFIER,
                                    "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                    "session_date": "01/01/2020",
                                    "source": "manual_input",
                                    "id": FAKE_SESSION_REPORT_ID
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
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                        "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                        "session_date": "01/01/2020",
                                        "source": "manual_input",
                                        "id": FAKE_SESSION_REPORT_ID
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
                                        "client_timezone_identifier": "fsrghshfsdhfsd",
                                        "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                        "session_date": "01-01-2020",
                                        "source": "manual_input",
                                        "id": FAKE_SESSION_REPORT_ID
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
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                        "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                        "session_date": "01-01-2020",
                                        "source": "undefined",
                                        "id": FAKE_SESSION_REPORT_ID
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
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                        "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                        "session_date": "01-01-2020",
                                        "source": "undefined",
                                        "id": ""
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
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                        "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                        "session_date": "01-01-2020",
                                        "source": "undefined",
                                        "id": FAKE_SESSION_REPORT_ID
                                    })
        assert response.status_code == 400

    def test_update_session_with_different_text_success(self):
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
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                        "notes_text": update_text,
                                        "session_date": "01-01-2020",
                                        "source": "manual_input",
                                        "id": FAKE_SESSION_REPORT_ID
                                    })
        assert response.status_code == 200
        assert self.fake_supabase_user_client.fake_text == update_text

    def test_update_session_with_same_text_success(self):
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
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                        "notes_text": update_text,
                                        "session_date": "01-01-2020",
                                        "source": "manual_input",
                                        "id": FAKE_SESSION_REPORT_ID
                                    })
        assert response.status_code == 200
        assert self.fake_supabase_user_client.fake_text == update_text

    def test_delete_session_with_invalid_auth(self):
        response = self.client.delete(AssistantRouter.SESSIONS_ENDPOINT,
                                        params={
                                            "session_report_id": FAKE_SESSION_REPORT_ID,
                                            "therapist_id": FAKE_THERAPIST_ID,
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
                                            "therapist_id": FAKE_THERAPIST_ID,
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
                                            "therapist_id": FAKE_THERAPIST_ID,
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
                                        "therapist_id": FAKE_THERAPIST_ID,
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
                                        "therapist_id": FAKE_THERAPIST_ID,
                                    })
        assert response.status_code == 400

    def test_delete_session_with_valid_auth_but_invalid_therapist_id(self):
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
                                        "therapist_id": ""
                                    })
        assert response.status_code == 401

    def test_delete_session_success(self):
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
                                        "therapist_id": FAKE_THERAPIST_ID
                                    })
        assert response.status_code == 200

    def test_session_query_with_missing_auth(self):
        response = self.client.post(AssistantRouter.QUERIES_ENDPOINT,
                                    json={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID,
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
                                        "therapist_id": FAKE_THERAPIST_ID,
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
                                        "therapist_id": FAKE_THERAPIST_ID,
                                        "text": "Quien es el jugador favorito de Lionel Andres?",
                                    })
        assert response.status_code == 401

    def test_session_query_with_valid_auth_token_but_empty_therapist_id(self):
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
                                        "therapist_id": "",
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
                                        "therapist_id": FAKE_THERAPIST_ID,
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
                                        "therapist_id": FAKE_THERAPIST_ID,
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
                                        "therapist_id": FAKE_THERAPIST_ID,
                                        "text": "Quien es el jugador favorito de Lionel?",
                                    })
        assert response.status_code == 200

    def test_greeting_with_missing_auth_token(self):
        response = self.client.get(AssistantRouter.GREETINGS_ENDPOINT,
                                    params={
                                        "client_tz_identifier": TZ_IDENTIFIER,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                    })
        assert response.status_code == 401

    def test_greeting_with_auth_but_auth_token_but_supabase_returns_unathenticated_session(self):
        response = self.client.get(AssistantRouter.GREETINGS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "client_tz_identifier": TZ_IDENTIFIER,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                    })
        assert response.status_code == 401

    def test_greeting_with_valid_auth_but_invalid_tz_identifier(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.get(AssistantRouter.GREETINGS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "client_timezone_identifier": "gfshsh",
                                        "therapist_id": FAKE_THERAPIST_ID,
                                    })
        assert response.status_code == 400

    def test_greeting_with_valid_auth_but_empty_therapist_id(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.get(AssistantRouter.GREETINGS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                        "therapist_id": "",
                                    })
        assert response.status_code == 401

    def test_greeting_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        response = self.client.get(AssistantRouter.GREETINGS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "client_timezone_identifier": TZ_IDENTIFIER,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                    })
        assert response.status_code == 200

    def test_presession_summary_with_missing_auth_token(self):
        response = self.client.get(AssistantRouter.PRESESSION_TRAY_ENDPOINT,
                                    params={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID
                                    })
        assert response.status_code == 401

    def test_presession_summary_with_auth_token_but_supabase_returns_unauthenticated(self):
        response = self.client.get(AssistantRouter.PRESESSION_TRAY_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID
                                    })
        assert response.status_code == 401

    def test_presession_summary_with_valid_tokens_but_empty_therapist_id(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.get(AssistantRouter.PRESESSION_TRAY_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": ""
                                    })
        assert response.status_code == 401

    def test_presession_summary_with_valid_tokens_but_empty_patient_id(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.get(AssistantRouter.PRESESSION_TRAY_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "patient_id": "",
                                        "therapist_id": FAKE_THERAPIST_ID
                                    })
        assert response.status_code == 400

    def test_presession_summary_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        response = self.client.get(AssistantRouter.PRESESSION_TRAY_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID
                                    })
        assert response.status_code == 200

    def test_question_suggestions_with_missing_auth(self):
        response = self.client.get(AssistantRouter.QUESTION_SUGGESTIONS_ENDPOINT,
                                    params={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                    })
        assert response.status_code == 401

    def test_question_suggestions_with_auth_token_but_supabase_returns_unauthenticated(self):
        response = self.client.get(AssistantRouter.QUESTION_SUGGESTIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                    })
        assert response.status_code == 401

    def test_question_suggestions_with_auth_token_but_empty_therapist_id(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.get(AssistantRouter.QUESTION_SUGGESTIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": "",
                                    })
        assert response.status_code == 401

    def test_question_suggestions_with_auth_token_but_empty_patient_id(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.get(AssistantRouter.QUESTION_SUGGESTIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "patient_id": "",
                                        "therapist_id": FAKE_THERAPIST_ID,
                                    })
        assert response.status_code == 400

    def test_question_suggestions_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_pinecone_client.vector_store_context_returns_data = True
        response = self.client.get(AssistantRouter.QUESTION_SUGGESTIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                    })
        assert response.status_code == 200

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
                                        "therapist_id": FAKE_THERAPIST_ID,
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
                                        "therapist_id": FAKE_THERAPIST_ID,
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
                                        "therapist_id": FAKE_THERAPIST_ID,
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
                                        "therapist_id": FAKE_THERAPIST_ID,
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
                                        "therapist_id": FAKE_THERAPIST_ID,
                                    })
        assert response.status_code == 400

    def test_add_patient_without_pre_existing_history_success(self):
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
                                        "consentment_channel": "verbal",
                                    })
        assert response.status_code == 200
        assert "patient_id" in response.json()

    def test_add_patient_with_pre_existing_history_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
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
                                        "therapist_id": FAKE_THERAPIST_ID,
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
                                        "therapist_id": FAKE_THERAPIST_ID,
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
                                        "therapist_id": FAKE_THERAPIST_ID,
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
                                        "therapist_id": FAKE_THERAPIST_ID,
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
                                        "therapist_id": FAKE_THERAPIST_ID,
                                    })
        assert response.status_code == 401

    def test_delete_patient_with_empty_therapist_id(self):
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
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": "",
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
                                        "therapist_id": FAKE_THERAPIST_ID,
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
                                        "therapist_id": FAKE_THERAPIST_ID,
                                    })
        assert response.status_code == 200

    def test_frequent_topics_with_missing_auth(self):
        response = self.client.get(AssistantRouter.TOPICS_ENDPOINT,
                                    params={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                    })
        assert response.status_code == 401

    def test_frequent_topics_with_auth_token_but_supabase_returns_unauthenticated(self):
        response = self.client.get(AssistantRouter.TOPICS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                    },
                                    params={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                    })
        assert response.status_code == 401

    def test_frequent_topics_with_missing_therapist_id(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.get(AssistantRouter.TOPICS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": "",
                                    })
        assert response.status_code == 401

    def test_frequent_topics_with_missing_patient_id(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.get(AssistantRouter.TOPICS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "patient_id": "",
                                        "therapist_id": FAKE_THERAPIST_ID,
                                    })
        assert response.status_code == 400

    def test_frequent_topics_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_pinecone_client.vector_store_context_returns_data = True
        response = self.client.get(AssistantRouter.TOPICS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    },
                                    params={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                    })
        assert response.status_code == 200

    def test_transform_with_template_with_missing_auth(self):
        response = self.client.post(AssistantRouter.TEMPLATES_ENDPOINT,
                                    json={
                                        "template": "soap",
                                        "therapist_id": FAKE_THERAPIST_ID,
                                        "session_notes_text": "My fake session notes"
                                    })
        assert response.status_code == 401

    def test_transform_with_template_with_empty_therapist_id(self):
        response = self.client.post(AssistantRouter.TEMPLATES_ENDPOINT,
                                    json={
                                        "template": "soap",
                                        "therapist_id": "",
                                        "session_notes_text": "My fake session notes"
                                    },
                                    cookies={
                                        "authorization": self.auth_cookie,
                                    },)
        assert response.status_code == 401

    def test_transform_with_template_with_empty_session_notes_text(self):
        response = self.client.post(AssistantRouter.TEMPLATES_ENDPOINT,
                                    json={
                                        "template": "soap",
                                        "therapist_id": FAKE_THERAPIST_ID,
                                        "session_notes_text": ""
                                    },
                                    cookies={
                                        "authorization": self.auth_cookie,
                                    },)
        assert response.status_code == 400

    def test_transform_with_template_success(self):
        response = self.client.post(AssistantRouter.TEMPLATES_ENDPOINT,
                                    json={
                                        "template": "soap",
                                        "therapist_id": FAKE_THERAPIST_ID,
                                        "session_notes_text": "My fake session notes"
                                    },
                                    cookies={
                                        "authorization": self.auth_cookie,
                                    },)
        assert response.status_code == 200
