"""
Provide utilities for working with WAV files.

Author: Nikolay Lysenko
"""


import subprocess
import sys

import numpy as np
from scipy.io import wavfile


def convert_raw_pcm_to_wav(input_path: str, output_path: str, frame_rate: int) -> None:
    """Convert raw PCM file to a true WAV file by adding header to it."""
    byte_order = 'le' if sys.byteorder == 'little' else 'be'
    command = f"ffmpeg -f float32{byte_order} -ar {frame_rate} -ac 2 -i {input_path} {output_path}"
    subprocess.run(command.split())


def read_wav_file(path_to_wav_file: str, expected_frame_rate: int) -> np.ndarray:
    """
    Read air pressure timeline from a WAV file into an array of shape (n_channels, n_samples).

    :param path_to_wav_file:
        path to WAV file
    :param expected_frame_rate:
        expected number of samples per second (also known as sampling frequency)
    :return:
        air pressure timeline as 2D array of shape (n_channels, n_samples)
    """
    frame_rate, timeline = wavfile.read(path_to_wav_file)
    if frame_rate != expected_frame_rate:
        raise ValueError(f"Frame rate is {frame_rate}, but {expected_frame_rate} is expected.")
    timeline = timeline.T
    if timeline.ndim == 1:
        timeline = np.reshape(timeline, (1, -1))
    if timeline.shape[0] == 1:
        timeline = np.vstack((timeline, timeline))
    return timeline
