import boto3
import json
import os

from ..api.aws_secret_manager_base_class import AwsSecretManagerBaseClass

class AwsSecretManagerClient(AwsSecretManagerBaseClass):

    def get_rds_secret(self) -> str:
        region = os.environ.get("AWS_SERVICES_REGION")
        session = boto3.session.Session()
        client = session.client(
            service_name="secretsmanager",
            region_name=region
        )

        try:
            response = client.get_secret_value(
                SecretId=os.environ.get("AWS_SECRET_MANAGER_RDS_SECRET_NAME")
            )
        except Exception as e:
            raise Exception(e)

        secret = json.loads(response["SecretString"])
        return secret
