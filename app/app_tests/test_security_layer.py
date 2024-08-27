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
from ..routers.security_router import SecurityRouter
from ..service_coordinator import EndpointServiceCoordinator

FAKE_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
FAKE_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
FAKE_SESSION_REPORT_ID = "09b6da8d-a58e-45e2-9022-7d58ca02266b"
FAKE_REFRESH_TOKEN = "3ac77394-86b5-42dc-be14-0b92414d8443"
FAKE_ACCESS_TOKEN = "884f507c-f391-4248-91c4-7c25a138633a"
FAKE_TZ_IDENTIFIER = "UTC"
ENVIRONMENT = "testing"

class TestingHarnessSecurityRouter:

    def setup_method(self):
        self.auth_manager = AuthManager()
        self.assistant_manager = AssistantManager()
        self.audio_processing_manager = AudioProcessingManager()
        self.fake_supabase_admin_client = FakeSupabaseClient()
        self.fake_openai_client = FakeAsyncOpenAI()
        self.fake_supabase_user_client = FakeSupabaseClient()
        self.fake_pinecone_client = FakePineconeClient()
        self.fake_supabase_client_factory = FakeSupabaseClientFactory(fake_supabase_admin_client=self.fake_supabase_admin_client,
                                                                      fake_supabase_user_client=self.fake_supabase_user_client)
        self.auth_cookie = self.auth_manager.create_access_token(user_id=FAKE_THERAPIST_ID)

        coordinator = EndpointServiceCoordinator(routers=[SecurityRouter(auth_manager=self.auth_manager,
                                                                         assistant_manager=self.assistant_manager,
                                                                         router_dependencies=RouterDependencies(openai_client=self.fake_openai_client,
                                                                                                                supabase_client_factory=self.fake_supabase_client_factory,
                                                                                                                pinecone_client=self.fake_pinecone_client)).router],
                                                 environment=ENVIRONMENT)
        self.client = TestClient(coordinator.app)

    def test_login_for_token_with_missing_supabase_tokens(self):
        response = self.client.post(SecurityRouter.TOKEN_ENDPOINT,
                               json={
                                   "datastore_access_token": "",
                                   "datastore_refresh_token": "",
                                   "user_id": FAKE_THERAPIST_ID
                               })
        assert response.status_code == 401

    def test_login_for_token_with_supabase_tokens_but_missing_user_id(self):
        response = self.client.post(SecurityRouter.TOKEN_ENDPOINT,
                               json={
                                   "datastore_access_token": FAKE_ACCESS_TOKEN,
                                   "datastore_refresh_token": FAKE_REFRESH_TOKEN,
                                   "user_id": ""
                               })
        assert response.status_code == 401

    def test_login_for_token_unauthenticated(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(SecurityRouter.TOKEN_ENDPOINT,
                               json={
                                   "datastore_access_token": FAKE_ACCESS_TOKEN,
                                   "datastore_refresh_token": FAKE_REFRESH_TOKEN,
                                   "user_id": FAKE_THERAPIST_ID
                               })
        assert response.status_code == 401

    def test_login_for_token_authenticated_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.user_authentication_id = FAKE_THERAPIST_ID
        response = self.client.post(SecurityRouter.TOKEN_ENDPOINT,
                                    json={
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN,
                                        "user_id": FAKE_THERAPIST_ID
                                    })
        assert response.status_code == 200
        assert response.cookies.get("datastore_access_token") == FAKE_ACCESS_TOKEN
        assert response.cookies.get("datastore_refresh_token") == FAKE_REFRESH_TOKEN
        assert response.cookies.get("authorization") != None
        assert response.cookies.get("session_id") is not None

    def test_refresh_token_with_invalid_user_id(self):
        response = self.client.put(SecurityRouter.TOKEN_ENDPOINT,
                                    json={
                                        "user_id": ""
                                    })
        assert response.status_code == 400

    def test_refresh_token_without_existing_auth_token(self):
        response = self.client.put(SecurityRouter.TOKEN_ENDPOINT,
                                    json={
                                        "user_id": FAKE_THERAPIST_ID
                                    })
        assert response.status_code == 400

    def test_refresh_token_without_supabase_cookies_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.user_authentication_id = FAKE_THERAPIST_ID
        response = self.client.put(SecurityRouter.TOKEN_ENDPOINT,
                                    json={
                                        "user_id": FAKE_THERAPIST_ID
                                    },
                                    cookies={
                                        "authorization": self.auth_cookie
                                    })
        assert response.status_code == 200
        assert self.fake_supabase_user_client.invoked_refresh_session == False
        assert response.cookies.get("datastore_access_token") == None
        assert response.cookies.get("datastore_refresh_token") == None
        assert response.cookies.get("authorization") != None

    def test_refresh_token_along_supabase_cookies_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.user_authentication_id = FAKE_THERAPIST_ID
        response = self.client.put(SecurityRouter.TOKEN_ENDPOINT,
                                    json={
                                        "user_id": FAKE_THERAPIST_ID
                                    },
                                    cookies={
                                        "authorization": self.auth_cookie,
                                        "datastore_access_token": FAKE_ACCESS_TOKEN,
                                        "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                    })
        assert response.status_code == 200
        assert self.fake_supabase_user_client.invoked_refresh_session == True
        assert response.cookies.get("datastore_access_token") != None
        assert response.cookies.get("datastore_refresh_token") != None
        assert response.cookies.get("authorization") != None

    def test_add_therapist_with_invalid_credentials(self):
        response = self.client.post(SecurityRouter.ACCOUNT_ENDPOINT,
                               json={
                                   "id": FAKE_THERAPIST_ID,
                                   "email": "foo@foo.com",
                                   "first_name": "foo",
                                   "last_name": "bar",
                                   "birth_date": "01/01/2000",
                                   "login_mechanism": "internal",
                                   "language_preference": "es-419",
                                   "gender": "male",
                               })
        assert response.status_code == 401

    def test_add_therapist_with_auth_token_but_supabase_returns_unauthenticated(self):
        response = self.client.post(SecurityRouter.ACCOUNT_ENDPOINT,
                                cookies={
                                    "authorization": self.auth_cookie,
                                    "datastore_access_token": FAKE_ACCESS_TOKEN,
                                    "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                },
                                json={
                                    "id": FAKE_THERAPIST_ID,
                                    "email": "foo@foo.com",
                                    "first_name": "foo",
                                    "last_name": "bar",
                                    "birth_date": "01/01/2000",
                                    "login_mechanism": "internal",
                                    "language_preference": "es-419",
                                    "gender": "male",
                                })
        assert response.status_code == 401

    def test_add_therapist_with_valid_credentials_but_invalid_birthdate_format(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(SecurityRouter.ACCOUNT_ENDPOINT,
                               cookies={
                                   "authorization": self.auth_cookie,
                                   "datastore_access_token": FAKE_ACCESS_TOKEN,
                                   "datastore_refresh_token": FAKE_REFRESH_TOKEN
                               },
                               json={
                                   "id": FAKE_THERAPIST_ID,
                                   "email": "foo@foo.com",
                                   "first_name": "foo",
                                   "last_name": "bar",
                                   "birth_date": "01/01/2000",
                                   "login_mechanism": "internal",
                                   "language_preference": "es-419",
                                   "gender": "male",
                               })
        assert response.status_code == 400

    def test_add_therapist_with_valid_credentials_but_invalid_language_preference(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(SecurityRouter.ACCOUNT_ENDPOINT,
                               cookies={
                                   "authorization": self.auth_cookie,
                                   "datastore_access_token": FAKE_ACCESS_TOKEN,
                                   "datastore_refresh_token": FAKE_REFRESH_TOKEN
                               },
                               json={
                                   "id": FAKE_THERAPIST_ID,
                                   "email": "foo@foo.com",
                                   "first_name": "foo",
                                   "last_name": "bar",
                                   "birth_date": "01-01-2000",
                                   "login_mechanism": "internal",
                                   "language_preference": "brbrbrbrbr",
                                   "gender": "male",
                               })
        assert response.status_code == 400

    def test_add_therapist_with_valid_credentials_but_invalid_gender_format(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(SecurityRouter.ACCOUNT_ENDPOINT,
                                cookies={
                                    "authorization": self.auth_cookie,
                                    "datastore_access_token": FAKE_ACCESS_TOKEN,
                                    "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                },
                                json={
                                    "id": FAKE_THERAPIST_ID,
                                    "email": "foo@foo.com",
                                    "first_name": "foo",
                                    "last_name": "bar",
                                    "birth_date": "01-01-2000",
                                    "login_mechanism": "internal",
                                    "language_preference": "es-419",
                                    "gender": "undefined",
                                })
        assert response.status_code == 400

    def test_add_therapist_with_valid_credentials_but_undefined_login_mechanism(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(SecurityRouter.ACCOUNT_ENDPOINT,
                               cookies={
                                   "authorization": self.auth_cookie,
                                   "datastore_access_token": FAKE_ACCESS_TOKEN,
                                   "datastore_refresh_token": FAKE_REFRESH_TOKEN
                               },
                               json={
                                   "id": FAKE_THERAPIST_ID,
                                   "email": "foo@foo.com",
                                   "first_name": "foo",
                                   "last_name": "bar",
                                   "birth_date": "01-01-2000",
                                   "login_mechanism": "undefined",
                                   "language_preference": "es-419",
                                   "gender": "male",
                               })
        assert response.status_code == 400

    def test_add_therapist_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(SecurityRouter.ACCOUNT_ENDPOINT,
                            cookies={
                                "authorization": self.auth_cookie,
                                "datastore_access_token": FAKE_ACCESS_TOKEN,
                                "datastore_refresh_token": FAKE_REFRESH_TOKEN
                            },
                            json={
                                "email": "foo@foo.com",
                                "first_name": "foo",
                                "last_name": "bar",
                                "birth_date": "01-01-2000",
                                "login_mechanism": "facebook",
                                "language_preference": "es-419",
                                "gender": "male",
                            })
        assert response.status_code == 200
        assert response.json()["therapist_id"] == self.fake_supabase_user_client.FAKE_THERAPIST_ID
        assert response.cookies.get("authorization") is not None

    def test_update_therapist_with_invalid_credentials(self):
        response = self.client.put(SecurityRouter.ACCOUNT_ENDPOINT,
                            json={
                                "email": "foo@foo.com",
                                "first_name": "foo",
                                "last_name": "bar",
                                "birth_date": "01-01-2000",
                                "language_preference": "es-419",
                                "gender": "male",
                            })
        assert response.status_code == 401

    def test_update_therapist_with_auth_token_but_supabase_returns_unauthenticated(self):
        response = self.client.put(SecurityRouter.ACCOUNT_ENDPOINT,
                            cookies={
                                "authorization": self.auth_cookie,
                                "datastore_access_token": FAKE_ACCESS_TOKEN,
                                "datastore_refresh_token": FAKE_REFRESH_TOKEN
                            },
                            json={
                                "email": "foo@foo.com",
                                "first_name": "foo",
                                "last_name": "bar",
                                "birth_date": "01-01-2000",
                                "language_preference": "es-419",
                                "gender": "male",
                            })
        assert response.status_code == 401

    def test_update_therapist_with_valid_credentials_but_undefined_gender(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.put(SecurityRouter.ACCOUNT_ENDPOINT,
                            cookies={
                                "authorization": self.auth_cookie,
                                "datastore_access_token": FAKE_ACCESS_TOKEN,
                                "datastore_refresh_token": FAKE_REFRESH_TOKEN
                            },
                            json={
                                "email": "foo@foo.com",
                                "first_name": "foo",
                                "last_name": "bar",
                                "birth_date": "01-01-2000",
                                "language_preference": "es-419",
                                "gender": "undefined",
                            })
        assert response.status_code == 400

    def test_update_therapist_with_valid_credentials_but_invalid_date(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.put(SecurityRouter.ACCOUNT_ENDPOINT,
                            cookies={
                                "authorization": self.auth_cookie,
                                "datastore_access_token": FAKE_ACCESS_TOKEN,
                                "datastore_refresh_token": FAKE_REFRESH_TOKEN
                            },
                            json={
                                "email": "foo@foo.com",
                                "first_name": "foo",
                                "last_name": "bar",
                                "birth_date": "01/01/2000",
                                "language_preference": "es-419",
                                "gender": "male",
                            })
        assert response.status_code == 400

    def test_update_therapist_with_valid_credentials_but_invalid_language_code(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.put(SecurityRouter.ACCOUNT_ENDPOINT,
                            cookies={
                                "authorization": self.auth_cookie,
                                "datastore_access_token": FAKE_ACCESS_TOKEN,
                                "datastore_refresh_token": FAKE_REFRESH_TOKEN
                            },
                            json={
                                "email": "foo@foo.com",
                                "first_name": "foo",
                                "last_name": "bar",
                                "birth_date": "01-01-2000",
                                "language_preference": "brbrbrbr",
                                "gender": "male",
                            })
        assert response.status_code == 400

    def test_update_therapist_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.put(SecurityRouter.ACCOUNT_ENDPOINT,
                            cookies={
                                "authorization": self.auth_cookie,
                                "datastore_access_token": FAKE_ACCESS_TOKEN,
                                "datastore_refresh_token": FAKE_REFRESH_TOKEN
                            },
                            json={
                                "email": "foo@foo.com",
                                "first_name": "foo",
                                "last_name": "bar",
                                "birth_date": "01-01-2000",
                                "language_preference": "es-419",
                                "gender": "male",
                            })
        assert response.status_code == 200

    def test_logout_with_invalid_credentials(self):
        response = self.client.post(SecurityRouter.LOGOUT_ENDPOINT)
        assert response.status_code == 401

    def test_logout_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(SecurityRouter.LOGOUT_ENDPOINT,
                                cookies={
                                    "authorization": self.auth_cookie,
                                    "datastore_access_token": FAKE_ACCESS_TOKEN,
                                    "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                })
        assert response.status_code == 200
        cookie_header = response.headers.get("set-cookie")
        assert cookie_header is not None
        assert "authorization=" in cookie_header
        assert "session_id=" in cookie_header
        assert "expires=" in cookie_header or "Max-Age=0" in cookie_header

    def test_delete_therapist_with_missing_auth(self):
        response = self.client.delete(SecurityRouter.ACCOUNT_ENDPOINT)
        assert response.status_code == 401

    def test_delete_therapist_with_auth_token_but_supabase_returns_unauthenticated(self):
        response = self.client.delete(SecurityRouter.ACCOUNT_ENDPOINT,
                                      cookies={
                                          "authorization": self.auth_cookie,
                                          "datastore_access_token": FAKE_ACCESS_TOKEN,
                                          "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                      })
        assert response.status_code == 401

    def test_delete_therapist_success(self):
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.delete(SecurityRouter.ACCOUNT_ENDPOINT,
                                        cookies={
                                            "authorization": self.auth_cookie,
                                            "datastore_access_token": FAKE_ACCESS_TOKEN,
                                            "datastore_refresh_token": FAKE_REFRESH_TOKEN
                                        })
        assert response.status_code == 200
