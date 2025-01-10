import os

from fastapi import BackgroundTasks
from influxdb_client_3 import InfluxDBClient3, Point

from ..api.influx_base_class import InfluxBaseClass

class InfluxClient(InfluxBaseClass):

    API_REQUESTS_BUCKET = "api_requests"
    API_RESPONSES_BUCKET = "api_responses"
    _optional_tags = ["patient_id",
                      "session_id",
                      "session_report_id",
                      "status_code",
                      "therapist_id"]

    def __init__(self, environment: str):
        token = os.environ.get("INFLUXDB_TOKEN")
        host = os.environ.get("INFLUXDB_HOST")

        org = "".join(["chartwise-", environment])
        self.client = InfluxDBClient3(host=host, token=token, org=org)
        self.environment = environment

    def log_api_request(self,
                        background_tasks: BackgroundTasks,
                        endpoint_name: str,
                        method: str,
                        **kwargs):
        point = (
            Point(self.API_REQUESTS_BUCKET)
            .tag("endpoint_name", endpoint_name)
            .tag("environment", self.environment)
            .tag("method", method)
            .field("request_count", 1)
        )

        for tag in self._optional_tags:
            value = kwargs.get(tag)
            if value is not None:
                point.tag(tag, str(value))

        background_tasks.add_task(self.client.write, point, self.API_REQUESTS_BUCKET)

    def log_api_response(self,
                         background_tasks: BackgroundTasks,
                         endpoint_name: str,
                         method: str,
                         response_time: float,
                         **kwargs):
        point = (
            Point(self.API_RESPONSES_BUCKET)
            .tag("endpoint_name", endpoint_name)
            .tag("environment", self.environment)
            .tag("method", method)
            .field("response_time", response_time)
        )

        for tag in self._optional_tags:
            value = kwargs.get(tag)
            if value is not None:
                point.tag(tag, str(value))

        background_tasks.add_task(self.client.write, point, self.API_RESPONSES_BUCKET)
