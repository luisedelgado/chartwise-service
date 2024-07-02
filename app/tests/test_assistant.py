from fastapi.testclient import TestClient

from ..managers.manager_factory import ManagerFactory
from ..routers.assistant_router import AssistantRouter
from ..routers.security_router import SecurityRouter
from ..service_coordinator import EndpointServiceCoordinator

DUMMY_AUTH_COOKIE = "my-auth-cookie"
DUMMY_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
DUMMY_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
ENVIRONMENT = "testing"

class TestingHarnessAssistantRouter:

    def setup_method(self):
        self.auth_manager = ManagerFactory().create_auth_manager(ENVIRONMENT)
        self.auth_manager.auth_cookie = DUMMY_AUTH_COOKIE

        self.assistant_manager = ManagerFactory.create_assistant_manager(ENVIRONMENT)
        self.audio_processing_manager = ManagerFactory.create_audio_processing_manager(ENVIRONMENT)

        coordinator = EndpointServiceCoordinator(routers=[AssistantRouter(environment=ENVIRONMENT,
                                                                          auth_manager=self.auth_manager,
                                                                          assistant_manager=self.assistant_manager).router,
                                                          SecurityRouter(auth_manager=self.auth_manager).router])
        self.client = TestClient(coordinator.service_app)

    def test_foo(self):
        assert True
