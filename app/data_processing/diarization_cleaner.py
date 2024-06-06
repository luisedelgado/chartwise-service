import json
from typing import Dict

class DiarizationCleaner:
    def __init__(self):
        self._current_speaker_content = str()
        self._current_speaker: str = None
        self._transcription = []
        self._entry_start_time = str()

    def clean_transcription(self, output: str) -> str:
        self._current_speaker = output[0]["alternatives"][0]["speaker"]
        for obj in output:
            speaker = obj["alternatives"][0]["speaker"]
            content = obj["alternatives"][0]["content"]
            start_time = obj["start_time"]
            end_time = obj["end_time"]
            has_end_of_sentence = False
            has_attaches_to = False

            if "attaches_to" in obj:
                has_attaches_to = True
                attaches_to = obj["attaches_to"]

            if "is_eos" in obj:
                has_end_of_sentence = True
                end_of_sentence = obj["is_eos"]
                
            if len(self._current_speaker_content) == 0:
                self._entry_start_time = start_time
                
            # Determine whether or not the current content is attached to a previous token.
            skip_space = (len(self._current_speaker_content) == 0) or (has_attaches_to and attaches_to.lower() == "previous")
            
            if speaker != self._current_speaker:
                # Update current speaker
                self._current_speaker = speaker

            # It's the same speaker, check if it's an end of a sentence
            if has_end_of_sentence and end_of_sentence == True:
                # Register current content as a standalone paragraph
                self.__append_speaker_content(content,
                                              prepend_space=(not skip_space))
                self._transcription.append(self.__get_entry_node(end_time))
                self._current_speaker_content = str()
                self._entry_start_time = str()
                continue

            # Speaker remains the same, we're just appending run-on content
            self.__append_speaker_content(content, prepend_space=(not skip_space))

        return json.dumps(self._transcription)

    def __append_speaker_content(self, content: str, prepend_space: bool):
        content_list = [self._current_speaker_content, content]
        if prepend_space:
            self._current_speaker_content = " ".join(str(item) for item in content_list)
            return

        self._current_speaker_content = "".join(str(item) for item in content_list)

    def __get_entry_node(self, entry_end_time: str) -> Dict:
        return {
            "content": self._current_speaker_content,
            "current_speaker": self._current_speaker,
            "start_time": self._entry_start_time,
            "end_time": entry_end_time
        }
