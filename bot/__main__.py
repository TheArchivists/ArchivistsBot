from telegram.ext import CommandHandler, run_async

from bot import AUTHORIZED_CHATS, dispatcher, updater
from bot.helper.drive_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import *


@run_async
def start(update, context):
    LOGGER.info(
        'UID: {} - UN: {} - MSG: {}'.format(update.message.chat.id, update.message.chat.username, update.message.text))
    if update.message.chat.type == "private":
        sendMessage(f"Hey <b>{update.message.chat.first_name}</b>. Welcome to <b>SearchX Bot</b>", context.bot, update)
    else:
        sendMessage("I'm alive :)", context.bot, update)


@run_async
def log(update, context):
    send_log_file(context.bot, update)


@run_async
def list_drive(update, context):
    LOGGER.info("List function called")
    try:
        search = update.message.text.split(' ', maxsplit=1)[1]
    except IndexError:
        sendMessage('Send a Search Key Along With Command', context.bot, update)
        return

    reply = sendMessage('Searching...', context.bot, update)
    LOGGER.info(f"Searching: {search}")
    google_drive = GoogleDriveHelper(None)

    try:
        msg, button = google_drive.drive_list(search)
    except Exception as e:
        msg, button = "Oops.. Something weird happened.. ( • ̀ω•́ )✄╰U╯. Probably my ____ (content) was too big for " \
                      "telegraph's _____ (page).", None
        LOGGER.exception(e)

    editMessage(msg, reply, button)


@run_async
def authorize(update, context):
    reply_message = update.message.reply_to_message
    message_ = update.message.text.split(' ')
    with open('authorized_chats.txt', 'a') as file:
        if len(message_) == 2:
            chat_id = int(message_[1])
            if chat_id not in AUTHORIZED_CHATS:
                file.write(f'{chat_id}\n')
                AUTHORIZED_CHATS.add(chat_id)
                msg = 'Chat authorized'
            else:
                msg = 'User already authorized'
        else:
            if reply_message is None:
                # Trying to authorize a chat
                chat_id = update.effective_chat.id
                if chat_id not in AUTHORIZED_CHATS:
                    file.write(f'{chat_id}\n')
                    AUTHORIZED_CHATS.add(chat_id)
                    msg = 'Chat authorized'
                else:
                    msg = 'Already authorized chat'
            else:
                # Trying to authorize someone in specific
                user_id = reply_message.from_user.id
                if user_id not in AUTHORIZED_CHATS:
                    file.write(f'{user_id}\n')
                    AUTHORIZED_CHATS.add(user_id)
                    msg = 'Person Authorized to use the bot!'
                else:
                    msg = 'Person already authorized'
        sendMessage(msg, context.bot, update)


@run_async
def revoke_authorization(update, context):
    reply_message = update.message.reply_to_message
    message_ = update.message.text.split(' ')
    if len(message_) == 2:
        chat_id = int(message_[1])
        if chat_id in AUTHORIZED_CHATS:
            AUTHORIZED_CHATS.remove(chat_id)
            msg = 'Chat unauthorized'
        else:
            msg = 'User already unauthorized'
    else:
        if reply_message is None:
            # Trying to revoke authorization of a chat
            chat_id = update.effective_chat.id
            if chat_id in AUTHORIZED_CHATS:
                AUTHORIZED_CHATS.remove(chat_id)
                msg = 'Chat unauthorized'
            else:
                msg = 'Already unauthorized chat'
        else:
            # Trying to authorize someone in specific
            user_id = reply_message.from_user.id
            if user_id in AUTHORIZED_CHATS:
                AUTHORIZED_CHATS.remove(user_id)
                msg = 'Person unauthorized to use the bot!'
            else:
                msg = 'Person already unauthorized!'
    with open('authorized_chats.txt', 'a') as file:
        file.truncate(0)
        for i in AUTHORIZED_CHATS:
            file.write(f'{i}\n')
    sendMessage(msg, context.bot, update)


@run_async
def send_auth_chats(update, context):
    users = ''
    for user in AUTHORIZED_CHATS:
        users += f"{user}\n"
    users = users if users != '' else "None"
    sendMessage(f'Authorized Chats are : \n<code>{users}</code>\n', context.bot, update)


def main():
    start_handler = CommandHandler(BotCommands.StartCommand, start,
                                   filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
    log_handler = CommandHandler(BotCommands.LogCommand, log, filters=CustomFilters.owner_filter)
    list_handler = CommandHandler(BotCommands.ListCommand, list_drive,
                                  filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
    send_auth_handler = CommandHandler(command=BotCommands.AuthorizedUsersCommand, callback=send_auth_chats,
                                       filters=CustomFilters.owner_filter)
    authorize_handler = CommandHandler(command=BotCommands.AuthorizeCommand, callback=authorize,
                                       filters=CustomFilters.owner_filter)
    unauthorized_handler = CommandHandler(command=BotCommands.UnAuthorizeCommand, callback=revoke_authorization,
                                          filters=CustomFilters.owner_filter)

    dispatcher.add_handler(send_auth_handler)
    dispatcher.add_handler(authorize_handler)
    dispatcher.add_handler(unauthorized_handler)
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(log_handler)
    dispatcher.add_handler(list_handler)

    updater.start_polling()
    LOGGER.info("Yeah I'm running!")
    updater.idle()


main()
