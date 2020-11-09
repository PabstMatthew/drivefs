# Consistency Policy
Consistency is enforced by the `_refresh_local` and the `_sync_remote` methods. 

## `_refresh_local`
Refreshing the local copy ensures that the locally cached version is up-to-date 
with the remote version of the file. The behavior is as follows:
- If file is not cached locally,
  - If the filename doesn't exist remotely, the file doesn't exist so nothing needs to be done.
  - If the filename does exist remotely, iteratively verify the path from the root down to the file.
- If file is cached locally, the cached attributes are compared to the remote attributes.
  - If the file doesn't exist anymore, remove the cached version.
  - If specific attributes don't match (mtime, parent, mimetype, trashed),
    the inconsistencies are dealt with depending on the difference:
    - If mimetype differs, something went wrong so an error is thrown.
    - If parent differs, fix up the locally cached hierarchy.
    - If trashed differs, move the file to the trash or out of the trash.
    - If mtime differs, download the new version of the file.
  - Otherwise, nothing needs to be done.

This method is used to guarantee consistency at time of `open()`. Additionally, 
calls to `access` may call this method to ensure that new files created remotely 
after initialization can be accessed.

## `_sync_remote`
Syncing the locally cached version of a file ensures that changes are 
propagated to the remote Drive.

