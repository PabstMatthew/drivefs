#!/bin/bash
TARGET=$1
ITERATIONS=$2
for (( i=0; i < $ITERATIONS; i++ ))
do
  sha512sum $TARGET/Getting\ started*
  sha512sum $TARGET/lab2.zip
  sha512sum $TARGET/folder2/vim-test.txt
done
