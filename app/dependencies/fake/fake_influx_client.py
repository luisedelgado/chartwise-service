from fastapi import BackgroundTasks

from ..api.influx_base_class import InfluxBaseClass

class FakeInfluxClient(InfluxBaseClass):

    def log_api_request(self,
                        background_tasks: BackgroundTasks,
                        endpoint_name: str,
                        method: str,
                        **kwargs):
        pass
