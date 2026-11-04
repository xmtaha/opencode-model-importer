from pathlib import Path

from PySide6.QtCore import QLocale, QSettings, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from config.opencode_config import ConfigFile, find_default_config
from config.writer import delete_provider, edit_model, sync_provider
from services import credentials, discovery
from ui.model_dialog import ModelDialog
from ui.theme import STYLE
from ui.worker import Worker
from utils import i18n
from utils.i18n import tr

SETTINGS = ("opencode-model-importer", "OpenCode Model Importer")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(940, 760)
        self.worker = None
        self.config: ConfigFile | None = None
        self.editing: str | None = None
        self._build()
        self.retranslate()
        self._load_config(find_default_config())

    # --- layout ----------------------------------------------------------

    def _build(self):
        root = QVBoxLayout()
        root.setContentsMargins(18, 14, 18, 12)
        root.setSpacing(10)

        self.title_label = QLabel()
        self.title_label.setObjectName("title")
        self.provider_combo = QComboBox()
        self.provider_combo.setMinimumWidth(220)
        self.provider_combo.currentIndexChanged.connect(self._pick_provider)
        self.delete_button = QPushButton()
        self.delete_button.setObjectName("danger")
        self.delete_button.clicked.connect(self.delete_provider)
        self.language_combo = QComboBox()
        for code, name in i18n.LANGUAGES.items():
            self.language_combo.addItem(name, code)
        index = self.language_combo.findData(i18n.current_language())
        self.language_combo.setCurrentIndex(max(index, 0))
        self.language_combo.currentIndexChanged.connect(self._change_language)

        self.record_label = QLabel()
        header = QHBoxLayout()
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.record_label)
        header.addWidget(self.provider_combo, 1)
        header.addWidget(self.delete_button)
        header.addWidget(self.language_combo)
        root.addLayout(header)

        self.config_label = QLabel("")
        self.config_label.setObjectName("hint")
        self.config_label.setWordWrap(True)
        self.config_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(self.config_label)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._provider_tab(), "")
        self.tabs.addTab(self._models_tab(), "")
        self.tabs.addTab(self._config_tab(), "")
        root.addWidget(self.tabs, 1)

        footer = QHBoxLayout()
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.result = QLabel("")
        self.result.setObjectName("hint")
        self.save_button = QPushButton()
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self.save)
        footer.addWidget(self.status, 1)
        footer.addWidget(self.result, 1)
        footer.addWidget(self.save_button)
        root.addLayout(footer)

        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

    def _provider_tab(self) -> QWidget:
        page = QWidget()
        self.provider_form = form = QFormLayout(page)
        form.setContentsMargins(16, 18, 16, 14)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        self.name = QLineEdit()
        self.name.textEdited.connect(lambda text: self.provider_id.setPlaceholderText(self._slug(text)))
        self.provider_id = QLineEdit()
        self.base_url = QLineEdit()
        self.base_url.setPlaceholderText("https://api.example.com/v1")
        self.api_kind = QComboBox()
        self.api_kind.addItem("", "openai-compatible")
        self.api_kind.addItem("", "openai")
        self.api_kind.addItem("", "anthropic")
        self.api_kind.addItem("", "")
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        self.show_key = QCheckBox()
        self.show_key.toggled.connect(
            lambda shown: self.key.setEchoMode(QLineEdit.Normal if shown else QLineEdit.Password)
        )
        key_row = QHBoxLayout()
        key_row.addWidget(self.key, 1)
        key_row.addWidget(self.show_key)
        self.name_label = QLabel()
        self.kind_label = QLabel()
        self.key_label = QLabel()
        form.addRow(self.name_label, self.name)
        form.addRow("Provider ID", self.provider_id)
        form.addRow("API Base URL", self.base_url)
        form.addRow(self.kind_label, self.api_kind)
        form.addRow(self.key_label, key_row)
        self.provider_hint = self._hint("")
        form.addRow("", self.provider_hint)
        return page

    def _models_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        fetch_row = QHBoxLayout()
        self.fetch_button = QPushButton()
        self.fetch_button.setObjectName("primary")
        self.fetch_button.clicked.connect(self.fetch_models)
        self.spinner = QProgressBar()
        self.spinner.setRange(0, 0)
        self.spinner.setFixedWidth(120)
        self.spinner.hide()
        fetch_row.addWidget(self.fetch_button)
        fetch_row.addWidget(self.spinner)
        fetch_row.addStretch(1)
        layout.addLayout(fetch_row)

        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.textChanged.connect(self._filter)
        self.count_label = QLabel("0 model")
        self.count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.count_label.setMinimumWidth(110)
        self.all_button = QPushButton()
        self.none_button = QPushButton()
        self.all_button.clicked.connect(lambda: self._check_all(True))
        self.none_button.clicked.connect(lambda: self._check_all(False))
        tools.addWidget(self.search, 1)
        tools.addWidget(self.count_label)
        tools.addWidget(self.all_button)
        tools.addWidget(self.none_button)
        layout.addLayout(tools)

        self.table = QTableWidget(0, 2)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.cellDoubleClicked.connect(lambda *_: self.edit_model())
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.model_button = QPushButton()
        self.model_button.setEnabled(False)
        self.model_button.clicked.connect(self.edit_model)
        self.models_hint = self._hint("")
        bottom.addWidget(self.model_button)
        bottom.addWidget(self.models_hint, 1)
        layout.addLayout(bottom)
        return page

    def _config_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(12)
        self.config_path = QLabel("")
        self.config_path.setWordWrap(True)
        self.config_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self.choose_config)
        row = QHBoxLayout()
        row.addWidget(self.config_path, 1)
        row.addWidget(self.browse_button)
        layout.addLayout(row)
        self.config_hint = self._hint("")
        layout.addWidget(self.config_hint)
        self.config_summary = QLabel("")
        self.config_summary.setWordWrap(True)
        self.config_summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.config_summary)
        layout.addStretch(1)
        return page

    @staticmethod
    def _hint(text: str = "") -> QLabel:
        label = QLabel(text)
        label.setObjectName("hint")
        label.setWordWrap(True)
        return label

    # --- language --------------------------------------------------------

    def _change_language(self):
        i18n.set_language(self.language_combo.currentData())
        QSettings(*SETTINGS).setValue("language", i18n.current_language())
        self.retranslate()

    def retranslate(self):
        self.setWindowTitle(tr("OpenCode Model Importer"))
        self.title_label.setText(tr("OpenCode Model Importer"))
        self.record_label.setText(tr("Sağlayıcı kaydı"))
        self.provider_combo.setToolTip(tr("Var olan bir sağlayıcıyı düzenleyin veya yeni bir tane ekleyin"))
        self.delete_button.setText(tr("Sağlayıcıyı sil"))
        self.language_combo.setToolTip(tr("Dil"))
        self.tabs.setTabText(0, tr("Sağlayıcı"))
        self.tabs.setTabText(1, tr("Modeller"))
        self.tabs.setTabText(2, tr("Yapılandırma"))

        self.name_label.setText(tr("Sağlayıcı adı"))
        self.kind_label.setText(tr("API protokolü"))
        self.key_label.setText(tr("API Key / ortam değişkeni"))
        self.name.setPlaceholderText(tr("ör. UnoRouter"))
        self.provider_id.setPlaceholderText(tr("ör. unorouter"))
        self.key.setPlaceholderText(
            tr("İsteğe bağlı: API anahtarı veya OPENROUTER_API_KEY gibi ortam değişkeni adı")
        )
        self.show_key.setText(tr("Göster"))
        self.show_key.setToolTip(tr("Girilen değeri açık göster"))
        self.api_kind.setItemText(0, tr("OpenAI uyumlu (önerilen)"))
        self.api_kind.setItemText(1, tr("OpenAI (yerel uyumlu sunucular)"))
        self.api_kind.setItemText(2, tr("Anthropic uyumlu proxy"))
        self.api_kind.setItemText(3, tr("Özel paket (korunur)"))
        self.provider_hint.setText(
            tr(
                "Provider ID kayıtlı bir sağlayıcıda değiştirilemez. API anahtarı dosyaya yazılmaz; "
                "ortam değişkeni adı kullanılırsa OpenCode aynı değişkenle çalışmalıdır."
            )
        )

        self.fetch_button.setText(tr("Modelleri Getir"))
        self.search.setPlaceholderText(tr("Ara…"))
        self.all_button.setText(tr("Tümünü seç"))
        self.none_button.setText(tr("Seçimi temizle"))
        self.table.setHorizontalHeaderLabels([tr("Seç"), "Model"])
        self.model_button.setText(tr("Model ayarları…"))
        self.model_button.setToolTip(tr("Varyant (:floor, :free…) ve sağlayıcı sırası/fallback"))
        self.models_hint.setText(tr("İşaretli modeller yapılandırmada kalır; işareti kaldırdıklarınız silinir."))
        self._update_count()

        self.browse_button.setText(tr("Dosya seç…"))
        self.config_hint.setText(
            tr(
                "Her kayıtta önce bir yedek dosyası oluşturulur (opencode.json.bak-<zaman>). "
                "Değişiklik yoksa dosyaya hiç dokunulmaz; yorumlar ve biçim korunur."
            )
        )
        self.save_button.setText(
            tr("Değişiklikleri Kaydet") if self.editing else tr("Yapılandırmaya Ekle")
        )
        self._render_config_texts()

    def _render_config_texts(self):
        providers = self.config.provider_models() if self.config else {}
        if self.config is None:
            self.config_label.setText(
                tr("OpenCode yapılandırması bulunamadı. “Dosya seç…” ile mevcut bir opencode.json seçin.")
            )
        else:
            self.config_label.setText(
                tr("{path}  ({count} sağlayıcı)").format(path=self.config.path, count=len(providers))
            )
            self.config_path.setText(str(self.config.path))
        self.config_summary.setText(self._summary_text(providers))
        if self.provider_combo.count():
            self.provider_combo.setItemText(0, tr("+ Yeni sağlayıcı"))
            for index in range(1, self.provider_combo.count()):
                provider_id = self.provider_combo.itemData(index)
                self.provider_combo.setItemText(
                    index,
                    tr("{id}  ({count} model)").format(id=provider_id, count=len(providers.get(provider_id, {}))),
                )

    @staticmethod
    def _summary_text(providers: dict) -> str:
        return "\n".join(
            tr("• {id} — {count} model").format(id=provider_id, count=len(models))
            for provider_id, models in providers.items()
        )

    # --- helpers ---------------------------------------------------------

    @staticmethod
    def _slug(text: str) -> str:
        slug = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in text.strip().lower())
        return "-".join(part for part in slug.split("-") if part)

    def _set_busy(self, busy: bool):
        self.spinner.setVisible(busy)
        self.fetch_button.setEnabled(not busy)
        self.provider_combo.setEnabled(not busy)
        self.save_button.setEnabled(not busy and self.config is not None)
        self.delete_button.setEnabled(not busy and self.editing is not None)
        self.model_button.setEnabled(not busy and self.table.currentRow() >= 0)

    def _run(self, job, on_done):
        self._set_busy(True)
        self.worker = Worker(job)
        self.worker.done.connect(lambda value: (self._set_busy(False), on_done(value)))
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _failed(self, message: str):
        self._set_busy(False)
        self.status.setText(message)
        self._update_count()
        QMessageBox.warning(self, tr("Hata"), message)

    def _load_config(self, path: Path | None):
        self.config = None
        self.save_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        if path is None:
            self._render_config_texts()
            self._fill_combo()
            return
        try:
            config = ConfigFile.load(path)
        except Exception as error:
            self.config_label.setText(tr("{path} — kullanılamıyor, başka dosya seçin.").format(path=path))
            self.status.setText(str(error))
            self._fill_combo()
            return
        self.config = config
        self.config_path.setText(str(path))
        self.save_button.setEnabled(True)
        self._render_config_texts()
        self._fill_combo()

    def _fill_combo(self):
        """List the providers in the file, keeping the current selection if it survives."""
        providers = self.config.provider_models() if self.config else {}
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()
        self.provider_combo.addItem(tr("+ Yeni sağlayıcı"), "")
        for provider_id, models in providers.items():
            self.provider_combo.addItem(
                tr("{id}  ({count} model)").format(id=provider_id, count=len(models)), provider_id
            )
        self.provider_combo.blockSignals(False)
        index = self.provider_combo.findData(self.editing or "")
        self.provider_combo.setCurrentIndex(max(index, 0))
        self._pick_provider()

    def _pick_provider(self):
        """Load the selected provider into the form, or clear it for a new one."""
        selected = self.provider_combo.currentData() or ""
        self.editing = selected or None
        self.table.setRowCount(0)
        self.search.clear()
        self.result.setText("")
        self.provider_id.setEnabled(not selected)
        self.provider_id.setToolTip(tr("Kayıtlı bir sağlayıcının ID'si değiştirilemez") if selected else "")
        self.save_button.setText(tr("Değişiklikleri Kaydet") if selected else tr("Yapılandırmaya Ekle"))
        self.delete_button.setEnabled(bool(selected) and self.config is not None)
        if not selected or self.config is None:
            self.editing = None
            for field in (self.name, self.provider_id, self.base_url, self.key):
                field.clear()
            self.api_kind.setCurrentIndex(0)
            self.key.setEnabled(True)
            self.key.setToolTip("")
            self.status.setText("")
            self._update_count()
            return
        details = self.config.provider_details(selected) or {}
        self.name.setText(details.get("name", ""))
        self.provider_id.setText(selected)
        self.base_url.setText(details.get("base_url", ""))
        self.key.setText(details.get("env", ""))
        has_settings_key = details.get("settings_key", False)
        self.key.setEnabled(not has_settings_key)
        self.key.setToolTip(
            tr("Bu sağlayıcının anahtarı settings.apiKey içinde tanımlı; buradan değiştirilmez.")
            if has_settings_key
            else ""
        )
        kind = details.get("api_kind", "")
        self.api_kind.setCurrentIndex(max(self.api_kind.findData(kind), 0))
        self._show_models((tr("yapılandırmadan okundu"), []))

    # --- actions ---------------------------------------------------------

    def choose_config(self):
        start = str(self.config.path.parent) if self.config else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, tr("opencode.json seç"), start, "OpenCode (*.json *.jsonc)"
        )
        if path:
            self._load_config(Path(path))

    def fetch_models(self):
        url = self.base_url.text().strip()
        if not url:
            QMessageBox.warning(self, tr("Eksik bilgi"), tr("API Base URL gerekli."))
            return
        key_input = self.key.text()

        def job():
            key = credentials.resolve(key_input)
            return key.label, discovery.fetch_models(url, key.secret)

        self.status.setText(tr("Modeller getiriliyor…"))
        self.table.setRowCount(0)
        self._update_count()
        self._run(job, self._show_models)

    def _show_models(self, value):
        label, models = value
        existing = self.config.provider_models().get(self.editing, {}) if self.editing and self.config else {}
        labels = {model.id: model.name or model.id for model in models}
        # Configured models the API no longer returns must stay visible, or they
        # could never be unchecked and removed.
        for model_id, name in existing.items():
            labels.setdefault(model_id, name or model_id)
        self.table.setRowCount(0)
        for model_id in sorted(labels, key=lambda m: labels[m].lower()):
            self._add_row(model_id, labels[model_id], model_id in existing)
        self.status.setText(tr("{count} model ({label}).").format(count=len(labels), label=label))
        self._update_count()

    def _add_row(self, model_id: str, label: str, in_config: bool):
        row = self.table.rowCount()
        self.table.insertRow(row)
        check = QTableWidgetItem()
        check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        check.setCheckState(Qt.CheckState.Checked if in_config else Qt.CheckState.Unchecked)
        check.setToolTip(
            tr("Yapılandırmada kayıtlı — işareti kaldırırsanız silinir") if in_config else tr("Yeni model")
        )
        self.table.setItem(row, 0, check)
        item = QTableWidgetItem(label)
        item.setData(Qt.UserRole, model_id)
        item.setToolTip(model_id)
        self.table.setItem(row, 1, item)

    def _filter(self, _=None):
        needle = self.search.text().strip().lower()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            haystack = f"{item.text()} {item.data(Qt.UserRole)}".lower()
            self.table.setRowHidden(row, bool(needle) and needle not in haystack)
        self._update_count()

    def _update_count(self):
        total = self.table.rowCount()
        visible = sum(not self.table.isRowHidden(row) for row in range(total))
        self.count_label.setText(tr("{visible} / {total} model").format(visible=visible, total=total))

    def _check_all(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                self.table.item(row, 0).setCheckState(state)

    def _selection_changed(self):
        self.model_button.setEnabled(self.table.currentRow() >= 0)

    def _selected(self) -> list[tuple[str, str]]:
        return [
            (self.table.item(row, 1).data(Qt.UserRole), self.table.item(row, 1).text())
            for row in range(self.table.rowCount())
            if self.table.item(row, 0).checkState() == Qt.CheckState.Checked
        ]

    def edit_model(self):
        if self.config is None or not self.editing or self.table.currentRow() < 0:
            return
        row = self.table.currentRow()
        model_id = self.table.item(row, 1).data(Qt.UserRole)
        if model_id not in self.config.provider_models().get(self.editing, {}):
            QMessageBox.information(
                self,
                tr("Önce ekleyin"),
                tr("Bu model henüz yapılandırmada yok. Önce kaydedin, sonra ayarlarını düzenleyin."),
            )
            return
        options = self.config.model_details(self.editing, model_id)["options"]
        dialog = ModelDialog(model_id, options, self)
        if dialog.exec() != QDialog.Accepted:
            return
        new_id, new_options = dialog.result_settings()
        try:
            text = edit_model(self.config, self.editing, model_id, new_id, new_options)
            if text is None:
                self.status.setText(tr("Değişiklik yok."))
                return
            backup = self.config.save(text)
        except Exception as error:
            QMessageBox.warning(self, tr("Kaydedilemedi"), str(error))
            return
        self.status.setText(tr("Model ayarlandı: {id} — yedek: {name}").format(id=new_id, name=backup.name))
        self._load_config(self.config.path)

    def delete_provider(self):
        provider_id = self.editing
        if self.config is None or not provider_id:
            return
        models = self.config.provider_models().get(provider_id, {})
        answer = QMessageBox.question(
            self,
            tr("Sağlayıcıyı sil"),
            tr(
                "'{id}' sağlayıcısı ve {count} modeli yapılandırmadan silinsin mi?\n"
                "Önce bir yedek dosyası oluşturulur."
            ).format(id=provider_id, count=len(models)),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            text, _ = delete_provider(self.config, provider_id)
            backup = self.config.save(text)
        except Exception as error:
            QMessageBox.warning(self, tr("Silinemedi"), str(error))
            return
        self.editing = None
        self._load_config(self.config.path)
        self.status.setText(tr("'{id}' silindi — yedek: {name}").format(id=provider_id, name=backup.name))

    def save(self):
        if self.config is None:
            QMessageBox.warning(self, tr("Dosya yok"), tr("Önce bir opencode.json dosyası seçin."))
            return
        provider_id = (self.provider_id.text().strip() or self.provider_id.placeholderText()).strip()
        if not provider_id or any(ch in provider_id for ch in "/#"):
            QMessageBox.warning(
                self, tr("Geçersiz bilgi"), tr("Provider ID gerekli ve '/' veya '#' içermemeli.")
            )
            return
        models = self._selected()
        known = self.config.provider_models().get(provider_id, {}) if self.editing else {}
        remove = [model_id for model_id in known if model_id not in {model[0] for model in models}]
        if not models and not remove:
            QMessageBox.warning(self, tr("Seçim yok"), tr("Ekleme için en az bir model seçin."))
            return
        try:
            base_url = discovery.normalized_base_url(self.base_url.text())
            key = credentials.resolve(self.key.text())
            name = self.name.text().strip() or provider_id
            kind = self.api_kind.currentData()
        except Exception as error:
            QMessageBox.warning(self, tr("Geçersiz bilgi"), str(error))
            return

        config = self.config

        def job():
            result = sync_provider(config, provider_id, name, base_url, kind, key.env_name, models, remove)
            return result, (config.save(result.text) if result.changed else None)

        self._run(job, lambda value: self._saved(config, provider_id, *value))

    def _saved(self, config: ConfigFile, provider_id, result, backup):
        lines = []
        if result.added:
            lines.append(
                tr("{count} model eklendi ({id}): {models}").format(
                    count=len(result.added), id=provider_id, models=", ".join(result.added)
                )
            )
        if result.removed:
            lines.append(
                tr("{count} model kaldırıldı: {models}").format(
                    count=len(result.removed), models=", ".join(result.removed)
                )
            )
        if result.changed and not result.added and not result.removed:
            lines.append(tr("{id} sağlayıcısının ayarları güncellendi.").format(id=provider_id))
        if backup:
            lines.append(tr("Yedek: {path}").format(path=backup))
        if result.skipped:
            lines.append(
                tr("{count} model zaten kayıtlıydı, atlandı: {models}").format(
                    count=len(result.skipped), models=", ".join(result.skipped)
                )
            )
        text = "\n".join(lines) or tr("Değişiklik yapılmadı.")
        self.editing = provider_id
        self._load_config(config.path)
        self.result.setText(text.replace("\n", "  "))
        QMessageBox.information(self, tr("Tamamlandı"), text)


def run():
    app = QApplication.instance() or QApplication([])
    settings = QSettings(*SETTINGS)
    code = settings.value("language", "")
    if code not in i18n.LANGUAGES:
        code = "tr" if QLocale.system().name().startswith("tr") else "en"
    i18n.set_language(code)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    return app.exec()
