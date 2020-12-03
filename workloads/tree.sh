#!/bin/bash
TARGET=$1
ITERATIONS=$2
for (( i=0; i < $ITERATIONS; i++ ))
do
  tree $TARGET
done
