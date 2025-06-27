from abc import ABC, abstractmethod

from fastapi import Request
from typing import Any, List, Optional

from .aws_secret_manager_base_class import AwsSecretManagerBaseClass
from .resend_base_class import ResendBaseClass

class AwsDbBaseClass(ABC):

    @abstractmethod
    async def insert(
        self,
        user_id: str,
        request: Request,
        payload: dict[str, Any],
        table_name: str
    ) -> Optional[dict]:
        """
        Inserts payload into a table.

        Arguments:
        user_id – the current user ID.
        request – the FastAPI request associated with the insert operation.
        payload – the payload to be inserted.
        table_name – the table into which the payload should be inserted.
        """
        pass

    @abstractmethod
    async def batch_insert(
        self,
        user_id: str,
        request: Request,
        payloads: list[dict[str, Any]],
        table_name: str,
    ) -> list[dict]:
        """
        Inserts multiple payloads into a table.

        Arguments:
        user_id – the current user ID.
        request – the FastAPI request associated with the insert operation.
        payloads – the list of payloads to be inserted.
        table_name – the table into which the payloads should be inserted.
        """
        pass

    @abstractmethod
    async def update(
        self,
        user_id: str,
        request: Request,
        payload: dict[str, Any],
        filters: dict[str, Any],
        table_name: str
    ) -> list | None:
        """
        Updates a table with the incoming payload and filters.

        Arguments:
        user_id – the current user ID.
        request – the FastAPI request associated with the update operation.
        payload – the payload to be updated.
        filters – the set of filters to be applied to the table.
        table_name – the table that should be updated.
        """
        pass

    @abstractmethod
    async def upsert(
        self,
        user_id: str,
        request: Request,
        conflict_columns: List[str],
        payload: dict[str, Any],
        table_name: str
    ) -> Optional[dict]:
        """
        Upserts into a table with the incoming data.

        Arguments:
        user_id – the current user ID.
        request – the FastAPI request associated with the upsert operation.
        conflict_columns – the key to be used to update the table if a conflict arises.
        payload – the payload to be updated.
        table_name – the table that should be updated.
        """
        pass

    async def upsert_with_stripe_connection(
        self,
        request: Request,
        conflict_columns: List[str],
        payload: dict[str, Any],
        table_name: str,
        resend_client: ResendBaseClass,
        secret_manager: AwsSecretManagerBaseClass,
    ) -> Optional[dict]:
        """
        Upserts into a table with the incoming data using a stripe_writer connection.

        Arguments:
        request – the FastAPI request associated with the upsert operation.
        conflict_columns – the key to be used to update the table if a conflict arises.
        payload – the payload to be updated.
        table_name – the table that should be updated.
        resend_client – the resend client to use for sending emails.
        secret_manager – the secret manager object to be used internally.
        """
        pass

    @abstractmethod
    async def select(
        self,
        user_id: str,
        request: Request,
        fields: list[str],
        table_name: str,
        filters: dict[str, Any] | None = None,
        limit: Optional[int] | None = None,
        order_by: Optional[tuple[str, str]] | None = None
    ) -> list[dict]:
        """
        Fetches data from a table based on the incoming params.

        Arguments:
        user_id – the current user ID.
        request – the FastAPI request associated with the select operation.
        fields – the fields to be retrieved from a table.
        filters – the set of filters to be applied to the table.
        table_name – the table to be queried.
        limit – the optional cap for count of results to be returned.
        order_by – the optional specification for column to sort by, and sort style.
        """
        pass

    @abstractmethod
    async def select_count(
        self,
        user_id: str,
        request: Request,
        table_name: str,
        filters: dict[str, Any] | None = None,
        order_by: Optional[tuple[str, str]] | None = None
    ) -> int:
        """
        Fetches the count of results matching the incoming params.

        Arguments:
        user_id – the current user ID.
        request – the FastAPI request associated with the select operation.
        filters – the set of filters to be applied to the table.
        table_name – the table to be queried.
        limit – the optional cap for count of results to be returned.
        order_by – the optional specification for column to sort by, and sort style.
        """
        pass

    @abstractmethod
    async def select_with_stripe_connection(
        self,
        resend_client: ResendBaseClass,
        fields: list[str],
        filters: dict[str, Any],
        table_name: str,
        secret_manager: AwsSecretManagerBaseClass,
        request: Request,
        limit: Optional[int] | None = None,
        order_by: Optional[tuple[str, str]] | None = None
    ) -> list[dict]:
        """
        Fetches data from a table based on the incoming params, using a stripe_reader connection.

        Arguments:
        resend_client – the resend client to use for sending emails.
        fields – the fields to be retrieved from a table.
        filters – the set of filters to be applied to the table.
        table_name – the table to be queried.
        secret_manager – the secret manager object to be used internally.
        request – the FastAPI request associated with the select operation.
        limit – the optional cap for count of results to be returned.
        order_by – the optional specification for column to sort by, and sort style.
        """
        pass

    @abstractmethod
    async def delete(
        self,
        user_id: str,
        request: Request,
        table_name: str,
        filters: dict[str, Any]
    ) -> list[dict]:
        """
        Deletes from a table name based on the incoming params.

        Arguments:
        user_id – the current user ID.
        request – the FastAPI request associated with the delete operation.
        table_name – the table name.
        filters – the set of filters to be applied to the table.
        """
        pass

    @abstractmethod
    async def set_session_user_id(
        self,
        request: Request,
        user_id: str
    ):
        """
        Sets the user ID for the incoming request session.
        Arguments:
        request – the incoming request.
        user_id – the user id to be deleted.
        """
        pass
