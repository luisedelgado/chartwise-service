import os

class SessionContainer:
    def __init__(self):
        self.environment = os.environ.get("ENVIRONMENT")
        self._user_id = None

    @property
    def user_id(self):
        return self._user_id

    @user_id.setter
    def user_id(self, user_id):
        # optional: add validation or transformation here
        self._user_id = user_id

session_container = SessionContainer()
