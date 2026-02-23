import os
from dataclasses import dataclass
from typing import Optional, Set

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: Set[int]
    database_path: str
    web_app_url: Optional[str]


    @classmethod
    def load(cls) -> "Config":
        load_dotenv()
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            raise RuntimeError("BOT_TOKEN is missing from environment")
        admin_ids = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}
        database_path = os.getenv("DATABASE_PATH", "data/bot.db")
        web_app_url = os.getenv("WEB_APP_URL", "").strip() or None
        return cls(
            bot_token=bot_token,
            admin_ids=admin_ids,
            database_path=database_path,
            web_app_url=web_app_url,
        )
