import os

from fastapi.testclient import TestClient

from ..dependencies.fake.fake_async_openai import FakeAsyncOpenAI
from ..dependencies.fake.fake_pinecone_client import FakePineconeClient
from ..dependencies.fake.fake_supabase_client import FakeSupabaseClient
from ..dependencies.fake.fake_supabase_client_factory import FakeSupabaseClientFactory
from ..dependencies.dependency_container import dependency_container
from ..managers.auth_manager import AuthManager
from ..routers.security_router import SecurityRouter
from ..service_coordinator import EndpointServiceCoordinator

FAKE_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
FAKE_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
FAKE_SESSION_REPORT_ID = "09b6da8d-a58e-45e2-9022-7d58ca02266b"
FAKE_REFRESH_TOKEN = "3ac77394-86b5-42dc-be14-0b92414d8443"
FAKE_ACCESS_TOKEN = "884f507c-f391-4248-91c4-7c25a138633a"
FAKE_TZ_IDENTIFIER = "UTC"

class TestingHarnessSecurityRouter:

    def setup_method(self):
        # Clear out any old state between tests
        dependency_container._openai_client = None
        dependency_container._pinecone_client = None
        dependency_container._stripe_client = None
        dependency_container._supabase_client_factory = None
        dependency_container._resend_client = None
        dependency_container._influx_client = None
        dependency_container._testing_environment = "testing"

        self.fake_supabase_admin_client:FakeSupabaseClient = dependency_container.inject_supabase_client_factory().supabase_admin_client()
        self.fake_openai_client:FakeAsyncOpenAI = dependency_container.inject_openai_client()
        self.fake_supabase_user_client:FakeSupabaseClient = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=FAKE_ACCESS_TOKEN,
                                                                                                                                    refresh_token=FAKE_REFRESH_TOKEN)
        self.fake_pinecone_client:FakePineconeClient = dependency_container.inject_pinecone_client()
        self.fake_supabase_client_factory:FakeSupabaseClientFactory = dependency_container.inject_supabase_client_factory()
        self.auth_cookie, _ = AuthManager().create_auth_token(user_id=FAKE_THERAPIST_ID)

        coordinator = EndpointServiceCoordinator(routers=[SecurityRouter().router],
                                                 environment=os.environ.get("ENVIRONMENT"))
        self.client = TestClient(coordinator.app)

    def test_login_for_token_unauthenticated(self):
        response = self.client.post(SecurityRouter.SIGNIN_ENDPOINT,
                               json={
                                   "email": "test@test.com",
                               })
        assert response.status_code == 401

    def test_login_for_token_authenticated_success(self):
        self.fake_supabase_admin_client.return_authenticated_session = True
        self.fake_supabase_user_client.user_authentication_email = "foo@foo.com"
        self.fake_supabase_user_client.user_authentication_id = "e"
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_supabase_admin_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_admin_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_admin_client.user_authentication_id = FAKE_THERAPIST_ID
        response = self.client.post(SecurityRouter.SIGNIN_ENDPOINT,
                                    json={
                                        "email": "foo@foo.com"
                                    },
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    })
        assert response.status_code == 200
        assert response.cookies.get("authorization") != None
        assert response.cookies.get("session_id") is not None

    def test_refresh_token_without_previous_auth_session(self):
        response = self.client.put(SecurityRouter.SESSION_REFRESH_ENDPOINT,
                               headers={
                                   "store-access-token": FAKE_ACCESS_TOKEN,
                                   "store-refresh-token": FAKE_REFRESH_TOKEN
                               })
        assert response.status_code == 401

    def test_refresh_token_success(self):
        self.fake_supabase_admin_client.return_authenticated_session = True
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_supabase_admin_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_admin_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_admin_client.user_authentication_id = FAKE_THERAPIST_ID
        response = self.client.put(SecurityRouter.SESSION_REFRESH_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie
                                    },
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    })
        assert response.status_code == 200

        response_json = response.json()
        assert "token" in response_json
        assert "subscription_status" in response_json

    def test_add_therapist_with_missing_store_tokens(self):
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                               json={
                                    "email": "foo@foo.com",
                                    "first_name": "foo",
                                    "last_name": "bar",
                                    "birth_date": "01/01/2000",
                                    "language_preference": "es-419",
                                    "gender": "male"
                               })
        assert response.status_code == 401

    def test_add_therapist_with_valid_credentials_but_invalid_birthdate_format(self):
        self.fake_supabase_user_client.user_authentication_email = "foo@foo.com"
        self.fake_supabase_user_client.user_authentication_id = "e"
        self.fake_supabase_admin_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                               headers={
                                   "store-access-token": FAKE_ACCESS_TOKEN,
                                   "store-refresh-token": FAKE_REFRESH_TOKEN
                               },
                               json={
                                    "email": "foo@foo.com",
                                    "first_name": "foo",
                                    "last_name": "bar",
                                    "birth_date": "01/01/2000",
                                    "language_preference": "es-419",
                                    "gender": "male"
                               })
        assert response.status_code == 400

    def test_add_therapist_with_valid_credentials_but_invalid_language_preference(self):
        self.fake_supabase_user_client.user_authentication_email = "foo@foo.com"
        self.fake_supabase_user_client.user_authentication_id = "e"
        self.fake_supabase_admin_client.return_authenticated_session = True
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                               cookies={
                                   "authorization": self.auth_cookie
                               },
                               headers={
                                   "store-access-token": FAKE_ACCESS_TOKEN,
                                   "store-refresh-token": FAKE_REFRESH_TOKEN
                               },
                               json={
                                    "email": "foo@foo.com",
                                    "first_name": "foo",
                                    "last_name": "bar",
                                    "birth_date": "01/01/2000",
                                    "language_preference": "brbrbrbrbr",
                                    "gender": "male"
                               })
        assert response.status_code == 400

    def test_add_therapist_with_valid_credentials_but_invalid_gender_format(self):
        self.fake_supabase_user_client.user_authentication_email = "foo@foo.com"
        self.fake_supabase_user_client.user_authentication_id = "e"
        self.fake_supabase_admin_client.return_authenticated_session = True
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                                cookies={
                                    "authorization": self.auth_cookie
                                },
                                headers={
                                    "store-access-token": FAKE_ACCESS_TOKEN,
                                    "store-refresh-token": FAKE_REFRESH_TOKEN
                                },
                                json={
                                    "email": "foo@foo.com",
                                    "first_name": "foo",
                                    "last_name": "bar",
                                    "birth_date": "01/01/2000",
                                    "language_preference": "es-419",
                                    "gender": "undefined"
                                })
        assert response.status_code == 400

    def test_add_therapist_without_previous_auth_cookie_success(self):
        self.fake_supabase_user_client.user_authentication_email = "foo@foo.com"
        self.fake_supabase_user_client.user_authentication_id = "e"
        self.fake_supabase_admin_client.return_authenticated_session = True
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                            headers={
                                "store-access-token": FAKE_ACCESS_TOKEN,
                                "store-refresh-token": FAKE_REFRESH_TOKEN
                            },
                            json={
                                "email": "foo@foo.com",
                                "first_name": "foo",
                                "last_name": "bar",
                                "birth_date": "01-01-2000",
                                "language_preference": "es-419",
                                "gender": "male"
                            })
        assert response.status_code == 200
        response_json = response.json()
        assert response_json["therapist_id"] == self.fake_supabase_user_client.FAKE_THERAPIST_ID
        assert response_json["token"] is not None

    def test_add_therapist_with_existing_auth_cookie_success(self):
        self.fake_supabase_user_client.user_authentication_email = "foo@foo.com"
        self.fake_supabase_user_client.user_authentication_id = "e"
        self.fake_supabase_admin_client.return_authenticated_session = True
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                            headers={
                                "store-access-token": FAKE_ACCESS_TOKEN,
                                "store-refresh-token": FAKE_REFRESH_TOKEN
                            },
                            json={
                                "email": "foo@foo.com",
                                "first_name": "foo",
                                "last_name": "bar",
                                "birth_date": "01-01-2000",
                                "language_preference": "es-419",
                                "gender": "male"
                            })
        assert response.status_code == 200
        response_json = response.json()
        assert response_json["therapist_id"] == self.fake_supabase_user_client.FAKE_THERAPIST_ID
        assert response_json["token"] is not None

    def test_update_therapist_with_invalid_credentials(self):
        response = self.client.put(SecurityRouter.THERAPISTS_ENDPOINT,
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
        response = self.client.put(SecurityRouter.THERAPISTS_ENDPOINT,
                            cookies={
                                "authorization": self.auth_cookie
                            },
                            headers={
                                "store-access-token": FAKE_ACCESS_TOKEN,
                                "store-refresh-token": FAKE_REFRESH_TOKEN
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
        response = self.client.put(SecurityRouter.THERAPISTS_ENDPOINT,
                            cookies={
                                "authorization": self.auth_cookie
                            },
                            headers={
                                "store-access-token": FAKE_ACCESS_TOKEN,
                                "store-refresh-token": FAKE_REFRESH_TOKEN
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
        response = self.client.put(SecurityRouter.THERAPISTS_ENDPOINT,
                            cookies={
                                "authorization": self.auth_cookie
                            },
                            headers={
                                "store-access-token": FAKE_ACCESS_TOKEN,
                                "store-refresh-token": FAKE_REFRESH_TOKEN
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
        response = self.client.put(SecurityRouter.THERAPISTS_ENDPOINT,
                            cookies={
                                "authorization": self.auth_cookie
                            },
                            headers={
                                "store-access-token": FAKE_ACCESS_TOKEN,
                                "store-refresh-token": FAKE_REFRESH_TOKEN
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

    def test_logout_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.post(SecurityRouter.LOGOUT_ENDPOINT,
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    })

        assert response.status_code == 200
        cookie_header = response.headers.get("set-cookie")
        assert cookie_header is not None
        assert "authorization=" in cookie_header
        assert "session_id=" in cookie_header
        assert "expires=" in cookie_header or "Max-Age=0" in cookie_header

    def test_delete_therapist_with_missing_auth(self):
        response = self.client.delete(SecurityRouter.THERAPISTS_ENDPOINT)
        assert response.status_code == 401

    def test_delete_therapist_success(self):
        self.fake_supabase_user_client.select_returns_data = True
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        response = self.client.delete(SecurityRouter.THERAPISTS_ENDPOINT,
                                        cookies={
                                            "authorization": self.auth_cookie
                                        },
                                        headers={
                                            "store-access-token": FAKE_ACCESS_TOKEN,
                                            "store-refresh-token": FAKE_REFRESH_TOKEN
                                        })
        assert response.status_code == 200
