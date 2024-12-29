from enum import Enum

class Gender(Enum):
    UNDEFINED = "undefined"
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    RATHER_NOT_SAY = "rather_not_say"

class SessionUploadStatus(Enum):
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"

class MediaType(Enum):
    IMAGE = "image"
    AUDIO = "audio"
