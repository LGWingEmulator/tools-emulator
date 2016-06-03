#!/bin/bash
# use this script to flush the file caches on linux or android
free && sync && echo 3 > /proc/sys/vm/drop_caches && free

