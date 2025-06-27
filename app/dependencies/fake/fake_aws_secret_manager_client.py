from ..api.aws_secret_manager_base_class import AwsSecretManagerBaseClass

from ..api.resend_base_class import ResendBaseClass

class FakeAwsSecretManagerClient(AwsSecretManagerBaseClass):

    def get_secret(
        self,
        secret_id: str,
        resend_client: ResendBaseClass,
    ) -> dict:
        return {"secret": "myFakeSecret"}
