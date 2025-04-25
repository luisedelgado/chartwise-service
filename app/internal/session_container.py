import os

class SessionContainer:
    def __init__(self):
        self.environment = os.environ.get("ENVIRONMENT")
        self._user_id = None
        self._session_id = None

    @property
    def session_id(self):
        return self._session_id

    @session_id.setter
    def session_id(self, session_id):
        self._session_id = session_id

    @property
    def user_id(self):
        return self._user_id

    @user_id.setter
    def user_id(self, user_id):
        self._user_id = user_id

session_container = SessionContainer()
