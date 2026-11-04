import json
import os
import re
from pathlib import Path

from utils.errors import DiscoveryError
from utils.i18n import tr

ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SCOPED_PACKAGES = {
    "openai-compatible": "@opencode/ai/providers/openai-compatible",
    "openai": "@opencode/ai/providers/openai",
    "anthropic": "@opencode/ai/providers/anthropic-compatible",
}


def json_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def model_entry(model_id: str, display_name: str) -> str:
    """The value for a model key: {} unless the API gave a display name."""
    name = display_name.strip() if display_name else ""
    return f"{{\"name\": {json_string(name)}}}" if name and name != model_id else "{}"


def provider_items(name: str, base_url: str, api_kind: str, env_name: str = "") -> dict[str, str]:
    """Entries of the provider object, ready to be placed in the config file."""
    if not name.strip():
        raise DiscoveryError(tr("Sağlayıcı adı boş olamaz."))
    if env_name and not ENV_NAME.match(env_name):
        raise DiscoveryError(tr("Ortam değişkeni adı geçersiz: {name}").format(name=env_name))
    package = SCOPED_PACKAGES.get(api_kind, SCOPED_PACKAGES["openai-compatible"])
    items = {"name": json_string(name.strip()), "package": json_string(package)}
    if env_name:
        items["env"] = f"[{json_string(env_name)}]"
    items["settings"] = f'{{"baseURL": {json_string(base_url)}}}'
    return items


def api_kind_of(package: str) -> str:
    """Protocol of an existing provider, from its package field."""
    for kind, scoped in SCOPED_PACKAGES.items():
        if package == scoped:
            return kind
    return "openai-compatible"


def global_config_candidates() -> list[Path]:
    """Files OpenCode reads as its global config, most likely first."""
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    explicit = os.environ.get("OPENCODE_CONFIG")
    if explicit:
        return [Path(explicit)]
    directory = os.environ.get("OPENCODE_CONFIG_DIR")
    if not directory:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        directory = os.path.join(xdg, "opencode") if xdg else str(home / ".config" / "opencode")
    return [Path(directory) / "opencode.json", Path(directory) / "opencode.jsonc"]
