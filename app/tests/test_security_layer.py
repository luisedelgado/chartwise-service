from fastapi.testclient import TestClient

from ..managers.manager_factory import ManagerFactory
from ..routers.security_router import SecurityRouter
from ..service_coordinator import EndpointServiceCoordinator

DUMMY_AUTH_COOKIE = "my-auth-cookie"
DUMMY_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
DUMMY_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
ENVIRONMENT = "testing"

class TestingHarnessSecurityRouter:

    def setup_method(self):
        self.auth_manager = ManagerFactory().create_auth_manager(ENVIRONMENT)
        self.auth_manager.auth_cookie = DUMMY_AUTH_COOKIE

        self.assistant_manager = ManagerFactory.create_assistant_manager(ENVIRONMENT)
        self.audio_processing_manager = ManagerFactory.create_audio_processing_manager(ENVIRONMENT)

        coordinator = EndpointServiceCoordinator(routers=[SecurityRouter(auth_manager=self.auth_manager).router])
        self.client = TestClient(coordinator.service_app)

    def test_login_for_token_with_invalid_credentials(self):
        response = self.client.post(SecurityRouter.TOKEN_ENDPOINT,
                               data={
                                   "username": "wrongUsername",
                                   "password": "wrongPassword"
                               })
        assert response.status_code == 400

    def test_login_for_token_with_valid_credentials(self):
        response = self.client.post(SecurityRouter.TOKEN_ENDPOINT,
                               data={
                                   "username": self.auth_manager.FAKE_USERNAME,
                                   "password": self.auth_manager.FAKE_PASSWORD
                               })
        assert response.status_code == 200
        assert response.cookies.get("authorization") == self.auth_manager.FAKE_ACCESS_TOKEN
        assert response.cookies.get("session_id") == self.auth_manager.FAKE_SESSION_ID

    def test_signup_with_invalid_credentials(self):
        response = self.client.post(SecurityRouter.SIGN_UP_ENDPOINT,
                               json={
                                   "user_email": "foo@foo.com",
                                   "user_password": "myPassword",
                                   "first_name": "foo",
                                   "last_name": "bar",
                                   "birth_date": "01/01/2000",
                                   "signup_mechanism": "custom",
                                   "language_preference": "es-419"
                               })
        assert response.status_code == 401

    def test_signup_with_valid_credentials_but_invalid_birthdate_format(self):
        response = self.client.post(SecurityRouter.SIGN_UP_ENDPOINT,
                               cookies={
                                   "authorization": DUMMY_AUTH_COOKIE,
                               },
                               json={
                                   "user_email": "foo@foo.com",
                                   "user_password": "myPassword",
                                   "first_name": "foo",
                                   "last_name": "bar",
                                   "birth_date": "01/01/2000",
                                   "signup_mechanism": "custom",
                                   "language_preference": "es-419"
                               })
        assert response.status_code == 417

    def test_signup_with_valid_credentials_but_invalid_language_preference(self):
        response = self.client.post(SecurityRouter.SIGN_UP_ENDPOINT,
                               cookies={
                                   "authorization": DUMMY_AUTH_COOKIE,
                               },
                               json={
                                   "user_email": "foo@foo.com",
                                   "user_password": "myPassword",
                                   "first_name": "foo",
                                   "last_name": "bar",
                                   "birth_date": "01-01-2000",
                                   "signup_mechanism": "custom",
                                   "language_preference": "brbrbrbrbrbrbr"
                               })
        assert response.status_code == 417

    def test_signup_with_valid_credentials_but_received_bad_role_from_service(self):
        self.auth_manager.fake_supabase_client.fake_role = "bad_role"
        self.auth_manager.fake_supabase_client.fake_access_token = "valid_token"
        self.auth_manager.fake_supabase_client.fake_refresh_token = "valid_token"

        response = self.client.post(SecurityRouter.SIGN_UP_ENDPOINT,
                               cookies={
                                   "authorization": DUMMY_AUTH_COOKIE,
                               },
                               json={
                                   "user_email": "foo@foo.com",
                                   "user_password": "myPassword",
                                   "first_name": "foo",
                                   "last_name": "bar",
                                   "birth_date": "01-01-2000",
                                   "signup_mechanism": "custom",
                                   "language_preference": "es-419"
                               })
        assert response.status_code == 417

    def test_signup_with_valid_credentials_but_received_bad_access_token_from_service(self):
        self.auth_manager.fake_supabase_client.fake_role = "authenticated"
        self.auth_manager.fake_supabase_client.fake_access_token = ""
        self.auth_manager.fake_supabase_client.fake_refresh_token = "valid_token"

        response = self.client.post(SecurityRouter.SIGN_UP_ENDPOINT,
                            cookies={
                                "authorization": DUMMY_AUTH_COOKIE,
                            },
                            json={
                                "user_email": "foo@foo.com",
                                "user_password": "myPassword",
                                "first_name": "foo",
                                "last_name": "bar",
                                "birth_date": "01-01-2000",
                                "signup_mechanism": "custom",
                                "language_preference": "es-419"
                            })
        assert response.status_code == 417

    def test_signup_with_valid_credentials_but_received_bad_refresh_token_from_service(self):
        self.auth_manager.fake_supabase_client.fake_role = "authenticated"
        self.auth_manager.fake_supabase_client.fake_access_token = ""
        self.auth_manager.fake_supabase_client.fake_refresh_token = "valid_token"

        response = self.client.post(SecurityRouter.SIGN_UP_ENDPOINT,
                            cookies={
                                "authorization": DUMMY_AUTH_COOKIE,
                            },
                            json={
                                "user_email": "foo@foo.com",
                                "user_password": "myPassword",
                                "first_name": "foo",
                                "last_name": "bar",
                                "birth_date": "01-01-2000",
                                "signup_mechanism": "custom",
                                "language_preference": "es-419"
                            })
        assert response.status_code == 417

    # TODO: Uncomment when async testing is figured out
    # def test_signup_success(self):
    #     fake_role = "authenticated"
    #     valid_access_token = "valid_access_token"
    #     valid_refresh_token = "valid_refresh_token"
    #     valid_user_id = "user_id"
    #     self.auth_manager.fake_supabase_client.fake_role = fake_role
    #     self.auth_manager.fake_supabase_client.fake_access_token = valid_access_token
    #     self.auth_manager.fake_supabase_client.fake_refresh_token = valid_refresh_token
    #     self.auth_manager.fake_supabase_client.fake_user_id = valid_user_id

    #     response = self.client.post(SecurityRouter.SIGN_UP_ENDPOINT,
    #                         cookies={
    #                             "authorization": DUMMY_AUTH_COOKIE,
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
    #     assert response.cookies.get("authorization") == self.auth_manager.FAKE_ACCESS_TOKEN
    #     assert response.cookies.get("session_id") == self.auth_manager.FAKE_SESSION_ID

    def test_logout_with_invalid_credentials(self):
        response = self.client.post(SecurityRouter.LOGOUT_ENDPOINT,
                               json={
                                   "therapist_id": DUMMY_THERAPIST_ID,
                               })
        assert response.status_code == 401

    def test_logout_with_valid_credentials(self):
        response = self.client.post(SecurityRouter.LOGOUT_ENDPOINT,
                               cookies={
                                   "authorization": DUMMY_AUTH_COOKIE,
                               },
                               json={
                                   "therapist_id": DUMMY_THERAPIST_ID,
                               })
        assert response.status_code == 200
        cookie_header = response.headers.get("set-cookie")
        assert cookie_header is not None
        assert "authorization=" in cookie_header
        assert "session_id=" in cookie_header
        assert "expires=" in cookie_header or "Max-Age=0" in cookie_header
