from abc import ABC, abstractmethod

class AwsDbBaseClass(ABC):

    """
    Deletes a user from the authentication schema.
    Arguments:
    user_id – the user id to be deleted.
    """
    @abstractmethod
    async def delete_user(user_id: str):
        pass

    """
    Inserts payload into a table.

    Arguments:
    payload – the payload to be inserted.
    table_name – the table into which the payload should be inserted.
    """
    @abstractmethod
    async def insert(payload: dict,
               table_name: str):
        pass

    """
    Updates a table with the incoming payload and filters.

    Arguments:
    payload – the payload to be updated.
    filters – the set of filters to be applied to the table.
    table_name – the table that should be updated.
    """
    @abstractmethod
    async def update(payload: dict,
               filters: dict,
               table_name: str):
        pass

    """
    Upserts into a table with the incoming data.

    Arguments:
    payload – the payload to be updated.
    on_conflict – the key to be used to update the table if a conflict arises.
    table_name – the table that should be updated.
    """
    @abstractmethod
    async def upsert(payload: dict,
               on_conflict: str,
               table_name: str):
        pass

    """
    Fetches data from a table based on the incoming params.

    Arguments:
    fields – the fields to be retrieved from a table.
    filters – the set of filters to be applied to the table.
    table_name – the table to be queried.
    limit – the optional cap for count of results to be returned.
    order_desc_column – the optional column that should be sorted desc.
    """
    @abstractmethod
    async def select(fields: str,
               filters: dict,
               table_name: str,
               limit: int = None,
               order_desc_column: str = None):
        pass

    """
    Deletes from a table name based on the incoming params.

    Arguments:
    filters – the set of filters to be applied to the table.
    table_name – the table name.
    """
    @abstractmethod
    async def delete(filters: dict,
               table_name: str):
        pass

    """
    Deletes from a table name based on the incoming params, applying a "where is not" logic to the filters.

    Arguments:
    is_not_filters – the set of filters to be applied to the table with a "where is not" logic.
    table_name – the table name.
    """
    @abstractmethod
    async def delete_where_is_not(is_not_filters: dict,
                            table_name: str):
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
