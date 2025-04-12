import json

from fastapi import Request
from typing import Any, List, Optional

from ..api.aws_db_base_class import AwsDbBaseClass
from ...internal.db.connection import get_conn
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
from ...internal.security.chartwise_encryptor import ChartWiseEncryptor

class AwsDbClient(AwsDbBaseClass):

    def __init__(self,
                 encryptor: ChartWiseEncryptor,
                 is_admin: bool = False):
        self.is_admin = is_admin
        self.encryptor = encryptor

    async def insert(self,
                     user_id: str,
                     request: Request,
                     payload: dict[str, Any],
                     table_name: str) -> Optional[dict]:
        try:
            # Set the current user ID for satisfying RLS.
            self.set_session_user_id(
                request=request,
                user_id=user_id
            )

            payload = self.encrypt_payload(payload, table_name)
            columns = list(payload.keys())
            values = list(payload.values())
            placeholders = ', '.join([f"${i+1}" for i in range(len(values))])
            column_names = ', '.join([f'"{col}"' for col in columns])

            insert_statement = (
                f"""
                INSERT INTO "{table_name}" ({column_names})
                VALUES ({placeholders})
                RETURNING *
                """
            )
            async with (await get_conn(request.app)) as conn:
                row = await conn.fetchrow(insert_statement, *values)
                return dict(row) if row else None
        except Exception as e:
            raise RuntimeError(f"Insert failed: {e}") from e

    async def upsert(self,
                     user_id: str,
                     request: Request,
                     conflict_columns: List[str],
                     payload: dict[str, Any],
                     table_name: str) -> Optional[dict]:
        try:
            # Set the current user ID for satisfying RLS.
            self.set_session_user_id(
                request=request,
                user_id=user_id
            )

            payload = self.encrypt_payload(payload, table_name)
            columns = list(payload.keys())
            values = list(payload.values())
            placeholders = ', '.join([f"${i+1}" for i in range(len(values))])
            column_names = ', '.join([f'"{col}"' for col in columns])

            conflict_clause = ', '.join([f'"{col}"' for col in conflict_columns])
            on_conflict_columns_to_update = [col for col in columns if col not in conflict_columns]
            update_expr = ', '.join([
                f'"{col}" = EXCLUDED."{col}"' for col in on_conflict_columns_to_update
            ])

            upsert_query = (
                f"""
                INSERT INTO "{table_name}" ({column_names})
                VALUES ({placeholders})
                ON CONFLICT ({conflict_clause})
                DO UPDATE SET {update_expr}
                RETURNING *
                """
            )

            async with (await get_conn(request.app)) as conn:
                row = await conn.fetchrow(upsert_query, *values)
                return dict(row) if row else None
        except Exception as e:
            raise RuntimeError(f"Upsert failed: {e}") from e

    async def update(self,
                     user_id: str,
                     request: Request,
                     payload: dict[str, Any],
                     filters: dict[str, Any],
                     table_name: str) -> Optional[dict]:
        try:
            # Set the current user ID for satisfying RLS.
            self.set_session_user_id(
                request=request,
                user_id=user_id
            )

            payload = self.encrypt_payload(payload, table_name)

            set_columns = list(payload.keys())
            set_values = list(payload.values())

            where_columns = list(filters.keys())
            where_values = list(filters.values())

            set_expr = ', '.join([
                f'"{col}" = ${i+1}' for i, col in enumerate(set_columns)
            ])

            where_expr = ' AND '.join([
                f'"{col}" = ${len(set_values) + i + 1}' for i, col in enumerate(where_columns)
            ])

            update_query = (
                f"""
                UPDATE "{table_name}"
                SET {set_expr}
                WHERE {where_expr}
                RETURNING *
                """
            )

            all_values = set_values + where_values

            async with (await get_conn(request.app)) as conn:
                row = await conn.fetchrow(update_query, *all_values)
                return dict(row) if row else None
        except Exception as e:
            raise Exception(e)

    async def select(self,
                     user_id: str,
                     request: Request,
                     fields: list[str],
                     filters: dict[str, Any],
                     table_name: str,
                     limit: Optional[int] = None,
                     order_by: Optional[tuple[str, str]] = None) -> list[dict]:
        try:
            # Set the current user ID for satisfying RLS.
            self.set_session_user_id(
                request=request,
                user_id=user_id
            )

            where_clause, where_values = self.build_where_clause(filters)
            field_expr = ', '.join([f'"{field}"' for field in fields])
            limit_clause = f"LIMIT {limit}" if limit is not None else ""
            order_clause = ""
            if order_by:
                col, direction = order_by
                direction = direction.upper()
                if direction not in {"ASC", "DESC"}:
                    raise ValueError(f"Invalid order direction: {direction}")
                order_clause = f'ORDER BY "{col}" {direction}'

            select_query = (
                f"""
                SELECT {field_expr} FROM "{table_name}"
                {where_clause}
                {order_clause}
                {limit_clause}
                """
            )
            select_query = " ".join(select_query.split())

            async with (await get_conn(request.app)) as conn:
                rows = await conn.fetch(select_query, *where_values)
                return [dict(row) for row in rows]

        except Exception as e:
            raise RuntimeError(f"Select failed: {e}") from e

    async def delete(self,
                     user_id: str,
                     request: Request,
                     table_name: str,
                     filters: dict[str, Any]) -> list[dict]:
        try:
            # Set the current user ID for satisfying RLS.
            self.set_session_user_id(
                request=request,
                user_id=user_id
            )

            where_clause, where_values = self.build_where_clause(filters)
            delete_query = (
                f"""
                DELETE FROM "{table_name}"
                {where_clause}
                RETURNING *
                """
            )
            delete_query = " ".join(delete_query.split())

            async with (await get_conn(request.app)) as conn:
                rows = await conn.fetch(delete_query, *where_values)
                return [dict(row) for row in rows]
        except Exception as e:
            raise RuntimeError(f"Delete failed: {e}") from e

    async def get_user(self):
        # # Set the current user ID for satisfying RLS.
        # self.set_session_user_id(
        #     request=request,
        #     user_id=user_id
        # )
        pass

    async def get_current_user_id(self) -> str:
        # # Set the current user ID for satisfying RLS.
        # self.set_session_user_id(
        #     request=request,
        #     user_id=user_id
        # )
        pass

    async def delete_user(self,
                          request: Request,
                          user_id: str):
        # # Set the current user ID for satisfying RLS.
        # self.set_session_user_id(
        #     request=request,
        #     user_id=user_id
        # )
        pass

    async def sign_out(self):
        # # Set the current user ID for satisfying RLS.
        # self.set_session_user_id(
        #     request=request,
        #     user_id=user_id
        # )
        pass

    async def set_session_user_id(self, request: Request, user_id: str):
        try:
            async with (await get_conn(request.app)) as conn:
                await conn.execute(
                    "SET app.current_user_id = $1", user_id
                )
        except Exception as e:
            raise RuntimeError(f"Failed to set session user ID: {e}") from e

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

    @staticmethod
    def build_where_clause(filters: dict[str, Any]) -> tuple[str, list[Any]]:
        operator_map = {
            "gte": ">=",
            "lte": "<=",
            "gt": ">",
            "lt": "<",
            "ne": "!=",
            "eq": "="
        }

        conditions = []
        values = []
        param_index = 1

        for key, val in filters.items():
            if "__" in key:
                col, op = key.split("__", 1)

                if op == "isnull":
                    if val is True:
                        conditions.append(f'"{col}" IS NULL')
                    elif val is False:
                        conditions.append(f'"{col}" IS NOT NULL')
                    else:
                        raise ValueError(f'"{key}" must be True or False for __isnull filter')
                elif op == "isnot":
                    conditions.append(f'"{col}" IS NOT ${param_index}')
                    values.append(val)
                    param_index += 1
                else:
                    sql_op = operator_map.get(op)
                    if not sql_op:
                        raise ValueError(f"Unsupported filter operator: {op}")
                    conditions.append(f'"{col}" {sql_op} ${param_index}')
                    values.append(val)
                    param_index += 1
            elif isinstance(val, list):
                placeholders = ', '.join([f"${param_index + i}" for i in range(len(val))])
                conditions.append(f'"{key}" IN ({placeholders})')
                values.extend(val)
                param_index += len(val)
            else:
                conditions.append(f'"{key}" = ${param_index}')
                values.append(val)
                param_index += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return where_clause, values
