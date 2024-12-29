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
        self.welcome_template = env.get_template("welcome.html")
        self.internal_eng_alert_template = env.get_template("internal_eng_alert.html")

    def send_new_subscription_welcome_email(self,
                                            user_first_name: str,
                                            language_code: str,
                                            to_address: str):
        try:
            if language_code.startswith("es-"):
                subject = "¡Te damos la bienvenida a ChartWise!"
                from_address = "El equipo de ChartWise <hello@chartwise.ai>"
                use_spanish_template = True
            elif language_code.startswith("en-"):
                subject = "Welcome to ChartWise!"
                from_address = "ChartWise Team <hello@chartwise.ai>"
                use_spanish_template = False
            else:
                raise Exception("Unrecognized language code")

            html_content = self.welcome_template.render(user_first_name=user_first_name,
                                                        use_spanish_template=use_spanish_template)
            self._send_email(from_address=from_address,
                             to_addresses=[to_address],
                             subject=subject,
                             html=html_content)
        except Exception as e:
            raise Exception(e)

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
            raise Exception(e)

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
