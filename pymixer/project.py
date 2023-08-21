"""
Mix multiple tracks to a single 2-channel track.

Author: Nikolay Lysenko
"""


import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pretty_midi
from sinethesizer.utils.misc import sum_two_sounds

from pymixer.midi import fix_fluidsynth_last_note_termination, merge_midi_objects, replace_programs
from pymixer.sound_makers import FluidsynthSoundMaker, SoundMaker
from pymixer.wav import read_wav_file


@dataclass
class MidiTrackSpec:
    """Specification of a track based on MIDI files."""
    sound_maker: SoundMaker
    start_pattern: str
    end_pattern: str


@dataclass
class MidiStub:
    """MIDI stub of a track."""
    sound_maker: SoundMaker
    midi_objects: list[pretty_midi.PrettyMIDI] = field(default_factory=list)
    start_time: float = 0.0
    offsets: list[float] = field(default_factory=list)


class WavTrackSpec:
    """Specification of a track based on a single WAV file."""
    file_name: str
    start_time: float = 0.0


@dataclass
class Track:
    """WAV-like air pressure timeline and meta-information on it."""
    timeline: np.ndarray
    start_time: float = 0.0


class Project:
    """
    Mixing project.
    """

    def __init__(
            self,
            input_dir: str,
            midi_tracks_specs: list[MidiTrackSpec],
            wav_tracks_specs: Optional[list[WavTrackSpec]] = None,
            frame_rate: int = 48000,
            offsets: Optional[list[float]] = None,
    ):
        """Initialize an instance."""
        self.input_dir = input_dir
        self.midi_tracks_specs = midi_tracks_specs
        self.wav_tracks_specs = wav_tracks_specs
        self.frame_rate = frame_rate
        self.offsets = offsets
        self.tracks = self._make_tracks()

    def _get_offsets(self) -> list[float]:
        """Generate copy of offsets which can be modified."""
        n_midi_files = 0
        for file_name in sorted(os.listdir(self.input_dir)):
            if file_name.split('.')[-1] in ["MID", "MIDI", "mid", "midi"]:
                n_midi_files += 1
        if self.offsets is None:
            return [0 for _ in range(n_midi_files)]
        if len(self.offsets) != n_midi_files - 1:
            raise ValueError(
                f"Number of offsets is equal to {len(self.offsets)}, "
                f"but {n_midi_files - 1} offsets are expected."
            )
        offsets = [x for x in self.offsets] + [0.0]  # Extra offset for the last file.
        return offsets

    def _find_dependent_tracks(self, file_name: str) -> list[int]:
        """Find indices of tracks that use a file."""
        results = []
        for index, track_spec in enumerate(self.midi_tracks_specs):
            if track_spec.start_pattern <= file_name <= track_spec.end_pattern:
                results.append(index)
        return results

    def _make_midi_stubs(self) -> list[MidiStub]:
        """Make MIDI stubs."""
        current_time = 0
        stubs = [MidiStub(spec.sound_maker) for spec in self.midi_tracks_specs]
        offsets = self._get_offsets()
        for file_name in sorted(os.listdir(self.input_dir)):
            if file_name.split('.')[-1] not in ["MID", "MIDI", "mid", "midi"]:
                continue
            offset = offsets.pop(0)
            midi_object = pretty_midi.PrettyMIDI(os.path.join(self.input_dir, file_name))
            for index in self._find_dependent_tracks(file_name):
                stub = stubs[index]
                if not stub.midi_objects:
                    stub.start_time = current_time
                stub.midi_objects.append(midi_object)
                stub.offsets.append(offset)
            notes = [
                note
                for instrument in midi_object.instruments for note in instrument.notes
                if note.velocity > 0
            ]
            duration = max(note.end for note in notes) - min(note.start for note in notes)
            current_time += duration + offset
        return stubs

    def _make_tracks(self) -> list[Track]:
        """Make tracks."""
        tracks = []
        stubs = self._make_midi_stubs()
        for stub in stubs:
            midi_object = merge_midi_objects(stub.midi_objects, stub.offsets[:-1])
            if isinstance(stub.sound_maker, FluidsynthSoundMaker):
                instrument_name_to_program = stub.sound_maker.instrument_name_to_program
                midi_object = replace_programs(midi_object, instrument_name_to_program)
                midi_object = fix_fluidsynth_last_note_termination(midi_object)
            midi_object.write(stub.sound_maker.path_to_midi_file)
            timeline = stub.sound_maker.make_sound(self.frame_rate)
            track = Track(timeline, stub.start_time)
            tracks.append(track)
        for wav_track_spec in self.wav_tracks_specs or []:
            path_to_wav_file = os.path.join(self.input_dir, wav_track_spec.file_name)
            timeline = read_wav_file(path_to_wav_file, self.frame_rate)
            track = Track(timeline, wav_track_spec.start_time)
            tracks.append(track)
        return tracks

    def mix(
            self,
            gains: Optional[list[float]] = None,
            opening_silence: float = 0.0,
            trailing_silence: float = 0.0,
            grouped_track_indices: Optional[list[list[int]]] = None
    ) -> np.ndarray:
        """
        Mix individual tracks to one or more 2-channel air pressure timelines.

        :param gains:
            list of gains for each track; by default, gains are not changed
        :param opening_silence:
            duration of opening silence (in seconds)
        :param trailing_silence:
            duration of trailing silence (in seconds)
        :param grouped_track_indices:
            groups of original tracks to be mixed together to a single output track;
            by default, all tracks form one group;
            if this argument is passed and a track is missed there, the track is ignored
        :return:
            array of shape (n_channels, n_samples) where `n_channels = 2 * n_groups`
        """
        n_channels_per_track = 2

        gains = gains or [1.0 for _ in self.tracks]
        if len(gains) != len(self.tracks):
            raise ValueError(
                f"Length of `gains` is {len(gains)}, but it must be equal to {len(self.tracks)}."
            )
        grouped_track_indices = grouped_track_indices or [list(range(len(self.tracks)))]
        flat_indices = [index for group in grouped_track_indices for index in group]
        if any(index != int(round(index)) for index in flat_indices):
            raise ValueError("Only integer values are allowed in `grouped_track_indices`.")
        if min(flat_indices) < -len(self.tracks) or max(flat_indices) >= len(self.tracks):
            raise ValueError("Out-of-range indices found in `grouped_track_indices`.")

        mixed_timelines = []
        for group_track_indices in grouped_track_indices:
            group_data = [(self.tracks[i], gains[i]) for i in group_track_indices]
            mixed_timeline = np.array([[], []], dtype=np.float64)
            for track, gain in group_data:
                current_timeline = np.hstack((
                    np.zeros((n_channels_per_track, int(round(self.frame_rate * track.start_time)))),
                    gain * track.timeline
                ))
                mixed_timeline = sum_two_sounds(mixed_timeline, current_timeline)
            mixed_timeline = np.hstack((
                np.zeros((n_channels_per_track, int(round(self.frame_rate * opening_silence)))),
                mixed_timeline,
                np.zeros((n_channels_per_track, int(round(self.frame_rate * trailing_silence)))),
            ))
            mixed_timelines.append(mixed_timeline)

        max_length = max(mixed_timeline.shape[1] for mixed_timeline in mixed_timelines)
        aligned_timelines = []
        for mixed_timeline in mixed_timelines:
            aligned_timeline = np.hstack((
                mixed_timeline,
                np.zeros((n_channels_per_track, max_length - mixed_timeline.shape[1]))
            ))
            aligned_timelines.append(aligned_timeline)
        result = np.vstack(aligned_timelines)
        return result
