from ...api.supabase_base_class import SupabaseBaseClass

class FakeSupabaseManager(SupabaseBaseClass):

    def insert(self,
               payload: dict,
               table_name: str):
        pass

    def update(self,
               payload: dict,
               filters: dict,
               table_name: str):
        pass

    def select(self,
               fields: str,
               filters: dict,
               table_name: str):
        pass

    def delete(self,
               filters: dict,
               table_name: str):
        pass

    def refresh_session(self):
        pass
