from abc import ABC, abstractmethod

class InfluxBaseClass(ABC):

    @abstractmethod
    def log_api_request(
        self,
        endpoint_name: str,
        method: str,
        **kwargs
    ):
        """
        Logs data about an API request.

        Arguments:
        endpoint_name – the name of the endpoint.
        method – the api method.
        kwargs – the set of optional parameters to be sent into the method.
        """
        pass

    @abstractmethod
    def log_api_response(
        self,
        endpoint_name: str,
        method: str,
        response_time: float,
        **kwargs
    ):
        """
        Logs data about an API response.

        Arguments:
        endpoint_name – the name of the endpoint.
        method – the api method.
        response_time – the response time.
        kwargs – the set of optional parameters to be sent into the method.
        """
        pass

    @abstractmethod
    def log_error(
        self,
        endpoint_name: str,
        method: str,
        error_code: int,
        description: str,
        **kwargs
    ):
        """
        Logs data about an API error.

        Arguments:
        endpoint_name – the name of the endpoint.
        method – the api method.
        error_code – the error code.
        description – the error description.
        kwargs – the set of optional parameters to be sent into the method.
        """
        pass
