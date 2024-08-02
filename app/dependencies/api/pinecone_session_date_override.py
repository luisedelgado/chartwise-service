class PineconeQuerySessionDateOverride:
    def __init__(self, output_prefix_override, output_suffix_override, session_date):
        self.output_prefix_override = output_prefix_override
        self.output_suffix_override = output_suffix_override
        self.session_date = session_date
