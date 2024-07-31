from abc import ABC

class SupabaseBaseClass(ABC):

    def insert(payload: dict,
               table_name: str):
        pass

    def update(payload: dict,
               filters: dict,
               table_name: str):
        pass

    def select(fields: str,
               filters: dict,
               table_name: str):
        pass

    def delete(filters: dict,
               table_name: str):
        pass

    def refresh_session():
        pass
