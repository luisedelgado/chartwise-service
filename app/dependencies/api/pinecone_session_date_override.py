class PineconeQuerySessionDateOverride:
    """
    Wrapper to carry data about a session date that wants to be included
    in any vector queries (regardless of what the query returns naturally)

    Arguments:
    session_date – the session_date for which to retrieve the respective vectors.
    output_prefix_override – an optional prefix to be included in the message prompt prior to the session_date vectors.
    output_suffix_override – an optional suffix to be included in the message prompt prior to the session_date vectors.
    """
    def __init__(
        self,
        session_date: str,
        output_prefix_override: str = None,
        output_suffix_override: str = None
    ):
        self.output_prefix_override = output_prefix_override
        self.output_suffix_override = output_suffix_override
        self.session_date = session_date
