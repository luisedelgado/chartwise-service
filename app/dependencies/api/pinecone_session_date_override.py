from enum import Enum

class PineconeQuerySessionDateOverrideType(Enum):
    SINGLE_DATE = "single_date"
    DATE_RANGE = "date_range"

class PineconeQuerySessionDateOverride:
    """
    Wrapper to carry data about a session date that wants to be included
    in any vector queries (regardless of what the query returns naturally)

    Arguments:
    override_type – the type of override to be applied.
    session_date_start – the session_date_start for which to retrieve the respective vectors.
    session_date_end – the optional session_date_end for which to retrieve the respective vectors.
    output_prefix_override – an optional prefix to be included in the message prompt prior to the session_date vectors.
    output_suffix_override – an optional suffix to be included in the message prompt prior to the session_date vectors.
    """
    def __init__(
        self,
        override_type: PineconeQuerySessionDateOverrideType,
        session_date_start: str,
        session_date_end: str | None = None,
        output_prefix_override: str | None = None,
        output_suffix_override: str | None = None
    ):
        self.override_type = override_type
        self.output_prefix_override = output_prefix_override
        self.output_suffix_override = output_suffix_override
        self.session_date_start = session_date_start

        if override_type == PineconeQuerySessionDateOverrideType.DATE_RANGE and session_date_end is None:
            raise ValueError("session_date_end must be provided for DATE_RANGE override type")

        self.session_date_end = session_date_end
