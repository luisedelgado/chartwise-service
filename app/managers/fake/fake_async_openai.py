class FakeOpenAICompletions:

    def create(self,
               model: str,
               messages: list,
               temperature: int,
               max_tokens: int):
        print("created")

class FakeOpenAIChat:

    def __init__(self):
        self.completions = FakeOpenAICompletions()

class FakeAsyncOpenAI:

    def __init__(self):
        self.chat = FakeOpenAIChat()
