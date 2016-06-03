#!/bin/bash -e
#
# ./android-bench.sh [-adb <adb-path>] <emulator-path> [<emulator arguments> ...]
#
# This script builds and runs the iobenchmark against a running emulator.
# Make sure your emulator has as least 1024MB of free space in
# /data/local/tmp
# TODO: reboot the emulator between each invocation to ensure
# cache is completely flushed

# size of benchmark scratch file in MB
MB=1024

DIR="$(cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

while [[ $# > 1 ]]
do
  key="$1"

  case $key in
    -a|--adb)
    shift
    ADB="$1"
    ;;
    *)
    # not a flag, must be emulator binary
    break
    ;;
  esac
  shift # past key
done

if [ -z "$ADB" ]; then
  ADB="$(which adb)"
fi

EMU="$(which $1)"
shift
EMU_ARGS=$@

echo ADB=$ADB
echo EMU=$EMU $EMU_ARGS

function wait_for_emulator() {
  echo "waiting for emulator..."
  while true; do
    BOOT="$($ADB shell getprop sys.boot_completed 2> /dev/null)" || true
    if [[ "$BOOT" = 1* ]]; then
      break
    fi
    sleep 1
  done
}

function error_exit() {
  echo "ERROR: $1"
  exit 1
}

# prompt user for password at the beginning of the script
sudo true

rm -rf $DIR/build-android || true
mkdir $DIR/build-android
cd $DIR/build-android
export ANDROID_NDK=$ANDROID_SDK_ROOT/ndk-bundle
$ANDROID_SDK_ROOT/cmake/bin/cmake .. \
  -DCMAKE_TOOLCHAIN_FILE=$ANDROID_SDK_ROOT/cmake/android.toolchain.cmake \
  -DANDROID_ABI=x86 \
  -DANDROID_DEFAULT_NDK_API_LEVEL=9 \
  -DCMAKE_CXX_FLAGS="-fPIE -pie"

make

TMP=/data/local/tmp

SCRATCH=$(mktemp /tmp/iobench.XXXXXX)

function bench {
  killall qemu-system-i386 qemu-system-x86_64 emulator-x86 emulator-x86_64 player 2> /dev/null || true
  sleep 4 # give the emulator a chance to shut down or it will still appear to be running below

  $EMU $EMU_ARGS &
  wait_for_emulator

  sleep 2 # give the emulator a chance to finish booting

  sudo $DIR/flush.sh > /dev/null || error_exit "flush"

  if [ -z "$READY" ]; then
    # first time device setup
    $ADB push iobench $TMP/iobench || error_exit "$ADB push iobench $TMP/iobench"
    $ADB shell rm $TMP/iobench.dat || true
    READY=true
  fi

  echo iobench "$@"

  # run the benchmark, capture just the "real" time
  (time $ADB shell $TMP/iobench "$@") 2> $SCRATCH

  # convert "real    0m1.234s" -> "0m1.234"
  REAL=$(grep real $SCRATCH)
  TIME=$(echo $REAL | sed -e 's/real \([m0-9\.]*\)s/\1/g')
  if [[ "$TIME" = "" ]]; then
    # invalid response
    cat $SCRATCH
    error_exit "running iobench failed"
  fi

  # TIME is in the format 0m1.234 where the value to the left of the 'm' is
  # minutes and the value to the right is seconds
  MIN=$(echo $TIME | cut -f1 -dm)
  SEC=$(echo $TIME | cut -f2 -dm)
  SEC=$(echo "scale=3; $MIN * 60 + $SEC" | bc)

  MBPS=$(echo "scale=3; $MB / $SEC" | bc)
  echo "Host measurement: $MBPS MB/S"
}

bench -seq -write $MB  # this invocation is just to create the file
bench -seq -write $MB
bench -seq -read $MB
bench -rand -write $MB
bench -rand -read $MB
