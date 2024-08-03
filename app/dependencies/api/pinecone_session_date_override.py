"""
Wrapper to carry data about a session date that wants to be included
in any vector queries (regardless of what the query returns naturally)

Arguments:
output_prefix_override – a prefix to be included in the message prompt prior to the session_date vectors.
output_suffix_override – a suffix to be included in the message prompt prior to the session_date vectors.
session_date – the session_date for which to retrieve the respective vectors.
"""
class PineconeQuerySessionDateOverride:
    def __init__(self, output_prefix_override, output_suffix_override, session_date):
        self.output_prefix_override = output_prefix_override
        self.output_suffix_override = output_suffix_override
        self.session_date = session_date
