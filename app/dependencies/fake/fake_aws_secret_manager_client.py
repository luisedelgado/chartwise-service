from ..api.aws_secret_manager_base_class import AwsSecretManagerBaseClass

class FakeAwsSecretManagerClient(AwsSecretManagerBaseClass):

    def get_rds_secret(self) -> str:
        return "myFakeUrl"
