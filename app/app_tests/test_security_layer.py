import os

from fastapi.testclient import TestClient

from ..dependencies.fake.fake_aws_cognito_client import FakeAwsCognitoClient
from ..dependencies.fake.fake_async_openai import FakeAsyncOpenAI
from ..dependencies.fake.fake_pinecone_client import FakePineconeClient
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
        dependency_container._aws_cognito_client = None
        dependency_container._aws_db_client = None
        dependency_container._aws_kms_client = None
        dependency_container._aws_s3_client = None
        dependency_container._aws_secret_manager_client = None
        dependency_container._chartwise_encryptor = None        
        dependency_container._influx_client = None
        dependency_container._openai_client = None
        dependency_container._pinecone_client = None
        dependency_container._resend_client = None
        dependency_container._stripe_client = None
        dependency_container._testing_environment = "testing"

        self.fake_cognito_client:FakeAwsCognitoClient = dependency_container.inject_aws_cognito_client()
        self.fake_openai_client:FakeAsyncOpenAI = dependency_container.inject_openai_client()
        self.fake_pinecone_client:FakePineconeClient = dependency_container.inject_pinecone_client()
        self.auth_cookie, _ = AuthManager().create_session_token(user_id=FAKE_THERAPIST_ID)

        coordinator = EndpointServiceCoordinator(routers=[SecurityRouter().router],
                                                 environment=os.environ.get("ENVIRONMENT"))
        self.client = TestClient(coordinator.app)

    def test_login_for_token_unauthenticated(self):
        self.fake_cognito_client.return_valid_tokens = False
        response = self.client.post(SecurityRouter.SIGNIN_ENDPOINT,
                                    headers={
                                        "auth-token": "myFakeToken",
                                    })
        assert response.status_code == 401

    def test_login_for_token_authenticated_success(self):
        response = self.client.post(SecurityRouter.SIGNIN_ENDPOINT,
                                    headers={
                                        "auth-token": FAKE_ACCESS_TOKEN,
                                    })
        assert response.status_code == 200
        assert response.cookies.get("session_token") is not None
        assert response.cookies.get("session_id") is not None

        session_token = response.json()
        assert session_token["token"]["session_token"] is not None
        assert session_token["token"]["token_type"] is not None
        assert session_token["token"]["expiration_timestamp"] is not None

    def test_refresh_token_without_previous_auth_session(self):
        response = self.client.put(SecurityRouter.SESSION_REFRESH_ENDPOINT,
                                   headers={
                                       "store-access-token": FAKE_ACCESS_TOKEN,
                                       "store-refresh-token": FAKE_REFRESH_TOKEN
                                   })
        assert response.status_code == 401

    def test_refresh_token_success(self):
        response = self.client.put(SecurityRouter.SESSION_REFRESH_ENDPOINT,
                                    cookies={
                                        "session_token": self.auth_cookie
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

    def test_add_therapist_with_auth_token_but_missing_store_tokens(self):
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                                    cookies={
                                        "session_token": self.auth_cookie
                                    },
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
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                               headers={
                                   "store-access-token": FAKE_ACCESS_TOKEN,
                                   "store-refresh-token": FAKE_REFRESH_TOKEN
                               },
                               cookies={
                                        "session_token": self.auth_cookie
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
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                               cookies={
                                   "session_token": self.auth_cookie
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
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                                cookies={
                                    "session_token": self.auth_cookie
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
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                            headers={
                                "store-access-token": FAKE_ACCESS_TOKEN,
                                "store-refresh-token": FAKE_REFRESH_TOKEN
                            },
                            cookies={
                                "session_token": self.auth_cookie
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
        assert response_json["therapist_id"] == FAKE_THERAPIST_ID
        assert response_json["token"] is not None

    def test_add_therapist_with_existing_auth_cookie_success(self):
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                            headers={
                                "store-access-token": FAKE_ACCESS_TOKEN,
                                "store-refresh-token": FAKE_REFRESH_TOKEN
                            },
                            cookies={
                                        "session_token": self.auth_cookie
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
        assert response_json["therapist_id"] == FAKE_THERAPIST_ID
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
        response = self.client.put(SecurityRouter.THERAPISTS_ENDPOINT,
                            cookies={
                                "session_token": self.auth_cookie
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
        response = self.client.put(SecurityRouter.THERAPISTS_ENDPOINT,
                            cookies={
                                "session_token": self.auth_cookie
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
        response = self.client.put(SecurityRouter.THERAPISTS_ENDPOINT,
                            cookies={
                                "session_token": self.auth_cookie
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
        response = self.client.put(SecurityRouter.THERAPISTS_ENDPOINT,
                            cookies={
                                "session_token": self.auth_cookie
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
        response = self.client.delete(SecurityRouter.THERAPISTS_ENDPOINT,
                                        cookies={
                                            "session_token": self.auth_cookie
                                        },
                                        headers={
                                            "store-access-token": FAKE_ACCESS_TOKEN,
                                            "store-refresh-token": FAKE_REFRESH_TOKEN
                                        })
        assert response.status_code == 200

    def encryption_base64_str_decryption_success(self):
        plaintext = "fooBar"
        chartwise_encryptor = dependency_container.inject_chartwise_encryptor()
        encrypted_value = chartwise_encryptor.encrypt(plaintext)
        assert len(encrypted_value or '') > 0
        assert encrypted_value != plaintext

        decrypted_value = chartwise_encryptor.decrypt(encrypted_value)
        assert decrypted_value == plaintext
