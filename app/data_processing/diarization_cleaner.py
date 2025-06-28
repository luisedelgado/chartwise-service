import json

from typing import Dict

"""
Class meant to be used for cleaning diarization records.
"""
class DiarizationCleaner:
    def __init__(self):
        self._current_speaker_content = str()
        self._current_speaker: str | None = None
        self._transcription = []
        self._entry_start_time = None
        self._entry_end_time = None

    """
    Returns a JSON representation of the transcription after having been transformed for easier manipulation.

    Arguments:
    raw_diarization – the object with the diarization content.
    """
    def clean_transcription(self, raw_diarization: list) -> str:
        self._current_speaker = raw_diarization[0]["speaker"]
        self._entry_start_time = raw_diarization[0]["start"]
        self._entry_end_time = raw_diarization[0]["end"]
        for obj in raw_diarization:
            start_time = obj['start']
            end_time = obj['end']
            content = obj['transcript']
            speaker = obj['speaker']

            prepend_space = (speaker == self._current_speaker and
                             len(self._current_speaker_content or '') > 0)

            if speaker != self._current_speaker:
                # Register previous speaker's section as a standalone paragraph
                self._transcription.append(self._get_entry_node())

                # Start tracking new speaker's block of information
                self._current_speaker = speaker
                self._current_speaker_content = str()
                self._append_speaker_content(content,
                                             prepend_space=prepend_space)
                self._entry_start_time = start_time
                self._entry_end_time = end_time
                continue

            # Append run-on content
            self._entry_end_time = end_time
            self._append_speaker_content(content, prepend_space=prepend_space)

        if len(self._current_speaker_content or '') > 0:
            self._transcription.append(self._get_entry_node())

        return json.dumps(self._transcription, ensure_ascii=False)

    """
    Helper method for appending data to the current speaker's run-on content.

    Arguments:
    content – the content to be appended.
    prepend_space – flag determining if we prepend the content with a space character.
    """
    def _append_speaker_content(self, content: str, prepend_space: bool):
        content_list = [self._current_speaker_content, content]
        if prepend_space:
            self._current_speaker_content = " ".join(str(item) for item in content_list)
            return

        self._current_speaker_content = "".join(str(item) for item in content_list)

    """
    Helper method for getting a Dict entry containing the current speaker's at-hand content.
    """
    def _get_entry_node(self) -> Dict:
        return {
            "content": self._current_speaker_content,
            "current_speaker": self._current_speaker,
            "start_time": self._entry_start_time,
            "end_time": self._entry_end_time
        }

    """
    Flattens diarization result into a single string object.
    """
    @staticmethod
    def flatten_diarization(diarization: list):
        formatted_objects = []
        for obj in diarization:
            content = obj.get('content', '')
            current_speaker = obj.get('current_speaker', '')
            start_time = obj.get('start_time', '')
            end_time = obj.get('end_time', '')

            # Format entries properly, ensuring values are enclosed in quotes
            entry = "{{'content': '{}', 'current_speaker': '{}', 'start_time': '{}', 'end_time': '{}'}}".format(
                content.replace("'", "\\'"),
                current_speaker,
                start_time,
                end_time
            )
            formatted_objects.append(entry)

        flattened_diarization = "[" + ", ".join(formatted_objects) + "]"
        return flattened_diarization
