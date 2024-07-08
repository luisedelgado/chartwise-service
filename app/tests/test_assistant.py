from fastapi.testclient import TestClient

from ..managers.manager_factory import ManagerFactory
from ..routers.assistant_router import AssistantRouter
from ..routers.security_router import SecurityRouter
from ..service_coordinator import EndpointServiceCoordinator

FAKE_AUTH_COOKIE = "my-auth-cookie"
FAKE_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
FAKE_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
DUMMY_REFRESH_TOKEN = "refreshToken"
DUMMY_ACCESS_TOKEN = "accessToken"
ENVIRONMENT = "testing"

class TestingHarnessAssistantRouter:

    def setup_method(self):
        self.auth_manager = ManagerFactory().create_auth_manager(ENVIRONMENT)
        self.auth_manager.auth_cookie = FAKE_AUTH_COOKIE

        self.assistant_manager = ManagerFactory.create_assistant_manager(ENVIRONMENT)
        self.audio_processing_manager = ManagerFactory.create_audio_processing_manager(ENVIRONMENT)

        coordinator = EndpointServiceCoordinator(routers=[AssistantRouter(environment=ENVIRONMENT,
                                                                          auth_manager=self.auth_manager,
                                                                          assistant_manager=self.assistant_manager).router,
                                                          SecurityRouter(auth_manager=self.auth_manager,
                                                                         assistant_manager=self.assistant_manager).router])
        self.client = TestClient(coordinator.service_app)

    def test_insert_new_session_with_invalid_auth(self):
        response = self.client.post(AssistantRouter.SESSIONS_ENDPOINT,
                               json={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                   "date": "01-01-2020",
                                   "datastore_access_token": DUMMY_ACCESS_TOKEN,
                                   "datastore_refresh_token": DUMMY_REFRESH_TOKEN,
                                   "source": "manual_input"
                               })
        assert response.status_code == 401

    def test_insert_new_session_with_valid_auth_but_invalid_date_format(self):
        response = self.client.post(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": FAKE_AUTH_COOKIE,
                                    },
                                    json={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                        "text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                        "date": "01/01/2020",
                                        "datastore_access_token": DUMMY_ACCESS_TOKEN,
                                        "datastore_refresh_token": DUMMY_REFRESH_TOKEN,
                                        "source": "manual_input"
                                    })
        assert response.status_code == 400

    def test_insert_new_session_with_valid_auth_but_undefined_source(self):
        response = self.client.post(AssistantRouter.SESSIONS_ENDPOINT,
                                    cookies={
                                        "authorization": FAKE_AUTH_COOKIE,
                                    },
                                    json={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                        "text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                                        "date": "01/01/2020",
                                        "datastore_access_token": DUMMY_ACCESS_TOKEN,
                                        "datastore_refresh_token": DUMMY_REFRESH_TOKEN,
                                        "source": "undefined"
                                    })
        assert response.status_code == 400

    # TODO: Uncomment when async testing is figured out
    # def test_insert_new_session_with_valid_auth_and_valid_payload(self):
    #     assert self.assistant_manager.fake_insert_text == None
    #     insert_text = "El jugador favorito de Lionel Andres siempre fue Aimar."
    #     response = self.client.post(AssistantRouter.SESSIONS_ENDPOINT,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                 },
    #                                 json={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                     "text": insert_text,
    #                                     "date": "01-01-2020",
    #                                     "datastore_access_token": DUMMY_ACCESS_TOKEN,
    #                                     "datastore_refresh_token": DUMMY_REFRESH_TOKEN,
    #                                     "source": "manual_input"
    #                                 })
    #     assert response.status_code == 200
    #     assert self.assistant_manager.fake_insert_text == insert_text
