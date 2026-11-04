from typing import NamedTuple

from config.opencode_config import ConfigFile
from config.schema import SCOPED_PACKAGES, model_entry, provider_items
from utils.errors import DiscoveryError
from utils.i18n import tr


class Sync(NamedTuple):
    text: str
    added: list[str]
    removed: list[str]
    skipped: list[str]
    changed: bool


def edit_model(config: ConfigFile, provider_id: str, old_id: str, new_id: str, options: dict) -> str | None:
    """Rename a model and/or set its options. Returns new text, or None if nothing changed."""
    known = config.provider_models().get(provider_id, {})
    if old_id not in known:
        raise DiscoveryError(tr("'{id}' modeli yapılandırmada kayıtlı değil.").format(id=old_id))
    if new_id != old_id and new_id in known:
        raise DiscoveryError(tr("'{id}' modeli zaten kayıtlı.").format(id=new_id))
    text = config.text
    if new_id != old_id:
        text = ConfigFile(config.path, text)._rename_model(provider_id, old_id, new_id)
    details = config.model_details(provider_id, old_id)
    # A legacy V1 `options.provider` is rewritten to V2 `body.provider` even when unchanged.
    if options != details["options"] or details["legacy"]:
        text = ConfigFile(config.path, text)._set_model_options(provider_id, new_id, options)
    return text if text != config.text else None


def delete_provider(config: ConfigFile, provider_id: str) -> tuple[str, list[str]]:
    """Remove a provider. Returns (new text, the model IDs it held)."""
    models = config.provider_models().get(provider_id, {})
    return config.render_delete_provider(provider_id), list(models)


def sync_provider(
    config: ConfigFile,
    provider_id: str,
    name: str,
    base_url: str,
    api_kind: str,
    env_name: str,
    models: list[tuple[str, str]],
    remove_ids: list[str] = (),
) -> Sync:
    """Create the provider or update it, so the file ends up matching the UI.

    models are the checked (model ID, display name) pairs; remove_ids are models
    the user unchecked. Existing models that were not removed are left untouched.
    """
    items = provider_items(name, base_url, api_kind, env_name)
    known = config.provider_models().get(provider_id, {})
    details = config.provider_details(provider_id)
    added = [(model_id, model_entry(model_id, label)) for model_id, label in models if model_id not in known]
    skipped = [model_id for model_id, _ in models if model_id in known]
    removed = [model_id for model_id in remove_ids if model_id in known]

    if details is None:
        if not added:
            return Sync(config.text, [], [], skipped, False)
        return Sync(config.render(provider_id, items, added), [m for m, _ in added], [], skipped, True)

    fields: dict[str, str | None] = {}
    if name.strip() != details["name"]:
        fields["name"] = items["name"]
    # An unrecognised package is the user's own; never rewrite it by accident.
    if api_kind and SCOPED_PACKAGES[api_kind] != details["package"]:
        fields["package"] = items["package"]
    if env_name != details["env"]:
        fields["env"] = items.get("env")
    base_url_update = base_url if base_url != details["base_url"] else None
    if not (fields or base_url_update or added or removed):
        return Sync(config.text, [], [], skipped, False)
    return Sync(
        config.render_update(provider_id, fields, base_url_update, added, removed),
        [m for m, _ in added],
        removed,
        skipped,
        True,
    )
