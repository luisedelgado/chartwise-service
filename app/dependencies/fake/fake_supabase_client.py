from pydantic import BaseModel

from .fake_supabase_session import FakeSession
from ...dependencies.api.supabase_base_class import SupabaseBaseClass

FAKE_SESSION_NOTES_ID = "c8d981a1-b751-4d2e-8dd7-c6c873f41f40"

class ResultQuery(BaseModel):
    data: list

class FakeSupabaseClient(SupabaseBaseClass):

    return_authenticated_session: bool = False
    fake_access_token: str = None
    fake_refresh_token: str = None
    fake_insert_text: str = None
    select_returns_data: bool = False

    def insert(self,
               payload: dict,
               table_name: str):
        self.fake_insert_text = None if "notes_text" not in payload else payload["notes_text"]
        return ResultQuery(data=[{
                "id": FAKE_SESSION_NOTES_ID
            }])

    def update(self,
               payload: dict,
               filters: dict,
               table_name: str):
        pass

    def select(self,
               fields: str,
               filters: dict,
               table_name: str,
               order_desc_column: str = None):
        if not self.select_returns_data:
            return ResultQuery(data=[])

        if table_name == "therapists":
            return ResultQuery(data=[{
                "language_preference": "en-US"
            }])
        if table_name == "patients":
            return ResultQuery(data=[{
                "last_session_date":"2000-01-01",
                "total_sessions": 2
            }])
        if table_name == "session_reports":
            return ResultQuery(data=["fake_data"])

        raise Exception("Untracked table name")

    def delete(self,
               filters: dict,
               table_name: str):
        pass

    def get_user(self):
        pass

    def refresh_session(self):
        return FakeSession(return_authenticated_session=self.return_authenticated_session,
                           fake_access_token=self.fake_access_token,
                           fake_refresh_token=self.fake_refresh_token)

    def sign_out(self):
        pass
