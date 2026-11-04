"""OpenRouter endpoints of one model, so a provider slug can be picked instead of typed.

Docs: https://openrouter.ai/docs/features/provider-routing (order = provider slugs,
slug shape provider[/variant][/region][/tier], e.g. particle-ai/us/flex).
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from utils.errors import DiscoveryError
from utils.i18n import tr

API = "https://openrouter.ai/api/v1"
TIMEOUT = 20


@dataclass(frozen=True)
class Endpoint:
    tag: str
    name: str
    detail: str
    max_output: int | None = None


def endpoint_url(model_id: str) -> str:
    """'x-ai/grok:floor' -> .../models/x-ai/grok/endpoints"""
    base = model_id.strip()
    head, sep, tail = base.rpartition(":")
    if sep and "/" not in tail and tail:
        base = head
    if "/" not in base or not base:
        raise DiscoveryError(
            tr("OpenRouter sağlayıcıları için model kimliği 'yazar/model' biçiminde olmalı (örn. x-ai/grok).")
        )
    return f"{API}/models/{base}/endpoints"


def _per_million(value) -> str | None:
    try:
        amount = float(value) * 1_000_000
    except (TypeError, ValueError):
        return None
    return f"${amount:.2f}/M" if amount >= 0 else None


def _detail(item: dict) -> str:
    pricing = item.get("pricing") if isinstance(item.get("pricing"), dict) else {}
    prompt = _per_million(pricing.get("prompt"))
    completion = _per_million(pricing.get("completion"))
    context = item.get("context_length")
    max_out = item.get("max_completion_tokens")
    quantization = item.get("quantization")
    parts = [
        tr("Giriş {price}").format(price=prompt) if prompt else "",
        tr("Çıkış {price}").format(price=completion) if completion else "",
        tr("{n:,} bağlam").format(n=context) if isinstance(context, int) else "",
        tr("{n:,} çıkış").format(n=max_out) if isinstance(max_out, int) else "",
        str(quantization) if quantization and quantization != "unknown" else "",
    ]
    return " · ".join(part for part in parts if part)


def parse_endpoints(payload: dict) -> list[Endpoint]:
    data = payload.get("data")
    items = data.get("endpoints") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise DiscoveryError(tr("OpenRouter yanıtında sağlayıcı listesi (data.endpoints) bulunamadı."))
    endpoints: dict[str, Endpoint] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("tag"), str) or not item["tag"].strip():
            continue
        tag = item["tag"].strip()
        name = item.get("provider_name")
        max_out = item.get("max_completion_tokens")
        endpoints.setdefault(
            tag,
            Endpoint(
                tag=tag,
                name=name.strip() if isinstance(name, str) and name.strip() else tag,
                detail=_detail(item),
                max_output=max_out if isinstance(max_out, int) and max_out > 0 else None,
            ),
        )
    if not endpoints:
        raise DiscoveryError(tr("Bu model için OpenRouter'da sağlayıcı bulunamadı."))
    return list(endpoints.values())


def fetch_endpoints(model_id: str) -> list[Endpoint]:
    url = endpoint_url(model_id)
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "opencode-model-importer"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        error.close()
        if error.code == 404:
            raise DiscoveryError(
                tr(
                    "OpenRouter'da '{model}' modeli bulunamadı. Sağlayıcı seçimi yalnızca "
                    "OpenRouter'daki modeller için çalışır."
                ).format(model=model_id)
            ) from None
        raise DiscoveryError(
            tr("OpenRouter HTTP {code} {reason} hatası döndürdü.").format(code=error.code, reason=error.reason)
        ) from None
    except urllib.error.URLError as error:
        raise DiscoveryError(tr("OpenRouter'a ulaşılamadı: {reason}").format(reason=error.reason)) from None
    except TimeoutError:
        raise DiscoveryError(
            tr("OpenRouter {timeout} saniye içinde yanıt vermedi.").format(timeout=TIMEOUT)
        ) from None
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise DiscoveryError(tr("OpenRouter yanıtı JSON değil.")) from None
    return parse_endpoints(payload)
