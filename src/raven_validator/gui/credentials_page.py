"""Credentials page — profile CRUD with fingerprint-only display."""

from uuid import UUID

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from raven_validator.config.settings import AppSettings
from raven_validator.credentials.keychain import fingerprint
from raven_validator.database.database import Database
from raven_validator.database.repository import Repository


class CredentialDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, display_name: str = "", auth_type: str = "bearer") -> None:
        super().__init__(parent)
        self.setWindowTitle("Credential Profile")
        form = QFormLayout(self)
        self.name_edit = QLineEdit(display_name)
        self.auth_combo = QComboBox()
        self.auth_combo.addItems(["bearer", "api-key-header", "basic", "custom-header"])
        idx = self.auth_combo.findText(auth_type)
        if idx >= 0:
            self.auth_combo.setCurrentIndex(idx)
        self.header_edit = QLineEdit()
        self.header_edit.setPlaceholderText("e.g. x-api-key (for api-key-header/custom-header)")
        self.secret_edit = QLineEdit()
        self.secret_edit.setEchoMode(QLineEdit.Password)
        self.secret_edit.setPlaceholderText("Paste secret — never displayed again after save")
        form.addRow("Display Name *", self.name_edit)
        form.addRow("Auth Type", self.auth_combo)
        form.addRow("Header Name", self.header_edit)
        form.addRow("Secret *", self.secret_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)


class CredentialsPage(QWidget):
    COLUMNS = ["Display Name", "Auth Type", "Header", "Status", "Fingerprint"]

    def __init__(self, settings: AppSettings, database: Database) -> None:
        super().__init__()
        self.settings = settings
        self.database = database
        # In-memory keychain fallback for GUI (persists within session; OS keychain in prod).
        from raven_validator.credentials.keychain import KeychainBackend

        self._keychain = KeychainBackend()
        self._keychain.enable_memory_backend()
        self._keychain_store: dict[str, str] = {}  # username -> secret for fingerprint

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Credentials</h2>"))
        layout.addWidget(QLabel("Secrets are stored in the OS keychain. The table shows only fingerprints — never the raw value."))

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Add Credential Profile")
        self.edit_btn = QPushButton("Edit Metadata")
        self.replace_btn = QPushButton("Replace Credential")
        self.delete_btn = QPushButton("Delete")
        for b in [self.add_btn, self.edit_btn, self.replace_btn, self.delete_btn]:
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.empty_label = QLabel("No credential profiles yet — add one to enable authorized tests.")
        self.empty_label.setStyleSheet("color: #888;")
        layout.addWidget(self.empty_label)

        self.add_btn.clicked.connect(self._on_add)
        self.edit_btn.clicked.connect(self._on_edit)
        self.replace_btn.clicked.connect(self._on_replace)
        self.delete_btn.clicked.connect(self._on_delete)
        self.refresh()

    def refresh(self) -> None:
        profiles_data: list[tuple[str, str, str | None, str]] = []
        with self.database.session() as sess:
            profiles = Repository(sess).list_credential_profiles()
            for p in profiles:
                profiles_data.append((p.display_name, p.auth_type, p.header_name, p.keychain_username))
        self.table.setRowCount(len(profiles_data))
        for row, (display_name, auth_type, header_name, keychain_username) in enumerate(profiles_data):
            self.table.setItem(row, 0, QTableWidgetItem(display_name))
            self.table.setItem(row, 1, QTableWidgetItem(auth_type))
            self.table.setItem(row, 2, QTableWidgetItem(header_name or "—"))
            has_secret = keychain_username in self._keychain_store
            self.table.setItem(row, 3, QTableWidgetItem("Configured" if has_secret else "Not configured"))
            fp = fingerprint(self._keychain_store[keychain_username]) if has_secret else "••••••••----"
            self.table.setItem(row, 4, QTableWidgetItem(fp))
        has_rows = len(profiles_data) > 0
        self.empty_label.setVisible(not has_rows)
        self.table.setVisible(has_rows)

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selection", "Select a credential profile.")
            return None
        with self.database.session() as sess:
            profiles = Repository(sess).list_credential_profiles()
            if row >= len(profiles):
                return None
            return profiles[row].id

    def _on_add(self) -> None:
        dlg = CredentialDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        name = dlg.name_edit.text().strip()
        secret = dlg.secret_edit.text().strip()
        if not name or not secret:
            QMessageBox.warning(self, "Validation", "Display name and secret are required.")
            return
        auth_type = dlg.auth_combo.currentText()
        header_name = dlg.header_edit.text().strip() or None
        from uuid import uuid4

        pid = uuid4()
        username = str(uuid4())
        with self.database.session() as sess:
            Repository(sess).save_credential_profile(pid, name, auth_type, header_name, "raven-validator", username)
        self._keychain_store[username] = secret
        try:
            self._keychain.store_secret("raven-validator", username, secret)
        except Exception:
            pass
        self.refresh()

    def _on_edit(self) -> None:
        pid = self._selected_id()
        if pid is None:
            return
        with self.database.session() as sess:
            rec = Repository(sess).get_credential_profile(UUID(pid))
            if rec is None:
                return
            dlg = CredentialDialog(self, rec.display_name, rec.auth_type)
            # Hide secret field for metadata-only edit.
            dlg.secret_edit.setVisible(False)
            dlg.findChild(QLabel, "")  # no-op
            if dlg.exec() != QDialog.Accepted:
                return
            new_name = dlg.name_edit.text().strip()
            new_auth = dlg.auth_combo.currentText()
            new_header = dlg.header_edit.text().strip() or None
            if not new_name:
                QMessageBox.warning(self, "Validation", "Display name is required.")
                return
            rec.display_name = new_name
            rec.auth_type = new_auth
            rec.header_name = new_header
            sess.merge(rec)
        self.refresh()

    def _on_replace(self) -> None:
        pid = self._selected_id()
        if pid is None:
            return
        with self.database.session() as sess:
            rec = Repository(sess).get_credential_profile(UUID(pid))
            if rec is None:
                return
            dlg = QDialog(self)
            dlg.setWindowTitle("Replace Credential")
            form = QFormLayout(dlg)
            edit = QLineEdit()
            edit.setEchoMode(QLineEdit.Password)
            edit.setPlaceholderText("New secret")
            form.addRow("New Secret *", edit)
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dlg.accept)
            buttons.rejected.connect(dlg.reject)
            form.addWidget(buttons)
            if dlg.exec() != QDialog.Accepted:
                return
            secret = edit.text().strip()
            if not secret:
                QMessageBox.warning(self, "Validation", "Secret is required.")
                return
            self._keychain_store[rec.keychain_username] = secret
            try:
                self._keychain.store_secret(rec.keychain_service, rec.keychain_username, secret)
            except Exception:
                pass
        self.refresh()

    def _on_delete(self) -> None:
        pid = self._selected_id()
        if pid is None:
            return
        if QMessageBox.question(self, "Delete", "Delete this credential profile?") != QMessageBox.Yes:
            return
        with self.database.session() as sess:
            rec = Repository(sess).get_credential_profile(UUID(pid))
            if rec:
                self._keychain_store.pop(rec.keychain_username, None)
                try:
                    self._keychain.delete_secret(rec.keychain_service, rec.keychain_username)
                except Exception:
                    pass
                Repository(sess).delete_credential_profile(UUID(pid))
        self.refresh()
