
current_speaker_content = str()
current_speaker:str = None
has_attached_precursor = False
    
def clean_transcription(output: str):
    current_speaker = output[0]["alternatives"][0]["speaker"]
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

        if speaker != current_speaker:
            __handle_activity_change_of_speaker(speaker,
                                                content,
                                                attaches_to if has_attaches_to else None,
                                                end_of_sentence if has_end_of_sentence else None)
            continue

        # Speaker remains the same
        __handle_activity_current_speaker(content,
                                          attaches_to if has_attaches_to else None,
                                          end_of_sentence if has_end_of_sentence else None)
        continue

def __handle_activity_change_of_speaker(speaker: str, content: str, **kwargs):
    # Update current speaker and capture content
    current_speaker = speaker
    current_speaker_content = content

    if "attaches_to" in kwargs:
        attaches_to = kwargs.get("attaches_to")
        
    if "end_of_sentence" in kwargs:
        end_of_sentences = kwargs.get("end_of_sentence")

def __handle_activity_current_speaker(content: str, **kwargs):
    if "attaches_to" in kwargs:
        attaches_to = kwargs.get("attaches_to")
        
    if "end_of_sentence" in kwargs:
        end_of_sentences = kwargs.get("end_of_sentence")

def __append_to_current_speaker_content(new_content: str,
                                        prepend_space: bool,
                                        append_space: bool):
    content_list = [new_content]
    if prepend_space:
        content_list.insert(0, " ")
    if append_space:
        content_list.append(" ")
    current_speaker_content.join(content_list)