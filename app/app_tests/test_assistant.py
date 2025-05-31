from fastapi.testclient import TestClient

from ..dependencies.dependency_container import (
    dependency_container,
    FakeAsyncOpenAI,
    FakePineconeClient,
    FakeAwsDbClient,
)
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
        # Clear out any old state between tests
        dependency_container._aws_cognito_client = None
        dependency_container._aws_db_client = None
        dependency_container._aws_kms_client = None
        dependency_container._aws_s3_client = None
        dependency_container._aws_secret_manager_client = None
        dependency_container._chartwise_encryptor = None
        dependency_container._deepgram_client = None
        dependency_container._docupanda_client = None
        dependency_container._influx_client = None
        dependency_container._openai_client = None
        dependency_container._pinecone_client = None
        dependency_container._resend_client = None
        dependency_container._stripe_client = None
        dependency_container._testing_environment = "testing"

        self.fake_openai_client: FakeAsyncOpenAI = dependency_container.inject_openai_client()
        self.fake_pinecone_client: FakePineconeClient = dependency_container.inject_pinecone_client()
        self.fake_aws_db_client: FakeAwsDbClient = dependency_container.inject_aws_db_client()
        self.session_token, _ = AuthManager().create_session_token(user_id=FAKE_THERAPIST_ID)

        coordinator = EndpointServiceCoordinator(routers=[AssistantRouter(environment=ENVIRONMENT).router],
                                                 environment=ENVIRONMENT)
        self.client = TestClient(coordinator.app)

    def test_get_single_session_report_with_missing_session_token(self):
        url = AssistantRouter.SINGLE_SESSION_ENDPOINT.format(
            session_report_id=FAKE_SESSION_REPORT_ID
        )
        response = self.client.get(url,
                                   headers={
                                       "auth-token": "myFakeToken",
                                   },)
        assert response.status_code == 401

    def test_get_single_session_report_success(self):
        url = AssistantRouter.SINGLE_SESSION_ENDPOINT.format(
            session_report_id=FAKE_SESSION_REPORT_ID
        )
        self.client.cookies.set(
            "session_token", self.session_token
        )
        response = self.client.get(
            url,
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 200

    def test_get_session_reports_with_missing_session_token(self):
        response = self.client.get(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "patient_id": FAKE_PATIENT_ID,
                "year": 2004
            }
        )
        assert response.status_code == 401

    def test_get_session_reports_with_no_filters(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "patient_id": FAKE_PATIENT_ID
            }
        )
        assert response.status_code == 400

    def test_get_session_reports_with_filters_recency_and_time_range(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "patient_id": FAKE_PATIENT_ID,
                "time_range": "month",
                "most_recent_n": 1
            }
        )
        assert response.status_code == 400

    def test_get_session_reports_with_filters_recency_and_year(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "patient_id": FAKE_PATIENT_ID,
                "most_recent_n": 1,
                "year": "2011"
            }
        )
        assert response.status_code == 400

    def test_get_session_reports_with_filters_time_range_and_year(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "patient_id": FAKE_PATIENT_ID,
                "time_range": "month",
                "year": 2011
            }
        )
        assert response.status_code == 400

    def test_get_session_reports_by_time_range_month_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "patient_id": FAKE_PATIENT_ID,
                "time_range": "month"
            }
        )
        assert response.status_code == 200

    def test_get_session_reports_by_time_range_year_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "patient_id": FAKE_PATIENT_ID,
                "time_range": "year"
            }
        )
        assert response.status_code == 200

    def test_get_session_reports_by_time_range_five_years_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "patient_id": FAKE_PATIENT_ID,
                "time_range": "five_years"
            }
        )
        assert response.status_code == 200

    def test_get_session_reports_by_recency_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "patient_id": FAKE_PATIENT_ID,
                "most_recent_n": 10
            }
        )
        assert response.status_code == 200

    def test_get_session_reports_by_year_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "patient_id": FAKE_PATIENT_ID,
                "year": 2004
            }
        )
        assert response.status_code == 200

    def test_insert_new_session_with_missing_session_token(self):
        response = self.client.post(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "insert_payload": {
                    "patient_id": FAKE_PATIENT_ID,
                    "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                    "session_date": "01-01-2020",
                    "source": "manual_input"
                },
                "client_timezone_identifier": TZ_IDENTIFIER,
            })
        assert response.status_code == 401

    def test_insert_new_session_with_valid_authentication_but_invalid_date_format(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "insert_payload": {
                    "patient_id": FAKE_PATIENT_ID,
                    "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                    "session_date": "01/01/2020",
                    "source": "manual_input"
                },
                "client_timezone_identifier": TZ_IDENTIFIER,
            }
        )
        assert response.status_code == 400

    def test_insert_new_session_beyond_freemium_usage_without_subscribing(self):
        self.client.cookies.set("session_token", self.session_token)
        self.fake_pinecone_client.vector_store_context_returns_data = True
        self.fake_aws_db_client.return_no_subscription_data = True
        self.fake_aws_db_client.return_freemium_usage_above_limit = True
        response = self.client.post(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "insert_payload": {
                    "patient_id": FAKE_PATIENT_ID,
                    "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                    "session_date": "01-01-2020",
                    "source": "manual_input"
                },
                "client_timezone_identifier": TZ_IDENTIFIER,
            }
        )
        assert response.status_code == 402

    def test_insert_new_session_with_empty_patient_id(self):
        insert_text = "El jugador favorito de Lionel Andres siempre fue Aimar."
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "insert_payload": {
                    "patient_id": "",
                    "notes_text": insert_text,
                    "session_date": "01-01-2020",
                    "source": "manual_input"
                },
                "client_timezone_identifier": "gfsghfsdhgdsgs",
            }
        )
        assert response.status_code == 400

    def test_insert_new_session_with_invalid_timezone(self):
        insert_text = "El jugador favorito de Lionel Andres siempre fue Aimar."
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "insert_payload": {
                    "patient_id": FAKE_PATIENT_ID,
                    "notes_text": insert_text,
                    "session_date": "01-01-2020",
                    "source": "manual_input"
                },
                "client_timezone_identifier": "gfsghfsdhgdsgs",
            }
        )
        assert response.status_code == 400

    def test_insert_new_session_success(self):
        assert not self.fake_pinecone_client.insert_session_vectors_invoked
        self.fake_pinecone_client.vector_store_context_returns_data = True
        insert_text = "El jugador favorito de Lionel Andres siempre fue Aimar."
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
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
        assert self.fake_pinecone_client.insert_session_vectors_invoked
        assert response.status_code == 200

    def test_update_session_with_missing_session_token(self):
        response = self.client.put(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "update_payload": {
                    "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                    "session_date": "01-01-2020",
                    "source": "manual_input",
                    "id": FAKE_SESSION_REPORT_ID
                },
                "client_timezone_identifier": TZ_IDENTIFIER,
            }
        )
        assert response.status_code == 401

    def test_update_session_with_valid_auth_but_invalid_date_format(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.put(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "update_payload": {
                    "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                    "session_date": "01/01/2020",
                    "source": "manual_input",
                    "id": FAKE_SESSION_REPORT_ID
                },
                "client_timezone_identifier": TZ_IDENTIFIER,
            }
        )
        assert response.status_code == 400

    def test_update_session_with_valid_auth_but_invalid_timezone(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.put(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "update_payload": {
                    "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                    "session_date": "01-01-2020",
                    "source": "manual_input",
                    "id": FAKE_SESSION_REPORT_ID
                },
                "client_timezone_identifier": "fsrghshfsdhfsd",
            }
        )
        assert response.status_code == 400

    def test_update_session_with_valid_auth_but_empty_session_notes_id(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.put(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "update_payload": {
                    "notes_text": "El jugador favorito de Lionel Andres siempre fue Aimar.",
                    "session_date": "01-01-2020",
                    "source": "undefined",
                    "id": "",
                },
                "client_timezone_identifier": TZ_IDENTIFIER,
            }
        )
        assert response.status_code == 400

    def test_update_session_with_different_text_success(self):
        assert not self.fake_pinecone_client.update_session_vectors_invoked
        self.client.cookies.set("session_token", self.session_token)
        self.fake_pinecone_client.vector_store_context_returns_data = True
        update_text = "new_text"
        response = self.client.put(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "update_payload": {
                    "notes_text": update_text,
                    "session_date": "01-01-2020",
                    "source": "manual_input",
                    "id": FAKE_SESSION_REPORT_ID
                },
                "client_timezone_identifier": TZ_IDENTIFIER,
            }
        )
        assert response.status_code == 200
        assert self.fake_pinecone_client.update_session_vectors_invoked

    def test_update_session_with_same_text_success(self):
        self.client.cookies.set("session_token", self.session_token)
        self.fake_pinecone_client.vector_store_context_returns_data = True
        update_text = "initial text"        
        response = self.client.put(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "update_payload": {
                    "notes_text": update_text,
                    "session_date": "01-01-2020",
                    "source": "manual_input",
                    "id": FAKE_SESSION_REPORT_ID
                },
                "client_timezone_identifier": TZ_IDENTIFIER,
            }
        )
        assert response.status_code == 200

    def test_delete_session_with_invalid_auth(self):
        response = self.client.delete(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "session_report_id": FAKE_SESSION_REPORT_ID,
            }
        )
        assert response.status_code == 401

    def test_delete_session_with_valid_auth_but_empty_session_notes_id(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.delete(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "session_report_id": "",
            }
        )
        assert response.status_code == 400

    def test_delete_session_success(self):
        assert not self.fake_pinecone_client.delete_session_vectors_invoked
        self.client.cookies.set("session_token", self.session_token)
        self.fake_pinecone_client.vector_store_context_returns_data = True
        response = self.client.delete(
            AssistantRouter.SESSIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "session_report_id": FAKE_SESSION_REPORT_ID,
            }
        )
        assert response.status_code == 200
        assert self.fake_pinecone_client.delete_session_vectors_invoked

    def test_session_query_with_missing_session_token(self):
        response = self.client.post(
            AssistantRouter.QUERIES_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "patient_id": FAKE_PATIENT_ID,
                "text": "Quien es el jugador favorito de Lionel Andres?",
            }
        )
        assert response.status_code == 401

    def test_session_query_with_valid_auth_token_but_empty_patient_id(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.QUERIES_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "patient_id": "",
                "text": "Quien es el jugador favorito de Lionel Andres?",
            }
        )
        assert response.status_code == 400

    def test_session_query_with_valid_auth_token_but_empty_text(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.QUERIES_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "patient_id": FAKE_PATIENT_ID,
                "text": "",
            }
        )
        assert response.status_code == 400

    def test_session_query_success(self):
        assert not self.fake_pinecone_client.get_vector_store_context_invoked
        self.client.cookies.set("session_token", self.session_token)
        self.fake_pinecone_client.vector_store_context_returns_data = True
        response = self.client.post(
            AssistantRouter.QUERIES_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "patient_id": FAKE_PATIENT_ID,
                "text": "Quien es el jugador favorito de Lionel?",
            }
        )
        assert response.status_code == 200
        assert self.fake_pinecone_client.get_vector_store_context_invoked

    def test_session_query_success_changing_patient_and_clearing_chat_history(self):
        self.client.cookies.set("session_token", self.session_token)
        assert not self.fake_pinecone_client.get_vector_store_context_invoked
        self.fake_pinecone_client.vector_store_context_returns_data = True

        MESSI_QUERY = "Quien es el jugador favorito de Lionel?"
        CRISTIANO_QUERY = "Quien es el jugador favorito de Cristiano?"

        assert len(self.fake_openai_client.chat_history) == 0
        response = self.client.post(
            AssistantRouter.QUERIES_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "patient_id": FAKE_PATIENT_ID,
                "text": MESSI_QUERY,
            }
        )
        assert response.status_code == 200
        assert len(self.fake_openai_client.chat_history) == 2
        assert MESSI_QUERY == self.fake_openai_client.chat_history[0].content
        assert CRISTIANO_QUERY != self.fake_openai_client.chat_history[1].content
        assert self.fake_pinecone_client.get_vector_store_context_invoked

        # Now trigger a query for a different patient id
        response = self.client.post(
            AssistantRouter.QUERIES_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "patient_id": FAKE_SECOND_THERAPIST_ID,
                "text": CRISTIANO_QUERY,
            }
        )
        assert response.status_code == 200

        # Previous chat history should get cleared, leaving us with the 2 new messages.
        assert len(self.fake_openai_client.chat_history) == 2
        assert CRISTIANO_QUERY == self.fake_openai_client.chat_history[0].content
        assert MESSI_QUERY != self.fake_openai_client.chat_history[1].content
        assert self.fake_pinecone_client.get_vector_store_context_invoked

    def test_get_single_patient_with_missing_session_token(self):
        url = AssistantRouter.SINGLE_PATIENT_ENDPOINT.format(
            patient_id=FAKE_PATIENT_ID
        )
        response = self.client.get(
            url,
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 401

    def test_get_single_patient_success(self):
        self.client.cookies.set("session_token", self.session_token)
        url = AssistantRouter.SINGLE_PATIENT_ENDPOINT.format(patient_id=FAKE_PATIENT_ID)
        response = self.client.get(
            url,
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 200

    def test_get_patients_with_missing_session_token(self):
        response = self.client.get(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 401

    def test_get_patients_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 200

    def test_add_patient_with_missing_session_token(self):
        response = self.client.post(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "first_name": "Pepito",
                "last_name": "Perez",
                "pre_existing_history": "My history",
                "birth_date": "10-24-1991",
                "gender": "female",
                "email": "foo@foo.foo",
                "phone_number": "123",
                "consentment_channel": "verbal",
                "onboarding_first_time_patient": True
            })
        assert response.status_code == 401

    def test_add_patient_with_undefined_gender(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "first_name": "Pepito",
                "last_name": "Perez",
                "birth_date": "10-24-1991",
                "gender": "undefined",
                "email": "foo@foo.foo",
                "phone_number": "123",
                "consentment_channel": "verbal",
                "onboarding_first_time_patient": True
            }
        )
        assert response.status_code == 400

    def test_add_patient_with_undefined_consentment_channel(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "first_name": "Pepito",
                "last_name": "Perez",
                "birth_date": "10-24-1991",
                "gender": "male",
                "email": "foo@foo.foo",
                "phone_number": "123",
                "consentment_channel": "undefined",
                "onboarding_first_time_patient": True
            }
        )
        assert response.status_code == 400

    def test_add_patient_with_invalid_date(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "first_name": "Pepito",
                "last_name": "Perez",
                "birth_date": "10/24/1991",
                "gender": "male",
                "email": "foo@foo.foo",
                "phone_number": "123",
                "consentment_channel": "verbal",
                "onboarding_first_time_patient": True
            }
        )
        assert response.status_code == 400

    def test_add_male_patient_without_pre_existing_history_and_different_gender_pronouns_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "first_name": "Pepito",
                "last_name": "Perez",
                "birth_date": "10-24-1991",
                "gender": "male",
                "email": "foo@foo.foo",
                "phone_number": "123",
                "consentment_channel": "verbal",
                "onboarding_first_time_patient": True
            }
        )
        assert response.status_code == 200
        assert "patient_id" in response.json()

    def test_add_male_patient_without_pre_existing_history_and_not_different_gender_pronouns_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "first_name": "Pepito",
                "last_name": "Perez",
                "birth_date": "10-24-1991",
                "gender": "male",
                "email": "foo@foo.foo",
                "phone_number": "123",
                "consentment_channel": "verbal",
                "onboarding_first_time_patient": True
            }
        )
        assert response.status_code == 200
        assert "patient_id" in response.json()

    def test_add_female_patient_without_pre_existing_history_and_different_gender_pronouns_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "first_name": "Pepito",
                "last_name": "Perez",
                "birth_date": "10-24-1991",
                "gender": "female",
                "email": "foo@foo.foo",
                "phone_number": "123",
                "consentment_channel": "verbal",
                "onboarding_first_time_patient": True
            }
        )
        assert response.status_code == 200
        assert "patient_id" in response.json()

    def test_add_female_patient_without_pre_existing_history_and_not_different_gender_pronouns_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "first_name": "Pepito",
                "last_name": "Perez",
                "birth_date": "10-24-1991",
                "gender": "female",
                "email": "foo@foo.foo",
                "phone_number": "123",
                "consentment_channel": "verbal",
                "onboarding_first_time_patient": True
            }
        )
        assert response.status_code == 200
        assert "patient_id" in response.json()

    def test_add_male_patient_with_pre_existing_history_and_different_gender_pronouns_success(self):
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 0
        assert not self.fake_pinecone_client.insert_preexisting_history_vectors_invoked
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
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
                "onboarding_first_time_patient": True
            }
        )
        assert response.status_code == 200
        assert self.fake_pinecone_client.insert_preexisting_history_vectors_invoked
        assert "patient_id" in response.json()
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 1

    def test_add_male_patient_with_pre_existing_history_and_not_different_gender_pronouns_success(self):
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 0
        assert not self.fake_pinecone_client.insert_preexisting_history_vectors_invoked
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
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
                "onboarding_first_time_patient": True
            }
        )
        assert response.status_code == 200
        assert self.fake_pinecone_client.insert_preexisting_history_vectors_invoked
        assert "patient_id" in response.json()
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 1

    def test_add_female_patient_with_pre_existing_history_and_different_gender_pronouns_success(self):
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 0
        assert not self.fake_pinecone_client.insert_preexisting_history_vectors_invoked
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
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
                "onboarding_first_time_patient": True
            }
        )
        assert response.status_code == 200
        assert self.fake_pinecone_client.insert_preexisting_history_vectors_invoked
        assert "patient_id" in response.json()
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 1

    def test_add_female_patient_with_pre_existing_history_and_not_different_gender_pronouns_success(self):
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 0
        assert not self.fake_pinecone_client.insert_preexisting_history_vectors_invoked
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
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
                "onboarding_first_time_patient": True
            }
        )
        assert response.status_code == 200
        assert self.fake_pinecone_client.insert_preexisting_history_vectors_invoked
        assert "patient_id" in response.json()
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 1

    def test_update_patient_with_missing_session_token(self):
        response = self.client.put(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
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
            }
        )
        assert response.status_code == 401

    def test_update_patient_with_empty_patient_id(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.put(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
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
            }
        )
        assert response.status_code == 400

    def test_update_patient_with_same_preexisting_history_success(self):
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 0
        assert not self.fake_pinecone_client.update_preexisting_history_vectors_invoked
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.put(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
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
            }
        )
        assert response.status_code == 200
        assert self.fake_pinecone_client.insert_preexisting_history_num_invocations == 0
        assert not self.fake_pinecone_client.update_preexisting_history_vectors_invoked

    def test_update_patient_with_new_preexisting_history_success(self):
        assert self.fake_pinecone_client.update_preexisting_history_num_invocations == 0
        assert not self.fake_pinecone_client.update_preexisting_history_vectors_invoked
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.put(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
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
            }
        )
        assert response.status_code == 200
        assert self.fake_pinecone_client.update_preexisting_history_vectors_invoked
        assert self.fake_pinecone_client.update_preexisting_history_num_invocations == 1

    def test_delete_patient_with_missing_session_token(self):
        response = self.client.delete(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "patient_id": FAKE_PATIENT_ID,
            }
        )
        assert response.status_code == 401

    def test_delete_patient_with_empty_patient_id(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.delete(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "patient_id": "",
            }
        )
        assert response.status_code == 400

    def test_delete_patient_success(self):
        assert not self.fake_pinecone_client.delete_preexisting_history_vectors_invoked
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.delete(
            AssistantRouter.PATIENTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "patient_id": FAKE_PATIENT_ID,
            }
        )
        assert response.status_code == 200
        assert self.fake_pinecone_client.delete_preexisting_history_vectors_invoked

    def test_transform_with_template_with_missing_session_token(self):
        response = self.client.post(
            AssistantRouter.TEMPLATES_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "template": "soap",
                "session_notes_text": "My fake session notes"
            }
        )
        assert response.status_code == 401

    def test_transform_with_template_with_empty_session_notes_text(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.TEMPLATES_ENDPOINT,
            json={
                "template": "soap",
                "session_notes_text": ""
            },
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 400

    def test_transform_with_template_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            AssistantRouter.TEMPLATES_ENDPOINT,
            json={
                "template": "soap",
                "session_notes_text": "My fake session notes"
            },
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 200

    def test_get_attendance_insights_with_missing_session_token(self):
        response = self.client.get(
            AssistantRouter.ATTENDANCE_INSIGHTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "patient_id": FAKE_PATIENT_ID
            }
        )
        assert response.status_code == 401

    def test_get_attendance_insights_with_auth_but_missing_patient_id(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.ATTENDANCE_INSIGHTS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 400

    def test_get_attendance_insights_with_auth_but_invalid_patient_id(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.ATTENDANCE_INSIGHTS_ENDPOINT,
            params={
                "patient_id": ""
            },
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 400

    def test_get_attendance_insights_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.ATTENDANCE_INSIGHTS_ENDPOINT,
            params={
                "patient_id": FAKE_PATIENT_ID
            },
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 200
        assert "attendance_insights_data" in response.json()

    def test_get_briefing_with_missing_session_token(self):
        response = self.client.get(
            AssistantRouter.BRIEFINGS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "patient_id": FAKE_PATIENT_ID
            }
        )
        assert response.status_code == 401

    def test_get_briefing_with_auth_but_missing_patient_id(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.BRIEFINGS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 400

    def test_get_briefing_with_auth_but_invalid_patient_id(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.BRIEFINGS_ENDPOINT,
            params={
                "patient_id": ""
            },
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 400

    def test_get_briefing_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.BRIEFINGS_ENDPOINT,
            params={
                "patient_id": FAKE_PATIENT_ID
            },
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 200
        assert "briefing_data" in response.json()

    def test_get_question_suggestions_with_missing_session_token(self):
        response = self.client.get(
            AssistantRouter.QUESTION_SUGGESTIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "patient_id": FAKE_PATIENT_ID
            }
        )
        assert response.status_code == 401

    def test_get_question_suggestions_with_auth_but_missing_patient_id(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.QUESTION_SUGGESTIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 400

    def test_get_question_suggestions_with_auth_but_invalid_patient_id(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.QUESTION_SUGGESTIONS_ENDPOINT,
            params={
                "patient_id": ""
            },
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 400

    def test_get_question_suggestions_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.QUESTION_SUGGESTIONS_ENDPOINT,
            params={
                "patient_id": FAKE_PATIENT_ID
            },
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 200
        assert "questions" in response.json()

    def test_get_recent_topics_with_missing_session_token(self):
        response = self.client.get(
            AssistantRouter.RECENT_TOPICS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            params={
                "patient_id": FAKE_PATIENT_ID
            }
        )
        assert response.status_code == 401

    def test_get_recent_topics_with_auth_but_missing_patient_id(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.RECENT_TOPICS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 400

    def test_get_recent_topics_with_auth_but_invalid_patient_id(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.RECENT_TOPICS_ENDPOINT,
            params={
                "patient_id": ""
            },
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 400

    def test_get_recent_topics_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.RECENT_TOPICS_ENDPOINT,
            params={
                "patient_id": FAKE_PATIENT_ID
            },
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 200
        assert "topics" in response.json()

    def test_get_greetings_with_auth_token_but_missing_session_token(self):
        response = self.client.get(
            AssistantRouter.GREETINGS_ENDPOINT,
            headers={
                "auth-token": FAKE_ACCESS_TOKEN,
            },
        )
        assert response.status_code == 401

    def test_get_greetings_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.GREETINGS_ENDPOINT,
            headers={
                "auth-token": FAKE_ACCESS_TOKEN,
            },
        )
        assert response.status_code == 200
        response_json = response.json()
        assert response_json["greetings_data"] is not None

    def test_get_ui_strings_with_auth_token_but_missing_session_token(self):
        response = self.client.get(
            AssistantRouter.USER_INTERFACE_STRINGS_ENDPOINT,
            headers={
                "auth-token": FAKE_ACCESS_TOKEN,
            },
            params={
                "ids": ["foo", "bar"]
            }
        )
        assert response.status_code == 401

    def test_get_ui_strings_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            AssistantRouter.USER_INTERFACE_STRINGS_ENDPOINT,
            headers={
                "auth-token": FAKE_ACCESS_TOKEN,
            },
            params={
                "ids": ["foo", "bar"]
            }
        )
        assert response.status_code == 200
        response_json = response.json()
        assert response_json["user_interface_strings_data"] is not None
