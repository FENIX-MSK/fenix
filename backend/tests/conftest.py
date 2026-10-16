import os

# Tests must never talk to the real bot; aiogram only validates the token format.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST-TOKEN")
