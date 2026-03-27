from __future__ import annotations

import asyncio
import logging
import os
from typing import Iterable

from aiogram import Bot, Dispatcher, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router()

BOT_TOKEN = os.getenv("BOT_TOKEN", "562973709:AAGTl_FtxfW3qKuxXbkv0Kc41h4-IaEcAmw")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1132147659"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def extract_visible_symbol(entity, source_text: str | None) -> str:
    """Extract visible emoji fallback from text entity when possible."""
    if not source_text:
        return "🔥"

    try:
        value = entity.extract_from(source_text)
        return value if value else "🔥"
    except Exception:
        return "🔥"


def collect_custom_emoji_pairs(message: Message) -> list[tuple[str, str]]:
    """Collect (visible_symbol, custom_emoji_id) pairs from message text/caption/sticker."""
    pairs: list[tuple[str, str]] = []

    text_sources: list[tuple[Iterable, str | None]] = [
        (message.entities or [], message.text),
        (message.caption_entities or [], message.caption),
    ]

    for entities, source_text in text_sources:
        for entity in entities:
            if entity.type == "custom_emoji" and entity.custom_emoji_id:
                visible_symbol = extract_visible_symbol(entity, source_text)
                pairs.append((visible_symbol, entity.custom_emoji_id))

    if message.sticker and message.sticker.custom_emoji_id:
        pairs.append((message.sticker.emoji or "🔥", message.sticker.custom_emoji_id))

    return pairs


def deduplicate_pairs(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Preserve order while removing duplicate ids."""
    seen: set[str] = set()
    result: list[tuple[str, str]] = []

    for symbol, custom_id in pairs:
        if custom_id in seen:
            continue
        seen.add(custom_id)
        result.append((symbol, custom_id))

    return result


def build_response_text(message: Message) -> str:
    """Build response for user with found ids and ready-to-use CustomEmoji snippets."""
    pairs = deduplicate_pairs(collect_custom_emoji_pairs(message))

    if not pairs:
        return (
            "Custom emoji не найдены.\n\n"
            "Что поддерживается:\n"
            "- premium/custom emoji в тексте\n"
            "- premium/custom emoji в подписи\n"
            "- custom emoji sticker"
        )

    ids_block = "\n".join(custom_id for _, custom_id in pairs)
    code_block = "\n".join(
        f'CustomEmoji({symbol!r}, custom_emoji_id={custom_id!r})'
        for symbol, custom_id in pairs
    )

    return (
        f"Найдено custom emoji: {len(pairs)}\n\n"
        f"ID:\n{ids_block}\n\n"
        f"Готовые строки:\n{code_block}"
    )


async def notify_admin_about_incoming(bot: Bot, message: Message) -> None:
    """Duplicate user incoming message to admin chat."""
    if message.chat.id == ADMIN_ID:
        return

    header = (
        "📥 Incoming message\n"
        f"from_user_id: {message.from_user.id if message.from_user else 'unknown'}\n"
        f"chat_id: {message.chat.id}\n"
        f"full_name: {message.from_user.full_name if message.from_user else 'unknown'}"
    )

    try:
        await bot.send_message(ADMIN_ID, header)
        await message.copy_to(chat_id=ADMIN_ID)
    except (TelegramBadRequest, TelegramForbiddenError):
        fallback_text = message.text or message.caption or "<non-text message>"
        await bot.send_message(
            ADMIN_ID,
            f"{header}\n\nFallback content:\n{fallback_text}",
        )


async def notify_admin_about_outgoing(bot: Bot, user_message: Message, bot_reply_text: str) -> None:
    """Duplicate bot outgoing message to admin chat."""
    if user_message.chat.id == ADMIN_ID:
        return

    admin_text = (
        "📤 Bot reply\n"
        f"to_user_id: {user_message.from_user.id if user_message.from_user else 'unknown'}\n"
        f"chat_id: {user_message.chat.id}\n"
        f"full_name: {user_message.from_user.full_name if user_message.from_user else 'unknown'}\n\n"
        f"{bot_reply_text}"
    )
    await bot.send_message(ADMIN_ID, admin_text)


async def answer_and_mirror(message: Message, text: str) -> None:
    """Reply to user and send the same reply to admin chat."""
    sent_message = await message.answer(text)
    await notify_admin_about_outgoing(message.bot, message, sent_message.text or text)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    text = (
        "Отправь мне сообщение с premium/custom emoji, и я верну:\n"
        "1) список найденных custom_emoji_id\n"
        "2) готовые строки вида\n"
        "CustomEmoji(\"🔥\", custom_emoji_id=\"...\")\n\n"
        "Также все входящие и исходящие сообщения дублируются админу."
    )
    await answer_and_mirror(message, text)


@router.message()
async def handle_any_message(message: Message) -> None:
    await notify_admin_about_incoming(message.bot, message)
    response_text = build_response_text(message)
    await answer_and_mirror(message, response_text)


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    me = await bot.get_me()
    logger.info("Bot started as @%s", me.username)

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
