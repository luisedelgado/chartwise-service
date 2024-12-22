import os

from supabase import Client

from ...dependencies.api.supabase_base_class import SupabaseBaseClass

class SupabaseClient(SupabaseBaseClass):

    def __init__(self, client: Client):
        self.client = client
        self.environment = os.environ.get("ENVIRONMENT")

    def delete_file(self,
                    source_bucket: str,
                    storage_filepath: str):
        # We don't want to delete files from the bucket in a non-production environment
        if self.environment != "prod":
            return None

        try:
            return self.client.storage.from_(source_bucket).remove([storage_filepath])
        except Exception as e:
            raise Exception(e)

    def download_file(self,
                      source_bucket: str,
                      storage_filepath: str):
        # We don't want to download files from the bucket in a non-production environment
        if self.environment != "prod":
            return None

        try:
            return self.client.storage.from_(source_bucket).download(storage_filepath)
        except Exception as e:
            raise Exception(e)

    def upload_file(self,
                    destination_bucket: str,
                    storage_filepath: str,
                    local_filename: str):
        # We don't want to upload files to the bucket in a non-production environment
        if self.environment != "prod":
            return

        try:
            self.client.storage.from_(destination_bucket).upload(path=storage_filepath,
                                                                 file=local_filename)
        except Exception as e:
            raise Exception(e)

    def move_file_between_buckets(self,
                                  source_bucket: str,
                                  destination_bucket: str,
                                  file_path: str):
        # We don't want to upload files to the bucket in a non-production environment
        if self.environment != "prod":
            return

        try:
            download_response = self.download_file(source_bucket=source_bucket,
                                                   storage_filepath=file_path)

            self.upload_file(destination_bucket=destination_bucket,
                             storage_filepath=file_path,
                             local_filename=download_response.content)

            self.delete_file(source_bucket=source_bucket,
                             storage_filepath=file_path)
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
                                       batch_start: int,
                                       batch_end: int,
                                       non_null_column: str = None,
                                       order_ascending_column: str = None):
        try:
            select_operation = self.client.table(table_name).select(fields).range(batch_start, batch_end)

            if non_null_column is not None:
                select_operation = select_operation.not_.is_(non_null_column, "null")

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
