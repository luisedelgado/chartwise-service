from abc import ABC, abstractmethod

from fastapi import Request
from typing import Any, List, Optional

class AwsDbBaseClass(ABC):

    """
    Inserts payload into a table.

    Arguments:
    request – the FastAPI request associated with the insert operation.
    payload – the payload to be inserted.
    table_name – the table into which the payload should be inserted.
    """
    @abstractmethod
    async def insert(request: Request,
                     payload: dict[str, Any],
                     table_name: str) -> Optional[dict]:
        pass

    """
    Updates a table with the incoming payload and filters.

    Arguments:
    request – the FastAPI request associated with the update operation.
    payload – the payload to be updated.
    filters – the set of filters to be applied to the table.
    table_name – the table that should be updated.
    """
    @abstractmethod
    async def update(request: Request,
                     payload: dict[str, Any],
                     filters: dict[str, Any],
                     table_name: str) -> Optional[dict]:
        pass

    """
    Upserts into a table with the incoming data.

    Arguments:
    request – the FastAPI request associated with the upsert operation.
    conflict_columns – the key to be used to update the table if a conflict arises.
    payload – the payload to be updated.
    table_name – the table that should be updated.
    """
    @abstractmethod
    async def upsert(request: Request,
                     conflict_columns: List[str],
                     payload: dict[str, Any],
                     table_name: str) -> Optional[dict]:
        pass

    """
    Fetches data from a table based on the incoming params.

    Arguments:
    request – the FastAPI request associated with the select operation.
    fields – the fields to be retrieved from a table.
    filters – the set of filters to be applied to the table.
    table_name – the table to be queried.
    limit – the optional cap for count of results to be returned.
    order_by – the optional specification for column to sort by, and sort style.
    """
    @abstractmethod
    async def select(request: Request,
                     fields: list[str],
                     filters: dict[str, Any],
                     table_name: str,
                     limit: Optional[int] = None,
                     order_by: Optional[tuple[str, str]] = None) -> list[dict]:
        pass

    """
    Deletes from a table name based on the incoming params.

    Arguments:
    request – the FastAPI request associated with the delete operation.
    table_name – the table name.
    filters – the set of filters to be applied to the table.
    """
    @abstractmethod
    async def delete(request: Request,
                     table_name: str,
                     filters: dict[str, Any]) -> list[dict]:
        pass

    """
    Retrieves the current user.
    """
    @abstractmethod
    async def get_user():
        pass

    """
    Retrieves the current user id.
    """
    @abstractmethod
    async def get_current_user_id() -> str:
        pass

    """
    Signs out.
    """
    @abstractmethod
    async def sign_out():
        pass

    """
    Deletes a user from the authentication schema.
    Arguments:
    user_id – the user id to be deleted.
    """
    @abstractmethod
    async def delete_user(user_id: str):
        pass
