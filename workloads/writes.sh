#!/bin/bash
TARGET=$1
ITERATIONS=$2
for (( i=0; i < $ITERATIONS; i++ ))
do
  echo 'This is a test write!' > $TARGET/test.txt
  sha512sum $TARGET/test.txt
  rm $TARGET/test.txt
  while [ -f $TARGET/test.txt ]; do
    # this loop is need because GDriveFS returns before actually finishing operations
    sleep 1
  done
  seq 1 1000000 > $TARGET/test.txt
  sha512sum $TARGET/test.txt
  rm $TARGET/test.txt
  while [ -f $TARGET/test.txt ]; do
    # this loop is need because GDriveFS returns before actually finishing operations
    sleep 1
  done
done
