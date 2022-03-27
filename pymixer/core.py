"""
Define key concepts and top-level interfaces.

Author: Nikolay Lysenko
"""


import subprocess
import tempfile
from abc import ABC, abstractmethod
from typing import Optional, Union

import numpy as np
from scipy.io import wavfile
from sinethesizer.io import (
    convert_midi_to_events, convert_events_to_timeline, create_instruments_registry
)
from sinethesizer.utils.misc import sum_two_sounds


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


class AbstractInput(ABC):
    """Abstract input of `Project` class."""

    @abstractmethod
    def create_track(self, frame_rate: int) -> np.ndarray:
        """
        Create air pressure timeline with two channels.

        :param frame_rate:
            desired number of samples per second (also known as sampling frequency)
        """
        pass


class FluidsynthMidiInput(AbstractInput):
    """MIDI input that is going to be played with `fluidsynth`."""

    def __init__(
            self,
            path_to_midi_file: str,
            path_to_soundfont: str,
            start_time: float = 0.0,
            fluidsynth_gain: float = 1.0,
            fluidsynth_chorus: bool = False,
            fluidsynth_reverb: bool = False
    ):
        """Initialize an instance."""
        self.path_to_midi_file = path_to_midi_file
        self.path_to_soundfont = path_to_soundfont
        self.start_time = start_time
        self.fluidsynth_gain = fluidsynth_gain
        self.fluidsynth_chorus = fluidsynth_chorus
        self.fluidsynth_reverb = fluidsynth_reverb

    def create_track(self, frame_rate: int) -> np.ndarray:
        """
        Create air pressure timeline with two channels.

        :param frame_rate:
            desired number of samples per second (also known as sampling frequency)
        """
        with tempfile.NamedTemporaryFile() as tmp_file:
            command = (
                f"fluidsynth -r {frame_rate} -g {self.fluidsynth_gain} "
                f"{'-C0 ' if not self.fluidsynth_chorus else ''}"
                f"{'-R0 ' if not self.fluidsynth_reverb else ''}"
                f"-F {tmp_file.name} "
                f"{self.path_to_soundfont} {self.path_to_midi_file}"
            )
            subprocess.run(command.split())
            timeline = read_wav_file(tmp_file.name, frame_rate)
        return timeline


class SinethesizerMidiInput(AbstractInput):
    """MIDI input that is going to be played with `sinethesizer`."""

    def __init__(
            self,
            path_to_midi_file: str,
            path_to_presets: str,
            track_name_to_instrument: dict[str, str],
            track_name_to_effects: Optional[dict[str, str]] = None,
            start_time: float = 0.0,
            peak_amplitude: Optional[float] = None
    ):
        """Initialize an instance."""
        self.path_to_midi_file = path_to_midi_file
        self.path_to_presets = path_to_presets
        self.track_name_to_instrument = track_name_to_instrument
        self.track_name_to_effects = track_name_to_effects or {}
        self.start_time = start_time
        self.peak_amplitude = peak_amplitude

    def create_track(self, frame_rate: int) -> np.ndarray:
        """
        Create air pressure timeline with two channels.

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


class WavInput(AbstractInput):
    """WAV input."""

    def __init__(
            self,
            path_to_wav_file: str,
            start_time: float = 0.0,
    ):
        """Initialize an instance."""
        self.path_to_wav_file = path_to_wav_file
        self.start_time = start_time

    def create_track(self, frame_rate: int) -> np.ndarray:
        """
        Create air pressure timeline with two channels.

        :param frame_rate:
            desired number of samples per second (also known as sampling frequency)
        """
        timeline = read_wav_file(self.path_to_wav_file, frame_rate)
        return timeline


class Project:
    """Mixing project."""

    def __init__(
            self,
            inputs: list[Union[FluidsynthMidiInput, SinethesizerMidiInput, WavInput]],
            frame_rate: int
    ):
        """Initialize an instance."""
        self.inputs = inputs
        self.frame_rate = frame_rate
        self.tracks = [x.create_track(self.frame_rate) for x in self.inputs]

    def mix(self, gains: Optional[list[float]] = None) -> np.ndarray:
        """
        Mix all project tracks into a single 2-channel air pressure timeline.

        :param gains:
            list of gains for each track; by default, gains are not changed
        :return:
            array of shape (n_channels, n_samples)
        """
        gains = gains or [1.0 for _ in self.tracks]
        output = np.array([[], []], dtype=np.float64)
        for track, input_params, gain in zip(self.tracks, self.inputs, gains):
            processed_track = np.hstack((
                np.zeros((track.shape[0], int(round(self.frame_rate * input_params.start_time)))),
                gain * track
            ))
            output = sum_two_sounds(output, processed_track)
        return output
