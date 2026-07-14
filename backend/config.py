import os

from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


class Settings:
    @property
    def backend_access_token(self) -> str:
        return os.getenv("QA_ASSISTANT_ACCESS_TOKEN", "").strip()

    @property
    def verify_ssl(self) -> bool:
        return _bool_env("QA_ASSISTANT_VERIFY_SSL", True)

    @property
    def max_message_chars(self) -> int:
        return _int_env("QA_ASSISTANT_MAX_MESSAGE_CHARS", 50_000)

    @property
    def max_image_data_chars(self) -> int:
        return _int_env("QA_ASSISTANT_MAX_IMAGE_DATA_CHARS", 13_500_000)

    @property
    def max_history_messages(self) -> int:
        return _int_env("QA_ASSISTANT_MAX_HISTORY_MESSAGES", 10)

    @property
    def max_history_content_chars(self) -> int:
        return _int_env("QA_ASSISTANT_MAX_HISTORY_CONTENT_CHARS", 12_000)

    @property
    def max_dom_fetch_bytes(self) -> int:
        return _int_env("QA_ASSISTANT_MAX_DOM_FETCH_BYTES", 500_000)

    @property
    def max_url_redirects(self) -> int:
        return _int_env("QA_ASSISTANT_MAX_URL_REDIRECTS", 2)

    @property
    def allowed_repo_roots(self) -> list[str]:
        raw = os.getenv("QA_ASSISTANT_ALLOWED_REPO_ROOTS", "")
        if not raw.strip():
            return []
        return [item.strip() for item in raw.split(os.pathsep) if item.strip()]

    @property
    def repo_command_timeout_seconds(self) -> int:
        return _int_env("QA_ASSISTANT_REPO_COMMAND_TIMEOUT_SECONDS", 60)


settings = Settings()
