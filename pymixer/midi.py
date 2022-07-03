"""
Provide utilities for working with MIDI files.

Author: Nikolay Lysenko
"""


import os
import random
import string
from copy import copy
from typing import Optional

import pretty_midi


def merge_midi_objects(
        midi_objects: list[pretty_midi.PrettyMIDI],
        opening_silence_in_sec: float = 0.0,
        trailing_silence_in_sec: float = 0.0,
        caesuras_in_sec: Optional[list[float]] = None,
        instrument_name_to_program: Optional[dict[int, int]] = None
) -> pretty_midi.PrettyMIDI:
    """
    Merge MIDI objects sequentially into a single MIDI object.

    :param midi_objects:
        MIDI objects to be merged
    :param opening_silence_in_sec:
        duration of opening silence (in seconds)
    :param trailing_silence_in_sec:
        duration of trailing silence (in seconds)
    :param caesuras_in_sec:
        durations of caesuras (i.e., pauses) between successive MIDI objects (in seconds);
        by default, there are no caesuras
    :param instrument_name_to_program:
        mapping from instrument name to program (according to General MIDI specification);
        if instrument name is absent in this mapping, original program is left unchanged
    :return:
        merged MIDI object
    """
    if caesuras_in_sec is None:
        caesuras_in_sec = [0 for _ in range(len(midi_objects) - 1)]
    if len(caesuras_in_sec) != len(midi_objects) - 1:
        raise ValueError(
            f"Length of `caesuras_in_sec` is {len(caesuras_in_sec)}, "
            f"but it should be {len(midi_objects) - 1}."
        )
    caesuras_in_sec = [opening_silence_in_sec] + caesuras_in_sec
    instrument_name_to_program = instrument_name_to_program or {}

    instruments = {}
    current_time = 0
    for midi_object, caesura_in_sec in zip(midi_objects, caesuras_in_sec):
        object_notes = [
            note
            for instrument in midi_object.instruments for note in instrument.notes
            if note.velocity > 0
        ]
        object_start_time = min(note.start for note in object_notes)
        object_end_time = max(note.end for note in object_notes)
        shift = current_time + caesura_in_sec - object_start_time
        for instrument in midi_object.instruments:
            if not instrument.name:
                raise ValueError("Only files with non-empty instrument names are supported.")
            if instrument.name not in instruments:
                instruments[instrument.name] = pretty_midi.Instrument(
                    instrument_name_to_program.get(instrument.name) or instrument.program,
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
        current_time += object_end_time - object_start_time + caesura_in_sec

    # A fictive note that prolongs output MIDI file.
    # This event is recognized by `sinethesizer`.
    trailing_silence_note = pretty_midi.Note(
        start=current_time,
        end=current_time + trailing_silence_in_sec,
        velocity=0,
        pitch=1
    )
    # A fictive control change that prolongs output MIDI file.
    # This event is recognized by `fluidsynth`.
    trailing_silence_control_change = pretty_midi.ControlChange(
        number=7,
        value=0,
        time=current_time + trailing_silence_in_sec
    )
    merged_midi_object = pretty_midi.PrettyMIDI()
    for name, instrument in sorted(instruments.items(), key=lambda x: x[0]):
        instrument.notes.sort(key=lambda x: (x.start, x.pitch))
        instrument.notes.append(trailing_silence_note)
        instrument.control_changes.append(trailing_silence_control_change)
        merged_midi_object.instruments.append(instrument)
    return merged_midi_object


def split_midi_file_by_instruments(path_to_midi_file: str, output_dir: str) -> None:
    """
    Place each instrument into a separate MIDI file.

    :param path_to_midi_file:
        path to MIDI file to be split
    :param output_dir:
        directory where output files are going to be saved
    :return:
        None
    """
    midi_object = pretty_midi.PrettyMIDI(path_to_midi_file)
    file_name_without_extension = os.path.splitext(os.path.basename(path_to_midi_file))[0]
    for instrument in midi_object.instruments:
        split_midi_object = pretty_midi.PrettyMIDI()
        split_midi_object.instruments.append(instrument)
        if instrument.name:
            instrument_name = instrument.name
        else:
            n_random_chars = 10
            instrument_name = ''.join(
                random.choice(string.ascii_lowercase) for _ in range(n_random_chars)
            )
        output_file_name = f"{file_name_without_extension}_{instrument_name}.mid"
        split_midi_object.write(os.path.join(output_dir, output_file_name))


def choirify_midi_file(
        path_to_input_midi_file: str,
        path_to_output_midi_file: str,
        program_to_programs: dict[int, list[int]]
) -> None:
    """
    Replace each instrument with its copies that differ only in programs.

    In particular, this function is useful for preparing pipe organ MIDI files for playing
    with soundfonts where programs correspond to single stops and so multiple programs are needed
    for each of the tracks.

    :param path_to_input_midi_file:
        path to MIDI file to be choirified
    :param path_to_output_midi_file:
        path to output file
    :param program_to_programs:
        mapping from original program to multiple programs that replace it;
        if an instrument has a program that is absent in this mapping, this instrument is skipped
    :return:
        None
    """
    midi_object = pretty_midi.PrettyMIDI(path_to_input_midi_file)
    new_instruments = []
    for instrument in midi_object.instruments:
        programs = program_to_programs.get(instrument.program)
        if programs is None:
            continue
        for program in programs:
            new_instrument = copy(instrument)
            new_instrument.program = program
            new_instrument.name = f'{instrument.name}_{program}'
            new_instruments.append(new_instrument)
    midi_object.instruments = new_instruments
    midi_object.write(path_to_output_midi_file)
