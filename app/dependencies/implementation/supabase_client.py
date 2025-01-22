import os

from supabase import Client

from ..api.supabase_storage_base_class import SupabaseStorageBaseClass
from ...dependencies.api.supabase_base_class import SupabaseBaseClass

class SupabaseClient(SupabaseBaseClass):

    def __init__(self,
                 client: Client,
                 storage_client: SupabaseStorageBaseClass,
                 is_admin: bool = False):
        self.client = client
        self.is_admin = is_admin
        self.storage_client = storage_client

    def delete_user(self, user_id: str):
        if not self.is_admin:
            raise Exception("User is not an admin, cannot delete user")

        try:
            return self.client.auth.admin.delete_user(user_id)
        except Exception as e:
            raise Exception(e)

    def insert(self,
               payload: dict,
               table_name: str):
        try:
            return self.client.table(table_name).insert(payload).execute()
        except Exception as e:
            raise Exception(e)

    def upsert(self,
               payload: dict,
               on_conflict: str,
               table_name: str):
        try:
            return self.client.table(table_name).upsert(json=payload, on_conflict=on_conflict).execute()
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

    def select_within_range(self,
                            fields: str,
                            filters: dict,
                            table_name: str,
                            range_start: str,
                            range_end: str,
                            column_marker: str,
                            limit: int = None):
        try:
            select_operation = self.client.table(table_name).select(fields).gt(column_marker, range_start).lt(column_marker, range_end)

            for key, value in filters.items():
                select_operation = select_operation.eq(f"{key}", f"{value}")

            if limit is not None:
                select_operation.limit(limit)

            return select_operation.execute()
        except Exception as e:
            raise Exception(e)

    def select_batch_where_is_not_null(self,
                                       table_name: str,
                                       fields: str,
                                       non_null_column: str,
                                       limit: int = None,
                                       order_ascending_column: str = None):
        try:
            select_operation = self.client.table(table_name).select(fields).not_.is_(non_null_column, "null")

            if limit is not None:
                select_operation.limit(limit)

            if order_ascending_column:
                select_operation = select_operation.order(order_ascending_column, desc=False)

            return select_operation.execute()
        except Exception as e:
            raise Exception(e)

    def select_batch_where_is_null(self,
                                   table_name: str,
                                   fields: str,
                                   null_column: str,
                                   limit: int = None,
                                   order_ascending_column: str = None):
        try:
            select_operation = self.client.table(table_name).select(fields).is_(null_column, "null")

            if limit is not None:
                select_operation.limit(limit)

            if order_ascending_column:
                select_operation = select_operation.order(order_ascending_column, desc=False)

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

    def delete_where_is_not(self,
                            is_not_filters: dict,
                            table_name: str):
        try:
            delete_operation = self.client.table(table_name).delete()

            for key, value in is_not_filters.items():
                delete_operation = delete_operation.neq(f"{key}", f"{value}")

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
            user_id = self.client.auth.get_user().model_dump()['user']['id']
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
