from utils import *

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

import pickle
import os.path
import re
import shutil
import io

CLIENT_SECRET_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive']
TYPE_FNAME = 'types.py'
CONFIG_DIR = os.path.expanduser('~/.drivefs/')
CONFIG_TYPE_PATH = CONFIG_DIR+TYPE_FNAME

FOLDER_MTYPE = 'application/vnd.google-apps.folder'

ID = 'id'
NAME = 'name'
MTYPE = 'mimeType'
ATIME = 'viewedByMeTime'
MTIME = 'modifiedTime'
PARENTS = 'parents'
TRASHED = 'trashed'
FIELD_LIST = [ID, NAME, MTYPE, MTIME, PARENTS, ATIME, MTIME, PARENTS, TRASHED]
FIELDS = ', '.join(FIELD_LIST)

class DriveAPI():
    def __init__(self):
        dbg('Creating API instance.')
        self.creds = None
        self.types = None

        self._init_config()
        self._init_creds()

        dbg('Building service.')
        self.service = build('drive', 'v3', credentials=self.creds)

    def _init_creds(self):
        # This file stores the user's access and refresh tokens, 
        # and is created automatically when auth flow completes for the first time.
        dbg('Loading access credentials.')
        token_path = os.path.join(CONFIG_DIR, 'token.pkl')
        if os.path.exists(token_path):
            dbg('Attempting to load saved creds from {}.'.format(token_path))
            with open(token_path, 'rb') as token:
                self.creds = pickle.load(token)
        # If no valid creds exist, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                dbg('Creds had expired. Refreshing.')
                self.creds.refresh(Request())
            else:
                dbg('Prompting user for permission.')
                if not os.path.exists(CLIENT_SECRET_FILE):
                    err('No OAuth credentials found! Expected a "{}" file. \
                         Since this project is not registered as an official project, \
                         you have to create your own OAuth client at \
                         https://console.developers.google.com/apis/credentials/oauthclient'.format(CLIENT_SECRET_FILE))
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
                self.creds = flow.run_local_server(port=0)
            # Save the creds for the next run
            dbg('Saving credentials for next time.')
            with open(token_path, 'wb') as token:
                pickle.dump(self.creds, token)

    def _init_config(self):
        dbg('Loading configuration.')
        if not os.path.exists(CONFIG_DIR):
            dbg('No config directory exists. Creating default configuration.')
            os.makedirs(CONFIG_DIR)
        if not os.path.exists(CONFIG_TYPE_PATH):
            dbg('No mimetype config file exists. Creating default mimetype config.')
            shutil.copy(TYPE_FNAME, CONFIG_TYPE_PATH)
        with open(CONFIG_TYPE_PATH, 'r') as f:
            contents = f.read()
            self.types = eval(contents)
            dbg('Loaded config: '+str(self.types))

    def exec_query(self, query):
        dbg('Executing query "{}".'.format(query))
        results = self.service.files().list(
            q=query,
            spaces='drive',
            corpora='user',
            fields='files({})'.format(FIELDS)
        ).execute()
        return results.get('files', [])

    def get_file(self, fid):
        dbg('Finding file by ID {}'.format(fid))
        results = self.service.files().get(
            fileId=fid,
            fields=FIELDS,
        ).execute()
        return results

    def traverse_path(self, path):
        dbg('Traversing path "{}".'.format(path))
        # TODO cache the results of this lookup somewhere
        hierarchy = re.split(r'/+', path)
        last_item = None
        parent_id = 'root'
        for fname in hierarchy:
            if not fname:
                # handle any empty filenames resulting from extra slashes
                continue
            # look for the current file in the current parent
            items = self.exec_query("name = '{0}' and '{1}' in parents".format(fname, parent_id))
            if not items:
                dbg('File "{}" not found!'.format(fname))
                return None
            elif len(items) != 1:
                dbg('Multiple files with the name "{}" were found!'.format(fname))
                return None
            # remember the file we found
            item = items[0]
            parent_id = item['id']
            last_item = item
        return last_item

    def download(self, node, local_path, cache=True):
        dbg('Downloading file "{}" to local path "{}".'.format(str(node), local_path))
        if cache and os.path.exists(local_path):
            return
        file_id = node[ID]
        mimetype = node[MTYPE]
        if mimetype == FOLDER_MTYPE:
            # if this is a folder, make sure the folder exists locally
            if not os.path.exists(local_path):
                os.makedirs(local_path)
            return
        elif mimetype in self.types:
            # if this file is a Google Workspace document, we need to export it using the configured mimetype
            mimetype = self.types[mimetype][0]
            request = self.service.files().export_media(fileId=file_id, mimeType=mimetype)
        else:
            # otherwise, this is just a generic file
            request = self.service.files().get_media(fileId=file_id)
        # download the file
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            #dbg("Download {}%.".format(int(status.progress()*100)))
        # write the data to a file
        with open(local_path, "wb") as f:
            f.write(fh.getbuffer())

    def delete(self, fid):
        dbg('Deleting file with ID "{}"'.format(fid))
        self.service.files().delete(fileId=fid).execute()

    def update(self, fid, body):
        dbg('Updating file with ID "{}" and body "{}"'.format(fid, body))
        return self.service.files().update(fileId=fid, body=body, fields=FIELDS).execute()

    def change_parent(self, fid, old_parent, new_parent):
        dbg('Changing parent for file with ID "{}", old parent "{}", and new parent "{}"'.format(fid, old_parent, new_parent))
        return self.service.files().update(fileId=fid, addParents=new_parent, 
                    removeParents=old_parent, fields=FIELDS).execute()

    def create(self, name, parent, is_dir, in_trash):
        dbg('Creating new file "{}" with parent "{}"'.format(name, parent))
        # Register a new file with the remote, without uploading any data
        file_metadata = {
            NAME: name,
            PARENTS: [parent]
        }
        if is_dir:
            file_metadata[MTYPE] = FOLDER_MTYPE
        item = self.service.files().create(body=file_metadata, fields=FIELDS).execute()
        if in_trash:
            body = {TRASHED: True}
            item = self.trash(item[ID], body)
        return item

    def upload(self, lpath, fid):
        dbg('Uploading local path "{}" for file ID "{}"'.format(lpath, fid))
        media = MediaFileUpload(lpath)
        return self.service.files().update(fileId=fid, media_body=media, fields=FIELDS).execute()

def main():
    api = DriveAPI()

if __name__ == '__main__':
    main()
