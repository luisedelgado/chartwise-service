from abc import ABC

class SupabaseBaseClass(ABC):

    """
    Inserts payload into a Supabase table.

    Arguments:
    payload – the payload to be inserted.
    table_name – the table into which the payload should be inserted.
    """
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
    def update(payload: dict,
               filters: dict,
               table_name: str):
        pass

    """
    Fetches data from a Supabase table based on the incoming params.

    Arguments:
    fields – the fields to be retrieved from a table.
    filters – the set of filters to be applied to the table.
    table_name – the table that should be updated.
    order_desc_column – the optional column that should be sorted desc.
    """
    def select(fields: str,
               filters: dict,
               table_name: str,
               order_desc_column: str = None):
        pass

    """
    Fetches data from a Supabase table based on the incoming params.

    Arguments:
    fields – the fields to be retrieved from a table.
    column_name – the column_name.
    possible_values – the list of possible values for which there would be results returned.
    table_name – the table that should be updated.
    order_desc_column – the optional column that should be sorted desc.
    """
    def select_either_or_from_column(fields: str,
                                     column_name: str,
                                     possible_values: list,
                                     table_name: str,
                                     order_desc_column: str = None):
        pass

    """
    Deletes from a table name based on the incoming params.

    Arguments:
    filters – the set of filters to be applied to the table.
    table_name – the table that should be updated.
    """
    def delete(filters: dict,
               table_name: str):
        pass

    """
    Retrieves the current user.
    """
    def get_user():
        pass

    """
    Refreshes the current session.
    """
    def refresh_session():
        pass

    """
    Signs out.
    """
    def sign_out():
        pass
