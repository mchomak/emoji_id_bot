# emoji-id-bot

Minimal Telegram bot on aiogram 3.26.0.

## What it does
- accepts any incoming message;
- extracts `custom_emoji_id` from text entities, caption entities, and custom emoji stickers;
- replies with:
  - list of found IDs;
  - ready-to-use lines like `CustomEmoji("🔥", custom_emoji_id="...")`;
- duplicates incoming user messages to admin chat;
- duplicates bot replies to admin chat.

## Setup
1. Copy `.env.example` to `.env`
2. Put your bot token into `.env`
3. Run:

```bash
docker compose up -d --build
```

## Stop

```bash
docker compose down
```

## Logs

```bash
docker compose logs -f
```
