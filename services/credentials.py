import os
import re
from dataclasses import dataclass

from utils.errors import DiscoveryError
from utils.i18n import tr

ENV_NAME = re.compile(r"^\$?([A-Za-z_][A-Za-z0-9_]*)$")


@dataclass(frozen=True)
class Key:
    secret: str | None = None
    env_name: str = ""
    label: str = ""


def resolve(raw: str) -> Key:
    """Interpret the API Key field.

    A value shaped like an environment variable name (OPENROUTER_API_KEY) is read
    with os.getenv, so the name itself is never sent as the key. Anything else is
    used as the key. Empty means no Authorization header.
    """
    text = raw.strip()
    if not text:
        return Key(label=tr("kimlik doğrulama yok"))
    match = ENV_NAME.match(text)
    looks_like_name = bool(match) and (text.isupper() or text.startswith("$"))
    if not looks_like_name:
        return Key(secret=text, label=tr("girilen API anahtarı"))
    name = match.group(1)
    value = os.getenv(name)
    if not value:
        raise DiscoveryError(
            tr(
                "'{name}' ortam değişkeni bu süreçte tanımlı değil. Değişkeni ekleyip (ör. setx {name} ...) "
                "uygulamayı yeniden başlatın ya da API anahtarını doğrudan girin."
            ).format(name=name)
        )
    return Key(secret=value, env_name=name, label=tr("ortam değişkeni {name}").format(name=name))
