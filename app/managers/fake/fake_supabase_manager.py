from ...api.supabase_base_class import SupabaseBaseClass
from .fake_supabase_session import FakeSession

class FakeSupabaseManager(SupabaseBaseClass):

    return_authenticated_session: bool = False
    fake_access_token: str = None
    fake_refresh_token: str = None
    fake_insert_text: str = None
    select_returns_data: bool = False

    def insert(self,
               payload: dict,
               table_name: str):
        self.fake_insert_text = None if "notes_text" not in payload else payload["notes_text"]

    def update(self,
               payload: dict,
               filters: dict,
               table_name: str):
        pass

    def select(self,
               fields: str,
               filters: dict,
               table_name: str):
        if not self.select_returns_data:
            return {"data": []}

        if table_name == "therapists":
            return {"data": [{
                "language_preference": "en-US"
            }]}
        if table_name == "patients":
            return {"data": ["fake_data"]}
        if table_name == "session_reports":
            return {"data": ["fake_data"]}

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
