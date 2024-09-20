from supabase import Client

from ...dependencies.api.supabase_base_class import SupabaseBaseClass

class SupabaseClient(SupabaseBaseClass):

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
               table_name: str,
               limit: int = None,
               order_desc_column: str = None):
        try:
            select_operation = self.client.from_(table_name).select(fields)

            for key, value in filters.items():
                select_operation = select_operation.eq(f"{key}", f"{value}")

            if limit is not None:
                select_operation.limit(limit)

            if len(order_desc_column or '') > 0:
                select_operation = select_operation.order(order_desc_column, desc=True)

            return select_operation.execute()
        except Exception as e:
            raise Exception(e)

    def select_either_or_from_column(self,
                                     fields: str,
                                     possible_values: list,
                                     table_name: str,
                                     order_desc_column: str = None):
        try:
            select_operation = self.client.from_(table_name).select(fields)

            or_clause = ",".join(f"id.eq.{value}" for value in possible_values)
            select_operation = select_operation.or_(or_clause)

            if len(order_desc_column or '') > 0:
                select_operation = select_operation.order(order_desc_column, desc=True)

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

    def get_user(self):
        try:
            return self.client.auth.get_user()
        except Exception as e:
            raise Exception(e)

    def get_current_user_id(self) -> str:
        try:
            user_id = self.client.auth.get_user().dict()['user']['id']
            assert len(user_id or '') > 0, "Did not find a valid user id for current user"
            return user_id
        except Exception as e:
            raise Exception(e)

    def refresh_session(self):
        try:
            return self.client.auth.refresh_session()
        except Exception as e:
            raise Exception(e)

    def sign_out(self):
        try:
            self.client.auth.sign_out()
        except Exception as e:
            raise Exception(e)

    def sign_in(self, email: str, password: str) -> dict:
        try:
            res_dict = self.client.auth.sign_in_with_password({"email": email, "password": password}).dict()
            assert "user" in res_dict, "Failed to authenticate user"
            return res_dict['user']['id']
        except Exception as e:
            raise Exception(e)
