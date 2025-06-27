import json
import os

from ..api.aws_secret_manager_base_class import AwsSecretManagerBaseClass
from ...dependencies.api.resend_base_class import ResendBaseClass
from ...internal.utilities.aws_utils import sign_and_send_aws_request

class AwsSecretManagerClient(AwsSecretManagerBaseClass):

    def get_secret(
        self,
        secret_id: str,
        resend_client: ResendBaseClass,
    ) -> dict:
        try:
            region = os.environ.get("AWS_SERVICES_REGION")
            assert region is not None, "Missing region"

            payload = {
                "SecretId": secret_id
            }

            result = sign_and_send_aws_request(
                service="secretsmanager",
                region=region,
                endpoint_url=f"https://secretsmanager.{region}.amazonaws.com/",
                payload=payload,
                target_action="secretsmanager.GetSecretValue",
                resend_client=resend_client,
            )
            return json.loads(result["SecretString"])
        except Exception as e:
            raise RuntimeError(f"Error getting secret: {e}") from e
