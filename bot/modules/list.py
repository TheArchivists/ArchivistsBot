from telegram.ext import CommandHandler, run_async

from bot import LOGGER, dispatcher
from bot.helper.drive_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import send_message, edit_message


@run_async
def list_drive(update, context):
    try:
        search = update.message.text.split(' ', maxsplit=1)[1]
    except IndexError:
        send_message('Send A Search Key Along With Command', context.bot, update)
        return

    reply = send_message('Searching...', context.bot, update)

    LOGGER.info(f"Searching: {search}")

    google_drive = GoogleDriveHelper(None)
    try:
        msg, button = google_drive.drive_list(search)
    except Exception as e:
        msg, button = "Damn... Some crappy exception has popped up. Probably telegraph content limit exceeded. My " \
                      "____ (content) was too big for telegraph's _____ (page).", None
        LOGGER.exception(e)

    edit_message(msg, reply, button)


list_handler = CommandHandler(BotCommands.ListCommand, list_drive,
                              filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
dispatcher.add_handler(list_handler)
