import asyncpg
import json
import os
import uuid

from fastapi import Request
from typing import (
    Any,
    Awaitable,
    Callable,
    List,
    Optional
)

from ..api.aws_db_base_class import AwsDbBaseClass
from ..api.aws_secret_manager_base_class import AwsSecretManagerBaseClass
from ..api.resend_base_class import ResendBaseClass
from ...internal.schemas import (
    ENCRYPTED_PATIENT_ATTENDANCE_TABLE_NAME,
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
    SESSION_REPORTS_ENCRYPTED_COLUMNS,
    STAGING_ENVIRONMENT,
    PROD_ENVIRONMENT
)
from ...internal.security.chartwise_encryptor import ChartWiseEncryptor

class AwsDbClient(AwsDbBaseClass):

    def __init__(
        self,
        encryptor: ChartWiseEncryptor
    ):
        self.encryptor = encryptor

    async def insert(
        self,
        user_id: str,
        request: Request,
        payload: dict[str, Any],
        table_name: str
    ) -> Optional[dict]:
        try:
            payload = self._encrypt_payload(payload, table_name)
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

            async with request.app.state.pool.acquire() as conn:
                # Set the current user ID for satisfying RLS.
                await self.set_session_user_id(
                    conn=conn,
                    user_id=user_id
                )
                row = await conn.fetchrow(
                    insert_statement,
                    *values
                )
                return dict(row) if row else None
        except Exception as e:
            raise RuntimeError(f"Insert failed: {e}") from e

    async def batch_insert(
        self,
        user_id: str,
        request: Request,
        payloads: list[dict[str, Any]],
        table_name: str,
    ) -> list[dict]:
        if not payloads:
            return []

        try:
            # Validate all payloads have the same keys
            columns = list(payloads[0].keys())
            for p in payloads:
                if set(p.keys()) != set(columns):
                    raise ValueError("All payloads must have the same keys")

            # Encrypt all payloads
            encrypted_payloads = [self._encrypt_payload(p, table_name) for p in payloads]

            # Prepare dynamic SQL
            column_names = ', '.join(f'"{col}"' for col in columns)
            placeholders = []
            values = []

            for payload in encrypted_payloads:
                value_placeholders = [
                    f"${len(values) + j + 1}" for j in range(len(columns))
                ]
                placeholders.append(f"({', '.join(value_placeholders)})")
                values.extend(payload[col] for col in columns)

            insert_statement = f"""
                INSERT INTO "{table_name}" ({column_names})
                VALUES {', '.join(placeholders)}
                RETURNING *
            """

            async with request.app.state.pool.acquire() as conn:
                await self.set_session_user_id(conn=conn, user_id=user_id)
                rows = await conn.fetch(insert_statement, *values)
                return [dict(row) for row in rows]

        except Exception as e:
            raise RuntimeError(f"Batch insert failed: {e}") from e

    async def upsert(
        self,
        user_id: str,
        request: Request,
        conflict_columns: List[str],
        payload: dict[str, Any],
        table_name: str
    ) -> Optional[dict]:
        async def connection_provider():
            conn = await request.app.state.pool.acquire()
            await self.set_session_user_id(conn=conn, user_id=user_id)
            return (conn, False) # False indicates "don't close after use"

        return await self._upsert_common(
            request=request,
            conflict_columns=conflict_columns,
            payload=payload,
            table_name=table_name,
            connection_provider=connection_provider,
        )

    async def upsert_with_stripe_connection(
        self,
        request: Request,
        conflict_columns: List[str],
        payload: dict[str, Any],
        table_name: str,
        resend_client: ResendBaseClass,
        secret_manager: AwsSecretManagerBaseClass,
    ) -> Optional[dict]:
        async def connection_provider():
            conn = await self._get_stripe_writer_connection(
                secret_manager=secret_manager,
                resend_client=resend_client,
            )
            return (conn, True) # True indicates "close after use"

        return await self._upsert_common(
            request=request,
            conflict_columns=conflict_columns,
            payload=payload,
            table_name=table_name,
            connection_provider=connection_provider,
        )

    async def update(
        self,
        user_id: str,
        request: Request,
        payload: dict[str, Any],
        filters: dict[str, Any],
        table_name: str
    ) -> dict | None:
        try:
            payload = self._encrypt_payload(payload, table_name)

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

            async with request.app.state.pool.acquire() as conn:
                # Set the current user ID for satisfying RLS.
                await self.set_session_user_id(
                    conn=conn,
                    user_id=user_id
                )
                rows = await conn.fetch(
                    update_query,
                    *all_values
                )
                return [dict(row) for row in rows]
        except Exception as e:
            raise RuntimeError(e) from e

    async def select(
        self,
        user_id: str,
        request: Request,
        fields: list[str],
        table_name: str,
        filters: dict[str, Any] = None,
        limit: Optional[int] = None,
        order_by: Optional[tuple[str, str]] = None
    ) -> list[dict]:
        async def connection_provider():
            conn = await request.app.state.pool.acquire()
            await self.set_session_user_id(conn=conn, user_id=user_id)
            return (conn, False) # False indicates "don't close after use"

        return await self._select_common(
            fields=fields,
            table_name=table_name,
            filters=filters,
            limit=limit,
            order_by=order_by,
            connection_provider=connection_provider,
            request=request,
        )

    async def select_count(
        self,
        user_id: str,
        request: Request,
        table_name: str,
        filters: dict[str, Any] = None,
        order_by: Optional[tuple[str, str]] = None
    ) -> int:
        async def connection_provider():
            conn = await request.app.state.pool.acquire()
            await self.set_session_user_id(conn=conn, user_id=user_id)
            return (conn, False) # False indicates "don't close after use"

        count_response = await self._select_common(
            fields=["COUNT(*) AS count"],
            table_name=table_name,
            filters=filters,
            order_by=order_by,
            connection_provider=connection_provider,
            request=request,
        )
        return count_response[0]["count"]

    async def select_with_stripe_connection(
        self,
        fields: list[str],
        filters: dict[str, Any],
        table_name: str,
        resend_client: ResendBaseClass,
        secret_manager: AwsSecretManagerBaseClass,
        request: Request,
        limit: Optional[int] = None,
        order_by: Optional[tuple[str, str]] = None
    ) -> list[dict]:
        async def connection_provider():
            conn = await self._get_stripe_reader_connection(
                secret_manager=secret_manager,
                resend_client=resend_client,
            )
            return (conn, True) # True indicates "close after use"

        return await self._select_common(
            fields=fields,
            table_name=table_name,
            filters=filters,
            limit=limit,
            order_by=order_by,
            connection_provider=connection_provider,
            request=request,
        )

    async def delete(
        self,
        user_id: str,
        request: Request,
        table_name: str,
        filters: dict[str, Any]
    ) -> list[dict]:
        try:
            where_clause, where_values = type(self)._build_where_clause(filters)
            delete_query = (
                f"""
                DELETE FROM "{table_name}"
                {where_clause}
                RETURNING *
                """
            )
            delete_query = " ".join(delete_query.split())

            async with request.app.state.pool.acquire() as conn:
                # Set the current user ID for satisfying RLS.
                await self.set_session_user_id(
                    conn=conn,
                    user_id=user_id
                )
                rows = await conn.fetch(
                    delete_query,
                    *where_values
                )
                return [dict(row) for row in rows]
        except Exception as e:
            raise RuntimeError(f"Delete failed: {e}") from e

    async def set_session_user_id(
        self,
        user_id: str,
        conn: asyncpg.Connection
    ):
        try:
            # Validate and normalize
            parsed_user_id = str(uuid.UUID(user_id))
            await conn.execute(f"SET app.current_user_id = '{parsed_user_id}'")
        except Exception as e:
            raise RuntimeError(f"Failed to set session user ID: {e}") from e

    # Private

    def _encrypt_payload(
        self,
        payload: dict,
        table_name: str
    ) -> dict:
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

    def _decrypt_payload(
        self,
        payload: dict,
        table_name: str
    ) -> dict:
        if table_name not in ENCRYPTED_TABLES:
            # Return payload untouched if no need for decryption
            return payload

        if table_name == ENCRYPTED_PATIENTS_TABLE_NAME:
            for key, value in payload.items():
                if key in PATIENTS_ENCRYPTED_COLUMNS:
                    if value is None:
                        continue
                    payload[key] = self.encryptor.decrypt(value)
            return payload

        if table_name == ENCRYPTED_SESSION_REPORTS_TABLE_NAME:
            for key, value in payload.items():
                if key in SESSION_REPORTS_ENCRYPTED_COLUMNS:
                    if value is None:
                        continue
                    decrypted_value = self.encryptor.decrypt(value)
                    payload[key] = decrypted_value if not SESSION_REPORTS_ENCRYPTED_COLUMNS[key][IS_JSON_KEY] else json.loads(decrypted_value)
            return payload

        if table_name == ENCRYPTED_PATIENT_ATTENDANCE_TABLE_NAME:
            for key, value in payload.items():
                if key in PATIENT_ATTENDANCE_ENCRYPTED_COLUMNS:
                    if value is None:
                        continue
                    payload[key] = self.encryptor.decrypt(value)
            return payload

        if table_name == ENCRYPTED_PATIENT_BRIEFINGS_TABLE_NAME:
            for key, value in payload.items():
                if key in PATIENT_BRIEFINGS_ENCRYPTED_COLUMNS:
                    if value is None:
                        continue
                    payload[key] = self.encryptor.decrypt(value)
            return payload

        if table_name == ENCRYPTED_PATIENT_QUESTION_SUGGESTIONS_TABLE_NAME:
            for key, value in payload.items():
                if key in PATIENT_QUESTION_SUGGESTIONS_ENCRYPTED_COLUMNS:
                    if value is None:
                        continue
                    decrypted_value = self.encryptor.decrypt(value)
                    payload[key] = decrypted_value if not PATIENT_QUESTION_SUGGESTIONS_ENCRYPTED_COLUMNS[key][IS_JSON_KEY] else json.loads(decrypted_value)
            return payload

        if table_name == ENCRYPTED_PATIENT_TOPICS_TABLE_NAME:
            for key, value in payload.items():
                if key in PATIENT_TOPICS_ENCRYPTED_COLUMNS:
                    if value is None:
                        continue
                    decrypted_value = self.encryptor.decrypt(value)
                    payload[key] = decrypted_value if not PATIENT_TOPICS_ENCRYPTED_COLUMNS[key][IS_JSON_KEY] else json.loads(decrypted_value)
            return payload

        raise Exception(f"Attempted to decrypt values for table {table_name}, which is not tracked.")

    @staticmethod
    def _build_where_clause(
        filters: dict[str, Any]
    ) -> tuple[str, list[Any]]:
        values = []
        if filters is None:
            return ("", values)

        operator_map = {
            "gte": ">=",
            "lte": "<=",
            "gt": ">",
            "lt": "<",
            "ne": "!=",
            "eq": "="
        }

        conditions = []
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

    async def _get_stripe_reader_connection(
        self,
        secret_manager: AwsSecretManagerBaseClass,
        resend_client: ResendBaseClass,
    ):
        return await self._get_db_connection_for_stripe(
            stripe_role=os.environ.get("AWS_SECRET_MANAGER_STRIPE_READER_ROLE"),
            secret_manager=secret_manager,
            resend_client=resend_client
        )

    async def _get_stripe_writer_connection(
        self,
        secret_manager: AwsSecretManagerBaseClass,
        resend_client: ResendBaseClass,
    ):
        return await self._get_db_connection_for_stripe(
            stripe_role=os.environ.get("AWS_SECRET_MANAGER_STRIPE_WRITER_ROLE"),
            secret_manager=secret_manager,
            resend_client=resend_client
        )

    async def _get_db_connection_for_stripe(
        self,
        stripe_role: str,
        secret_manager: AwsSecretManagerBaseClass,
        resend_client: ResendBaseClass,
    ):
        try:
            secret = secret_manager.get_secret(
                secret_id=stripe_role,
                resend_client=resend_client,
            )

            db = os.getenv("AWS_RDS_DB_NAME")
            if os.environ.get("ENVIRONMENT") not in [STAGING_ENVIRONMENT, PROD_ENVIRONMENT]:
                # Running locally, let's leverage Bastion's SSH tunnel
                endpoint = os.getenv("AWS_BASTION_RDS_DATABASE_ENDPOINT", "127.0.0.1")
                port = os.getenv("AWS_BASTION_RDS_DB_PORT", 5433)
            else:
                endpoint = os.getenv("AWS_RDS_DATABASE_ENDPOINT")
                port = secret.get("port") or os.getenv("AWS_RDS_DB_PORT")

            conn = await asyncpg.connect(
                user=secret.get("username", None),
                password=secret.get("password", None),
                database=db,
                host=endpoint,
                port=port,
                ssl='require',
                timeout=10
            )
            return conn
        except Exception as e:
            raise RuntimeError(e) from e

    async def _select_common(
        self,
        fields: list[str],
        table_name: str,
        filters: dict[str, Any],
        order_by: Optional[tuple[str, str]],
        connection_provider: Callable[[], Awaitable[tuple[Any, bool]]],
        request: Request,
        limit: Optional[int] = None,
    ) -> list[dict]:
        try:
            where_clause, where_values = type(self)._build_where_clause(filters)
            field_expr = "*" if fields == ["*"] else ', '.join([
                field if " AS " in field.upper() or "(" in field else f'"{field}"'
                for field in fields
            ])
            limit_clause = f"LIMIT {limit}" if limit is not None else ""
            order_clause = ""

            if order_by:
                col, direction = order_by
                direction = direction.upper()
                if direction not in {"ASC", "DESC"}:
                    raise ValueError(f"Invalid order direction: {direction}")
                order_clause = f'ORDER BY "{col}" {direction}'

            query = f"""
                SELECT {field_expr} FROM "{table_name}"
                {where_clause}
                {order_clause}
                {limit_clause}
            """
            query = " ".join(query.split())

            conn, should_close = await connection_provider()
            try:
                rows = await conn.fetch(query, *where_values)
                result = [dict(row) for row in rows]
                if table_name in ENCRYPTED_TABLES and rows:
                    result = [self._decrypt_payload(row, table_name) for row in result]
                return result
            finally:
                if should_close:
                    await conn.close()
                else:
                    await request.app.state.pool.release(conn)
        except Exception as e:
            raise RuntimeError(f"Select failed: {e}") from e

    async def _upsert_common(
        self,
        request: Request,
        conflict_columns: List[str],
        payload: dict[str, Any],
        table_name: str,
        connection_provider: Callable[[], Awaitable[tuple[Any, bool]]],
    ) -> Optional[dict]:
        try:
            payload = self._encrypt_payload(payload, table_name)
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

            conn, should_close = await connection_provider()
            try:
                row = await conn.fetchrow(
                    upsert_query,
                    *values
                )
                return dict(row) if row else None
            finally:
                if should_close:
                    await conn.close()
                else:
                    await request.app.state.pool.release(conn)
        except Exception as e:
            raise RuntimeError(f"Upsert failed: {e}") from e
