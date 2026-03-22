# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


try:
    import ujson as json
except ImportError:
    import json
import os
import asyncio
from random import randint
from time import time

from anony import config, logger, userbot

DB_FILE = "db.json"

class MockCollection:
    def __init__(self, data, save_func):
        self.data = data
        self.save_func = save_func

    async def find_one(self, query):
        _id = query.get("_id")
        return self.data.get(str(_id))

    async def update_one(self, query, update, upsert=False):
        _id = str(query.get("_id"))
        if "$set" in update:
            if _id not in self.data:
                if not upsert: return
                self.data[_id] = {}
            self.data[_id].update(update["$set"])
        if "$addToSet" in update:
            if _id not in self.data:
                if not upsert: return
                self.data[_id] = {}
            for field, value in update["$addToSet"].items():
                if field not in self.data[_id]:
                    self.data[_id][field] = []
                if value not in self.data[_id][field]:
                    self.data[_id][field].append(value)
        if "$pull" in update:
            if _id in self.data:
                for field, value in update["$pull"].items():
                    if field in self.data[_id] and value in self.data[_id][field]:
                        self.data[_id][field].remove(value)
        await self.save_func()

    async def insert_one(self, doc):
        _id = str(doc.get("_id"))
        self.data[_id] = doc
        await self.save_func()

    async def delete_one(self, query):
        _id = str(query.get("_id"))
        self.data.pop(_id, None)
        await self.save_func()

    async def find(self):
        for item in self.data.values():
            yield item

    async def drop(self):
        self.data.clear()
        await self.save_func()

    async def insert_many(self, docs):
        for doc in docs:
            _id = str(doc.get("_id"))
            self.data[_id] = doc
        await self.save_func()

class MongoDB:
    def __init__(self):
        self._db_file = DB_FILE
        self._data = {}
        self._lock = asyncio.Lock()
        self._pending_save = False
        self.load_data()

        self.admin_list = {}
        self.active_calls = {}
        self.admin_play = []
        self.blacklisted = []
        self.cmd_delete = []
        self.loop = {}
        self.notified = []

        # Simulated collections
        self.cache = MockCollection(self._data.setdefault("cache", {}), self.save_data)
        self.assistantdb = MockCollection(self._data.setdefault("assistant", {}), self.save_data)
        self.authdb = MockCollection(self._data.setdefault("auth", {}), self.save_data)
        self.chatsdb = MockCollection(self._data.setdefault("chats", {}), self.save_data)
        self.langdb = MockCollection(self._data.setdefault("lang", {}), self.save_data)
        self.usersdb = MockCollection(self._data.setdefault("users", {}), self.save_data)

        self.logger = False
        self.assistant = {}
        self.auth = {}
        self.chats = []
        self.lang = {}
        self.users = []

    def load_data(self):
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r") as f:
                    self._data = json.load(f)
            except Exception as e:
                logger.error(f"Error loading {DB_FILE}: {e}")
                self._data = {}
        else:
            self._data = {}

    async def save_data(self):
        if self._pending_save:
            return
        self._pending_save = True
        asyncio.create_task(self._scheduled_save())

    async def _scheduled_save(self):
        await asyncio.sleep(2)
        try:
            await asyncio.to_thread(self._sync_save)
        finally:
            self._pending_save = False

    def _sync_save(self):
        try:
            with open(self._db_file, "w") as f:
                json.dump(self._data, f)
        except Exception as e:
            logger.error(f"Error saving {self._db_file}: {e}")

    async def connect(self) -> None:
        logger.info("Local JSON storage initialized.")
        await self.load_cache()

    async def close(self) -> None:
        await self.save_data()
        logger.info("Local JSON storage saved and closed.")

    # CACHE
    async def get_call(self, chat_id: int) -> bool:
        return chat_id in self.active_calls

    async def add_call(self, chat_id: int) -> None:
        self.active_calls[chat_id] = 1

    async def remove_call(self, chat_id: int) -> None:
        self.active_calls.pop(chat_id, None)

    async def playing(self, chat_id: int, paused: bool = None) -> bool | None:
        if paused is not None:
            self.active_calls[chat_id] = int(not paused)
        return bool(self.active_calls.get(chat_id, 0))

    async def get_admins(self, chat_id: int, reload: bool = False) -> list[int]:
        from anony.helpers._admins import reload_admins
        if chat_id not in self.admin_list or reload:
            self.admin_list[chat_id] = await reload_admins(chat_id)
        return self.admin_list[chat_id]

    async def get_loop(self, chat_id: int) -> int:
        return self.loop.get(chat_id, 0)

    async def set_loop(self, chat_id: int, count: int) -> None:
        self.loop[chat_id] = count

    # AUTH METHODS
    async def _get_auth(self, chat_id: int) -> set[int]:
        if chat_id not in self.auth:
            doc = await self.authdb.find_one({"_id": chat_id}) or {}
            self.auth[chat_id] = set(doc.get("user_ids", []))
        return self.auth[chat_id]

    async def is_auth(self, chat_id: int, user_id: int) -> bool:
        return user_id in await self._get_auth(chat_id)

    async def add_auth(self, chat_id: int, user_id: int) -> None:
        users = await self._get_auth(chat_id)
        if user_id not in users:
            users.add(user_id)
            await self.authdb.update_one(
                {"_id": chat_id}, {"$addToSet": {"user_ids": user_id}}, upsert=True
            )

    async def rm_auth(self, chat_id: int, user_id: int) -> None:
        users = await self._get_auth(chat_id)
        if user_id in users:
            users.discard(user_id)
            await self.authdb.update_one(
                {"_id": chat_id}, {"$pull": {"user_ids": user_id}}
            )

    # ASSISTANT METHODS
    async def set_assistant(self, chat_id: int) -> int:
        num = randint(1, len(userbot.clients))
        await self.assistantdb.update_one(
            {"_id": chat_id}, {"$set": {"num": num}}, upsert=True,
        )
        self.assistant[chat_id] = num
        return num

    async def get_assistant(self, chat_id: int):
        from anony import anon
        if chat_id not in self.assistant:
            doc = await self.assistantdb.find_one({"_id": chat_id})
            num = doc["num"] if doc else await self.set_assistant(chat_id)
            self.assistant[chat_id] = num
        return anon.clients[self.assistant[chat_id] - 1]

    async def get_client(self, chat_id: int):
        if chat_id not in self.assistant:
            await self.get_assistant(chat_id)
        return {1: userbot.one, 2: userbot.two, 3: userbot.three}.get(self.assistant[chat_id])

    # BLACKLIST METHODS
    async def add_blacklist(self, chat_id: int) -> None:
        if str(chat_id).startswith("-"):
            self.blacklisted.append(chat_id)
            return await self.cache.update_one(
                {"_id": "bl_chats"}, {"$addToSet": {"chat_ids": chat_id}}, upsert=True
            )
        await self.cache.update_one(
            {"_id": "bl_users"}, {"$addToSet": {"user_ids": chat_id}}, upsert=True
        )

    async def del_blacklist(self, chat_id: int) -> None:
        if str(chat_id).startswith("-"):
            if chat_id in self.blacklisted: self.blacklisted.remove(chat_id)
            return await self.cache.update_one(
                {"_id": "bl_chats"}, {"$pull": {"chat_ids": chat_id}},
            )
        await self.cache.update_one(
            {"_id": "bl_users"}, {"$pull": {"user_ids": chat_id}},
        )

    async def get_blacklisted(self, chat: bool = False) -> list[int]:
        if chat:
            if not self.blacklisted:
                doc = await self.cache.find_one({"_id": "bl_chats"})
                self.blacklisted.extend(doc.get("chat_ids", []) if doc else [])
            return self.blacklisted
        doc = await self.cache.find_one({"_id": "bl_users"})
        return doc.get("user_ids", []) if doc else []

    # CHAT METHODS
    async def is_chat(self, chat_id: int) -> bool:
        return chat_id in self.chats

    async def add_chat(self, chat_id: int) -> None:
        if not await self.is_chat(chat_id):
            self.chats.append(chat_id)
            await self.chatsdb.insert_one({"_id": chat_id})

    async def rm_chat(self, chat_id: int) -> None:
        if await self.is_chat(chat_id):
            self.chats.remove(chat_id)
            await self.chatsdb.delete_one({"_id": chat_id})

    async def get_chats(self) -> list:
        if not self.chats:
            self.chats.extend([chat["_id"] async for chat in self.chatsdb.find()])
        return self.chats

    # COMMAND DELETE
    async def get_cmd_delete(self, chat_id: int) -> bool:
        if chat_id not in self.cmd_delete:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("cmd_delete"):
                self.cmd_delete.append(chat_id)
        return chat_id in self.cmd_delete

    async def set_cmd_delete(self, chat_id: int, delete: bool = False) -> None:
        if delete:
            self.cmd_delete.append(chat_id)
        elif chat_id in self.cmd_delete:
            self.cmd_delete.remove(chat_id)
        await self.chatsdb.update_one(
            {"_id": chat_id}, {"$set": {"cmd_delete": delete}}, upsert=True,
        )

    # LANGUAGE METHODS
    async def set_lang(self, chat_id: int, lang_code: str):
        await self.langdb.update_one(
            {"_id": chat_id}, {"$set": {"lang": lang_code}}, upsert=True,
        )
        self.lang[chat_id] = lang_code

    async def get_lang(self, chat_id: int) -> str:
        if chat_id not in self.lang:
            doc = await self.langdb.find_one({"_id": chat_id})
            self.lang[chat_id] = doc["lang"] if doc else config.LANG_CODE
        return self.lang[chat_id]

    # LOGGER METHODS
    async def is_logger(self) -> bool:
        return self.logger

    async def get_logger(self) -> bool:
        doc = await self.cache.find_one({"_id": "logger"})
        if doc:
            self.logger = doc["status"]
        return self.logger

    async def set_logger(self, status: bool) -> None:
        self.logger = status
        await self.cache.update_one(
            {"_id": "logger"}, {"$set": {"status": status}}, upsert=True,
        )

    # PLAY MODE METHODS
    async def get_play_mode(self, chat_id: int) -> bool:
        if chat_id not in self.admin_play:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("admin_play"):
                self.admin_play.append(chat_id)
        return chat_id in self.admin_play

    async def set_play_mode(self, chat_id: int, remove: bool = False) -> None:
        if remove and chat_id in self.admin_play:
            self.admin_play.remove(chat_id)
        elif not remove:
            self.admin_play.append(chat_id)
        await self.chatsdb.update_one(
            {"_id": chat_id}, {"$set": {"admin_play": not remove}}, upsert=True,
        )

    # SUDO METHODS
    async def add_sudo(self, user_id: int) -> None:
        await self.cache.update_one(
            {"_id": "sudoers"}, {"$addToSet": {"user_ids": user_id}}, upsert=True
        )

    async def del_sudo(self, user_id: int) -> None:
        await self.cache.update_one(
            {"_id": "sudoers"}, {"$pull": {"user_ids": user_id}}
        )

    async def get_sudoers(self) -> list[int]:
        doc = await self.cache.find_one({"_id": "sudoers"})
        return doc.get("user_ids", []) if doc else []

    # USER METHODS
    async def is_user(self, user_id: int) -> bool:
        return user_id in self.users

    async def add_user(self, user_id: int) -> None:
        if not await self.is_user(user_id):
            self.users.append(user_id)
            await self.usersdb.insert_one({"_id": user_id})

    async def rm_user(self, user_id: int) -> None:
        if await self.is_user(user_id):
            self.users.remove(user_id)
            await self.usersdb.delete_one({"_id": user_id})

    async def get_users(self) -> list:
        if not self.users:
            self.users.extend([user["_id"] async for user in self.usersdb.find()])
        return self.users

    async def migrate_coll(self) -> None:
        pass # Not needed for fresh local storage

    async def load_cache(self) -> None:
        await self.get_chats()
        await self.get_users()
        await self.get_blacklisted(True)
        await self.get_logger()
        logger.info("Local database cache loaded.")
