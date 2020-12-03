#!/bin/bash
TARGET=$1
ITERATIONS=$2
for (( i=0; i < $ITERATIONS; i++ ))
do
  du -sh $TARGET
  mkdir $TARGET/dir-test
  head -n 64 /dev/urandom > $TARGET/random.txt
  mv $TARGET/random.txt $TARGET/dir-test/random.txt
  rm -rf $TARGET/dir-test
  while [ -d $TARGET/dir-test ]; do
    # this loop is need because GDriveFS returns before actually finishing operations
    sleep 1
  done
done
