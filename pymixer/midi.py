"""
Provide utilities for working with MIDI files.

Author: Nikolay Lysenko
"""


from copy import deepcopy
from typing import Optional

import pretty_midi


def merge_midi_objects(
        midi_objects: list[pretty_midi.PrettyMIDI],
        offsets: Optional[list[float]] = None
) -> pretty_midi.PrettyMIDI:
    """
    Merge MIDI objects sequentially into a single MIDI object.

    :param midi_objects:
        MIDI objects to be merged
    :param offsets:
        durations of offsets (in seconds) between successive MIDI objects;
        by default, there are no offsets; negative values are also supported
    :return:
        merged MIDI object
    """
    if offsets is None:
        offsets = [0 for _ in range(len(midi_objects) - 1)]
    if len(offsets) != len(midi_objects) - 1:
        raise ValueError(
            f"Length of `offsets` is {len(offsets)}, but it should be {len(midi_objects) - 1}."
        )
    offsets = [0.0] + offsets

    instruments = {}
    current_time = 0
    for midi_object, offset in zip(midi_objects, offsets):
        object_notes = [
            note
            for instrument in midi_object.instruments for note in instrument.notes
            if note.velocity > 0
        ]
        object_start_time = min(note.start for note in object_notes)
        object_end_time = max(note.end for note in object_notes)
        shift = current_time + offset - object_start_time
        for instrument in midi_object.instruments:
            if not instrument.name:
                raise ValueError("Only files with non-empty instrument names are supported.")
            if instrument.name not in instruments:
                instruments[instrument.name] = pretty_midi.Instrument(
                    instrument.program,
                    instrument.is_drum,
                    instrument.name
                )
            output_instrument = instruments[instrument.name]

            for note in instrument.notes:
                if note.velocity <= 0:
                    continue
                output_note = pretty_midi.Note(
                    start=note.start + shift,
                    end=note.end + shift,
                    pitch=note.pitch,
                    velocity=note.velocity
                )
                output_instrument.notes.append(output_note)

            for control_change in instrument.control_changes:
                output_control_change = pretty_midi.ControlChange(
                    number=control_change.number,
                    value=control_change.value,
                    time=control_change.time + shift
                )
                output_instrument.control_changes.append(output_control_change)

            for pitch_bend in instrument.pitch_bends:
                output_pitch_bend = pretty_midi.PitchBend(
                    pitch_bend.pitch,
                    pitch_bend.time
                )
                output_instrument.pitch_bends.append(output_pitch_bend)

        current_time += object_end_time - object_start_time + offset

    merged_midi_object = pretty_midi.PrettyMIDI()
    for name, instrument in sorted(instruments.items(), key=lambda x: x[0]):
        instrument.notes.sort(key=lambda x: (x.start, x.pitch))
        merged_midi_object.instruments.append(instrument)
    return merged_midi_object


def replace_programs(
        midi_object: pretty_midi.PrettyMIDI,
        instrument_name_to_program: dict[str, int]
) -> pretty_midi.PrettyMIDI:
    """
    Replace programs and, maybe, drop some instruments.

    :param midi_object:
        MIDI object to be edited
    :param instrument_name_to_program:
        mapping from instrument name to program (according to General MIDI specification);
        if instrument name is absent in this mapping, the instrument is dropped
    :return:
        edited MIDI object
    """
    output_midi_object = deepcopy(midi_object)
    new_instruments = []
    for instrument in output_midi_object.instruments:
        if instrument.name in instrument_name_to_program:
            instrument.program = instrument_name_to_program[instrument.name]
            new_instruments.append(instrument)
    output_midi_object.instruments = new_instruments
    return output_midi_object


def fix_fluidsynth_last_note_termination(
        midi_object: pretty_midi.PrettyMIDI,
        trailing_silence: float = 0.5
) -> pretty_midi.PrettyMIDI:
    """
    Prevent abrupt termination of sound due to the bug in versions of FluidSynth prior to 2.3.1.

    :param midi_object:
        MIDI object to be made compatible with older versions of FluidSynth
    :param trailing_silence:
        duration of trailing silence (in seconds); adding this silence is a workaround to the issue
    :return:
        MIDI object with extra trailing silence
    """
    total_duration = max(
        note.end
        for instrument in midi_object.instruments
        for note in instrument.notes
    )
    # A fictive control change that prolongs output MIDI file.
    # Unlike notes of zero velocity, this event affects duration of `fluidsynth` output.
    trailing_silence_control_change = pretty_midi.ControlChange(
        number=7,
        value=0,
        time=total_duration + trailing_silence
    )
    for instrument in midi_object.instruments:
        instrument.control_changes.append(trailing_silence_control_change)
    return midi_object
