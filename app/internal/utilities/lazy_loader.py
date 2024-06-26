class LazyLoader:
    def __init__(self, function):
        self.function = function
        self._cached_value = None

    def __call__(self):
        if self._cached_value is None:
            self._cached_value = self.function()
        return self._cached_value

    @property
    def app(self):
        if self._cached_value is None:
            self._cached_value = self.function()
        return self._cached_value

    @app.setter
    def app(self, value):
        self._cached_value = value
