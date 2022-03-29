[![PyPI version](https://badge.fury.io/py/pymixer.svg)](https://badge.fury.io/py/pymixer)

# PyMixer

## Overview

It is a library for mixing input MIDI and/or WAV files into output WAV files. The library can convert MIDI inputs to WAV with [[Sine]thesizer](https://github.com/Nikolay-Lysenko/sinethesizer) and [FluidSynth](https://github.com/FluidSynth/fluidsynth).

To study utilities from the library, one can read their docstring from the source code. These docstrings are informative enough.

Also, there is a [demo tutorial](https://github.com/Nikolay-Lysenko/pymixer/blob/master/docs/demo.ipynb) containing a project where this library is used for:
* stacking multiple MIDI files one by one into a single MIDI file,
* splitting the combined file into multiple MIDI files each of which contains exactly one track,
* creating a mixing project with files from the previous step,
* applying sound effects to tracks,
* interactive evaluation of output mixed with chosen gains,
* saving output to WAV.

## Installation

To install a stable version, run:
```bash
pip install pymixer
```

Above command also installs `sinethesizer` Python package as a dependency, but it does not install `fluidsynth` (which is not a Python package). Please install it according to instructions from its [official website](https://www.fluidsynth.org/).
