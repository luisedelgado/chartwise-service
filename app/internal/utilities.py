import os

"""
Cleans up the incoming set of files from the local directory.

Arguments:
files  – the set of files to be cleaned up
"""
async def clean_up_files(files):
    for file in files:
        os.remove(file)
