from supabase import Client

from ...api.supabase_base_class import SupabaseBaseClass

class SupabaseManager(SupabaseBaseClass):

    def __init__(self, client: Client):
        self.client = client

    def insert(self,
               payload: dict,
               table_name: str):
        try:
            return self.client.table(table_name).insert(payload).execute()
        except Exception as e:
            raise Exception(e)

    def update(self,
               payload: dict,
               filters: dict,
               table_name: str):
        try:
            update_operation = self.client.table(table_name).update(payload)

            for key, value in filters.items():
                update_operation = update_operation.eq(f"{key}", f"{value}")

            return update_operation.execute()
        except Exception as e:
            raise Exception(e)

    def select(self,
               fields: str,
               filters: dict,
               table_name: str):
        try:
            select_operation = self.client.from_(table_name).select(fields)

            for key, value in filters.items():
                select_operation = select_operation.eq(f"{key}", f"{value}")

            return select_operation.execute()
        except Exception as e:
            raise Exception(e)

    def delete(self,
               filters: dict,
               table_name: str):
        try:
            delete_operation = self.client.table(table_name).delete()

            for key, value in filters.items():
                delete_operation = delete_operation.eq(f"{key}", f"{value}")

            return delete_operation.execute()
        except Exception as e:
            raise Exception(e)

    def refresh_session(self):
        try:
            return self.client.auth.refresh_session()
        except Exception as e:
            raise Exception(e)
