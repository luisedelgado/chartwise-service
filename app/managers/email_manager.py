from ..internal.dependency_container import (dependency_container,
                                             ResendBaseClass,
                                             SupabaseBaseClass)
from ..internal.internal_alert import (InternalAlert,
                                       InternalAlertCategory,
                                       MediaJobProcessingAlert,
                                       PaymentsActivityAlert)
from ..internal.schemas import MediaType

class EmailManager:

    ALERT_SUBJECT = "ChartWise Engineering Alert 🚨"
    SESSION_DATA_DETAILS = ("<li><b>Therapist ID:</b> {therapist_id}</li>"
                             "<li><b>Session ID:</b> {session_id}</li>")
    PAYMENTS_ACTIVITY_DETAILS = ("<li><b>Subscription ID:</b> {subscription_id}</li>"
                                 "<li><b>Customer ID:</b> {customer_id}</li>"
                                 "<li><b>Payment Method ID:</b> {payment_method_id}</li>")
    MEDIA_JOB_ACTIVITY_DETAILS = ("<li><b>Media Type:</b> {media_type}</li>"
                                  "<li><b>Session Report ID:</b> {session_report_id}</li>"
                                  "<li><b>Storage Filepath:</b> {storage_filepath}</li>")

    async def send_new_user_welcome_email(self,
                                          therapist_id: str,
                                          supabase_client: SupabaseBaseClass):
        try:
            therapist_query = supabase_client.select(fields="*",
                                                        filters={
                                                            "id": therapist_id
                                                        },
                                                        table_name="therapists")
            therapist_response_data = therapist_query.dict()['data'][0]
            therapist_first_name = therapist_response_data['first_name']
            language_code = therapist_response_data['language_preference']
            therapist_email = therapist_response_data['email']

            resend_client: ResendBaseClass = dependency_container.inject_resend_client()
            resend_client.send_new_subscription_welcome_email(user_first_name=therapist_first_name,
                                                              language_code=language_code,
                                                              to_address=therapist_email)
        except Exception as e:
            raise Exception(e)

    async def send_internal_eng_alert(self,
                                      alert: InternalAlert):
        try:
            resend_client: ResendBaseClass = dependency_container.inject_resend_client()
            therapist_id = alert.therapist_id if alert.therapist_id is not None else "N/A"

            assert hasattr(alert, "category")

            if alert.category == InternalAlertCategory.PAYMENTS_ACTIVITY:
                alert: PaymentsActivityAlert = alert
                subscription_id = alert.subscription_id if alert.subscription_id is not None else "N/A"
                customer_id = alert.customer_id if alert.customer_id is not None else "N/A"
                payment_method_id = alert.payment_method_id if alert.payment_method_id is not None else "N/A"
                activity_details = self.PAYMENTS_ACTIVITY_DETAILS.format(subscription_id=subscription_id,
                                                                         customer_id=customer_id,
                                                                         payment_method_id=payment_method_id)
            elif (alert.category == InternalAlertCategory.AUDIO_JOB_PROCESSING
                  or alert.category == InternalAlertCategory.IMAGE_JOB_PROCESSING):
                alert: MediaJobProcessingAlert = alert
                media_type = MediaType.AUDIO.value if alert.category == InternalAlertCategory.AUDIO_JOB_PROCESSING else MediaType.IMAGE.value
                session_report_id = alert.session_report_id if alert.session_report_id is not None else "N/A"
                storage_filepath = alert.storage_filepath if alert.storage_filepath is not None else "N/A"
                activity_details = self.MEDIA_JOB_ACTIVITY_DETAILS.format(media_type=media_type,
                                                                          session_report_id=session_report_id,
                                                                          storage_filepath=storage_filepath)
            else:
                raise Exception("Unrecognized alert category")

            body = "".join([
                "<ul>",
                self.SESSION_DATA_DETAILS.format(therapist_id=therapist_id,
                                                 session_id=alert.session_id),
                activity_details,
                "</ul>",
                f"<p>{alert.description}</p>",
                "" if alert.exception is None else f"<p>Additionally, the following exception was raised: <i>{str(alert.exception)}</i></p>"
            ])

            resend_client.send_eng_team_internal_alert_email(subject=self.ALERT_SUBJECT,
                                                             body=body,
                                                             alert_category=alert.category)
        except Exception as e:
            raise Exception(e)
