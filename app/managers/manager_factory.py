from .fake.fake_assistant_manager import FakeAssistantManager
from .fake.fake_audio_processing_manager import FakeAudioProcessingManager
from .fake.fake_auth_manager import FakeAuthManager
from .fake.fake_image_processing_manager import FakeImageProcessingManager
from .implementations.assistant_manager import AssistantManager
from .implementations.audio_processing_manager import AudioProcessingManager
from .implementations.auth_manager import AuthManager
from .implementations.image_processing_manager import ImageProcessingManager

class ManagerFactory:

    @staticmethod
    def create_audio_processing_manager(environment: str):
        assert len(environment) > 0, "Received invalid environment value"
        if environment == 'testing':
            return FakeAudioProcessingManager()
        return AudioProcessingManager()

    @staticmethod
    def create_image_processing_manager(environment: str):
        assert len(environment) > 0, "Received invalid environment value"
        if environment == 'testing':
            return FakeImageProcessingManager()
        return ImageProcessingManager()

    @staticmethod
    def create_auth_manager(environment: str):
        assert len(environment) > 0, "Received invalid environment value"
        if environment == 'testing':
            return FakeAuthManager()
        return AuthManager()

    @staticmethod
    def create_assistant_manager(environment: str):
        assert len(environment) > 0, "Received invalid environment value"
        if environment == 'testing':
            return FakeAssistantManager()
        return AssistantManager()
