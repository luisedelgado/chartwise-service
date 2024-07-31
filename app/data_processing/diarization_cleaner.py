import json

from fastapi import status
from typing import Dict

from ..api.supabase_base_class import SupabaseBaseClass
from ..internal.logging import Logger

"""
Class meant to be used for cleaning diarization records.
"""
class DiarizationCleaner:
    def __init__(self):
        self._current_speaker_content = str()
        self._current_speaker: str = None
        self._transcription = []
        self._entry_start_time = str()

    """
    Returns a JSON representation of the transcription after having been transformed for easier manipulation.

    Arguments:
    input – the diarization input.
    auth_manager – the auth manager to be leveraged internally.
    """
    def clean_transcription(self, input: str, supabase_manager: SupabaseBaseClass) -> str:
        self._current_speaker = input[0]["alternatives"][0]["speaker"]
        for obj in input:
            speaker = obj["alternatives"][0]["speaker"]
            content = obj["alternatives"][0]["content"]
            start_time = obj["start_time"]
            end_time = obj["end_time"]
            has_end_of_sentence = False
            has_attaches_to = False

            if "attaches_to" in obj:
                has_attaches_to = True
                attaches_to = obj["attaches_to"]
                if attaches_to.lower() != "previous":
                    Logger(supabase_manager=supabase_manager).log_diarization_event(error_code=status.HTTP_417_EXPECTATION_FAILED,
                                                                                    description="Seeing Speechmatics' \'attaches_to\' field with value: {attaches_to}")

            if "is_eos" in obj:
                has_end_of_sentence = True
                end_of_sentence = obj["is_eos"]
                
            if len(self._current_speaker_content or '') == 0:
                self._entry_start_time = start_time
                
            # Determine whether or not the current content is attached to a previous token.
            skip_space = (len(self._current_speaker_content) == 0) or (has_attaches_to and attaches_to.lower() == "previous")
            
            if speaker != self._current_speaker:
                # Update current speaker
                self._current_speaker = speaker

            # Check if it's an end of a sentence
            if has_end_of_sentence and end_of_sentence == True:
                # Register current content as a standalone paragraph
                self.__append_speaker_content(content,
                                              prepend_space=(not skip_space))
                self._transcription.append(self.__get_entry_node(end_time))
                self._current_speaker_content = str()
                self._entry_start_time = str()
                continue

            # Append run-on content
            self.__append_speaker_content(content, prepend_space=(not skip_space))

        return json.dumps(self._transcription)

    """
    Helper method for appending data to the current speaker's run-on content.

    Arguments:
    content – the content to be appended.
    prepend_space – flag determining if we prepend the content with a space character.
    """
    def __append_speaker_content(self, content: str, prepend_space: bool):
        content_list = [self._current_speaker_content, content]
        if prepend_space:
            self._current_speaker_content = " ".join(str(item) for item in content_list)
            return

        self._current_speaker_content = "".join(str(item) for item in content_list)

    """
    Helper method for getting a Dict entry containing the current speaker's at-hand content.

    Arguments:
    entry_end_time – the time at which the speaker's intervention finished.
    """
    def __get_entry_node(self, entry_end_time: str) -> Dict:
        return {
            "content": self._current_speaker_content,
            "current_speaker": self._current_speaker,
            "start_time": self._entry_start_time,
            "end_time": entry_end_time
        }
