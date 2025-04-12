from abc import ABC, abstractmethod

from fastapi import Request
from typing import Any, List, Optional

class AwsDbBaseClass(ABC):

    @abstractmethod
    async def insert(user_id: str,
                     request: Request,
                     payload: dict[str, Any],
                     table_name: str) -> Optional[dict]:
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
    async def update(user_id: str,
                     request: Request,
                     payload: dict[str, Any],
                     filters: dict[str, Any],
                     table_name: str) -> Optional[dict]:
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
    async def upsert(user_id: str,
                     request: Request,
                     conflict_columns: List[str],
                     payload: dict[str, Any],
                     table_name: str) -> Optional[dict]:
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

    @abstractmethod
    async def select(user_id: str,
                     request: Request,
                     fields: list[str],
                     filters: dict[str, Any],
                     table_name: str,
                     limit: Optional[int] = None,
                     order_by: Optional[tuple[str, str]] = None) -> list[dict]:
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
    async def delete(user_id: str,
                     request: Request,
                     table_name: str,
                     filters: dict[str, Any]) -> list[dict]:
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
    async def get_user():
        """
        Retrieves the current user.
        """
        pass

    @abstractmethod
    async def get_current_user_id() -> str:
        """
        Retrieves the current user id.
        """
        pass

    @abstractmethod
    async def sign_out():
        """
        Signs out.
        """
        pass

    @abstractmethod
    async def delete_user(user_id: str):
        """
        Deletes a user from the authentication schema.
        Arguments:
        user_id – the user id to be deleted.
        """
        pass

    @abstractmethod
    async def set_session_user_id(request: Request, user_id: str):
        """
        Sets the user ID for the incoming request session.
        Arguments:
        request – the incoming request.
        user_id – the user id to be deleted.
        """
        pass
