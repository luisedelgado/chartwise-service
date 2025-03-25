from fastapi import BackgroundTasks

from .email_manager import EmailManager
from ..dependencies.api.supabase_base_class import SupabaseBaseClass
from ..internal.internal_alert import EngineeringAlert
from ..internal.schemas import PROD_ENVIRONMENT
from ..dependencies.dependency_container import dependency_container

class PhiAuditManager:

    """
    Logs PHI activity to the audit_logs table in the database.

    Params:
    - email_manager: EmailManager
    - background_tasks: BackgroundTasks
    - environment: str
    - session_id: str
    - therapist_id: str
    - patient_id: str
    - api_method: str
    - status_code: int
    - endpoint: str
    - ip_address: str
    """
    async def log_phi_activity(self,
                               email_manager: EmailManager,
                               background_tasks: BackgroundTasks,
                               environment: str,
                               session_id: str,
                               therapist_id: str,
                               patient_id: str,
                               api_method: str,
                               status_code: int,
                               endpoint: str,
                               ip_address: str,):
        try:
            if environment != PROD_ENVIRONMENT:
                return

            assert len(therapist_id or '') > 0, "Therapist ID is required."

            payload = {
                "therapist_id": therapist_id,
                "patient_id": patient_id,
                "method": api_method,
                "status_code": status_code,
                "url_path": endpoint,
                "session_id": session_id,
                "ip_address": ip_address
            }

            supabase_client = dependency_container.inject_supabase_client_factory().inject_admin_client()
            background_tasks.add_task(supabase_client.insert,
                                      payload=payload,
                                      table_name="audit_logs")
        except Exception as e:
            # Fail silently but send an internal alert.
            eng_alert = EngineeringAlert(description=f"Failed to log PHI activity ({api_method} {endpoint}). Exception raised: {str(e)}",
                                         session_id=session_id,
                                         environment=environment,
                                         exception=e,
                                         therapist_id=therapist_id,
                                         patient_id=patient_id)
            await email_manager.send_internal_alert(alert=eng_alert)
            pass
