import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

from utils.errors import DiscoveryError
from utils.i18n import tr

TIMEOUT = 30


@dataclass(frozen=True)
class RemoteModel:
    id: str
    name: str


def normalized_base_url(raw: str) -> str:
    """Validate the URL and drop a trailing /models so it is never doubled."""
    text = raw.strip().rstrip("/")
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise DiscoveryError(tr("API Base URL http:// veya https:// ile başlayan geçerli bir adres olmalı."))
    if text.endswith("/models"):
        text = text[: -len("/models")].rstrip("/")
        if not urlparse(text).netloc:
            raise DiscoveryError(tr("API Base URL bir host içermeli."))
    return text


def _models_endpoint(base_url: str) -> str:
    base = normalized_base_url(base_url)
    # Most OpenAI-compatible APIs live under /v1; keep the address as typed otherwise.
    if urlparse(base).path.rstrip("/").endswith("/v1"):
        return base + "/models"
    return base + "/v1/models"


def _request(url: str, key: str | None) -> dict:
    headers = {"Accept": "application/json", "User-Agent": "opencode-model-importer"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=TIMEOUT) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        error.close()
        if error.code in (401, 403):
            raise DiscoveryError(
                tr("Sağlayıcı {code} döndürdü: bu API model listesi için geçerli bir API anahtarı istiyor.").format(
                    code=error.code
                )
            ) from None
        if error.code == 404:
            raise DiscoveryError(
                tr(
                    "{url} bulunamadı (404). Sağlayıcı /models endpoint'ini desteklemiyor olabilir; "
                    "API Base URL adresini kontrol edin."
                ).format(url=url)
            ) from None
        raise DiscoveryError(
            tr("Sağlayıcı HTTP {code} {reason} hatası döndürdü.").format(code=error.code, reason=error.reason)
        ) from None
    except urllib.error.URLError as error:
        raise DiscoveryError(tr("Sunucuya ulaşılamadı: {reason}").format(reason=error.reason)) from None
    except TimeoutError:
        raise DiscoveryError(
            tr("Sunucu {timeout} saniye içinde yanıt vermedi.").format(timeout=TIMEOUT)
        ) from None
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise DiscoveryError(
            tr("Yanıt JSON değil; bu adres OpenAI uyumlu bir /models endpoint'i olmayabilir.")
        ) from None
    if not isinstance(payload, dict):
        raise DiscoveryError(tr("Yanıt beklenen formatta değil (bir JSON nesnesi bekleniyordu)."))
    return payload


def _model_name(item: dict) -> str:
    for key in ("display_name", "name"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return item["id"]


def parse_models(payload: dict) -> list[RemoteModel]:
    items = payload.get("data", payload.get("models"))
    if not isinstance(items, list):
        raise DiscoveryError(tr("Yanıtta model listesi (data) bulunamadı; API beklenen formatta değil."))
    models = []
    for item in items:
        # Some providers return bare model ID strings instead of objects.
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip():
            models.append(RemoteModel(item["id"].strip(), _model_name(item)))
    if not models:
        raise DiscoveryError(tr("Yanıtta geçerli model ID'si bulunamadı."))
    return sorted(models, key=lambda model: model.name.lower())


def fetch_models(base_url: str, key: str | None) -> list[RemoteModel]:
    try:
        payload = _request(_models_endpoint(base_url), key)
    except DiscoveryError as error:
        if "404" not in str(error):
            raise
        # Servers that only serve the bare base URL still expose /models there.
        payload = _request(normalized_base_url(base_url) + "/models", key)
    return parse_models(payload)
