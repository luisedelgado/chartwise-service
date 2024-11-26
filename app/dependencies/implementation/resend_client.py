import os

import resend

from jinja2 import Environment, FileSystemLoader

from ..api.resend_base_class import ResendBaseClass

class ResendClient(ResendBaseClass):

    def __init__(self):
        resend.api_key = os.environ.get('RESEND_API_KEY')
        env = Environment(loader=FileSystemLoader("app/internal/email_templates"))
        self.welcome_template = env.get_template("welcome.html")

    def send_new_subscription_welcome_email(self,
                                            user_first_name: str,
                                            language_code: str,
                                            to_address: str):
        html_content = self.welcome_template.render(user_first_name=user_first_name,
                                                    use_spanish_template=False)
        self._send_email(from_address="luis@chartwise.ai",
                         to_addresses=["luis.e.delgado24@gmail.com"],
                         subject="Welcome to ChartWise!",
                         html=html_content)

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
