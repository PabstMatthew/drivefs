from utils import *

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

import pickle
import os.path
import re

SCOPES = ['https://www.googleapis.com/auth/drive']
CONFIG_DIR = os.path.expanduser('~/.drivefs/')

class DriveAPI():
    def __init__(self):
        dbg('Creating API instance ...')
        self.creds = None

        self._init_config()
        self._init_creds()

        dbg('Building service ...')
        self.service = build('drive', 'v3', credentials=self.creds)


    def _init_creds(self):
        # This file stores the user's access and refresh tokens, 
        # and is created automatically when auth flow completes for the first time.
        dbg('Loading access credentials ...')
        token_path = os.path.join(CONFIG_DIR, 'token.pkl')
        if os.path.exists(token_path):
            dbg('Attempting to load saved creds from {} ...'.format(token_path))
            with open(token_path, 'rb') as token:
                self.creds = pickle.load(token)
        # If no valid creds exist, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                dbg('Creds had expired. Refreshing ...')
                self.creds.refresh(Request())
            else:
                dbg('Prompting user for permission ...')
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                self.creds = flow.run_local_server(port=0)
            # Save the creds for the next run
            dbg('Saving credentials for next time ...')
            with open(token_path, 'wb') as token:
                pickle.dump(self.creds, token)
        

    def _init_config(self):
        dbg('Loading configuration ...')
        if not os.path.exists(CONFIG_DIR):
            dbg('No config directory exists. Creating default configuration ...')
            os.makedirs(CONFIG_DIR)
        # TODO load/create configuration


    def exec_query(self, query):
        dbg('Executing query "{}" ...'.format(query))
        results = self.service.files().list(
            q=query,
            spaces='drive',
            corpora='user',
            fields='files(id, name, mimeType, modifiedTime, viewedByMeTime)'
        ).execute()
        return results
    
    def traverse_path(self, path):
        # TODO replace this if it's too slow to check the complete path everytime
        dbg('Traversing path "{}" ...'.format(path))
        hierarchy = re.split(r'/+', path)
        last_item = None
        parent_id = 'root'
        for fname in hierarchy:
            if not fname:
                # handle any empty filenames resulting from extra slashes
                continue
            # look for the current file in the current parent
            results = self.exec_query("name = '{0}' and '{1}' in parents".format(fname, parent_id))
            items = results.get('files', [])
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

def main():
    api = DriveAPI()

    # API call sample
    node = api.traverse_path('/folder1/doc1')
    print(node)
    '''
    results = api.exec_query("'root' in parents")
    items = results.get('files', [])
    if not items:
        print('No files found.')
    else:
        print('Files:')
        for item in items:
            print('{0}: {1} ({2})'.format(item['name'], item['id'], item['parents'] if 'parents' in item else 'no parents'))
    '''

if __name__ == '__main__':
    main()
