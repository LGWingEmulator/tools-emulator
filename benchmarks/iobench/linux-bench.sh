#!/bin/bash -e

# prompt user for password
sudo true

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

rm -rf $DIR/build || true
mkdir $DIR/build
cd $DIR/build
$ANDROID_SDK_ROOT/cmake/bin/cmake ..
make
rm /tmp/iobench.tmp || true
./iobench -seq -write 1024 > /dev/null # create the file

sudo $DIR/flush.sh > /dev/null
./iobench -seq -write 1024

sudo $DIR/flush.sh > /dev/null
./iobench -seq -read 1024

sudo $DIR/flush.sh > /dev/null
./iobench -rand -write 1024

sudo $DIR/flush.sh > /dev/null
./iobench -rand -read 1024
