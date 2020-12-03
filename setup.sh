#!/bin/bash
# Only works for Ubuntu right now.
sudo apt-get update -y
sudo apt-get install -y fuse
python3 -m pip install fusepy
