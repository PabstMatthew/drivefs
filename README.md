# Google Drive FUSE
A FUSE implementation of Google Drive, which allows you to mount your 
Google Drive filesystem locally. The filesystem provides close-to-open 
consistency, meaning that a file will be consistent with the remote drive 
upon opening it and will be synced with the remote drive upon closing. 

Additionally, DriveFS provides the following features:
- A .Trash directory which stores all deleted files. Files deleted from 
  this directory are permanently deleted.
- Configurable filetype exports for GSuite product-specific files such as 
  Google Docs, Sheets, and Slides. These files will automatically be 
  exported to a configurable filetype and extension, and then reconverted 
  and uploaded upon modification.

## Setup
`./setup.sh` (only works for Ubuntu right now)

## Running
`./drivefs.py <mount-point>`

