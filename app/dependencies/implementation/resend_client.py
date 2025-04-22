import os

import resend

from jinja2 import Environment, FileSystemLoader

from ..api.resend_base_class import ResendBaseClass
from ...internal.internal_alert import InternalAlertCategory

class ResendClient(ResendBaseClass):

    LUIS_CHARTWISE_EMAIL = "luis@chartwise.ai"

    def __init__(self):
        resend.api_key = os.environ.get('RESEND_API_KEY')
        env = Environment(loader=FileSystemLoader("app/internal/email_templates"))
        self.internal_eng_alert_template = env.get_template("internal_eng_alert.html")
        self.customer_relations_alert_template = env.get_template("customer_relations_alert.html")

    def send_eng_team_internal_alert_email(self,
                                           subject: str,
                                           body: str,
                                           alert_category: InternalAlertCategory):
        try:
            from_address = "ChartWise Engineering <engineering@chartwise.ai>"
            html_content = self.internal_eng_alert_template.render(problem_area=alert_category.value,
                                                                   alert_content=body)
            self._send_email(from_address=from_address,
                             to_addresses=[self.LUIS_CHARTWISE_EMAIL],
                             subject=subject,
                             html=html_content)
        except Exception as e:
            raise RuntimeError(e) from e

    def send_customer_relations_alert_email(self,
                                            subject: str,
                                            body: str,
                                            alert_category: InternalAlertCategory):
        try:
            from_address = "ChartWise Customer Relations <customer_relations@chartwise.ai>"
            html_content = self.customer_relations_alert_template.render(problem_area=alert_category.value,
                                                                         alert_content=body)
            self._send_email(from_address=from_address,
                             to_addresses=[self.LUIS_CHARTWISE_EMAIL],
                             subject=subject,
                             html=html_content)
        except Exception as e:
            raise RuntimeError(e) from e

    # Private

    """
    Helper method for generically sending an email based on the incoming parameters.

    Arguments:
    from_address – the address to send from.
    to_addresses – the set of addresses to send to.
    subject – the email subject to use.
    html – the html to use.
    """
    def _send_email(self,
                    from_address: str,
                    to_addresses: list[str],
                    subject: str,
                    html: str):
        params: resend.Emails.SendParams = {
            "from": from_address,
            "to": to_addresses,
            "subject": subject,
            "html": html,
        }

        resend.Emails.send(params)
