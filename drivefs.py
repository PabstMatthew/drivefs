#!/usr/bin/env python3
from utils import *
from api import DriveAPI

from fuse import FUSE, FuseOSError, Operations

import os
import sys
import errno

class Passthrough(Operations):
    def __init__(self, root):
        self.root = root

    # Helpers
    # =======

    def _full_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        path = os.path.join(self.root, partial)
        return path

    # Filesystem methods
    # ==================

    def access(self, path, mode):
        full_path = self._full_path(path)
        if not os.access(full_path, mode):
            raise FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        full_path = self._full_path(path)
        return os.chmod(full_path, mode)

    def chown(self, path, uid, gid):
        full_path = self._full_path(path)
        return os.chown(full_path, uid, gid)

    def getattr(self, path, fh=None):
        full_path = self._full_path(path)
        st = os.lstat(full_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                     'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def readdir(self, path, fh):
        full_path = self._full_path(path)

        dirents = ['.', '..']
        if os.path.isdir(full_path):
            dirents.extend(os.listdir(full_path))
        for r in dirents:
            yield r

    def readlink(self, path):
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    def mknod(self, path, mode, dev):
        return os.mknod(self._full_path(path), mode, dev)

    def rmdir(self, path):
        full_path = self._full_path(path)
        return os.rmdir(full_path)

    def mkdir(self, path, mode):
        return os.mkdir(self._full_path(path), mode)

    def statfs(self, path):
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def unlink(self, path):
        return os.unlink(self._full_path(path))

    def symlink(self, name, target):
        return os.symlink(name, self._full_path(target))

    def rename(self, old, new):
        return os.rename(self._full_path(old), self._full_path(new))

    def link(self, target, name):
        return os.link(self._full_path(target), self._full_path(name))

    def utimens(self, path, times=None):
        return os.utime(self._full_path(path), times)

    # File methods
    # ============

    def open(self, path, flags):
        full_path = self._full_path(path)
        return os.open(full_path, flags)

    def create(self, path, mode, fi=None):
        full_path = self._full_path(path)
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path, length, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def write(self, path, buf, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        full_path = self._full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        return os.fsync(fh)

    def release(self, path, fh):
        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        return self.flush(path, fh)

def DriveFS():
    def __init__(self):
        dbg('intializing API')
        self.api = DriveAPI()
        dbg('hello')

    ''' Helper methods '''

    ''' Filesystem methods '''

    def access(self, path, mode):
        dbg('access: {}'.format(path))
        if self.api.traverse_path(path) is None:
            raise FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        dbg('chmod: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        '''
        full_path = self._full_path(path)
        full_path = self._full_path(path)
        return os.chmod(full_path, mode)
        '''

    def chown(self, path, uid, gid):
        dbg('chown: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        '''
        full_path = self._full_path(path)
        return os.chown(full_path, uid, gid)
        '''

    def getattr(self, path, fh=None):
        dbg('getattr: {}'.format(path))
        node = self.api.traverse_path(path)
        if node is None:
            raise FuseOSError(errno.ENOENT)
        result = dict()
        result['st_atime'] = node['viewedByMeTime']
        result['st_ctime'] = node['createdTime']
        result['st_mtime'] = node['modifiedTime']
        #result['st_gid'] = None
        #result['st_mode'] = None
        #result['st_nlink'] = None
        result['st_size'] = None
        result['st_uid'] = None
        result['st_blocks'] = None
        result['st_size'] = None
        return result
        '''
        full_path = self._full_path(path)
        st = os.lstat(full_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                     'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))
        '''

    def readdir(self, path, fh):
        dbg('readdir: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        '''
        full_path = self._full_path(path)

        dirents = ['.', '..']
        if os.path.isdir(full_path):
            dirents.extend(os.listdir(full_path))
        for r in dirents:
            yield r
        '''

    def readlink(self, path):
        dbg('readlink: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        '''
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname
        '''

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
        raise FuseOSError(errno.ENOSYS)
        '''
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))
        '''

    ''' File methods '''
    def open(self, path, flags):
        dbg('open: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        '''
        full_path = self._full_path(path)
        return os.open(full_path, flags)
        '''

    def create(self, path, mode, fi=None):
        dbg('create: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        '''
        full_path = self._full_path(path)
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)
        '''

    def read(self, path, length, offset, fh):
        dbg('read: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        '''
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)
        '''

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

def main(mountpoint, root):
    FUSE(DriveFS(), mountpoint, nothreads=True, foreground=True, debug=True)
    #FUSE(Passthrough(root), mountpoint, nothreads=True, foreground=True, debug=True)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        err('not enough arguments! usage: `./drivefs.py <mount-point>`')
    main(sys.argv[2], sys.argv[1])

