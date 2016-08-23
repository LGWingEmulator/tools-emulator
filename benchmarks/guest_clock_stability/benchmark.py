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
Module designed for testing the reliability of guest OS clock

This module runs a testing program on the guest OS under varying levels of
"contention" and logs the results. Contention is defined as how much
demand/load
the QEMU lock is currently bearing.

Currently we configure the amount of contention by spawning multiple threads
to repeatedly adb push files from the host to the guest.
"""

import logging
import os
import subprocess
import threading

from os.path import join

_CONTENTION_LEVEL_MAP = {
    "NONE" : [0, 0, 0],
    "HIGH" : [12, 12, 12]
}

_SCRPDIR = os.path.dirname(os.path.abspath(__file__))

_GUEST_WORK_DIR = "/data/local/tmp"
_GUEST_LOG_PATH = join(_GUEST_WORK_DIR, "logs.txt")

contention_start_event = threading.Event()
contention_stop_event = threading.Event()
main_thread_exec_event = threading.Event()

class ThreadWrapper(threading.Thread):
    def __init__(self, target, *args):
        self._target = target
        self._args = args
        self._done_event = threading.Event()
        threading.Thread.__init__(self)

    def run(self):
        self._target(*self._args)

    def stop(self):
        self._done_event.set()

    def done(self):
        return self._done_event.is_set()

class BenchmarkException(Exception):
  pass

def adb_push(ID, filename):
    with open(os.devnull, "w") as nullpipe:
        while not threading.current_thread().done():
            subprocess.call(["adb", "push", filename,
                             join(_GUEST_WORK_DIR,
                                  os.path.basename(filename) + str(ID))
                            ], stdout=nullpipe, stderr=subprocess.STDOUT)

def spawn_push_threads(num, filename):
    return [ThreadWrapper(adb_push, i, filename) for i in range(0, num)]

def manage_contention(num_small, num_med, num_large):
    while True:
        contention_start_event.wait()
        contention_start_event.clear()

        if threading.current_thread().done():
            return

        threads = []
        threads.extend(spawn_push_threads(num_small,
                                     join(_SCRPDIR, "contention", "small.txt")))
        threads.extend(spawn_push_threads(num_med,
                                     join(_SCRPDIR, "contention", "med.txt")))
        threads.extend(spawn_push_threads(num_large,
                                     join(_SCRPDIR, "contention", "large.txt")))

        for thread in threads:
            thread.start()

        main_thread_exec_event.set()
        contention_stop_event.wait()
        contention_stop_event.clear()

        for thread in threads:
            thread.stop()
        for thread in threads:
            thread.join()

        main_thread_exec_event.set()

def Benchmark(clock_type, cont_level):
    if _SCRPDIR == "":
        raise BenchmarkException("Could not find script directory")
    if clock_type.upper() not in ["TIME", "RTC", "KVM"]:
        raise BenchmarkException("Supplied clock type \"%s\" not supported" \
                                  % clock_type)
    if cont_level.upper() not in _CONTENTION_LEVEL_MAP:
        raise BenchmarkException("Supplied contention level \"%s\" \
                                  not supported" % cont_level)

    # Setup the contention manager
    small, med, large = _CONTENTION_LEVEL_MAP[cont_level.upper()]
    cont_manager = ThreadWrapper(manage_contention, small, med, large)
    cont_manager.start()

    for i in range(0, 100):
        # Start contenion
        contention_start_event.set()
        main_thread_exec_event.wait()
        main_thread_exec_event.clear()

        logging.info("Logging %d", i)
        os.system("adb shell \"cd " + _GUEST_WORK_DIR + "; ./timing\"")

        # Stop contention
        contention_stop_event.set()
        main_thread_exec_event.wait()
        main_thread_exec_event.clear()

        logging.info("Saving output")
        log_filename = "timestamps_" + str(i) + ".txt"
        subprocess.call(["adb", "pull", _GUEST_LOG_PATH,
                         join(_SCRPDIR, "logs", clock_type, cont_level,
                              "raw_times", log_filename)])

    # Safely stop the contention manager

    # TODO: Currently dangerously using events to wait forever,
    # which could introduce halting if incorrectly managing threads.
    # Also dirty due to calling contention_start_event to actually
    # kill the cont_manager. Can be fixed if cont_manager is waiting
    # instead on a cv for a set amount of time before once again checking
    # its done condition. Much cleaner kill.
    cont_manager.stop()
    contention_start_event.set()
    cont_manager.join()

    return True
