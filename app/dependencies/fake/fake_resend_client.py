from ..api.resend_base_class import ResendBaseClass
from ...internal.alerting.internal_alert import InternalAlertCategory

class FakeResendClient(ResendBaseClass):

    def send_eng_team_internal_alert_email(
        self,
        subject: str,
        body: str,
        alert_category: InternalAlertCategory
    ):
        pass

    def send_customer_relations_alert_email(
        self,
        subject: str,
        body: str,
        alert_category: InternalAlertCategory
    ):
        pass
