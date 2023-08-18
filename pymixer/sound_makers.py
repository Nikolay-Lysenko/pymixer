"""
Convert input files to in-memory WAV-like air pressure timelines.

Author: Nikolay Lysenko
"""


import subprocess
import tempfile
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np
from sinethesizer.io import (
    convert_midi_to_events, convert_events_to_timeline, create_instruments_registry
)

from pymixer.wav import convert_raw_pcm_to_wav, read_wav_file


class SoundMaker(ABC):
    """Abstract class for converting MIDI files to arrays with air pressure timelines."""
    path_to_midi_file: str

    @abstractmethod
    def make_sound(self, frame_rate: int) -> np.ndarray:
        """
        Generate 2-channel air pressure timeline.

        :param frame_rate:
            desired number of samples per second (also known as sampling frequency)
        """
        pass


class FluidsynthSoundMaker(SoundMaker):
    """Converter of MIDI files to WAV-like timelines with `fluidsynth`."""

    def __init__(
            self,
            path_to_midi_file: str,
            path_to_soundfont: str,
            instrument_name_to_program: dict[str, int],
            fluidsynth_chorus: bool = False,
            fluidsynth_reverb: bool = False,
            fluidsynth_gain: float = 1.0
    ):
        """Initialize an instance."""
        self.path_to_midi_file = path_to_midi_file
        self.path_to_soundfont = path_to_soundfont
        self.instrument_name_to_program = instrument_name_to_program
        self.fluidsynth_chorus = fluidsynth_chorus
        self.fluidsynth_reverb = fluidsynth_reverb
        self.fluidsynth_gain = fluidsynth_gain

    def make_sound(self, frame_rate: int) -> np.ndarray:
        """
        Create 2-channel air pressure timeline.

        :param frame_rate:
            desired number of samples per second (also known as sampling frequency)
        """
        with tempfile.NamedTemporaryFile() as tmp_file:
            command = (
                f"fluidsynth -r {frame_rate} -g {self.fluidsynth_gain} "
                f"{'-C0 ' if not self.fluidsynth_chorus else ''}"
                f"{'-R0 ' if not self.fluidsynth_reverb else ''}"
                "-O float "
                f"-F {tmp_file.name} "
                f"{self.path_to_soundfont} {self.path_to_midi_file}"
            )
            subprocess.run(command.split())
            try:
                timeline = read_wav_file(tmp_file.name, frame_rate)
            # Some installations of FluidSynth produce raw PCM files instead of WAV files.
            except ValueError as e:
                if "not understood. Only 'RIFF' and 'RIFX' supported" not in str(e):
                    raise e
                with tempfile.NamedTemporaryFile(suffix='.wav') as tmp_wav_file:
                    convert_raw_pcm_to_wav(tmp_file.name, tmp_wav_file.name, frame_rate)
                    timeline = read_wav_file(tmp_wav_file.name, frame_rate)
        return timeline


class SinethesizerSoundMaker(SoundMaker):
    """Converter of MIDI files to WAV-like timelines with `sinethesizer`."""

    def __init__(
            self,
            path_to_midi_file: str,
            path_to_presets: str,
            track_name_to_instrument: dict[str, str],
            track_name_to_effects: Optional[dict[str, str]] = None,
            peak_amplitude: Optional[float] = None
    ):
        """Initialize an instance."""
        self.path_to_midi_file = path_to_midi_file
        self.path_to_presets = path_to_presets
        self.track_name_to_instrument = track_name_to_instrument
        self.track_name_to_effects = track_name_to_effects or {}
        self.peak_amplitude = peak_amplitude

    def make_sound(self, frame_rate: int) -> np.ndarray:
        """
        Generate 2-channel air pressure timeline.

        :param frame_rate:
            desired number of samples per second (also known as sampling frequency)
        """
        settings = {
            'frame_rate': frame_rate,
            'trailing_silence': 0.0,
            'peak_amplitude': self.peak_amplitude,
            'instruments_registry': create_instruments_registry(self.path_to_presets),
            'midi': {
                'track_name_to_instrument': self.track_name_to_instrument,
                'track_name_to_effects': self.track_name_to_effects,
            }
        }
        events = convert_midi_to_events(self.path_to_midi_file, settings)
        timeline = convert_events_to_timeline(events, settings)
        return timeline


# class WavSoundMaker(SoundMaker):
#     """Dummy converter of WAV files to WAV-like timelines."""
#
#     def __init__(self, path_to_wav_file: str):
#         """Initialize an instance."""
#         self.path_to_wav_file = path_to_wav_file
#
#     def make_sound(self, frame_rate: int) -> np.ndarray:
#         """
#         Generate 2-channel air pressure timeline.
#
#         :param frame_rate:
#             desired number of samples per second (also known as sampling frequency)
#         """
#         timeline = read_wav_file(self.path_to_wav_file, frame_rate)
#         return timeline
