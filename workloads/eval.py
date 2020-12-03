#!/bin/python3
import subprocess
import numpy as np
import itertools
import time

N = 16

mnt_path = '../mnt'
mnt_gdfs_cmd = ['gdfs', 'default', mnt_path]
mnt_gdocaml_cmd = ['google-drive-ocamlfuse', mnt_path]
mnt_drivefs_cmd = ['../drivefs.py', mnt_path]
unmount_cmd = ['fusermount', '-u', mnt_path]
workloads = ['./tree.sh', './fs-ops.sh', './reads.sh', './writes.sh']

def scrape(output):
    return [float(x) for x in output.split()]

def run_command(cmd, cwd="."):
    result = subprocess.run(cmd, stderr=subprocess.PIPE, cwd=cwd)
    return result.stderr.decode()

def list_to_str(arr):
    return ' '.join(arr)

if __name__ == '__main__':
    data = []
    mnt_cmds = [mnt_gdfs_cmd, mnt_gdocaml_cmd, mnt_drivefs_cmd]
    for mnt_cmd in mnt_cmds:
        run_command(mnt_cmd)
        # give the FS time to mount
        time.sleep(15)
        results = []
        for workload in workloads:
            workload_cmd = '{} {} {} > /dev/null 2> /dev/null'.format(workload, mnt_path, str(N))
            workload_cmd = ['/usr/bin/time', '-f', '%e %U %S', 'bash', '-c', workload_cmd]
            output = run_command(workload_cmd)
            times = scrape(output)
            print(times)
            results.append(times)
        run_command(unmount_cmd)
        data.append(results)
    print(data)

