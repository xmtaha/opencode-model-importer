import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from config import jsonc
from config.schema import api_kind_of, global_config_candidates, json_string
from utils.errors import DiscoveryError
from utils.i18n import tr


def find_default_config() -> Path | None:
    for path in global_config_candidates():
        if path.is_file():
            return path
    return None


class ConfigFile:
    """A parsed OpenCode (JSONC) config that providers and models are added to.

    Edits insert text at known positions, so comments, formatting and every
    existing entry stay byte-for-byte unchanged.
    """

    def __init__(self, path: Path, text: str):
        self.path = path
        self.text = text
        self.root = self._parse(text)

    @classmethod
    def load(cls, path: Path) -> "ConfigFile":
        try:
            return cls(path, path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError) as error:
            raise DiscoveryError(tr("{path} okunamadı: {error}").format(path=path, error=error)) from None

    def _parse(self, text: str) -> jsonc.ObjectNode:
        try:
            first = jsonc.skip_ws(text, 0, len(text))
            if first >= len(text) or text[first] != "{":
                raise ValueError(tr("kök bir JSON nesnesi olmalı"))
            root = jsonc.parse_object(text, first, len(text))
            json.loads(jsonc.strip_jsonc(text))  # Trailing commas, escapes and extra content.
        except json.JSONDecodeError as error:
            raise DiscoveryError(
                tr(
                    "Dosya geçerli JSON/JSONC değil (satır {line}, sütun {col}): {msg}. Dosya değiştirilmedi."
                ).format(line=error.lineno, col=error.colno, msg=error.msg)
            ) from None
        except ValueError as error:
            raise DiscoveryError(
                tr("Dosya geçerli JSON/JSONC değil: {error}. Dosya değiştirilmedi.").format(error=error)
            ) from None
        return root

    # --- reading ---------------------------------------------------------

    def _value_object(self, key: str, within: "jsonc.ObjectNode") -> "jsonc.ObjectNode | None":
        start = within.value(key)
        if start is None:
            return None
        if self.text[start] != "{":
            where = f"'{key}'" if within is self.root else f"'{key}'"
            raise DiscoveryError(
                tr("Dosyadaki {where} alanı bir nesne değil; dosya değiştirilmedi.").format(where=where)
            )
        return jsonc.parse_object(self.text, start, len(self.text))

    def provider_models(self) -> dict[str, dict[str, str]]:
        """Existing providers -> {model ID: display name}."""
        result: dict[str, dict[str, str]] = {}
        providers = self._value_object("providers", self.root)
        for member in providers.members if providers else []:
            models: dict[str, str] = {}
            if self.text[member.value_start] == "{":
                entry = jsonc.parse_object(self.text, member.value_start, len(self.text))
                node = self._value_object("models", entry)
                for item in node.members if node else []:
                    models[item.key] = self._model_name(item)
            result[member.key] = models
        return result

    def _model_name(self, member: jsonc.Member) -> str:
        if self.text[member.value_start] != "{":
            return ""
        node = jsonc.parse_object(self.text, member.value_start, len(self.text))
        return self._value_json(node, "name") or ""

    def _value_json(self, node: "jsonc.ObjectNode", key: str):
        """A member's value decoded as JSON, or None. Comments are tolerated."""
        start = node.value(key)
        if start is None:
            return None
        end = jsonc._scan_value(self.text, start, len(self.text))
        try:
            return json.loads(jsonc.strip_jsonc(self.text[start:end]))
        except json.JSONDecodeError:
            return None

    def _provider_node(self, provider_id: str) -> "jsonc.ObjectNode | None":
        providers = self._value_object("providers", self.root)
        start = providers.value(provider_id) if providers else None
        if start is None:
            return None
        if self.text[start] != "{":
            raise DiscoveryError(
                tr("'{id}' sağlayıcısı bir nesne değil; dosya değiştirilmedi.").format(id=provider_id)
            )
        return jsonc.parse_object(self.text, start, len(self.text))

    def provider_details(self, provider_id: str) -> dict[str, str] | None:
        """A provider's editable fields as plain strings, or None if absent."""
        entry = self._provider_node(provider_id)
        if entry is None:
            return None
        settings = self._value_json(entry, "settings")
        env = self._value_json(entry, "env")
        package = self._value_json(entry, "package")
        return {
            "name": self._value_json(entry, "name") or "",
            "package": package if isinstance(package, str) else "",
            "api_kind": api_kind_of(package) if isinstance(package, str) else "",
            "base_url": settings.get("baseURL", "") if isinstance(settings, dict) else "",
            "env": env[0] if isinstance(env, list) and env and isinstance(env[0], str) else "",
            # Older configs keep the credential in settings.apiKey (e.g. "env://X").
            "settings_key": bool(settings.get("apiKey")) if isinstance(settings, dict) else False,
        }

    def _model_node(self, provider_id: str, model_id: str) -> "jsonc.ObjectNode | None":
        entry = self._provider_node(provider_id)
        models = self._value_object("models", entry) if entry else None
        start = models.value(model_id) if models else None
        if start is None:
            return None
        if self.text[start] != "{":
            raise DiscoveryError(
                tr("'{id}' modeli bir nesne değil; dosya değiştirilmedi.").format(id=model_id)
            )
        return jsonc.parse_object(self.text, start, len(self.text))

    def _routing(self, node: "jsonc.ObjectNode") -> tuple[dict, bool]:
        """(provider routing dict, came from the legacy V1 `options` key)."""
        for key in ("body", "options"):
            container = self._value_object(key, node)
            provider = self._value_json(container, "provider") if container else None
            if isinstance(provider, dict) and provider:
                return provider, key == "options"
        return {}, False

    def model_details(self, provider_id: str, model_id: str) -> dict:
        """A model's display name and its routing options ({} when absent)."""
        node = self._model_node(provider_id, model_id)
        if node is None:
            return {"name": "", "options": {}, "legacy": False}
        routing, legacy = self._routing(node)
        options: dict = {"provider": routing} if routing else {}
        body = self._value_object("body", node)
        if body is not None:
            tier = self._value_json(body, "service_tier")
            if isinstance(tier, str) and tier:
                options["service_tier"] = tier
            cap = self._value_json(body, "max_completion_tokens")
            if isinstance(cap, int) and not isinstance(cap, bool) and cap > 0:
                options["max_completion_tokens"] = cap
        return {
            "name": self._value_json(node, "name") or "",
            "options": options,
            "legacy": legacy,
        }

    def _set_model_options(self, provider_id: str, model_id: str, options: dict) -> str:
        """Write routing keys to `body` (V2) and retire the V1 `options.provider` key.

        `provider`, `service_tier` and `max_completion_tokens` are managed: present in
        `options` means set, absent means remove. Other `body` keys stay untouched.
        """
        node = self._model_node(provider_id, model_id)
        if node is None:
            raise DiscoveryError(
                tr("'{id}' modeli bulunamadı; dosya değiştirilmedi.").format(id=model_id)
            )

        text = self.text
        legacy = self._value_object("options", node)
        if legacy is not None and legacy.value("provider") is not None:
            text = self._drop(legacy, {"provider"})
            step = ConfigFile(self.path, text)
            leftover = step._value_object("options", step._model_node(provider_id, model_id))
            if leftover is not None and not leftover.members:
                text = step._drop(step._model_node(provider_id, model_id), {"options"})

        for key in ("provider", "service_tier", "max_completion_tokens"):
            value = options.get(key)
            if key == "provider" and not (isinstance(value, dict) and value):
                value = None
            elif key == "service_tier" and not (isinstance(value, str) and value):
                value = None
            elif key == "max_completion_tokens" and not (
                isinstance(value, int) and not isinstance(value, bool) and value > 0
            ):
                value = None

            step = ConfigFile(self.path, text)
            node = step._model_node(provider_id, model_id)
            body = step._value_object("body", node)
            if value is None:
                if body is None or body.value(key) is None:
                    continue
                text = step._drop(body, {key})
                step = ConfigFile(self.path, text)
                node = step._model_node(provider_id, model_id)
                body = step._value_object("body", node)
                if body is not None and not body.members:
                    text = step._drop(node, {"body"})
                continue

            encoded = json.dumps(value, ensure_ascii=False)
            if body is None:
                text = step._insert(node, [step._entry_text("body", '{"' + key + '": ' + encoded + "}")])
                continue
            start = body.value(key)
            if start is None:
                text = step._insert(body, [step._entry_text(key, encoded)])
            else:
                end = jsonc._scan_value(step.text, start, len(step.text))
                text = step.text[:start] + encoded + step.text[end:]
        return text

    def _rename_model(self, provider_id: str, old_id: str, new_id: str) -> str:
        """Move a model to a new key, keeping its value (name, options, ...)."""
        entry = self._provider_node(provider_id)
        models = self._value_object("models", entry) if entry else None
        member = next((m for m in models.members if m.key == old_id), None) if models else None
        if member is None:
            return self.text
        value = self.text[member.value_start : member.value_end].rstrip()
        text = self._drop(models, {old_id})
        step = ConfigFile(self.path, text)
        node = step._value_object("models", step._provider_node(provider_id))
        return step._insert(node, [step._entry_text(new_id, value)])

    def render_delete_provider(self, provider_id: str) -> str:
        """New file text without the provider (and its models)."""
        providers = self._value_object("providers", self.root)
        if providers is None or providers.value(provider_id) is None:
            raise DiscoveryError(
                tr("'{id}' sağlayıcısı bulunamadı; dosya değiştirilmedi.").format(id=provider_id)
            )
        return self._drop(providers, {provider_id})

    def _indent_of(self, position: int) -> str:
        lead = self.text[self.text.rfind("\n", 0, position) + 1 : position]
        return "" if lead.strip() else lead

    # --- writing ---------------------------------------------------------

    def _object_text(self, items: list[str], like: "jsonc.ObjectNode") -> str:
        """One-line or multi-line object literal, matching the layout of `like`."""
        if "\n" in self.text[like.start : like.end]:
            lead = self._indent_of(like.start)
            inner = "\n" + lead + "  "
            body = ("," + inner).join(items)
            return "{" + inner + body + "\n" + lead + "}"
        return "{" + ", ".join(items) + "}"

    def _entry_text(self, key: str, value_text: str) -> str:
        return f"{json.dumps(key)}: {value_text}"

    def _items_text(self, items: dict[str, str]) -> list[str]:
        return [self._entry_text(key, value) for key, value in items.items()]

    def _insert(self, node: "jsonc.ObjectNode", entries: list[str]) -> str:
        """Return new file text with `entries` added at the end of `node`."""
        text = self.text
        if not node.members:
            return text[: node.start] + self._object_text(entries, node) + text[node.end :]
        joined = ("," + self._indent_of(node.end - 1)).join(entries)
        if node.trailing:
            return text[: node.trailing[0]] + joined + "," + text[node.trailing[0] :]
        at = node.members[-1].value_end
        return text[:at] + "," + (self._indent_of(at) or " ") + joined + text[at:]

    def render(self, provider_id: str, items: dict[str, str], new_models: list[tuple[str, str]]) -> str:
        """New file text with the provider and models added.

        items are entries of the provider entry ("name", "package", ...);
        new_models are (model ID, entry) pairs where entry is "{}" or '{"name": ...}'.
        """
        providers = self._value_object("providers", self.root)
        rendered = [self._entry_text(key, value) for key, value in new_models]
        if providers is None:
            provider = self._object_text(
                self._items_text(items) + [self._entry_text("models", self._object_text(rendered, self.root))],
                self.root,
            )
            providers = self._object_text([self._entry_text(provider_id, provider)], self.root)
            return self._insert(self.root, [self._entry_text("providers", providers)])

        start = providers.value(provider_id)
        if start is None:
            provider = self._object_text(
                self._items_text(items) + [self._entry_text("models", self._object_text(rendered, providers))],
                providers,
            )
            return self._insert(providers, [self._entry_text(provider_id, provider)])

        entry = self._provider_node(provider_id)
        models = self._value_object("models", entry)
        if models is None:
            return self._insert(entry, [self._entry_text("models", self._object_text(rendered, entry))])
        return self._insert(models, rendered)

    def render_update(
        self,
        provider_id: str,
        fields: dict[str, str | None],
        base_url: str | None,
        new_models: list[tuple[str, str]],
        remove_ids: list[str],
    ) -> str:
        """New file text with provider fields changed and models added/removed.

        fields maps provider keys to their new JSON value (None deletes the key).
        base_url is updated inside `settings`, next to any other settings keys.
        """
        text = self.text
        if fields:
            text = ConfigFile(self.path, text)._update_provider(provider_id, fields)
        if base_url is not None:
            text = ConfigFile(self.path, text)._set_base_url(provider_id, base_url)
        for model_id in remove_ids:
            text = ConfigFile(self.path, text)._drop_model(provider_id, model_id)
        if new_models:
            text = ConfigFile(self.path, text).render(provider_id, {}, new_models)
        return text

    def _set_base_url(self, provider_id: str, base_url: str) -> str:
        """Replace only baseURL, so apiKey/headers and other settings survive."""
        entry = self._provider_node(provider_id)
        if entry is None:
            raise DiscoveryError(
                tr("'{id}' sağlayıcısı bulunamadı; dosya değiştirilmedi.").format(id=provider_id)
            )
        settings = self._value_object("settings", entry)
        if settings is None:
            value = '{"baseURL": ' + json_string(base_url) + "}"
            return self._insert(entry, [self._entry_text("settings", value)])
        start = settings.value("baseURL")
        if start is None:
            return self._insert(settings, [self._entry_text("baseURL", json_string(base_url))])
        end = jsonc._scan_value(self.text, start, len(self.text))
        return self.text[:start] + json_string(base_url) + self.text[end :]

    def _update_provider(self, provider_id: str, fields: dict[str, str | None]) -> str:
        entry = self._provider_node(provider_id)
        if entry is None:
            raise DiscoveryError(
                tr("'{id}' sağlayıcısı bulunamadı; dosya değiştirilmedi.").format(id=provider_id)
            )
        edits, missing, drop = [], [], set()
        for key, value in fields.items():
            start = entry.value(key)
            if start is None:
                if value is not None:
                    missing.append(self._entry_text(key, value))
            elif value is None:
                drop.add(key)
            else:
                edits.append((start, jsonc._scan_value(self.text, start, len(self.text)), value))
        text = self.text
        for start, end, value in sorted(edits, reverse=True):
            text = text[:start] + value + text[end:]
        step = ConfigFile(self.path, text)
        if drop:
            step = ConfigFile(self.path, step._drop(step._provider_node(provider_id), drop))
        if missing:
            step = ConfigFile(self.path, step._insert(step._provider_node(provider_id), missing))
        return step.text

    def _drop_model(self, provider_id: str, model_id: str) -> str:
        entry = self._provider_node(provider_id)
        models = self._value_object("models", entry) if entry else None
        if models is None:
            return self.text
        return self._drop(models, {model_id})

    def _drop(self, node: "jsonc.ObjectNode", keys: set[str]) -> str:
        """Remove member keys from node, taking the commas with them.

        A run that reaches the closing brace also eats the comma before it, so no
        trailing comma is left behind. Its own lines are removed, but a trailing
        comment on the previous member's line stays.
        """
        doomed = [i for i, member in enumerate(node.members) if member.key in keys]
        if not doomed:
            return self.text
        if len(doomed) == len(node.members):
            return self.text[: node.start] + "{}" + self.text[node.end :]
        runs: list[list[int]] = []
        for i in doomed:
            if runs and i == runs[-1][1] + 1:
                runs[-1][1] = i
            else:
                runs.append([i, i])
        last = len(node.members) - 1
        edits: list[tuple[int, int, str]] = []
        for first, final in runs:
            if final < last:
                edits.append((node.members[first].key_start, node.members[final + 1].key_start, ""))
                continue
            line_start = self.text.rfind("\n", 0, node.members[first].key_start) + 1
            if self.text[line_start : node.members[first].key_start].strip():
                edits.append((node.members[first - 1].value_end, node.members[final].value_end, ""))
            else:
                indent = self._indent_of(node.end - 1)
                edits.append((line_start, node.end, indent + "}"))
                comma = node.members[first - 1].value_end
                edits.append((comma, comma + 1, ""))
        text = self.text
        for start, end, replacement in sorted(edits, reverse=True):
            text = text[:start] + replacement + text[end:]
        return text

    # --- saving ----------------------------------------------------------

    def save(self, new_text: str) -> Path:
        """Validate, back up the original, then replace it atomically. Returns the backup path."""
        try:
            json.loads(jsonc.strip_jsonc(new_text))
        except json.JSONDecodeError as error:
            raise DiscoveryError(
                tr("Yeni içerik geçerli JSON değil ({msg}); dosya değiştirilmedi.").format(msg=error.msg)
            ) from None
        backup = self.path.with_name(f"{self.path.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
        temp = None
        try:
            shutil.copy2(self.path, backup)
            handle, temp = tempfile.mkstemp(dir=self.path.parent, prefix=".opencode-", suffix=".tmp")
            with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
                stream.write(new_text)
            os.replace(temp, self.path)
        except OSError as error:
            if temp and os.path.exists(temp):
                os.unlink(temp)
            raise DiscoveryError(
                tr("Dosya yazılamadı, orijinal korundu: {error}").format(error=error)
            ) from None
        return backup

