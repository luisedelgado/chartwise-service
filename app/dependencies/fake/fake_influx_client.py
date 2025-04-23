from ..api.influx_base_class import InfluxBaseClass

class FakeInfluxClient(InfluxBaseClass):

    def log_api_request(
        self,
        endpoint_name: str,
        method: str,
        **kwargs
    ):
        pass

    def log_api_response(
        self,
        endpoint_name: str,
        method: str,
        response_time: float,
        **kwargs
    ):
        pass

    def log_error(
        self,
        endpoint_name: str,
        method: str,
        error_code: int,
        description: str,
        **kwargs
    ):
        pass
