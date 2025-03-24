from abc import ABC, abstractmethod

from .supabase_storage_base_class import SupabaseStorageBaseClass

class SupabaseBaseClass(ABC):

    # Private instance of a Supabase storage client
    storage_client: SupabaseStorageBaseClass

    """
    Deletes a user from the authentication schema.
    Arguments:
    user_id – the user id to be deleted.
    """
    @abstractmethod
    def delete_user(user_id: str):
        pass

    """
    Inserts payload into a Supabase table.

    Arguments:
    payload – the payload to be inserted.
    table_name – the table into which the payload should be inserted.
    """
    @abstractmethod
    def insert(payload: dict,
               table_name: str):
        pass

    """
    Updates a Supabase table with the incoming payload and filters.

    Arguments:
    payload – the payload to be updated.
    filters – the set of filters to be applied to the table.
    table_name – the table that should be updated.
    """
    @abstractmethod
    def update(payload: dict,
               filters: dict,
               table_name: str):
        pass

    """
    Upserts into a Supabase table with the incoming data.

    Arguments:
    payload – the payload to be updated.
    on_conflict – the key to be used to update the table if a conflict arises.
    table_name – the table that should be updated.
    """
    @abstractmethod
    def upsert(payload: dict,
               on_conflict: str,
               table_name: str):
        pass

    """
    Fetches data from a Supabase table based on the incoming params.

    Arguments:
    fields – the fields to be retrieved from a table.
    filters – the set of filters to be applied to the table.
    table_name – the table to be queried.
    limit – the optional cap for count of results to be returned.
    order_desc_column – the optional column that should be sorted desc.
    """
    @abstractmethod
    def select(fields: str,
               filters: dict,
               table_name: str,
               limit: int = None,
               order_desc_column: str = None):
        pass

    """
    Fetches data from a Supabase table based on the incoming params, fitting the provided range.

    Arguments:
    fields – the fields to be retrieved from a table.
    table_name – the table to be queried.
    filters – the set of filters to be applied to the table.
    range_start – the starting point for the selection range.
    range_end – the finish point for the selection range.
    column_marker – the column to be used for calculating the range.
    limit – the optional cap for count of results to be returned.
    """
    @abstractmethod
    def select_within_range(fields: str,
                            table_name: str,
                            filters: dict,
                            range_start: str,
                            range_end: str,
                            column_marker: str,
                            limit: int = None):
        pass

    """
    Fetches data from a Supabase table based on the incoming params, fitting the provided criteria.

    Arguments:
    table_name – the table to be queried.
    fields – the fields to be retrieved from a table.
    non_null_column – the column that should not be null.
    limit – the limit for count of rows to be retrieved.
    order_ascending_column – optional flag by which the results are ordered ascendingly.
    """
    @abstractmethod
    def select_batch_where_is_not_null(table_name: str,
                                       fields: str,
                                       non_null_column: str,
                                       limit: int = None,
                                       order_ascending_column: str = None):
        pass

    """
    Fetches data from a Supabase table based on the incoming params, fitting the provided criteria.

    Arguments:
    table_name – the table to be queried.
    fields – the fields to be retrieved from a table.
    null_column – the column that should not be null.
    limit – the limit for count of rows to be retrieved.
    order_ascending_column – optional flag by which the results are ordered ascendingly.
    """
    @abstractmethod
    def select_batch_where_is_null(table_name: str,
                                   fields: str,
                                   null_column: str,
                                   limit: int = None,
                                   order_ascending_column: str = None):
        pass

    """
    Fetches data from a Supabase table based on the incoming params.

    Arguments:
    fields – the fields to be retrieved from a table.
    possible_values – the list of possible values for which there would be results returned.
    table_name – the table that should be queried.
    order_desc_column – the optional column that should be sorted desc.
    """
    @abstractmethod
    def select_either_or_from_column(fields: str,
                                     possible_values: list,
                                     table_name: str,
                                     order_desc_column: str = None):
        pass

    """
    Deletes from a table name based on the incoming params.

    Arguments:
    filters – the set of filters to be applied to the table.
    table_name – the table name.
    """
    @abstractmethod
    def delete(filters: dict,
               table_name: str):
        pass

    """
    Deletes from a table name based on the incoming params, applying a "where is not" logic to the filters.

    Arguments:
    is_not_filters – the set of filters to be applied to the table with a "where is not" logic.
    table_name – the table name.
    """
    @abstractmethod
    def delete_where_is_not(is_not_filters: dict,
                            table_name: str):
        pass

    """
    Retrieves the current user.
    """
    @abstractmethod
    def get_user():
        pass

    """
    Retrieves the current user id.
    """
    @abstractmethod
    def get_current_user_id() -> str:
        pass

    """
    Signs out.
    """
    @abstractmethod
    def sign_out():
        pass
