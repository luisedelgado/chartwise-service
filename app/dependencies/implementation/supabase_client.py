import base64
import json

from supabase import Client

from ..api.supabase_storage_base_class import SupabaseStorageBaseClass
from ...dependencies.api.supabase_base_class import SupabaseBaseClass
from ...internal.security import ChartWiseEncryptor
from ...internal.schemas import (ENCRYPTED_PATIENT_ATTENDANCE_TABLE_NAME,
                                 ENCRYPTED_PATIENT_BRIEFINGS_TABLE_NAME,
                                 ENCRYPTED_PATIENT_QUESTION_SUGGESTIONS_TABLE_NAME,
                                 ENCRYPTED_PATIENT_TOPICS_TABLE_NAME,
                                 ENCRYPTED_PATIENTS_TABLE_NAME,
                                 ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
                                 ENCRYPTED_TABLES,
                                 IS_JSON_KEY,
                                 PATIENT_ATTENDANCE_ENCRYPTED_COLUMNS,
                                 PATIENT_BRIEFINGS_ENCRYPTED_COLUMNS,
                                 PATIENT_QUESTION_SUGGESTIONS_ENCRYPTED_COLUMNS,
                                 PATIENT_TOPICS_ENCRYPTED_COLUMNS,
                                 PATIENTS_ENCRYPTED_COLUMNS,
                                 SESSION_REPORTS_ENCRYPTED_COLUMNS)

class SupabaseClient(SupabaseBaseClass):

    def __init__(self,
                 client: Client,
                 storage_client: SupabaseStorageBaseClass,
                 is_admin: bool = False):
        self.client = client
        self.is_admin = is_admin
        self.storage_client = storage_client
        self.encryptor = ChartWiseEncryptor()

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
            payload = self.encrypt_payload(payload, table_name)
            return self.client.table(table_name).insert(payload).execute().model_dump()
        except Exception as e:
            raise Exception(e)

    def upsert(self,
               payload: dict,
               on_conflict: str,
               table_name: str):
        try:
            payload = self.encrypt_payload(payload, table_name)
            return self.client.table(table_name).upsert(json=payload, on_conflict=on_conflict).execute().model_dump()
        except Exception as e:
            raise Exception(e)

    def update(self,
               payload: dict,
               filters: dict,
               table_name: str):
        try:
            payload = self.encrypt_payload(payload, table_name)
            update_operation = self.client.table(table_name).update(payload)

            for key, value in filters.items():
                update_operation = update_operation.eq(f"{key}", f"{value}")

            return update_operation.execute().model_dump()
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

            response = select_operation.execute().model_dump()
            if table_name not in ENCRYPTED_TABLES or (0 == len(response['data'])):
                # Return response untouched if no need for decryption, or if no data was returned
                return response

            response_data = response['data']
            for index in range(0, len(response_data)):
                response_data[index] = self.decrypt_payload(response_data[index], table_name)

            return response
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

            return select_operation.execute().model_dump()
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

            return select_operation.execute().model_dump()
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

            return select_operation.execute().model_dump()
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

            return select_operation.execute().model_dump()
        except Exception as e:
            raise Exception(e)

    def delete(self,
               filters: dict,
               table_name: str):
        try:
            delete_operation = self.client.table(table_name).delete()

            for key, value in filters.items():
                delete_operation = delete_operation.eq(f"{key}", f"{value}")

            return delete_operation.execute().model_dump()
        except Exception as e:
            raise Exception(e)

    def delete_where_is_not(self,
                            is_not_filters: dict,
                            table_name: str):
        try:
            delete_operation = self.client.table(table_name).delete()

            for key, value in is_not_filters.items():
                delete_operation = delete_operation.neq(f"{key}", f"{value}")

            return delete_operation.execute().model_dump()
        except Exception as e:
            raise Exception(e)

    def get_user(self):
        try:
            return self.client.auth.get_user().model_dump()
        except Exception as e:
            raise Exception(e)

    def get_current_user_id(self) -> str:
        try:
            user_id = self.client.auth.get_user().model_dump()['user']['id']
            assert len(user_id or '') > 0, "Did not find a valid user id for current user"
            return user_id
        except Exception as e:
            raise Exception(e)

    def sign_out(self):
        try:
            self.client.auth.sign_out()
        except Exception as e:
            raise Exception(e)

    # Private

    def encrypt_payload(self, payload: dict, table_name: str) -> dict:
        if table_name not in ENCRYPTED_TABLES:
            # Return payload untouched if no need for encryption
            return payload

        if table_name == ENCRYPTED_PATIENTS_TABLE_NAME:
            for key, value in payload.items():
                if key in PATIENTS_ENCRYPTED_COLUMNS:
                    payload[key] = self.encryptor.encrypt(value)
            return payload

        if table_name == ENCRYPTED_SESSION_REPORTS_TABLE_NAME:
            for key, value in payload.items():
                if key in SESSION_REPORTS_ENCRYPTED_COLUMNS:
                    value_to_encrypt = value if not SESSION_REPORTS_ENCRYPTED_COLUMNS[key][IS_JSON_KEY] else json.dumps(value)
                    payload[key] = self.encryptor.encrypt(value_to_encrypt)
            return payload

        if table_name == ENCRYPTED_PATIENT_ATTENDANCE_TABLE_NAME:
            for key, value in payload.items():
                if key in PATIENT_ATTENDANCE_ENCRYPTED_COLUMNS:
                    payload[key] = self.encryptor.encrypt(value)
            return payload

        if table_name == ENCRYPTED_PATIENT_BRIEFINGS_TABLE_NAME:
            for key, value in payload.items():
                if key in PATIENT_BRIEFINGS_ENCRYPTED_COLUMNS:
                    payload[key] = self.encryptor.encrypt(value)
            return payload

        if table_name == ENCRYPTED_PATIENT_QUESTION_SUGGESTIONS_TABLE_NAME:
            for key, value in payload.items():
                if key in PATIENT_QUESTION_SUGGESTIONS_ENCRYPTED_COLUMNS:
                    value_to_encrypt = value if not PATIENT_QUESTION_SUGGESTIONS_ENCRYPTED_COLUMNS[key][IS_JSON_KEY] else json.dumps(value)
                    payload[key] = self.encryptor.encrypt(value_to_encrypt)
            return payload

        if table_name == ENCRYPTED_PATIENT_TOPICS_TABLE_NAME:
            for key, value in payload.items():
                if key in PATIENT_TOPICS_ENCRYPTED_COLUMNS:
                    value_to_encrypt = value if not PATIENT_TOPICS_ENCRYPTED_COLUMNS[key][IS_JSON_KEY] else json.dumps(value)
                    payload[key] = self.encryptor.encrypt(value_to_encrypt)
            return payload

        raise Exception(f"Attempted to encrypt values for table {table_name}, which is not tracked.")

    def decrypt_payload(self, payload: dict, table_name: str) -> dict:
        if table_name not in ENCRYPTED_TABLES:
            # Return payload untouched if no need for decryption
            return payload

        if table_name == ENCRYPTED_PATIENTS_TABLE_NAME:
            for key, value in payload.items():
                if key in PATIENTS_ENCRYPTED_COLUMNS:
                    if value is None:
                        continue

                    # Supabase returns BYTEA as hex-encoded base64 strings prefixed with "\\x"
                    if value.startswith("\\x") or value.startswith("0x"):
                        # Decode hex to get raw base64 bytes (which represent the actual ciphertext)
                        b64_encoded_ciphertext_bytes = bytes.fromhex(value[2:])
                    else:
                        # If already a base64 string, encode to bytes if needed
                        b64_encoded_ciphertext_bytes = value.encode("utf-8") if isinstance(value, str) else value
                    payload[key] = self.encryptor.decrypt_b64_encoded_ciphertext(b64_encoded_ciphertext_bytes)
            return payload

        if table_name == ENCRYPTED_SESSION_REPORTS_TABLE_NAME:
            for key, value in payload.items():
                if key in SESSION_REPORTS_ENCRYPTED_COLUMNS:
                    if value is None:
                        continue

                    # Supabase returns BYTEA as hex-encoded base64 strings prefixed with "\\x"
                    if value.startswith("\\x") or value.startswith("0x"):
                        # Decode hex to get raw base64 bytes (which represent the actual ciphertext)
                        b64_encoded_ciphertext_bytes = bytes.fromhex(value[2:])
                    else:
                        # If already a base64 string, encode to bytes if needed
                        b64_encoded_ciphertext_bytes = value.encode("utf-8") if isinstance(value, str) else value
                    decrypted_value = self.encryptor.decrypt_b64_encoded_ciphertext(b64_encoded_ciphertext_bytes)
                    payload[key] = decrypted_value if not SESSION_REPORTS_ENCRYPTED_COLUMNS[key][IS_JSON_KEY] else json.loads(decrypted_value)
            return payload

        if table_name == ENCRYPTED_PATIENT_ATTENDANCE_TABLE_NAME:
            for key, value in payload.items():
                if key in PATIENT_ATTENDANCE_ENCRYPTED_COLUMNS:
                    if value is None:
                        continue

                    # Supabase returns BYTEA as hex-encoded base64 strings prefixed with "\\x"
                    if value.startswith("\\x") or value.startswith("0x"):
                        # Decode hex to get raw base64 bytes (which represent the actual ciphertext)
                        b64_encoded_ciphertext_bytes = bytes.fromhex(value[2:])
                    else:
                        # If already a base64 string, encode to bytes if needed
                        b64_encoded_ciphertext_bytes = value.encode("utf-8") if isinstance(value, str) else value
                    payload[key] = self.encryptor.decrypt_b64_encoded_ciphertext(b64_encoded_ciphertext_bytes)
            return payload

        if table_name == ENCRYPTED_PATIENT_BRIEFINGS_TABLE_NAME:
            for key, value in payload.items():
                if key in PATIENT_BRIEFINGS_ENCRYPTED_COLUMNS:
                    if value is None:
                        continue

                    # Supabase returns BYTEA as hex-encoded base64 strings prefixed with "\\x"
                    if value.startswith("\\x") or value.startswith("0x"):
                        # Decode hex to get raw base64 bytes (which represent the actual ciphertext)
                        b64_encoded_ciphertext_bytes = bytes.fromhex(value[2:])
                    else:
                        # If already a base64 string, encode to bytes if needed
                        b64_encoded_ciphertext_bytes = value.encode("utf-8") if isinstance(value, str) else value
                    payload[key] = self.encryptor.decrypt_b64_encoded_ciphertext(b64_encoded_ciphertext_bytes)
            return payload

        if table_name == ENCRYPTED_PATIENT_QUESTION_SUGGESTIONS_TABLE_NAME:
            for key, value in payload.items():
                if key in PATIENT_QUESTION_SUGGESTIONS_ENCRYPTED_COLUMNS:
                    if value is None:
                        continue

                    # Supabase returns BYTEA as hex-encoded base64 strings prefixed with "\\x"
                    if value.startswith("\\x") or value.startswith("0x"):
                        # Decode hex to get raw base64 bytes (which represent the actual ciphertext)
                        b64_encoded_ciphertext_bytes = bytes.fromhex(value[2:])
                    else:
                        # If already a base64 string, encode to bytes if needed
                        b64_encoded_ciphertext_bytes = value.encode("utf-8") if isinstance(value, str) else value
                    decrypted_value = self.encryptor.decrypt_b64_encoded_ciphertext(b64_encoded_ciphertext_bytes)
                    payload[key] = decrypted_value if not PATIENT_QUESTION_SUGGESTIONS_ENCRYPTED_COLUMNS[key][IS_JSON_KEY] else json.loads(decrypted_value)
            return payload

        if table_name == ENCRYPTED_PATIENT_TOPICS_TABLE_NAME:
            for key, value in payload.items():
                if key in PATIENT_TOPICS_ENCRYPTED_COLUMNS:
                    if value is None:
                        continue

                    # Supabase returns BYTEA as hex-encoded base64 strings prefixed with "\\x"
                    if value.startswith("\\x") or value.startswith("0x"):
                        # Decode hex to get raw base64 bytes (which represent the actual ciphertext)
                        b64_encoded_ciphertext_bytes = bytes.fromhex(value[2:])
                    else:
                        # If already a base64 string, encode to bytes if needed
                        b64_encoded_ciphertext_bytes = value.encode("utf-8") if isinstance(value, str) else value
                    decrypted_value = self.encryptor.decrypt_b64_encoded_ciphertext(b64_encoded_ciphertext_bytes)
                    payload[key] = decrypted_value if not PATIENT_TOPICS_ENCRYPTED_COLUMNS[key][IS_JSON_KEY] else json.loads(decrypted_value)
            return payload

        raise Exception(f"Attempted to decrypt values for table {table_name}, which is not tracked.")
