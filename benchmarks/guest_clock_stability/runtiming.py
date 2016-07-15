# Copyright 2016 The Android Open Source Project
#
# This software is licensed under the terms of the GNU General Public
# License version 2, as published by the Free Software Foundation, and
# may be copied, distributed, and modified under those terms.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

"""
Driver for testing the reliability of guest OS clock

This driver imports both parse and benchmark modules. It first compiles and
adb pushes the test program with the given clock_type selected to the guest OS.
It then calls benchmark.Benchmark and parse.Parse in that order to run the
experiment and parse its results.
"""

import benchmark
import logging
import os
import parse
import subprocess
import sys

from os.path import join

_PARSE_CLOCK_MAP = {"TIME" : "DIFFS", "RTC" : "RUNS", "KVM" : "DIFFS"}
_CONTENTION_LEVELS = ("NONE", "HIGH")

_SCRPDIR = os.path.dirname(os.path.abspath(__file__))

_HOST_PROG_PATH = join(_SCRPDIR, "timing.cpp")
_HOST_EXEC_PATH = join(_SCRPDIR, "timing")
_GUEST_EXEC_PATH = "/data/local/tmp/timing"

def compile_and_push(clock_type):
    subprocess.call(["lCXX", _HOST_PROG_PATH, _HOST_EXEC_PATH, clock_type])
    subprocess.call(["adb", "push", _HOST_EXEC_PATH, _GUEST_EXEC_PATH])

def main(clock_type):
    FORMAT = '%(asctime)-15s %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.DEBUG)

    if _SCRPDIR == "":
        logging.error("Could not find script directory")
        return True
    if clock_type.upper() not in _PARSE_CLOCK_MAP:
        logging.error("Supplied clock type \"%s\" has no parsing method",
                     clock_type)
        return True

    logging.info("Compiling and adb pushing timing exec")
    compile_and_push(clock_type.upper())

    logging.info("Running with clock_type: %s", clock_type)
    for cont_level in _CONTENTION_LEVELS:
        logging.info("Running with contention_level: %s", cont_level)

        try:
          benchmark.Benchmark(clock_type, cont_level)
          parse.Parse(_PARSE_CLOCK_MAP[clock_type.upper()],
                      join(_SCRPDIR, "logs", clock_type, cont_level))
        except BenchmarkException as err:
          logging.error("ERROR: BenchmarkException caught: %s", err)
          return False
        except ParseException as err:
          logging.error("ERROR: ParseException caught: %s", err)
          return False

    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print "Usage: " + sys.argv[0] + " clock_type"
        sys.exit(1)

    main(sys.argv[1])
