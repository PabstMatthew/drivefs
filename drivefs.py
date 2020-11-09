#!/usr/bin/env python3
from utils import *
from api import *

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

        # These dicts cache local state, and need to be updated for relevant operations
        self.path_to_id = dict()
        self.id_to_item = dict()
        self.id_to_children = dict()

        # Initialize the local FS
        self._init_tmp()
        self._build_cache()

    ''' Helper methods '''

    def _build_cache(self):
        # Build a locally cached version of the Google Drive by downloading
        # all files to the temporary directory.
        dbg('Building local cache')
        stack = [('', 'root')]
        while len(stack) != 0:
            cur = stack.pop()
            path = cur[0]
            dir_id = cur[1]
            items = self.api.exec_query("'{}' in parents".format(dir_id))
            if not items:
                continue
            self.id_to_children[dir_id] = []
            for item in items:
                self.id_to_children[dir_id].append(item[ID])
                new_path = path+'/'+item[NAME]
                self._cache(item, new_path)
                # if this is a directory, so add it to the stack for processing
                if item[MTYPE] == FOLDER_MTYPE:
                    stack.append((new_path, item[ID]))

    def _cache(self, item, rpath):
        # Cache the file 'item' at the remote path 'rpath'
        dbg('Caching file "{}" at "{}".'.format(item[NAME], rpath))
        lpath = self._lpath(rpath)
        # fix up internal state caches
        self.path_to_id[rpath] = item[ID]
        self.id_to_item[item[ID]] = item
        # download the file
        self.api.download(item, lpath)
        # fix up file time metadata
        atime = tstr_to_posix(item.get(ATIME))
        mtime = tstr_to_posix(item.get(MTIME))
        os.utime(lpath, (atime, mtime))

    def _refresh_local(self, rpath):
        # Ensure that the local copy of a file is up-to-date with the remote version.
        dbg('Refreshing local copy of "{}".'.format(rpath))
        if re.fullmatch('/+', rpath):
            # If this is the root, nothing needs to be done
            return

        if rpath not in self.path_to_id:
            # File not cached locally
            tree = re.split('/+', rpath)
            fname = tree[-1]
            items = self.api.exec_query('name = "{}"'.format(fname))
            if len(items) == 0:
                dbg('File not found remotely.')
                return
            item = self.api.traverse_path(rpath)
            self._cache(item, rpath)
        else:
            # File cached locally
            lpath = self._lpath(rpath)
            fid = self.path_to_id[rpath]
            local_item = self.id_to_item[fid]
            remote_item = self.api.get_file(fid)
            if not remote_item:
                dbg('File does not exist anymore!')
                if local_item[MTYPE] != FOLDER_MTYPE:
                    os.remove(lpath)
                else:
                    # TODO what should we do if a folder doesn't exist anymore?
                    pass
            else:
                if local_item[MTYPE] != remote_item[MTYPE]:
                    err('Mimetype changed!') # TODO when would this ever happen?
                if local_item[PARENTS] != remote_item[PARENTS]:
                    dbg('Parents changed!')
                    # TODO
                if local_item[TRASHED] != remote_item[TRASHED]:
                    if local_item[TRASHED]:
                        dbg('File remotely restored!')
                        # TODO
                    else:
                        dbg('File remotely trashed!')
                        # TODO
                if local_item[MTIME] < remote_item[MTIME]:
                    dbg('Locally cached copy is stale!')
                    # TODO


    def _sync_remote(self, path):
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

    def _rpath(self, lpath):
        # Return the remote filepath from the local path
        return lpath[len(self.tmp_dir):]

    def _lpath(self, rpath):
        # Return the local filepath from the remote path
        return self.tmp_dir+rpath;

    ''' Filesystem methods '''

    def destroy(self, path):
        dbg('destroy: {}'.format(path))
        self._cleanup_tmp()

    def access(self, path, mode):
        dbg('access: {}'.format(path))
        lpath = self._lpath(path)
        if not os.access(lpath, mode):
            # if file doesn't exist locally, refresh and try again
            self._refresh_local(path)
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
        try:
            st = os.lstat(lpath)
        except FileNotFoundError:
            # if file doesn't exist locally, refresh and try again
            self._refresh_local(path)
        st = os.lstat(lpath)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                     'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid', 'st_blocks'))

    def readdir(self, path, fh):
        dbg('readdir: {}'.format(path))
        dirents = ['.', '..']
        # reads should be consistent
        self._refresh_local(path)
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

