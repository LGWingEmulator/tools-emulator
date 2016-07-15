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
Module designed for parsing results of guest OS clock reliability tests

This module parses the "results" in two passes. It first computes some latency
data from the raw timestamps and writes those data pts out to several data
files. It then reads in those same data pts, computes some statistics, and
writes out the results as various stats/ files.
"""

import logging
import os

from os.path import join

_PARSE_METHOD_DIFFS = "DIFFS"
_PARSE_METHOD_RUNS = "RUNS"
_PARSE_METHODS = (_PARSE_METHOD_DIFFS, _PARSE_METHOD_RUNS)

class ParseException(Exception):
  pass

def compute_latency(timestamps, parse_method):
    if parse_method == _PARSE_METHOD_DIFFS:
        return [j - i for i, j in zip(timestamps, timestamps[1:])]

    elif parse_method == _PARSE_METHOD_RUNS:
        changes = {tstamp:timestamps.count(tstamp)
                   for tstamp in set(timestamps)}
        del changes[max(changes.keys())]
        return [1 / float(num_calls) for num_calls in changes.values()]

def extract_data(logspath, datapath, parse_method):
    for filename in os.listdir(logspath):
        if not filename.startswith("timestamps_") or \
           not filename.endswith(".txt"):
            continue

        logging.info("Extracting Data from %s", filename)
        with open(join(logspath, filename), "r") as logfile:
            # Convert logfile into list of timestamps and pass to compute_diffs
            data = compute_latency([long(timestamp)
                                    for timestamp in list(logfile)],
                                   parse_method)

            ID = ''.join(char for char in filename if char.isdigit())
            datafile_path = join(datapath, "data_" + ID + ".txt")
            with open(datafile_path, "w") as data_outfile:
                for val in data:
                    data_outfile.write(str(val) + "\n")

def compute_stats(statspath, datapath):
    averages = []
    variances = []

    logging.info("Computing Stats")
    for filename in os.listdir(datapath):
        if not filename.startswith("data_") or not filename.endswith(".txt"):
            continue

        with open(join(datapath, filename), "r") as datafile:
            data = [float(datapt) for datapt in list(datafile)]

            average = sum(data) / float(len(data))
            variance = sum((average - val) ** 2 for val in data) \
                        / float(len(data))

            averages.append(average)
            variances.append(variance)

    logging.info("Saving results")
    with open(join(statspath, "averages.txt"), "a") as avg_outfile:
        for avg in averages:
            avg_outfile.write(str(avg) + "\n")
    with open(join(statspath, "variances.txt"), "a") as var_outfile:
        for var in variances:
            var_outfile.write(str(var) + "\n")

def Parse(parse_method, path):
    if parse_method not in _PARSE_METHODS:
        raise ParseException("Supplied parse method \"%s\" not supported" \
                             % parse_method)

    # Extract data from logs and save them
    logspath = join(path, "raw_times")
    datapath = join(path, "data")
    statspath = join(path, "stats")

    # Extract data from logs and save them
    extract_data(logspath, datapath, parse_method)

    # Compute stats on the data logged above
    compute_stats(statspath, datapath)

    return True
