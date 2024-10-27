import os
import warnings

# Suppress the ffmpeg warning
warnings.filterwarnings("ignore", category=RuntimeWarning, module='pydub.utils')

from pydub import AudioSegment

# Define a list of compressed formats where converting to WAV would result in a larger file
COMPRESSED_FORMATS = ['.mp3', '.ogg', '.aac', '.flac', '.m4a']

COMPRESSED_SAMPLE_RATE = 16000
MIN_SIZE_REDUCTION = 20
MIN_FILE_SIZE_KB = 500

def get_output_filepath_for_sample_rate_reduction(input_file_directory: str,
                                                  input_filename_without_ext: str) -> str:
    return input_file_directory + input_filename_without_ext + "_reduced_sample_rate.wav"

def reduce_sample_rate_if_worthwhile(input_filepath: str, output_filepath: str) -> bool:
    if len(input_filepath or '') == 0 or len(output_filepath or '') == 0:
        return False

    # Check if input format is in a compressed format (e.g., mp3, ogg, etc.)
    file_extension = os.path.splitext(input_filepath)[1].lower()
    if file_extension in COMPRESSED_FORMATS:
        # Skip reduction as it's likely to increase the file size
        return False

    # Load the audio file
    audio = AudioSegment.from_file(input_filepath)

    # Get the original sample rate
    original_sample_rate = audio.frame_rate

    # Check if the original sample rate is already low.
    # If it's already below our threshold, we skip the reduction.
    if original_sample_rate <= COMPRESSED_SAMPLE_RATE:
        return False

    # Check if the file is large enough to justify reduction
    original_file_size_kb = os.path.getsize(input_filepath) / 1024  # File size in KB
    if original_file_size_kb < MIN_FILE_SIZE_KB:
        return False

    # Apply the sample rate reduction, and export file
    reduced_audio = audio.set_frame_rate(COMPRESSED_SAMPLE_RATE)
    reduced_audio.export(output_filepath, format="wav")    
    return True
