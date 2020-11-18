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
        self.trash_dir = '/.Trash'
        self.root_name = 'My Drive'
        self.root_id = self.api.get_file('root')[ID]

        # These dicts cache local state, and need to be updated for relevant operations
        self.path_to_id = {self.trash_dir: 'root'}
        self.id_to_item = dict()
        self.id_to_children = dict()

        # Initialize the local FS
        self._init_tmp()
        self._build_cache()

    ''' Helper methods '''

    def _in_trash(self, rpath):
        # Returns whether a given remote path is in the trash directory
        return rpath[:len(self.trash_dir)] == self.trash_dir

    def _build_cache(self):
        # Build a locally cached version of the Google Drive by downloading
        # all files to the temporary directory.
        dbg('Building local cache')
        stack = [('', self.root_id)]
        while len(stack) != 0:
            cur = stack.pop()
            path = cur[0]
            dir_id = cur[1]
            items = self.api.exec_query("'{}' in parents".format(dir_id))
            if not items:
                continue
            for item in items:
                if item[TRASHED] and not self._in_trash(path):
                    new_path = self.trash_dir+'/'+item[NAME]
                else:
                    new_path = path+'/'+item[NAME]
                self._cache(item, new_path)
                # if this is a directory, so add it to the stack for processing
                if item[MTYPE] == FOLDER_MTYPE:
                    stack.append((new_path, item[ID]))

    def _cache(self, item, rpath):
        # Cache the file 'item' at the remote path 'rpath'
        dbg('Caching file "{}" at "{}".'.format(item[NAME], rpath))
        lpath = self._lpath(rpath)
        # add extension
        mimetype = item[MTYPE]
        if mimetype in self.api.types:
            lpath += self.api.types[mimetype][1]
        # fix up internal state caches
        self.path_to_id[rpath] = item[ID]
        self.id_to_item[item[ID]] = item
        parent = item[PARENTS][0]
        if not parent in self.id_to_children:
            self.id_to_children[parent] = []
        self.id_to_children[parent].append(item[ID])
        # download the file
        self.api.download(item, lpath)
        # fix up file time metadata
        atime = tstr_to_posix(item.get(ATIME))
        mtime = tstr_to_posix(item.get(MTIME))
        os.utime(lpath, (atime, mtime))

    def _get_rpath(self, item):
        # Calculates the remote path for an item
        dbg('Getting remote path for item {}'.format(item))
        rpath = item[NAME]
        cur_item = item
        is_trashed = item[TRASHED]
        while True:
            cur_item = self.api.get_file(cur_item[PARENTS][0])
            if cur_item[NAME] == self.root_name:
                # TODO other cases like shared drives
                rpath = '/'+rpath
                break
            rpath = cur_item[NAME]+'/'+rpath
        if is_trashed:
            rpath = self.trash_dir+rpath
        # add extension
        mimetype = item[MTYPE]
        if mimetype in self.api.types:
            lpath += self.api.types[mimetype][1]
        return rpath

    def _get_cached_rpath(self, fid):
        for rp, f in self.path_to_id.items():
            if f == fid: 
                return rp
        err('Failed to find file ID "{}" in local state!'.format(fid))

    def _update_in_hierarchy(self, old_rpath, old_item, new_item):
        # Move a cached file to its new path, and update internal state
        # find new location in hierarchy
        new_rpath = self._get_rpath(new_item)
        dbg('Moving cached file at "{}" to "{}".'.format(old_rpath, new_rpath))
        dbg('Old item: {}'.format(old_item))
        dbg('New item: {}'.format(new_item))
        # move the file
        old_lpath = self._lpath(old_rpath)
        new_lpath = self._lpath(new_rpath)
        os.rename(old_lpath, new_lpath)
        # fix internal state
        fid = new_item[ID]
        del self.path_to_id[old_rpath]
        self.path_to_id[new_rpath] = fid
        self.id_to_item[fid] = new_item
        old_parent = old_item[PARENTS][0]
        new_parent = new_item[PARENTS][0]
        if old_parent != new_parent:
            self.id_to_children[old_parent].remove(fid)
            self.id_to_children[new_parent].append(fid)
            dbg('Removing from metadata {} {}'.format(self.id_to_children[old_parent], self.id_to_children[new_parent]))

    def _update_directory(self, fid, rpath):
        # Update folder contents
        dbg('Updating directory contents.')
        new_children_items = self.api.exec_query('"{}" in parents'.format(fid))
        new_children = set([child_item[ID] for child_item in new_children_items])
        old_children = set(self.id_to_children[fid])
        for new_child in new_children.difference(old_children):
            # cache new children
            for new_child_item in new_children_items:
                child_id = new_child_item[ID]
                if child_id == new_child:
                    if child_id in self.id_to_item:
                        # new child came from another directory
                        old_rpath = self._get_cached_rpath(child_id)
                        self._update_in_hierarchy(old_rpath, self.id_to_item[child_id], new_child_item)
                    else:
                        child_rpath = rpath+'/'+new_child_item[NAME]
                        self._cache(new_child_item, child_rpath)
                    break
        for removed_child in old_children.difference(new_children):
            # remove old children
            removed_item = self.id_to_item[removed_child]
            removed_rpath = rpath+'/'+removed_item[NAME]
            new_item = self.api.get_file(removed_item[ID])
            if new_item:
                # item exists somewhere else, so update it
                self._update_in_hierarchy(removed_rpath, removed_item, new_item)
            else:
                # remove the item
                self._remove_from_cache(removed_item, removed_rpath)
        # TODO check for trashed/untrashed items

    def _remove_from_cache(self, item, rpath):
        dbg('Removing "{}" from the cache'.format(rpath))
        lpath = self._lpath(rpath)
        if item[MTYPE] != FOLDER_MTYPE:
            os.remove(lpath)
        else:
            # Make sure the directory is empty
            children = os.listdir(lpath)
            while len(children) > 0:
                child = children.pop()
                child_rpath = rpath+'/'+child
                if child_rpath in self.path_to_id:
                    # Child file exists, but was moved
                    child_id = self.path_to_id[child_rpath]
                    child_item = self.api.get_file(fid)
                    old_child_item = self.id_to_item[child_id]
                    self._update_in_hierarchy(child_rpath, old_child_item, child_item)
                else:
                    # Child file is gone too, so remove the child file
                    child_lpath = lpath+'/'+child
                    os.remove(child_lpath)
            # Finally, remove the directory
            os.rmdir(lpath)
            del self.id.to_children[item[ID]]
        del self.path_to_id[rpath]
        del self.id_to_item[item[ID]]

    def _refresh_local(self, rpath):
        # Ensure that the local copy of a file is up-to-date with the remote version.
        dbg('Refreshing local copy of "{}".'.format(rpath))
        if rpath == '/':
            # If this is the root, update the dir contents, then return
            self._update_directory(self.root_id, '')
            return
        if rpath == self.trash_dir:
            # If this is the trash dir, update the dir contents (TODO)
            return

        if rpath not in self.path_to_id:
            # Path not cached locally
            tree = re.split('/+', rpath)
            fname = tree[-1]
            items = self.api.exec_query('name = "{}"'.format(fname))
            # Quick check to see if this filename even exists
            if len(items) == 0:
                dbg('File not found remotely.')
                return
            # If such a filename exists, let's make sure we get the right one
            item = self.api.traverse_path(rpath)
            if not item[ID] in self.id_to_item:
                # Cache this new file, and we're done
                self._cache(item, rpath)
                return
            elif item[PARENTS][0] != self._get_parent(rpath):
                # This was not the file we were looking for
                return
            else:
                # File was cached under a different path, so let's just restart the whole check
                # (this could be made a little more efficient, but it's a rare case)
                rpath = self._get_cached_rpath(fid)

        # File cached locally
        lpath = self._lpath(rpath)
        fid = self.path_to_id[rpath]
        # TODO there is a case where a file is replaced by a new file,
        # which is currently not accounted for here
        local_item = self.id_to_item[fid]
        remote_item = self.api.get_file(fid)
        self.id_to_item[fid] = remote_item
        if not remote_item:
            dbg('File does not exist anymore!')
            self._remove_from_cache(local_item, rpath)
        else:
            if local_item[MTYPE] != remote_item[MTYPE]:
                # This should never happen.
                err('Mimetype changed!') 
            if local_item[PARENTS] != remote_item[PARENTS]:
                dbg('Parents changed!')
                self._update_in_hierarchy(rpath, local_item, remote_item)
            if local_item[TRASHED] != remote_item[TRASHED]:
                if local_item[TRASHED]:
                    dbg('File remotely restored!')
                else:
                    dbg('File remotely trashed!')
                self._update_in_hierarchy(rpath, local_item, remote_item)
            if local_item[MTIME] < remote_item[MTIME]:
                dbg('Locally cached copy is stale!')
                self._cache(remote_item, rpath)
            if remote_item[MTYPE] == FOLDER_MTYPE:
                self._update_directory(fid, rpath)

    def _sync_remote(self, rpath):
        # Push local file data/attributes to the remote.
        dbg('Syncing file "{}" with the remote'.format(rpath))
        lpath = self._lpath(rpath)
        # TODO

    def _register_file(self, rpath, is_dir):
        dbg('Registering new file at "{}"'.format(rpath))
        beg = rpath.rindex('/')
        parent = self._get_parent(rpath)
        # register new file
        name = rpath[beg+1:]
        in_trash = self._in_trash(rpath)
        self.api.create(name, parent, is_dir, in_trash)

    def _remove_file(self, rpath):
        fid = self.path_to_id[rpath]
        item = self.id_to_item[fid]
        lpath = self._lpath(rpath)
        if item[TRASHED]:
            # Remove the file permanently
            self.api.delete(fid)
            if item[MTYPE] == FOLDER_MTYPE:
                os.rmdir(lpath)
                del self.id_to_children[fid]
            else:
                os.remove(lpath)
            del self.path_to_id[rpath]
            del self.id_to_item[fid]
        else:
            # Mark the file as trashed, and set its parent to the root to avoid directory hierachy confusion
            item[TRASHED] = True
            item[PARENTS] = ['root']
            # TODO it would be great if this could be left as the original parent.
            # to do this, the trash directory logic would need to be changed
            self.api.update(fid, item)
            # Fix up internal state
            del self.path_to_id[rpath]
            new_rpath = self.trash_dir+'/'+item[NAME]
            new_lpath = self._lpath(new_rpath)
            self.path_to_id[new_rpath] = fid
            os.rename(lpath, new_lpath)
            if item[MTYPE] == FOLDER_MTYPE:
                del self.id_to_children[fid]

    def _init_tmp(self):
        dbg('Initializing temporary directory')
        if os.path.exists(self.tmp_dir):
            err('"{}" already exists! Remove it or rename it to continue.'.format(self.tmp_dir))
        os.makedirs(self.tmp_dir)
        os.makedirs(self.tmp_dir+self.trash_dir)

    def _cleanup_tmp(self):
        dbg('Cleaning up temporary directory')
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)

    def _get_parent(self, rpath):
        beg = rpath.rindex('/')
        if beg == 0:
            # parent is root
            return 'root'
        else:
            # find parent ID from cached metadata
            parent_path = rpath[:beg]
            if not parent_path in self.path_to_id:
                dbg('Failed to find parent "{}" in cached metadata!'.format(parent_path))
                raise FuseOSError(errno.ENOENT)
            return self.path_to_id[parent_path]

    def _rpath(self, lpath):
        # Return the remote filepath from the local path
        return lpath[len(self.tmp_dir):]

    def _lpath(self, rpath):
        # Return the local filepath from the remote path
        return self.tmp_dir+rpath

    ''' Filesystem methods '''

    def destroy(self, path):
        dbg('destroy: {}'.format(path))
        self._cleanup_tmp()
        # call _sync_remote on every file

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
        if not os.path.exists(lpath):
            raise FuseOSError(errno.ENOENT)
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
        if dev != 0:
            # Don't support creating special device files
            raise FuseOSError(errno.ENOSYS)
        lpath = self._lpath(path)
        # Make the locally cached copy, which will handle any errors (dirnoent, already exists, etc.)
        os.mknod(lpath, mode, dev)
        # Register the file with the remote
        self._register_file(path, False)

    def rmdir(self, path):
        dbg('rmdir: {}'.format(path))
        lpath = self._lpath(path)
        if not os.path.isdir(lpath):
            raise FuseOSError(errno.ENOTDIR)
        if len(os.listdir(lpath)) != 0:
            raise FuseOSError(errno.ENOTEMPTY)
        raise FuseOSError(errno.ENOSYS)
        self._remove_file(path)

    def unlink(self, path):
        dbg('unlink: {}'.format(path))
        # Since links aren't supported, assume there's only one link to this file
        if not os.path.exists(path):
            raise FuseOSError(errno.ENOENT)
        self._remove_file(path)

    def rename(self, old_path, new_path):
        dbg('rename: {} to {}'.format(old_path, new_path))
        if not old_path in self.path_to_id:
            raise FuseOSError(errno.ENOENT)
        if os.path.exists(new_path):
            raise FuseOSError(errno.EEXIST)
        fid = self.path_to_id[old_path]
        old_item = self.id_to_item[fid]
        new_parent = self._get_parent(new_path)
        new_item = self.api.change_parent(fid, old_item[PARENTS][0], new_parent)
        self._update_in_hierarchy(old_path, old_item, new_item)

    def utimens(self, path, times):
        dbg('utime: {} to {}'.format(path, times))
        lpath = self._lpath(path)
        os.utime(lpath, times)

    def symlink(self, path, new_path):
        dbg('symlink: {} to {}'.format(path, new_path))
        raise FuseOSError(errno.ENOSYS)

    def link(self, path, new_path):
        dbg('link: {} to {}'.format(path, new_path))
        raise FuseOSError(errno.ENOSYS)

    def mkdir(self, path, mode):
        dbg('mkdir: {}'.format(path))
        # Make the locally cached copy, which will handle any errors (dirnoent, already exists, etc.)
        os.mkdir(self._full_path(path), mode)
        # Register the file with the remote
        self._register_file(path, True)

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
        lpath = self._lpath(path)
        if not os.path.exists(lpath):
            # If creating a new file, register it
            self._register_file(path, False)
        return os.open(lpath, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path, length, offset, fh):
        dbg('read: {}'.format(path))
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def write(self, path, buf, offset, fh):
        dbg('write: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        dbg('truncate: {}'.format(path))
        raise FuseOSError(errno.ENOSYS)
        lpath = self._lpath(path)
        with open(lpath, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        dbg('flush: {}'.format(path))
        os.fsync(fh)
        self._sync_remote(path)

    def release(self, path, fh):
        dbg('release: {}'.format(path))
        self.flush(path, fh)
        os.close(fh)

    def fsync(self, path, fdatasync, fh):
        dbg('fsync: {}'.format(path))
        self.flush(path, fh)

def main(mountpoint):
    FUSE(DriveFS(), mountpoint, nothreads=True, foreground=True)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        err('Not enough arguments! usage: `./drivefs.py <mount-point>`')
    main(sys.argv[1])

