from ..api.resend_base_class import ResendBaseClass
from ...internal.alerting.internal_alert import InternalAlert

class FakeResendClient(ResendBaseClass):

    def send_internal_alert(
        self,
        alert: InternalAlert,
    ):
        pass

    def send_customer_relations_alert(
        self,
        alert: InternalAlert,
    ):
        pass
