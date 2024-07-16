from fastapi.testclient import TestClient

from ..internal.model import Gender
from ..managers.manager_factory import ManagerFactory
from ..routers.security_router import SecurityRouter
from ..service_coordinator import EndpointServiceCoordinator

FAKE_AUTH_COOKIE = "my-auth-cookie"
FAKE_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
FAKE_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
ENVIRONMENT = "testing"

class TestingHarnessSecurityRouter:

    def setup_method(self):
        self.auth_manager = ManagerFactory().create_auth_manager(ENVIRONMENT)
        self.auth_manager.auth_cookie = FAKE_AUTH_COOKIE

        self.assistant_manager = ManagerFactory.create_assistant_manager(ENVIRONMENT)
        self.audio_processing_manager = ManagerFactory.create_audio_processing_manager(ENVIRONMENT)

        coordinator = EndpointServiceCoordinator(routers=[SecurityRouter(auth_manager=self.auth_manager,
                                                                         assistant_manager=self.assistant_manager).router])
        self.client = TestClient(coordinator.service_app)

    def test_login_for_token_with_invalid_auth_token(self):
        response = self.client.post(SecurityRouter.TOKEN_ENDPOINT,
                               json={
                                   "datastore_access_token": "",
                                   "datastore_refresh_token": "",
                                   "user_id": ""
                               })
        assert response.status_code == 401

    def test_login_for_token_with_valid_credentials_new_session(self):
        response = self.client.post(SecurityRouter.TOKEN_ENDPOINT,
                               json={
                                   "datastore_access_token": self.auth_manager.FAKE_DATASTORE_ACCESS_TOKEN,
                                   "datastore_refresh_token": self.auth_manager.FAKE_DATASTORE_REFRESH_TOKEN,
                                   "user_id": self.auth_manager.FAKE_USER_ID
                               })
        assert response.status_code == 200
        assert response.cookies.get("datastore_access_token") == self.auth_manager.FAKE_DATASTORE_ACCESS_TOKEN
        assert response.cookies.get("datastore_refresh_token") == self.auth_manager.FAKE_DATASTORE_REFRESH_TOKEN
        assert response.cookies.get("authorization") == self.auth_manager.FAKE_AUTH_TOKEN
        assert response.cookies.get("session_id") is not None

    def test_add_therapist_with_invalid_credentials(self):
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                               json={
                                   "id": FAKE_THERAPIST_ID,
                                   "email": "foo@foo.com",
                                   "first_name": "foo",
                                   "last_name": "bar",
                                   "birth_date": "01/01/2000",
                                   "signup_mechanism": "internal",
                                   "language_code_preference": "es-419",
                                   "gender": "male",
                               })
        assert response.status_code == 401

    def test_add_therapist_with_valid_auth_token_but_missing_datastore_tokens(self):
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                                cookies={
                                    "authorization": FAKE_AUTH_COOKIE,
                                },
                                json={
                                    "id": FAKE_THERAPIST_ID,
                                    "email": "foo@foo.com",
                                    "first_name": "foo",
                                    "last_name": "bar",
                                    "birth_date": "01/01/2000",
                                    "signup_mechanism": "internal",
                                    "language_code_preference": "es-419",
                                    "gender": "male",
                                })
        assert response.status_code == 401

    def test_add_therapist_with_valid_datastore_tokens_but_missing_auth_token(self):
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                                cookies={
                                   "datastore_access_token": self.auth_manager.FAKE_DATASTORE_ACCESS_TOKEN,
                                   "datastore_refresh_token": self.auth_manager.FAKE_DATASTORE_REFRESH_TOKEN
                                },
                                json={
                                    "id": FAKE_THERAPIST_ID,
                                    "email": "foo@foo.com",
                                    "first_name": "foo",
                                    "last_name": "bar",
                                    "birth_date": "01/01/2000",
                                    "signup_mechanism": "internal",
                                    "language_code_preference": "es-419",
                                    "gender": "male",
                                })
        assert response.status_code == 401

    def test_add_therapist_with_valid_credentials_but_invalid_birthdate_format(self):
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                               cookies={
                                   "authorization": FAKE_AUTH_COOKIE,
                                   "datastore_access_token": self.auth_manager.FAKE_DATASTORE_ACCESS_TOKEN,
                                   "datastore_refresh_token": self.auth_manager.FAKE_DATASTORE_REFRESH_TOKEN
                               },
                               json={
                                   "id": FAKE_THERAPIST_ID,
                                   "email": "foo@foo.com",
                                   "first_name": "foo",
                                   "last_name": "bar",
                                   "birth_date": "01/01/2000",
                                   "signup_mechanism": "internal",
                                   "language_code_preference": "es-419",
                                   "gender": "male",
                               })
        assert response.status_code == 400

    def test_add_therapist_with_valid_credentials_but_invalid_language_preference(self):
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                               cookies={
                                   "authorization": FAKE_AUTH_COOKIE,
                                   "datastore_access_token": self.auth_manager.FAKE_DATASTORE_ACCESS_TOKEN,
                                   "datastore_refresh_token": self.auth_manager.FAKE_DATASTORE_REFRESH_TOKEN
                               },
                               json={
                                   "id": FAKE_THERAPIST_ID,
                                   "email": "foo@foo.com",
                                   "first_name": "foo",
                                   "last_name": "bar",
                                   "birth_date": "01-01-2000",
                                   "signup_mechanism": "internal",
                                   "language_code_preference": "brbrbrbrbr",
                                   "gender": "male",
                               })
        assert response.status_code == 400

    def test_add_therapist_with_valid_credentials_but_invalid_gender_format(self):
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                                cookies={
                                    "authorization": FAKE_AUTH_COOKIE,
                                    "datastore_access_token": self.auth_manager.FAKE_DATASTORE_ACCESS_TOKEN,
                                    "datastore_refresh_token": self.auth_manager.FAKE_DATASTORE_REFRESH_TOKEN
                                },
                                json={
                                    "id": FAKE_THERAPIST_ID,
                                    "email": "foo@foo.com",
                                    "first_name": "foo",
                                    "last_name": "bar",
                                    "birth_date": "01-01-2000",
                                    "signup_mechanism": "internal",
                                    "language_code_preference": "es-419",
                                    "gender": "undefined",
                                })
        assert response.status_code == 400

    def test_add_therapist_with_valid_credentials_but_undefined_signup_mechanism(self):
        response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
                               cookies={
                                   "authorization": FAKE_AUTH_COOKIE,
                                   "datastore_access_token": self.auth_manager.FAKE_DATASTORE_ACCESS_TOKEN,
                                   "datastore_refresh_token": self.auth_manager.FAKE_DATASTORE_REFRESH_TOKEN
                               },
                               json={
                                   "id": FAKE_THERAPIST_ID,
                                   "email": "foo@foo.com",
                                   "first_name": "foo",
                                   "last_name": "bar",
                                   "birth_date": "01-01-2000",
                                   "signup_mechanism": "undefined",
                                   "language_code_preference": "es-419",
                                   "gender": "male",
                               })
        assert response.status_code == 400

    # TODO: Uncomment when async testing is figured out
    # def test_signup_success(self):
    #     fake_role = "authenticated"
    #     valid_access_token = "valid_access_token"
    #     valid_refresh_token = "valid_refresh_token"
    #     valid_user_id = "user_id"
    #     self.auth_manager.fake_supabase_client.fake_role = fake_role
    #     self.auth_manager.fake_supabase_client.FAKE_AUTH_TOKEN = valid_access_token
    #     self.auth_manager.fake_supabase_client.fake_refresh_token = valid_refresh_token
    #     self.auth_manager.fake_supabase_client.fake_user_id = valid_user_id

    #     response = self.client.post(SecurityRouter.THERAPISTS_ENDPOINT,
    #                         cookies={
    #                             "authorization": FAKE_AUTH_COOKIE,
    #                         },
    #                         json={
    #                             "user_email": "foo@foo.com",
    #                             "user_password": "myPassword",
    #                             "first_name": "foo",
    #                             "last_name": "bar",
    #                             "birth_date": "01-01-2000",
    #                             "signup_mechanism": "custom",
    #                             "language_preference": "es-419"
    #                         })
    #     assert response.status_code == 200
    #     assert response.json() == {
    #         "user_id": valid_user_id,
    #         "access_token": valid_access_token,
    #         "refresh_token": valid_refresh_token
    #     }
    #     assert response.cookies.get("authorization") == self.auth_manager.FAKE_AUTH_TOKEN
    #     assert response.cookies.get("session_id") == self.auth_manager.FAKE_SESSION_ID

    def test_update_therapist_with_invalid_credentials(self):
        response = self.client.put(SecurityRouter.THERAPISTS_ENDPOINT,
                            json={
                                "id": FAKE_THERAPIST_ID,
                                "email": "foo@foo.com",
                                "first_name": "foo",
                                "last_name": "bar",
                                "birth_date": "01-01-2000",
                                "language_code_preference": "es-419",
                                "gender": "male",
                            })
        assert response.status_code == 401

    def test_update_therapist_with_valid_credentials_but_undefined_gender(self):
        response = self.client.put(SecurityRouter.THERAPISTS_ENDPOINT,
                            cookies={
                                "authorization": FAKE_AUTH_COOKIE,
                                "datastore_access_token": self.auth_manager.FAKE_DATASTORE_ACCESS_TOKEN,
                                "datastore_refresh_token": self.auth_manager.FAKE_DATASTORE_REFRESH_TOKEN
                            },
                            json={
                                "id": FAKE_THERAPIST_ID,
                                "email": "foo@foo.com",
                                "first_name": "foo",
                                "last_name": "bar",
                                "birth_date": "01-01-2000",
                                "language_code_preference": "es-419",
                                "gender": "undefined",
                            })
        assert response.status_code == 400

    def test_update_therapist_with_valid_credentials_but_invalid_date(self):
        response = self.client.put(SecurityRouter.THERAPISTS_ENDPOINT,
                            cookies={
                                "authorization": FAKE_AUTH_COOKIE,
                                "datastore_access_token": self.auth_manager.FAKE_DATASTORE_ACCESS_TOKEN,
                                "datastore_refresh_token": self.auth_manager.FAKE_DATASTORE_REFRESH_TOKEN
                            },
                            json={
                                "id": FAKE_THERAPIST_ID,
                                "email": "foo@foo.com",
                                "first_name": "foo",
                                "last_name": "bar",
                                "birth_date": "01/01/2000",
                                "language_code_preference": "es-419",
                                "gender": "male",
                            })
        assert response.status_code == 400

    def test_update_therapist_with_valid_credentials_but_invalid_language_code(self):
        response = self.client.put(SecurityRouter.THERAPISTS_ENDPOINT,
                            cookies={
                                "authorization": FAKE_AUTH_COOKIE,
                                "datastore_access_token": self.auth_manager.FAKE_DATASTORE_ACCESS_TOKEN,
                                "datastore_refresh_token": self.auth_manager.FAKE_DATASTORE_REFRESH_TOKEN
                            },
                            json={
                                "id": FAKE_THERAPIST_ID,
                                "email": "foo@foo.com",
                                "first_name": "foo",
                                "last_name": "bar",
                                "birth_date": "01-01-2000",
                                "language_code_preference": "brbrbrbr",
                                "gender": "male",
                            })
        assert response.status_code == 400

    def test_update_therapist_success(self):
        response = self.client.put(SecurityRouter.THERAPISTS_ENDPOINT,
                            cookies={
                                "authorization": FAKE_AUTH_COOKIE,
                                "datastore_access_token": self.auth_manager.FAKE_DATASTORE_ACCESS_TOKEN,
                                "datastore_refresh_token": self.auth_manager.FAKE_DATASTORE_REFRESH_TOKEN
                            },
                            json={
                                "id": self.auth_manager.FAKE_USER_ID,
                                "email": "foo@foo.com",
                                "first_name": "foo",
                                "last_name": "bar",
                                "birth_date": "01-01-2000",
                                "language_code_preference": "es-419",
                                "gender": "male",
                            })
        assert response.status_code == 200

    def test_logout_with_invalid_credentials(self):
        response = self.client.post(SecurityRouter.LOGOUT_ENDPOINT,
                                json={
                                    "therapist_id": FAKE_THERAPIST_ID,
                                })
        assert response.status_code == 401

    def test_logout_with_valid_credentials(self):
        response = self.client.post(SecurityRouter.LOGOUT_ENDPOINT,
                                cookies={
                                    "authorization": FAKE_AUTH_COOKIE,
                                    "datastore_access_token": self.auth_manager.FAKE_DATASTORE_ACCESS_TOKEN,
                                    "datastore_refresh_token": self.auth_manager.FAKE_DATASTORE_REFRESH_TOKEN
                                },
                                json={
                                    "therapist_id": self.auth_manager.FAKE_USER_ID,
                                })
        assert response.status_code == 200
        cookie_header = response.headers.get("set-cookie")
        assert cookie_header is not None
        assert "authorization=" in cookie_header
        assert "session_id=" in cookie_header
        assert "expires=" in cookie_header or "Max-Age=0" in cookie_header

    def test_delete_therapist_with_invalid_credentials(self):
        response = self.client.delete(SecurityRouter.THERAPISTS_ENDPOINT,
                                      params={
                                          "id": FAKE_THERAPIST_ID,
                                          })
        assert response.status_code == 401

    def test_delete_therapist_with_empty_id(self):
        response = self.client.delete(SecurityRouter.THERAPISTS_ENDPOINT,
                                        cookies={
                                            "authorization": FAKE_AUTH_COOKIE,
                                            "datastore_access_token": self.auth_manager.FAKE_DATASTORE_ACCESS_TOKEN,
                                            "datastore_refresh_token": self.auth_manager.FAKE_DATASTORE_REFRESH_TOKEN
                                        },
                                        params={
                                            "id": "",
                                        })
        assert response.status_code == 400

    def test_delete_therapist_success(self):
        response = self.client.delete(SecurityRouter.THERAPISTS_ENDPOINT,
                                        cookies={
                                            "authorization": FAKE_AUTH_COOKIE,
                                            "datastore_access_token": self.auth_manager.FAKE_DATASTORE_ACCESS_TOKEN,
                                            "datastore_refresh_token": self.auth_manager.FAKE_DATASTORE_REFRESH_TOKEN
                                        },
                                        params={
                                            "therapist_id": self.auth_manager.FAKE_USER_ID,
                                        })
        assert response.status_code == 200
