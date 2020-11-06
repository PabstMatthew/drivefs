#!/usr/bin/env python3
from utils import *
from api import DriveAPI

from fuse import FUSE, FuseOSError, Operations

import os
import sys
import errno
import shutil

class DriveFS(Operations):
    def __init__(self):
        dbg('Intializing API')
        self.api = DriveAPI()
        self.tmp_dir = '/tmp/drivefs'
        self.path_to_id = dict()
        self._init_tmp()
        self._build_cache()

    ''' Helper methods '''

    def _build_cache(self):
        # Build a locally cached version of the Google Drive by downloading
        # all files to the temporary directory.
        dbg('Building local cache')
        stack = [(self.tmp_dir, 'root')]
        while len(stack) != 0:
            cur = stack.pop()
            path = cur[0]
            dir_name = cur[1]
            results = self.api.exec_query("'{}' in parents".format(dir_name))
            items = results.get('files', [])
            if not items:
                continue
            for item in items:
                new_path = path+'/'+item['name']
                short_path = new_path[len(self.tmp_dir):]
                self.path_to_id[short_path] = item['id']
                self.api.download(item, new_path)
                # fix up file time metadata
                atime = tstr_to_posix(item.get('viewedByMeTime'))
                mtime = tstr_to_posix(item.get('modifiedTime'))
                os.utime(new_path, (atime, mtime))
                # if this is a directory, so add it to the stack for processing
                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    stack.append((new_path, item['id']))

    def _refresh_path(self, path):
        # Check for changes to a path, and make changes if necessary.
        dbg('Checking for changes on file {}'.format(path))
        if path not in self.path_to_id:
            dbg('File "{}" not found'.format(path))
            # TODO should probably do some check that the file doesn't exist remotely
            return
        fid = self.path_to_id[path]
        item = self.api.get_file(fid)
        if not item:
            dbg('File does not exist anymore!')
            # TODO remove from local cache?
        else:
            lpath = self._lpath(path)
            if item['modifiedTime'] > os.path.getmtime(lpath):
                # the file is stale, so we need to fix up the local cache
                dbg('Locally cached copy is stale!')
                if item['mimeType'] != 'application/vnd.google-apps.folder':
                    # if the file was not a folder, just redownload the new file
                    self.api.download(item, lpath)
                else:
                    # if the file was a folder, we need to do some more complicated checks
                    # TODO
                    pass

    def _init_tmp(self):
        dbg('Initializing temporary directory')
        if os.path.exists(self.tmp_dir):
            err('"{}" already exists! Remove it or rename it to continue.'.format(self.tmp_dir))
        os.makedirs(self.tmp_dir)

    def _cleanup_tmp(self):
        dbg('Cleaning up temporary directory')
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)

    def _lpath(self, path):
        return self.tmp_dir+path;

    ''' Filesystem methods '''

    def destroy(self, path):
        dbg('destroy: {}'.format(path))
        self._cleanup_tmp()

    def access(self, path, mode):
        dbg('access: {}'.format(path))
        lpath = self._lpath(path)
        if not os.access(lpath, mode):
            raise FuseOSError(errno.ENOENT)

    def chmod(self, path, mode):
        dbg('chmod: {}'.format(path))
        lpath = self._lpath(path)
        lpath = self._lpath(path)
        return os.chmod(lpath, mode)

    def chown(self, path, uid, gid):
        dbg('chown: {}'.format(path))
        lpath = self._lpath(path)
        return os.chown(lpath, uid, gid)

    def getattr(self, path, fh=None):
        dbg('getattr: {}'.format(path))

        lpath = self._lpath(path)
        st = os.lstat(lpath)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                     'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid', 'st_blocks'))

    def readdir(self, path, fh):
        dbg('readdir: {}'.format(path))
        dirents = ['.', '..']

        lpath = self._lpath(path)
        if os.path.isdir(lpath):
            dirents.extend(os.listdir(lpath))
        for r in dirents:
            yield r

    def readlink(self, path):
        dbg('readlink: {}'.format(path))
        lpath = self._lpath(path)
        pathname = os.readlink(lpath)
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    def mknod(self, path, mode, dev):
        dbg('mknod: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        '''
        return os.mknod(self._full_path(path), mode, dev)
        '''

    def rmdir(self, path):
        dbg('rmdir: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        '''
        full_path = self._full_path(path)
        return os.rmdir(full_path)
        '''

    def mkdir(self, path, mode):
        dbg('mkdir: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        '''
        return os.mkdir(self._full_path(path), mode)
        '''

    def statfs(self, path):
        dbg('statfs: {}'.format(path))
        lpath = self._lpath(path)
        stv = os.statvfs(lpath)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    ''' File methods '''
    def open(self, path, flags):
        dbg('open: {}'.format(path))
        lpath = self._lpath(path)
        return os.open(lpath, flags)

    def create(self, path, mode, fi=None):
        dbg('create: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        '''
        full_path = self._full_path(path)
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)
        '''

    def read(self, path, length, offset, fh):
        dbg('read: {}'.format(path))
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def write(self, path, buf, offset, fh):
        dbg('write: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        '''
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)
        '''

    def truncate(self, path, length, fh=None):
        dbg('truncate: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        '''
        full_path = self._full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)
        '''

    def flush(self, path, fh):
        dbg('flush: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        '''
        return os.fsync(fh)
        '''

    def release(self, path, fh):
        dbg('release: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        '''
        return os.close(fh)
        '''

    def fsync(self, path, fdatasync, fh):
        dbg('fsync: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        '''
        return self.flush(path, fh)
        '''

def main(mountpoint):
    FUSE(DriveFS(), mountpoint, nothreads=True, foreground=True)
    #FUSE(Passthrough(root), mountpoint, nothreads=True, foreground=True)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        err('Not enough arguments! usage: `./drivefs.py <mount-point>`')
    main(sys.argv[1])

