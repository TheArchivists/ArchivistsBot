import logging
import os
import pickle
import re

import requests
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from telegram import InlineKeyboardMarkup

from bot import DRIVE_NAME, DRIVE_ID, INDEX_URL, telegraph_obj
from bot.helper.telegram_helper import button_builder

LOGGER = logging.getLogger(__name__)
logging.getLogger('googleapiclient.discovery').setLevel(logging.ERROR)

SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
telegraph_limit = 95


def get_readable_file_size(size_in_bytes) -> str:
    if size_in_bytes is None:
        return '0B'
    index = 0
    size_in_bytes = int(size_in_bytes)
    while size_in_bytes >= 1024:
        size_in_bytes /= 1024
        index += 1
    try:
        return f'{round(size_in_bytes, 2)}{SIZE_UNITS[index]}'
    except IndexError:
        return 'File too large'


def escapes(str_val):
    chars = ['\\', "'", '"', r'\a', r'\b', r'\f', r'\n', r'\r', r'\t']
    for char in chars:
        str_val = str_val.replace(char, '\\' + char)
    return str_val


class GoogleDriveHelper:
    def __init__(self, name=None, listener=None):
        self.listener = listener
        self.name = name
        self.__G_DRIVE_TOKEN_FILE = "token.pickle"
        # Check https://developers.google.com/drive/scopes for all available scopes
        self.__OAUTH_SCOPE = ['https://www.googleapis.com/auth/drive']
        self.__service = self.authorize()
        self.telegraph_content = []
        self.num_of_path = 0
        self.path = []

    def authorize(self):
        # Get credentials
        credentials = None
        if os.path.exists(self.__G_DRIVE_TOKEN_FILE):
            with open(self.__G_DRIVE_TOKEN_FILE, 'rb') as f:
                credentials = pickle.load(f)
        if credentials is None or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', self.__OAUTH_SCOPE)
                LOGGER.info(flow)
                credentials = flow.run_console(port=0)

            # Save the credentials for the next run
            with open(self.__G_DRIVE_TOKEN_FILE, 'wb') as token:
                pickle.dump(credentials, token)
        return build('drive', 'v3', credentials=credentials, cache_discovery=False)

    def get_recursive_list(self, file, root_id="root"):
        return_list = []
        if not root_id:
            root_id = file.get('teamDriveId')
        if root_id == "root":
            root_id = self.__service.files().get(fileId='root', fields="id").execute().get('id')
        x = file.get("name")
        y = file.get("id")
        while y != root_id:
            return_list.append(x)
            file = self.__service.files().get(
                fileId=file.get("parents")[0],
                supportsAllDrives=True,
                fields='id, name, parents'
            ).execute()
            x = file.get("name")
            y = file.get("id")
        return_list.reverse()
        return return_list

    def drive_query_backup(self, parent_id, file_name):
        file_name = escapes(str(file_name))
        query = f"'{parent_id}' in parents and (name contains '{file_name}')"
        response = self.__service.files().list(supportsTeamDrives=True,
                                               includeTeamDriveItems=True,
                                               q=query,
                                               spaces='drive',
                                               pageSize=1000,
                                               fields='files(id, name, mimeType, size, parents)',
                                               orderBy='folder, modifiedTime desc').execute()["files"]
        return response

    def drive_query(self, parent_id, search_type, file_name):
        query = ""
        if search_type is not None:
            if search_type == '-d':
                query += "mimeType = 'application/vnd.google-apps.folder' and "
            elif search_type == '-f':
                query += "mimeType != 'application/vnd.google-apps.folder' and "
        var = re.split('[ ._,\\[\\]-]+', file_name)
        for text in var:
            if text != '':
                query += f"name contains '{text}' and "
        query += "trashed=false"
        response = []
        try:
            if parent_id != "root":
                response = self.__service.files().list(supportsTeamDrives=True,
                                                       includeTeamDriveItems=True,
                                                       teamDriveId=parent_id,
                                                       q=query,
                                                       corpora='drive',
                                                       spaces='drive',
                                                       pageSize=1000,
                                                       fields='files(id, name, mimeType, size, teamDriveId, parents)',
                                                       orderBy='folder, modifiedTime desc').execute()["files"]
            else:
                response = self.__service.files().list(q=query + " and 'me' in owners",
                                                       pageSize=1000,
                                                       spaces='drive',
                                                       fields='files(id, name, mimeType, size, parents)',
                                                       orderBy='folder, modifiedTime desc').execute()["files"]
        except Exception as e:
            LOGGER.exception(f"Error while calling drive api function...")
            LOGGER.exception(e)
        LOGGER.info(f"ParentId : {parent_id}")
        LOGGER.info(f"Primary Response Length: {len(response)}")
        if len(response) <= 0:
            response = self.drive_query_backup(parent_id, file_name)
            LOGGER.info(f"Backup Response Length: {len(response)}")
        return response

    def edit_telegraph(self):
        nxt_page = 1
        prev_page = 0
        for content in self.telegraph_content:
            if nxt_page == 1:
                content += f'<b><a href="https://graph.org/{self.path[nxt_page]}">Next</a></b>'
                nxt_page += 1
            else:
                if prev_page < self.num_of_path:
                    content += f'<b><a href="https://graph.org/{self.path[prev_page]}">Previous</a></b>'
                    prev_page += 1
                if nxt_page < self.num_of_path:
                    content += f'<b> | <a href="https://graph.org/{self.path[nxt_page]}">Next</a></b>'
                    nxt_page += 1
            telegraph_obj.edit_page(path=self.path[prev_page],
                                    title='SearchX',
                                    html_content=content)

    def drive_list(self, file_name):
        file_name = escapes(file_name)
        search_type = None
        if re.search("^-d ", file_name, re.IGNORECASE):
            search_type = '-d'
            file_name = file_name[2: len(file_name)]
        elif re.search("^-f ", file_name, re.IGNORECASE):
            search_type = '-f'
            file_name = file_name[2: len(file_name)]
        if len(file_name) > 2:
            remove_list = ['A', 'a', 'X', 'x']
            if file_name[1] == ' ' and file_name[0] in remove_list:
                file_name = file_name[2: len(file_name)]
        msg = ''
        index = -1
        content_count = 0
        reached_max_limit = False
        add_title_msg = True
        for parent_id in DRIVE_ID:
            add_drive_title = True
            response = self.drive_query(parent_id, search_type, file_name)

            index += 1
            if response:
                for file in response:

                    if add_title_msg:
                        msg = f'<h3>I found: {file_name}</h3><br><b><a href="https://github.com/AnimeKaizoku' \
                              f'/ArchivistsBot"> Bot Repo </a></b> || @TheArchivists '
                        add_title_msg = False
                    if add_drive_title:
                        msg += f"╾────────────╼<br><b>{DRIVE_NAME[index]}</b><br>╾────────────╼<br>"
                        add_drive_title = False

                    # Detect Whether Current Entity is a Folder or File.
                    if file.get('mimeType') == "application/vnd.google-apps.folder":
                        msg += f"🗃️<code>{file.get('name')}</code> <b>(folder)</b><br>" \
                               f"<b><a href='https://drive.google.com/drive/folders/{file.get('id')}'>Google Drive " \
                               f"link</a></b> "
                        if INDEX_URL[index] is not None:
                            url_path = "/".join(
                                [requests.utils.quote(n, safe='') for n in self.get_recursive_list(file, parent_id)])
                            url = f'{INDEX_URL[index]}/{url_path}/'
                            msg += f'<b> | <a href="{url}">Index Link</a></b>'
                    else:
                        msg += f"<code>{file.get('name')}</code> <b>({get_readable_file_size(file.get('size'))})" \
                               f"</b><br><b><a href='https://drive.google.com/uc?id={file.get('id')}" \
                               f"&export=download'>Google Drive link</a></b> "
                        if INDEX_URL[index] is not None:
                            url_path = "/".join(
                                [requests.utils.quote(n, safe='') for n in self.get_recursive_list(file, parent_id)])
                            url = f'{INDEX_URL[index]}/{url_path}'
                            msg += f'<b> | <a href="{url}">Index link</a></b>'

                    msg += '<br><br>'
                    content_count += 1
                    if content_count >= telegraph_limit:
                        reached_max_limit = True
                        break

        if msg != '':
            self.telegraph_content.append(msg)

        if len(self.telegraph_content) == 0:
            return "I ..I found nothing of that sort :(", None

        pref = "♙"
        for content in self.telegraph_content:
            self.path.append(
                telegraph_obj.create_page(title=f'{pref} The Archivists • 04 • Dragonia', html_content=content)['path'])

        self.num_of_path = len(self.path)
        if self.num_of_path > 1:
            self.edit_telegraph()

        msg = "Found " + ("95+" if content_count > 95 else f"{content_count}") + " results."

        if reached_max_limit:
            msg += "\n(Only showing top 95 results.)"

        buttons = button_builder.ButtonMaker()
        buttons.build_button("Click Here for results", f"https://graph.org/{self.path[0]}")

        return msg, InlineKeyboardMarkup(buttons.build_menu(1))
