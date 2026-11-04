"""Turkish/English UI text. Turkish strings are the keys; unknown text passes through."""

LANGUAGES = {"tr": "Türkçe", "en": "English"}
_current = "tr"

EN = {
    # --- window and tabs ------------------------------------------------
    "Var olan bir sağlayıcıyı düzenleyin veya yeni bir tane ekleyin": "Edit an existing provider or add a new one",
    "Sağlayıcıyı sil": "Delete provider",
    "Sağlayıcı kaydı": "Provider",
    "Sağlayıcı": "Provider",
    "Modeller": "Models",
    "Yapılandırma": "Configuration",
    "Dil": "Language",
    "Yapılandırmaya Ekle": "Add to configuration",
    "Değişiklikleri Kaydet": "Save changes",
    # --- provider tab ---------------------------------------------------
    "Sağlayıcı adı": "Provider name",
    "API protokolü": "API protocol",
    "API Key / ortam değişkeni": "API key / environment variable",
    "ör. UnoRouter": "e.g. UnoRouter",
    "ör. unorouter": "e.g. unorouter",
    "İsteğe bağlı: API anahtarı veya OPENROUTER_API_KEY gibi ortam değişkeni adı": (
        "Optional: API key or an environment variable name such as OPENROUTER_API_KEY"
    ),
    "Göster": "Show",
    "Girilen değeri açık göster": "Show the entered value",
    "Provider ID kayıtlı bir sağlayıcıda değiştirilemez. API anahtarı dosyaya yazılmaz; "
    "ortam değişkeni adı kullanılırsa OpenCode aynı değişkenle çalışmalıdır.": (
        "Provider ID cannot be changed for a saved provider. The API key is never written to the file; "
        "if you use an environment variable name, OpenCode must run with the same variable."
    ),
    "OpenAI uyumlu (önerilen)": "OpenAI compatible (recommended)",
    "OpenAI (yerel uyumlu sunucular)": "OpenAI (locally compatible servers)",
    "Anthropic uyumlu proxy": "Anthropic-compatible proxy",
    "Özel paket (korunur)": "Custom package (preserved)",
    # --- models tab -----------------------------------------------------
    "Modelleri Getir": "Fetch models",
    "Ara…": "Search…",
    "0 model": "0 models",
    "Tümünü seç": "Select all",
    "Seçimi temizle": "Clear selection",
    "Seç": "Select",
    "Model ayarları…": "Model settings…",
    "Varyant (:floor, :free…) ve sağlayıcı sırası/fallback": "Variant (:floor, :free…) and provider order/fallback",
    "İşaretli modeller yapılandırmada kalır; işareti kaldırdıklarınız silinir.": (
        "Checked models stay in the configuration; unchecked ones are removed."
    ),
    # --- configuration tab ----------------------------------------------
    "Dosya seç…": "Choose file…",
    "Her kayıtta önce bir yedek dosyası oluşturulur (opencode.json.bak-<zaman>). "
    "Değişiklik yoksa dosyaya hiç dokunulmaz; yorumlar ve biçim korunur.": (
        "A backup file is created before every save (opencode.json.bak-<time>). "
        "When nothing changed the file is not touched at all; comments and formatting are preserved."
    ),
    "opencode.json seç": "Choose opencode.json",
    # --- messages and state ---------------------------------------------
    "Hata": "Error",
    "OpenCode yapılandırması bulunamadı. “Dosya seç…” ile mevcut bir opencode.json seçin.": (
        "No OpenCode configuration found. Use “Choose file…” to pick an existing opencode.json."
    ),
    "{path} — kullanılamıyor, başka dosya seçin.": "{path} — unusable, choose another file.",
    "{path}  ({count} sağlayıcı)": "{path}  ({count} providers)",
    "+ Yeni sağlayıcı": "+ New provider",
    "{id}  ({count} model)": "{id}  ({count} models)",
    "• {id} — {count} model": "• {id} — {count} models",
    "Kayıtlı bir sağlayıcının ID'si değiştirilemez": "The ID of a saved provider cannot be changed",
    "Bu sağlayıcının anahtarı settings.apiKey içinde tanımlı; buradan değiştirilmez.": (
        "This provider's key is defined in settings.apiKey; it is not changed here."
    ),
    "yapılandırmadan okundu": "read from configuration",
    "Modeller getiriliyor…": "Fetching models…",
    "{count} model ({label}).": "{count} models ({label}).",
    "Yapılandırmada kayıtlı — işareti kaldırırsanız silinir": "Saved in configuration — uncheck to remove",
    "Yeni model": "New model",
    "{visible} / {total} model": "{visible} / {total} models",
    "Önce ekleyin": "Add it first",
    "Bu model henüz yapılandırmada yok. Önce kaydedin, sonra ayarlarını düzenleyin.": (
        "This model is not in the configuration yet. Save it first, then edit its settings."
    ),
    "Değişiklik yok.": "No changes.",
    "Kaydedilemedi": "Could not save",
    "Model ayarlandı: {id} — yedek: {name}": "Model updated: {id} — backup: {name}",
    "'{id}' sağlayıcısı ve {count} modeli yapılandırmadan silinsin mi?\n"
    "Önce bir yedek dosyası oluşturulur.": (
        "Delete provider '{id}' and its {count} model(s) from the configuration?\n"
        "A backup file is created first."
    ),
    "Silinemedi": "Could not delete",
    "'{id}' silindi — yedek: {name}": "'{id}' deleted — backup: {name}",
    "Dosya yok": "No file",
    "Önce bir opencode.json dosyası seçin.": "Choose an opencode.json file first.",
    "Geçersiz bilgi": "Invalid input",
    "Provider ID gerekli ve '/' veya '#' içermemeli.": "Provider ID is required and must not contain '/' or '#'.",
    "Seçim yok": "Nothing selected",
    "Ekleme için en az bir model seçin.": "Select at least one model to add.",
    "Eksik bilgi": "Missing information",
    "API Base URL gerekli.": "API Base URL is required.",
    "{count} model eklendi ({id}): {models}": "{count} model(s) added ({id}): {models}",
    "{count} model kaldırıldı: {models}": "{count} model(s) removed: {models}",
    "{id} sağlayıcısının ayarları güncellendi.": "Provider {id} settings updated.",
    "Yedek: {path}": "Backup: {path}",
    "{count} model zaten kayıtlıydı, atlandı: {models}": "{count} model(s) already saved, skipped: {models}",
    "Değişiklik yapılmadı.": "No changes were made.",
    "Tamamlandı": "Done",
    # --- model dialog ---------------------------------------------------
    "Model ayarları": "Model settings",
    ":floor en ucuz sağlayıcıya yönlendirir; :free ücretsiz, :nitro en hızlı.": (
        ":floor routes to the cheapest provider; :free is free, :nitro the fastest."
    ),
    "örn. particle-ai/us/flex, baseten": "e.g. particle-ai/us/flex, baseten",
    "OpenRouter sağlayıcı slug'ları; soldan sağa denenir": "OpenRouter provider slugs; tried left to right",
    "Sağlayıcıları getir": "Fetch providers",
    "Bu modeli OpenRouter'da hangi sağlayıcıların sunduğunu listeler": (
        "Lists which providers serve this model on OpenRouter"
    ),
    "Varsayılan (yazılmaz)": "Default (not written)",
    "İzin ver": "Allow",
    "İzin verme": "Deny",
    "İzin verme: seçili sağlayıcı uygun değilse (bağlam/çıktı limiti, hesap kısıtı) istek başarısız olur": (
        "Deny: the request fails if the selected provider is unsuitable (context/output limit, account restriction)"
    ),
    "Varyant": "Variant",
    "Sağlayıcı sırası": "Provider order",
    "Sağlayıcılar getiriliyor…": "Fetching providers…",
    "{count} sağlayıcı · işaretledikleriniz sıraya eklenir": (
        "{count} providers · checked ones are added to the order"
    ),
    "Elle yazıldı": "Typed by hand",
    "Ek ayar yazılmayacak.": "No extra settings will be written.",
    # --- credentials ----------------------------------------------------
    "kimlik doğrulama yok": "no authentication",
    "girilen API anahtarı": "entered API key",
    "'{name}' ortam değişkeni bu süreçte tanımlı değil. Değişkeni ekleyip (ör. setx {name} ...) "
    "uygulamayı yeniden başlatın ya da API anahtarını doğrudan girin.": (
        "The '{name}' environment variable is not defined in this process. Add it "
        "(e.g. setx {name} ...) and restart the app, or enter the API key directly."
    ),
    "ortam değişkeni {name}": "environment variable {name}",
    # --- discovery ------------------------------------------------------
    "API Base URL http:// veya https:// ile başlayan geçerli bir adres olmalı.": (
        "API Base URL must be a valid address starting with http:// or https://."
    ),
    "API Base URL bir host içermeli.": "API Base URL must contain a host.",
    "Sağlayıcı {code} döndürdü: bu API model listesi için geçerli bir API anahtarı istiyor.": (
        "The provider returned {code}: this API requires a valid API key to list models."
    ),
    "{url} bulunamadı (404). Sağlayıcı /models endpoint'ini desteklemiyor olabilir; "
    "API Base URL adresini kontrol edin.": (
        "{url} not found (404). The provider may not support the /models endpoint; check the API Base URL."
    ),
    "Sağlayıcı HTTP {code} {reason} hatası döndürdü.": "The provider returned HTTP {code} {reason}.",
    "Sunucuya ulaşılamadı: {reason}": "Could not reach the server: {reason}",
    "Sunucu {timeout} saniye içinde yanıt vermedi.": "The server did not respond within {timeout} seconds.",
    "Yanıt JSON değil; bu adres OpenAI uyumlu bir /models endpoint'i olmayabilir.": (
        "The response is not JSON; this address may not be an OpenAI-compatible /models endpoint."
    ),
    "Yanıt beklenen formatta değil (bir JSON nesnesi bekleniyordu).": (
        "The response is not in the expected format (a JSON object was expected)."
    ),
    "Yanıtta model listesi (data) bulunamadı; API beklenen formatta değil.": (
        "No model list (data) in the response; the API is not in the expected format."
    ),
    "Yanıtta geçerli model ID'si bulunamadı.": "No valid model ID in the response.",
    # --- openrouter -----------------------------------------------------
    "OpenRouter sağlayıcıları için model kimliği 'yazar/model' biçiminde olmalı (örn. x-ai/grok).": (
        "For OpenRouter providers the model ID must look like 'author/model' (e.g. x-ai/grok)."
    ),
    "Bu model için OpenRouter'da sağlayıcı bulunamadı.": "No providers found for this model on OpenRouter.",
    "OpenRouter'da '{model}' modeli bulunamadı. Sağlayıcı seçimi yalnızca OpenRouter'daki modeller için çalışır.": (
        "Model '{model}' was not found on OpenRouter. Provider selection only works for OpenRouter models."
    ),
    "OpenRouter HTTP {code} {reason} hatası döndürdü.": "OpenRouter returned HTTP {code} {reason}.",
    "OpenRouter'a ulaşılamadı: {reason}": "Could not reach OpenRouter: {reason}",
    "OpenRouter {timeout} saniye içinde yanıt vermedi.": "OpenRouter did not respond within {timeout} seconds.",
    "OpenRouter yanıtı JSON değil.": "The OpenRouter response is not JSON.",
    "OpenRouter yanıtında sağlayıcı listesi (data.endpoints) bulunamadı.": (
        "No provider list (data.endpoints) in the OpenRouter response."
    ),
    "Giriş {price}": "In {price}",
    "Çıkış {price}": "Out {price}",
    "{n:,} bağlam": "{n:,} context",
    "{n:,} çıkış": "{n:,} output",
    # --- JSONC parser ---------------------------------------------------
    "kapatılmamış /* yorumu": "unterminated /* comment",
    "kapatılmamış dize": "unterminated string",
    "kapatılmamış süslü/köşeli parantez": "unterminated brace/bracket",
    "kapatılmamış nesne": "unterminated object",
    "nesne anahtarı bekleniyordu ({pos})": "expected an object key ({pos})",
    "':' bekleniyordu ({pos})": "expected ':' ({pos})",
    "',' veya '}}' bekleniyordu ({pos})": "expected ',' or '}}' ({pos})",
    "kök bir JSON nesnesi olmalı": "the root must be a JSON object",
    # --- config file ----------------------------------------------------
    "{path} okunamadı: {error}": "Could not read {path}: {error}",
    "Dosya geçerli JSON/JSONC değil (satır {line}, sütun {col}): {msg}. Dosya değiştirilmedi.": (
        "The file is not valid JSON/JSONC (line {line}, column {col}): {msg}. The file was not changed."
    ),
    "Dosya geçerli JSON/JSONC değil: {error}. Dosya değiştirilmedi.": (
        "The file is not valid JSON/JSONC: {error}. The file was not changed."
    ),
    "Dosyadaki {where} alanı bir nesne değil; dosya değiştirilmedi.": (
        "The {where} field in the file is not an object; the file was not changed."
    ),
    "'{id}' sağlayıcısı bir nesne değil; dosya değiştirilmedi.": (
        "Provider '{id}' is not an object; the file was not changed."
    ),
    "'{id}' modeli bir nesne değil; dosya değiştirilmedi.": (
        "Model '{id}' is not an object; the file was not changed."
    ),
    "'{id}' sağlayıcısı bulunamadı; dosya değiştirilmedi.": (
        "Provider '{id}' was not found; the file was not changed."
    ),
    "'{id}' modeli bulunamadı; dosya değiştirilmedi.": (
        "Model '{id}' was not found; the file was not changed."
    ),
    "Yeni içerik geçerli JSON değil ({msg}); dosya değiştirilmedi.": (
        "The new content is not valid JSON ({msg}); the file was not changed."
    ),
    "Dosya yazılamadı, orijinal korundu: {error}": (
        "Could not write the file; the original was preserved: {error}"
    ),
    "Sağlayıcı adı boş olamaz.": "Provider name cannot be empty.",
    "Ortam değişkeni adı geçersiz: {name}": "Invalid environment variable name: {name}",
    "'{id}' modeli yapılandırmada kayıtlı değil.": "Model '{id}' is not saved in the configuration.",
    "'{id}' modeli zaten kayıtlı.": "Model '{id}' is already saved.",
}


def set_language(code: str) -> None:
    global _current
    _current = code if code in LANGUAGES else "tr"


def current_language() -> str:
    return _current


def tr(text: str) -> str:
    """English when selected; Turkish (the key itself) otherwise."""
    return EN.get(text, text) if _current == "en" else text
