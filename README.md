[![PyPI version](https://badge.fury.io/py/pymixer.svg)](https://badge.fury.io/py/pymixer)

# PyMixer

## Overview

It is a library for mixing input MIDI and/or WAV files to output WAV files. To convert MIDI to WAV, [[Sine]thesizer](https://github.com/Nikolay-Lysenko/sinethesizer) and [FluidSynth](https://github.com/FluidSynth/fluidsynth) are used.

To start with, there is a [tutorial](https://github.com/Nikolay-Lysenko/pymixer/blob/master/docs/tutorial.ipynb) where this library is used for generating polyphonic audio from MIDI representation of a demo fugue.

To get more information, one can read docstrings from the source code. These docstrings are informative enough.

## Installation

To install a stable version, run:
```bash
pip install pymixer
```

Above command also installs `sinethesizer` Python package as a dependency, but it does not install `fluidsynth` (which is not a Python package). Please install it according to instructions from its [official website](https://www.fluidsynth.org/).
