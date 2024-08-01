class FakeSession:

    def __init__(self,
                 return_authenticated_session: bool,
                 fake_access_token: str,
                 fake_refresh_token: str):
        self.return_authenticated_session = return_authenticated_session
        self.fake_access_token = fake_access_token
        self.fake_refresh_token = fake_refresh_token

    def dict(self):
        if self.return_authenticated_session:
            return {
                "user": {
                    "role": "authenticated"
                },
                "session": {
                    "access_token": self.fake_access_token,
                    "refresh_token": self.fake_refresh_token
                }
            }
        return {}
