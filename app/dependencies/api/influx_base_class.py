from abc import ABC, abstractmethod
from fastapi import BackgroundTasks

class InfluxBaseClass(ABC):

    @abstractmethod
    def log_api_request(background_tasks: BackgroundTasks,
                        endpoint_name: str,
                        method: str,
                        **kwargs):
        """
        Logs data about an API request.

        Arguments:
        background_tasks – object for scheduling background tasks.
        endpoint_name – the name of the endpoint.
        method – the api method.
        kwargs – the set of optional parameters to be sent into the method.
        """
        pass
