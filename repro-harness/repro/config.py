from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class TargetConfig:
    base_url: str
    token_a: str | None
    token_b: str | None


def load_config() -> TargetConfig:
    base_url = os.getenv("BASE_URL", "").strip()
    if not base_url:
        raise RuntimeError("Missing BASE_URL in .env")

    token_a = os.getenv("TOKEN_A")
    token_b = os.getenv("TOKEN_B")

    return TargetConfig(base_url=base_url, token_a=token_a, token_b=token_b)
