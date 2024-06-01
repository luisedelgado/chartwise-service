from fastapi.testclient import TestClient

from .. import main

client = TestClient(main.app)
token = client.post("/v1/token", data={"username": "testonly",
                                       "password": "thisismytestpassword"}).json()['access_token']

def test_invoke_endpoint_without_auth_token():
    response = client.post("/v1/sessions", json={})
    assert response.status_code == 401

def test_auth_token_endpoint():
    response = client.post("/v1/token", data={"username": "testonly",
                                              "password": "thisismytestpassword"})
    assert response.status_code == 200

    local_token: str = response.json()['access_token']
    assert len(local_token) > 0

def test_upload_session_endpoint_with_missing_tokens():
    bearer_token_header = "Bearer " + token
    response = client.post("/v1/sessions",
                           headers={"Authorization": bearer_token_header},
                           json=__get_session_upload_payload("", ""))
    assert response.status_code == 400

def test_upload_session_endpoint_with_invalid_tokens():
    bearer_token_header = "Bearer " + token
    response = client.post("/v1/sessions",
                           headers={"Authorization": bearer_token_header},
                           json=__get_session_upload_payload("123", "123"))
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
