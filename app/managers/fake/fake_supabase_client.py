import json
import requests, requests_mock

from supabase import Client

class FakeAuthWrapper:

    fake_role: str = None
    fake_access_token: str = None
    fake_refresh_token: str = None
    fake_user_id: str = None

    def __init__(self, fake_role, fake_access_token, fake_refresh_token, fake_user_id):
        self.fake_role = fake_role
        self.fake_access_token = fake_access_token
        self.fake_refresh_token = fake_refresh_token
        self.fake_user_id = fake_user_id

    def sign_up(self, obj: dict):
        with requests_mock.Mocker() as mock:
            url = 'https://api.example.com/data'
            fake_response = {
                "user": {
                    "role": self.fake_role,
                    "id": self.fake_user_id
                },
                "session": {
                    "access_token": self.fake_access_token,
                    "refresh_token": self.fake_refresh_token
                }
            }
            mock.get(url, json=json.dumps(fake_response))
            response = requests.get(url)
            return response

class FakeSupabasesInsertResult:
    def execute(self):
        pass

class FakeSupabaseTable:
    def __init__(self, table_name: str):
        self.table_name = table_name

    def insert(self, obj: dict):
        return FakeSupabasesInsertResult()

class FakeSupabaseClient(Client):

    fake_role: str = None
    fake_access_token: str = None
    fake_refresh_token: str = None
    fake_user_id: str = None

    def __init__(self):
        pass

    @property
    def auth(self):
        return FakeAuthWrapper(fake_role=self.fake_role,
                               fake_access_token=self.fake_access_token,
                               fake_refresh_token=self.fake_refresh_token,
                               fake_user_id=self.fake_user_id)

    def table(self, table_name):
        return FakeSupabaseTable(table_name)
