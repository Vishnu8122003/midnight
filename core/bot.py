# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


import pyrogram

from anony import config, logger


class DynamicFilter(pyrogram.filters.Filter):
    def __init__(self, initial_ids=None):
        self.ids = set(initial_ids or [])

    async def __call__(self, client, update: pyrogram.types.Message | pyrogram.types.CallbackQuery):
        user_id = None
        if isinstance(update, pyrogram.types.Message):
            user_id = update.from_user.id if update.from_user else None
        elif isinstance(update, pyrogram.types.CallbackQuery):
            user_id = update.from_user.id
        return user_id in self.ids

    def add(self, user_id):
        self.ids.add(user_id)

    def discard(self, user_id):
        self.ids.discard(user_id)

    def update(self, ids):
        self.ids.update(ids)

    def __contains__(self, user_id):
        return user_id in self.ids

    def __iter__(self):
        return iter(self.ids)

    def __len__(self):
        return len(self.ids)


class Bot(pyrogram.Client):
    def __init__(self):
        super().__init__(
            name="Anony",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            parse_mode=pyrogram.enums.ParseMode.HTML,
            max_concurrent_transmissions=7,
            link_preview_options=pyrogram.types.LinkPreviewOptions(is_disabled=True),
            in_memory=True,
        )
        self.owner = config.OWNER_ID
        self.logger = config.LOGGER_ID
        self.bl_users = DynamicFilter()
        self.sudoers = DynamicFilter([self.owner])

    async def boot(self):
        """
        Starts the bot and performs initial setup.

        Raises:
            SystemExit: If the bot fails to access the log group or is not an administrator in the logger group.
        """
        await super().start()
        self.id = self.me.id
        self.name = self.me.first_name
        self.username = self.me.username
        self.mention = self.me.mention

        try:
            await self.send_message(self.logger, "Bot Started")
            get = await self.get_chat_member(self.logger, self.id)
            if get.status != pyrogram.enums.ChatMemberStatus.ADMINISTRATOR:
                logger.warning("Bot is not an admin in logger group. Logging might be limited.")
        except Exception as ex:
            logger.warning(f"Bot has failed to access the log group: {self.logger}\nReason: {ex}")
        
        logger.info(f"Bot started as @{self.username}")

    async def exit(self):
        """
        Asynchronously stops the bot.
        """
        await super().stop()
        logger.info("Bot stopped.")
