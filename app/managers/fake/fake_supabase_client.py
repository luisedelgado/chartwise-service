import json
import requests, requests_mock

from supabase import Client

class FakeAuthWrapper:

    fake_role: str = None
    FAKE_AUTH_TOKEN: str = None
    fake_refresh_token: str = None
    fake_user_id: str = None

    def __init__(self, fake_role, FAKE_AUTH_TOKEN, fake_refresh_token, fake_user_id):
        self.fake_role = fake_role
        self.FAKE_AUTH_TOKEN = FAKE_AUTH_TOKEN
        self.fake_refresh_token = fake_refresh_token
        self.fake_user_id = fake_user_id

    def sign_out(self):
        pass

    def sign_up(self, obj: dict):
        # with requests_mock.Mocker() as mock:
        #     url = 'https://api.example.com/data'
        #     fake_response = {
        #         "user": {
        #             "role": self.fake_role,
        #             "id": self.fake_user_id
        #         },
        #         "session": {
        #             "access_token": self.FAKE_AUTH_TOKEN,
        #             "refresh_token": self.fake_refresh_token
        #         }
        #     }
        #     mock.get(url, json=json.dumps(fake_response))
        #     response = requests.get(url)
        #     return response
        return json.dumps({
                "user": {
                    "role": self.fake_role,
                    "id": self.fake_user_id
                },
                "session": {
                    "access_token": self.FAKE_AUTH_TOKEN,
                    "refresh_token": self.fake_refresh_token
                }
            })

class FakeSupabaseOperationResult:

    def __init__(self, operation_obj = None):
        self._operation_obj = operation_obj

    _operation_obj = None

    def execute(self):
        return FakeSupabaseOperationResult(self._operation_obj)

    def eq(self, left, right):
        self._operation_obj = right
        return FakeSupabaseOperationResult(right)

    def dict(self):
        data = []
        if self._operation_obj is not None:
            data.append(self._operation_obj)
        return {
            "data": data
        }

class FakeSupabaseTable:
    def __init__(self, table_name: str):
        self.table_name = table_name

    def insert(self, obj: dict):
        return FakeSupabaseOperationResult()

    def update(self, obj: dict):
        return FakeSupabaseOperationResult()

    def delete(self):
        return FakeSupabaseOperationResult()

class FakeSupabaseClient(Client):

    fake_role: str = None
    FAKE_AUTH_TOKEN: str = None
    fake_refresh_token: str = None
    fake_user_id: str = None

    def __init__(self):
        pass

    @property
    def auth(self):
        return FakeAuthWrapper(fake_role=self.fake_role,
                               FAKE_AUTH_TOKEN=self.FAKE_AUTH_TOKEN,
                               fake_refresh_token=self.fake_refresh_token,
                               fake_user_id=self.fake_user_id)

    def table(self, table_name):
        return FakeSupabaseTable(table_name)
