from ..dependencies.dependency_container import (
    dependency_container,
    ResendBaseClass,
    AwsDbBaseClass,
)
from ..internal.internal_alert import (
    CustomerRelationsAlert,
    InternalAlert,
    InternalAlertCategory,
    MediaJobProcessingAlert,
    PaymentsActivityAlert
)
from ..internal.schemas import MediaType

class EmailManager:

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

    async def send_internal_alert(self, alert: InternalAlert):
        try:
            resend_client: ResendBaseClass = dependency_container.inject_resend_client()
            therapist_id = alert.therapist_id if alert.therapist_id is not None else "N/A"

            assert hasattr(alert, "category")

            if alert.category == InternalAlertCategory.PAYMENTS_ACTIVITY:
                alert: PaymentsActivityAlert = alert
                subscription_id = alert.subscription_id if alert.subscription_id is not None else "N/A"
                customer_id = alert.customer_id if alert.customer_id is not None else "N/A"
                payment_method_id = alert.payment_method_id if alert.payment_method_id is not None else "N/A"
                activity_details = self.PAYMENTS_ACTIVITY_DETAILS.format(
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
                activity_details = self.MEDIA_JOB_ACTIVITY_DETAILS.format(
                    media_type=media_type,
                    session_report_id=session_report_id,
                    storage_filepath=storage_filepath,
                )
            else:
                # Not tracking any `activity_details` for an internal eng alert.
                activity_details = ""
                assert alert.category == InternalAlertCategory.ENGINEERING_ALERT, f"Untracked alert category: {alert.category.value}."

            body = "".join([
                f"<b>{alert.description}</b>",
                "<ul>",
                self.SESSION_DATA_DETAILS.format(
                    therapist_id=therapist_id,
                    session_id=alert.session_id,
                    environment=alert.environment
                ),
                activity_details,
                "</ul>",
                "" if alert.exception is None else f"<p>Additionally, the following exception was raised: <i>{str(alert.exception)}</i></p>"
            ])

            resend_client.send_eng_team_internal_alert_email(
                subject=self.ENGINEERING_ALERT_SUBJECT,
                body=body,
                alert_category=alert.category
            )
        except Exception as e:
            raise Exception(e)

    async def send_customer_relations_alert(self, alert: InternalAlert):
        try:
            resend_client: ResendBaseClass = dependency_container.inject_resend_client()
            therapist_id = alert.therapist_id if alert.therapist_id is not None else "N/A"

            assert hasattr(alert, "category") and alert.category == InternalAlertCategory.CUSTOMER_RELATIONS

            alert: CustomerRelationsAlert = alert

            therapist_email = alert.therapist_email if alert.therapist_email is not None else "N/A"
            therapist_name = alert.therapist_name if alert.therapist_name is not None else "N/A"

            activity_details = self.CUSTOMER_RELATIONS_ACTIVITY_DETAILS.format(
                therapist_email=therapist_email,
                therapist_name=therapist_name
            )

            body = "".join([
                f"<b>{alert.description}</b>",
                "<ul>",
                self.SESSION_DATA_DETAILS.format(
                    therapist_id=therapist_id,
                    session_id=alert.session_id,
                    environment=alert.environment
                ),
                activity_details,
                "</ul>",
                "" if alert.exception is None else f"<p>Additionally, the following exception was raised: <i>{str(alert.exception)}</i></p>"
            ])

            resend_client.send_customer_relations_alert_email(
                subject=self.CUSTOMER_RELATIONS_ALERT_SUBJECT,
                body=body,
                alert_category=alert.category
            )
        except Exception as e:
            raise Exception(e)
