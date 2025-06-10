import os

import resend

from jinja2 import Environment, FileSystemLoader

from ..api.resend_base_class import ResendBaseClass
from ...internal.alerting.internal_alert import (
    CustomerRelationsAlert,
    EngineeringAlert,
    InternalAlert,
    InternalAlertCategory,
    MediaJobProcessingAlert,
    PaymentsActivityAlert
)
from ...internal.schemas import MediaType, PROD_ENVIRONMENT

class ResendClient(ResendBaseClass):

    ENGINEERING_ALERT_SUBJECT = "ChartWise Engineering Alert 🚨"
    CUSTOMER_RELATIONS_ALERT_SUBJECT = "ChartWise Customer Alert 🔔"
    SESSION_DATA_DETAILS = ("<li><b>Therapist ID:</b> {therapist_id}</li>"
                             "<li><b>Session ID:</b> {session_id}</li>"
                             "<li><b>Environment:</b> {environment}</li>")
    PAYMENTS_ACTIVITY_DETAILS = ("<li><b>Subscription ID:</b> {subscription_id}</li>"
                                 "<li><b>Customer ID:</b> {customer_id}</li>"
                                 "<li><b>Payment Method ID:</b> {payment_method_id}</li>")
    MEDIA_JOB_ACTIVITY_DETAILS = ("<li><b>Media Type:</b> {media_type}</li>"
                                  "<li><b>Session Report ID:</b> {session_report_id}</li>"
                                  "<li><b>Storage Filepath:</b> {storage_filepath}</li>")
    CUSTOMER_RELATIONS_ACTIVITY_DETAILS = ("<li><b>Therapist Email:</b> {therapist_email}</li>"
                                           "<li><b>Therapist Name:</b> {therapist_name}</li>")
    LUIS_CHARTWISE_EMAIL = "luis@chartwise.ai"
    CUSTOMER_RELATIONS_FROM_ADDRESS = "ChartWise Customer Relations <customer_relations@chartwise.ai>"
    ENGINEERING_FROM_ADDRESS = "ChartWise Engineering <engineering@chartwise.ai>"

    def __init__(self):
        resend.api_key = os.environ.get('RESEND_API_KEY')
        env = Environment(loader=FileSystemLoader("app/internal/email_templates"))
        self.internal_eng_alert_template = env.get_template("internal_eng_alert.html")
        self.customer_relations_alert_template = env.get_template("customer_relations_alert.html")

    def send_internal_alert(
        self,
        alert: InternalAlert,
    ):
        try:
            therapist_id = alert.therapist_id if alert.therapist_id is not None else "N/A"
            session_id = alert.session_id if alert.session_id is not None else "N/A"

            assert hasattr(alert, "category")

            cls = type(self)
            if alert.category == InternalAlertCategory.PAYMENTS_ACTIVITY:
                alert: PaymentsActivityAlert = alert
                subscription_id = alert.subscription_id if alert.subscription_id is not None else "N/A"
                customer_id = alert.customer_id if alert.customer_id is not None else "N/A"
                payment_method_id = alert.payment_method_id if alert.payment_method_id is not None else "N/A"
                activity_details = cls.PAYMENTS_ACTIVITY_DETAILS.format(
                    subscription_id=subscription_id,
                    customer_id=customer_id,
                    payment_method_id=payment_method_id,
                )
            elif (alert.category == InternalAlertCategory.AUDIO_JOB_PROCESSING
                  or alert.category == InternalAlertCategory.IMAGE_JOB_PROCESSING):
                alert: MediaJobProcessingAlert = alert
                media_type = MediaType.AUDIO.value if alert.category == InternalAlertCategory.AUDIO_JOB_PROCESSING else MediaType.IMAGE.value
                session_report_id = alert.session_report_id if alert.session_report_id is not None else "N/A"
                storage_filepath = alert.storage_filepath if alert.storage_filepath is not None else "N/A"
                activity_details = cls.MEDIA_JOB_ACTIVITY_DETAILS.format(
                    media_type=media_type,
                    session_report_id=session_report_id,
                    storage_filepath=storage_filepath,
                )
            else:
                assert alert.category == InternalAlertCategory.ENGINEERING_ALERT, f"Untracked alert category: {alert.category.value}."
                alert: EngineeringAlert = alert
                activity_details = f"<li><b>Patient ID:</b> {alert.patient_id}</li>"

            body = "".join([
                f"<b>{alert.description}</b>",
                "<ul>",
                cls.SESSION_DATA_DETAILS.format(
                    therapist_id=therapist_id,
                    session_id=session_id,
                    environment=alert.environment
                ),
                activity_details,
                "</ul>",
                "" if alert.exception is None else f"<p>Additionally, the following exception was raised: <i>{str(alert.exception)}</i></p>"
            ])

            html_content = self.internal_eng_alert_template.render(
                problem_area=alert.category,
                alert_content=body
            )
            self._send_email(
                from_address=cls.ENGINEERING_FROM_ADDRESS,
                to_addresses=[cls.LUIS_CHARTWISE_EMAIL],
                subject=cls.ENGINEERING_ALERT_SUBJECT,
                html=html_content
            )
        except Exception as e:
            raise RuntimeError(e) from e

    def send_customer_relations_alert(
        self,
        alert: InternalAlert,
    ):
        if alert.environment != PROD_ENVIRONMENT:
            # Do not send customer relations alerts for non-prod environments.
            return

        try:
            therapist_id = alert.therapist_id if alert.therapist_id is not None else "N/A"

            assert hasattr(alert, "category") and alert.category == InternalAlertCategory.CUSTOMER_RELATIONS

            alert: CustomerRelationsAlert = alert

            therapist_email = alert.therapist_email if alert.therapist_email is not None else "N/A"
            therapist_name = alert.therapist_name if alert.therapist_name is not None else "N/A"

            cls = type(self)
            activity_details = cls.CUSTOMER_RELATIONS_ACTIVITY_DETAILS.format(
                therapist_email=therapist_email,
                therapist_name=therapist_name
            )

            body = "".join([
                f"<b>{alert.description}</b>",
                "<ul>",
                cls.SESSION_DATA_DETAILS.format(
                    therapist_id=therapist_id,
                    session_id=alert.session_id,
                    environment=alert.environment
                ),
                activity_details,
                "</ul>",
                "" if alert.exception is None else f"<p>Additionally, the following exception was raised: <i>{str(alert.exception)}</i></p>"
            ])

            html_content = self.customer_relations_alert_template.render(
                problem_area=alert.category,
                alert_content=body
            )
            self._send_email(
                from_address=cls.CUSTOMER_RELATIONS_FROM_ADDRESS,
                to_addresses=[cls.LUIS_CHARTWISE_EMAIL],
                subject=cls.CUSTOMER_RELATIONS_ALERT_SUBJECT,
                html=html_content
            )
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
    def _send_email(
        self,
        from_address: str,
        to_addresses: list[str],
        subject: str,
        html: str
    ):
        params: resend.Emails.SendParams = {
            "from": from_address,
            "to": to_addresses,
            "subject": subject,
            "html": html,
        }

        resend.Emails.send(params)
