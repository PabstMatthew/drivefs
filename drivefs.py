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
        self.init_tmp()

    ''' Helper methods '''

    def init_tmp(self):
        if os.path.exists(self.tmp_dir):
            err('"{}" already exists! Remove it or rename it to continue.'.format(self.tmp_dir))
        os.makedirs(self.tmp_dir)

    def cleanup_tmp(self):
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)

    ''' Filesystem methods '''

    def destroy(self, path):
        dbg('destroy: {}'.format(path))
        self.cleanup_tmp()

    def access(self, path, mode):
        dbg('access: {}'.format(path))
        # / (root) should always exist.
        # for other files, do a traversal to check for existence
        if path != '/' and self.api.traverse_path(path) is None:
            raise FuseOSError(errno.ENOENT)

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

        # if called on root, just return values for the temporary directory
        if path == '/':
            st = os.lstat(self.tmp_dir)
            return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                     'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

        # traverse the path and set the result accordingly
        node = self.api.traverse_path(path)
        if node is None:
            raise FuseOSError(errno.ENOENT)
        local_path = self.tmp_dir+path
        self.api.download(node, local_path)
        st = os.lstat(local_path)
        result = dict()
        # TODO fix all this stuff
        result['st_atime'] = tstr_to_posix(node.get('viewedByMeTime'))
        result['st_ctime'] = tstr_to_posix(node.get('createdTime'))
        result['st_mtime'] = tstr_to_posix(node.get('modifiedTime'))
        result['st_uid'] = getattr(st, 'st_uid')
        result['st_gid'] = getattr(st, 'st_gid')
        result['st_mode'] = getattr(st, 'st_mode')
        result['st_nlink'] = getattr(st, 'st_nlink')
        result['st_size'] = getattr(st, 'st_size')
        result['st_blocks'] = getattr(st, 'st_blocks')
        return result

    def readdir(self, path, fh):
        dbg('readdir: {}'.format(path))
        dirents = ['.', '..']

        # figure which directory is the one in question
        dir_name = None
        if path == '/':
            dir_name = 'root'
        else:
            node = self.api.traverse_path(path)
            if node and node['mimeType'] == 'application/vnd.google-apps.folder':
                dir_name = node['name']

        # if it was a valid directory, list its children
        if dir_name:
            results = self.api.exec_query("'{}' in parents".format(dir_name))
            child_nodes = results.get('files', [])
            children = [x['name'] for x in child_nodes]
            dirents.extend(children)
        for r in dirents:
            yield r

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

def main(mountpoint):
    FUSE(DriveFS(), mountpoint, nothreads=True, foreground=True)
    #FUSE(Passthrough(root), mountpoint, nothreads=True, foreground=True)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        err('Not enough arguments! usage: `./drivefs.py <mount-point>`')
    main(sys.argv[1])

