from datetime import datetime, timedelta

from .datetime_handler import DATE_FORMAT
from ..schemas import ENCRYPTED_SESSION_REPORTS_TABLE_NAME
from ...dependencies.dependency_container import AwsDbBaseClass

NUM_SESSIONS_IN_BASIC_PLAN = 20

def reached_subscription_tier_usage_limit(tier: str,
                                          therapist_id: str,
                                          aws_db_client: AwsDbBaseClass,
                                          is_free_trial_active: bool) -> bool:
    if is_free_trial_active or tier == "premium":
        return False

    today = datetime.now().date()
    current_monday = today - timedelta(days=today.weekday())
    today_formatted = today.strftime(DATE_FORMAT)
    current_monday_formatted = current_monday.strftime(DATE_FORMAT)

    try:
        session_reports_data = aws_db_client.select(
            user_id=therapist_id,
            fields="*",
            filters={
                "therapist_id": therapist_id,
                "created_at__gte": current_monday_formatted,
                "created_at__lte": today_formatted,
            },
            table_name=ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
            limit=20,
        )
        return len(session_reports_data['data']) >= NUM_SESSIONS_IN_BASIC_PLAN
    except Exception as e:
        raise Exception(e)
