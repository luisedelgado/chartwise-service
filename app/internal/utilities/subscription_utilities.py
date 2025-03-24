from datetime import datetime, timedelta

from .datetime_handler import DATE_FORMAT
from ..schemas import ENCRYPTED_SESSION_REPORTS_TABLE_NAME
from ...dependencies.dependency_container import SupabaseBaseClass

NUM_SESSIONS_IN_BASIC_PLAN = 20

def reached_subscription_tier_usage_limit(tier: str,
                                          therapist_id: str,
                                          supabase_client: SupabaseBaseClass,
                                          is_free_trial_active: bool) -> bool:
    if is_free_trial_active or tier == "premium":
        return False

    today = datetime.now().date()
    current_monday = today - timedelta(days=today.weekday())
    today_formatted = today.strftime(DATE_FORMAT)
    current_monday_formatted = current_monday.strftime(DATE_FORMAT)

    try:
        session_reports_data = supabase_client.select_within_range(fields="*",
                                                                   filters={
                                                                       "therapist_id": therapist_id
                                                                   },
                                                                   range_start=current_monday_formatted,
                                                                   range_end=today_formatted,
                                                                   column_marker="created_at",
                                                                   limit=20,
                                                                   table_name=ENCRYPTED_SESSION_REPORTS_TABLE_NAME)
        return len(session_reports_data['data']) >= NUM_SESSIONS_IN_BASIC_PLAN
    except Exception as e:
        raise Exception(e)
