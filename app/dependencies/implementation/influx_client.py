import os

from datetime import datetime, timezone
from influxdb_client_3 import InfluxDBClient3, Point, write_client_options, WriteOptions
from influxdb_client_3.write_client.client.write_api import WriteType

from ..api.influx_base_class import InfluxBaseClass

class InfluxClient(InfluxBaseClass):

    API_REQUESTS_BUCKET = "api_requests"
    API_RESPONSES_BUCKET = "api_responses"
    API_ERRORS_BUCKET = "errors"
    _optional_tags = ["patient_id",
                      "session_id",
                      "session_report_id",
                      "status_code",
                      "therapist_id",
                      "notes_template"]

    def __init__(self, environment: str):
        token = os.environ.get("INFLUXDB_TOKEN")
        host = os.environ.get("INFLUXDB_HOST")

        write_client_opts = write_client_options(write_options=WriteOptions(write_type=WriteType.asynchronous),)
        self.client = InfluxDBClient3(host=host,
                                      token=token,
                                      org="".join(["chartwise-", environment]),
                                      write_client_options=write_client_opts)
        self.environment = environment

    def log_api_request(self,
                        endpoint_name: str,
                        method: str,
                        **kwargs):
        point = (
            Point(self.API_REQUESTS_BUCKET)
            .tag("endpoint_name", endpoint_name)
            .tag("environment", self.environment)
            .tag("method", method)
            .field("request_count", 1)
            .time(datetime.now(timezone.utc).isoformat())
        )

        for tag in self._optional_tags:
            value = kwargs.get(tag)
            if value is not None:
                point.tag(tag, str(value))

        self.client.write(record=point, database=self.API_REQUESTS_BUCKET)

    def log_api_response(self,
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

        self.client.write(record=point, database=self.API_RESPONSES_BUCKET)

    def log_error(self,
                  endpoint_name: str,
                  method: str,
                  error_code: int,
                  description: str,
                  **kwargs):
        point = (
            Point(self.API_RESPONSES_BUCKET)
            .tag("endpoint_name", endpoint_name)
            .tag("environment", self.environment)
            .tag("method", method)
            .tag("error_code", error_code)
            .field("description", description)
        )

        for tag in self._optional_tags:
            value = kwargs.get(tag)
            if value is not None:
                point.tag(tag, str(value))

        self.client.write(record=point, database=self.API_ERRORS_BUCKET)
