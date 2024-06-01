import os

from fastapi.testclient import TestClient

from .. import main

client = TestClient(main.app)
token = "Bearer " + client.post("/v1/token",
                                data={"username": "testonly",
                                      "password": os.getenv("FASTAPI_ENDPOINTS_TEST_PSWD")}).json()['access_token']

def test_invoke_endpoint_without_auth_token():
    response = client.post("/v1/sessions", json={})
    assert response.status_code == 401

def test_auth_token_endpoint():
    response = client.post("/v1/token", data={"username": "testonly",
                                              "password": os.getenv("FASTAPI_ENDPOINTS_TEST_PSWD")})
    assert response.status_code == 200

    local_token: str = response.json()['access_token']
    assert len(local_token) > 0

def test_upload_session_endpoint_with_missing_tokens():
    response = client.post("/v1/sessions",
                           headers={"Authorization": token},
                           json=__get_session_upload_payload("", ""))
    assert response.status_code == 400

def test_upload_session_endpoint_with_invalid_tokens():
    response = client.post("/v1/sessions",
                           headers={"Authorization": token},
                           json=__get_session_upload_payload("123", "123"))
    assert response.status_code == 400

def test_assistant_query_invalid_response_language_code():
    response = client.post("/v1/assistant-queries",
                           headers={"Authorization": token},
                           json=__get_assistant_queries_payload("123",
                                                                "123",
                                                                "kjhbvbkub"))
    assert response.status_code == 400

# Helper methods

def __get_session_upload_payload(access_token, refresh_token):
    return {
    "patient_id": "126b4c15-2301-48f4-9674-75ec9f1e707a",
    "therapist_id": "1e19ead4-8b30-4be8-898c-7b4356743a1b",
    "text": "The sky is blue today",
    "date": "05/30/2024",
    "supabase_access_token": access_token,
    "supabase_refresh_token": refresh_token
    }

def __get_assistant_queries_payload(access_token, refresh_token, language_code):
    return {
    "patient_id": "126b4c15-2301-48f4-9674-75ec9f1e707a",
    "therapist_id": "1e19ead4-8b30-4be8-898c-7b4356743a1b",
    "text": "What color is the sky today?",
    "response_language_code": language_code,
    "supabase_access_token": access_token,
    "supabase_refresh_token": refresh_token
    }