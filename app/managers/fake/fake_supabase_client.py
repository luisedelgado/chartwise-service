from supabase import Client
from supabase.lib.client_options import ClientOptions

class FakeSupabasesInsertResult:
    def execute(self):
        pass

class FakeSupabaseTable:
    def __init__(self, table_name: str):
        self.table_name = table_name

    def insert(self, obj: dict):
        return FakeSupabasesInsertResult()

class FakeSupabaseClient(Client):
    
    def __init__(self):
        pass

    def table(self, table_name):
        return FakeSupabaseTable(table_name)
