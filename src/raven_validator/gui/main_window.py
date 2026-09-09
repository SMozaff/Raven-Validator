"""PySide6 GUI with working candidate/credential association and validation controls."""
from __future__ import annotations

import asyncio
from uuid import uuid4

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMainWindow,
    QMessageBox, QPushButton, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from raven_validator.config.settings import AppSettings
from raven_validator.credentials.keychain import OSKeychain, fingerprint, KeychainError
from raven_validator.credentials.manager import CredentialManager
from raven_validator.database.database import Database
from raven_validator.domain.candidates import APICandidate
from raven_validator.domain.credentials import AuthScheme, CredentialProfile
from raven_validator.services.import_service import ImportService
from raven_validator.services.validation_service import BatchEvent, ValidationOptions, ValidationService


class CandidateDialog(QDialog):
    def __init__(self, db: Database, candidate: APICandidate | None = None, parent=None) -> None:
        super().__init__(parent); self.db = db; self.candidate = candidate; self.setWindowTitle("API Candidate")
        form = QFormLayout(self)
        self.name = QLineEdit(candidate.name if candidate else "")
        self.url = QLineEdit(str(candidate.base_url) if candidate else "")
        self.protocol = QComboBox(); self.protocol.addItems(["", "openai-compatible", "anthropic-compatible", "generic-rest"])
        if candidate and candidate.protocol_hint: self.protocol.setCurrentText(candidate.protocol_hint)
        self.credential = QComboBox(); self.credential.addItem("None", None)
        for p in db.list_profiles(): self.credential.addItem(p.display_name, p.id)
        if candidate and candidate.credential_profile_id:
            idx = self.credential.findData(candidate.credential_profile_id)
            if idx >= 0: self.credential.setCurrentIndex(idx)
        self.quota = QLineEdit(candidate.quota_endpoint if candidate and candidate.quota_endpoint else "")
        form.addRow("Name", self.name); form.addRow("Base URL", self.url); form.addRow("Protocol Hint", self.protocol)
        form.addRow("Credential Profile", self.credential); form.addRow("Documented Quota URL", self.quota)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addWidget(buttons)

    def value(self) -> APICandidate:
        return APICandidate(
            id=self.candidate.id if self.candidate else uuid4(), name=self.name.text().strip(),
            base_url=self.url.text().strip(), protocol_hint=self.protocol.currentText() or None,
            credential_profile_id=self.credential.currentData(), quota_endpoint=self.quota.text().strip() or None,
            provider_hint=self.candidate.provider_hint if self.candidate else None,
            source_url=self.candidate.source_url if self.candidate else None,
            source_type=self.candidate.source_type if self.candidate else None,
            notes=self.candidate.notes if self.candidate else None,
        )


class CredentialDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent); self.setWindowTitle("Credential Profile"); form = QFormLayout(self)
        self.name = QLineEdit(); self.secret = QLineEdit(); self.secret.setEchoMode(QLineEdit.Password)
        self.auth = QComboBox(); self.auth.addItems([x.value for x in (AuthScheme.BEARER, AuthScheme.API_KEY_HEADER, AuthScheme.BASIC, AuthScheme.CUSTOM_HEADER)])
        self.header = QLineEdit(); form.addRow("Name", self.name); form.addRow("Auth Type", self.auth); form.addRow("Header Name", self.header); form.addRow("Secret", self.secret)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addWidget(buttons)


class ValidationWorker(QObject):
    event = Signal(object); failed = Signal(str); finished = Signal()
    def __init__(self, service: ValidationService, candidates: list[APICandidate], options: ValidationOptions) -> None:
        super().__init__(); self.service=service; self.candidates=candidates; self.options=options
    @Slot()
    def run(self) -> None:
        async def go():
            async for e in self.service.validate_batch(self.candidates, self.options): self.event.emit(e)
        try: asyncio.run(go())
        except Exception as exc: self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally: self.finished.emit()
    @Slot()
    def cancel(self) -> None: self.service.cancel()


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__(); self.settings=settings; self.db=Database(settings.db_url); self.keychain=OSKeychain(); self.cred_manager=CredentialManager(self.keychain)
        self.setWindowTitle("Raven-Validator"); self.resize(1200,760)
        self.tabs=QTabWidget(); self.setCentralWidget(self.tabs)
        self.candidates_tab=QWidget(); self.validator_tab=QWidget(); self.credentials_tab=QWidget(); self.results_tab=QWidget(); self.settings_tab=QWidget()
        for title,w in [("Candidates",self.candidates_tab),("Validator",self.validator_tab),("Credentials",self.credentials_tab),("Results",self.results_tab),("Settings",self.settings_tab)]: self.tabs.addTab(w,title)
        self._build_candidates(); self._build_validator(); self._build_credentials(); self._build_results(); self._build_settings(); self.refresh_all()
        self._thread=None; self._worker=None

    def _build_candidates(self):
        l=QVBoxLayout(self.candidates_tab); row=QHBoxLayout(); l.addLayout(row)
        for text,fn in [("Add API",self.add_candidate),("Import Targeter",self.import_targeter),("Edit",self.edit_candidate),("Delete",self.delete_candidate),("Validate Selected",self.validate_selected)]:
            b=QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        row.addStretch(); self.candidates=QTableWidget(0,6); self.candidates.setHorizontalHeaderLabels(["Name","Base URL","Protocol","Credential","Quota","Source"]); self.candidates.setSelectionBehavior(QTableWidget.SelectRows); l.addWidget(self.candidates)

    def _build_credentials(self):
        l=QVBoxLayout(self.credentials_tab); row=QHBoxLayout(); l.addLayout(row)
        add=QPushButton("Add Credential Profile"); add.clicked.connect(self.add_credential); delete=QPushButton("Delete"); delete.clicked.connect(self.delete_credential); row.addWidget(add); row.addWidget(delete); row.addStretch()
        self.credentials=QTableWidget(0,4); self.credentials.setHorizontalHeaderLabels(["Name","Auth Type","Header","Status/Fingerprint"]); l.addWidget(self.credentials)
        l.addWidget(QLabel("Secrets are stored in the OS keychain. No in-memory production fallback is used."))

    def _build_validator(self):
        l=QVBoxLayout(self.validator_tab); l.addWidget(QLabel("Select APIs to validate:")); self.api_list=QListWidget(); self.api_list.setSelectionMode(QListWidget.MultiSelection); l.addWidget(self.api_list)
        form=QFormLayout(); l.addLayout(form); self.mode=QComboBox(); self.mode.addItems(["Quick","Standard","Authorized"]); self.mode.setCurrentText("Standard")
        self.concurrency=QSpinBox(); self.concurrency.setRange(1,50); self.concurrency.setValue(self.settings.max_concurrency)
        self.timeout=QSpinBox(); self.timeout.setRange(1,300); self.timeout.setValue(int(max(self.settings.connect_timeout,self.settings.read_timeout)))
        form.addRow("Mode",self.mode); form.addRow("Concurrency",self.concurrency); form.addRow("Timeout seconds",self.timeout)
        row=QHBoxLayout(); l.addLayout(row); self.streaming=QCheckBox("Test streaming"); self.quota=QCheckBox("Check quota/credits"); self.rate_limits=QCheckBox("Inspect rate limits"); self.rate_limits.setChecked(True)
        row.addWidget(self.streaming); row.addWidget(self.quota); row.addWidget(self.rate_limits); row.addStretch()
        row2=QHBoxLayout(); l.addLayout(row2); self.start=QPushButton("START VALIDATION"); self.cancel=QPushButton("CANCEL"); self.cancel.setEnabled(False); row2.addWidget(self.start); row2.addWidget(self.cancel); row2.addStretch()
        self.status=QLabel("Ready"); l.addWidget(self.status); self.start.clicked.connect(self.start_validation); self.cancel.clicked.connect(self.cancel_validation)

    def _build_results(self):
        l=QVBoxLayout(self.results_tab); self.results=QTableWidget(0,10); self.results.setHorizontalHeaderLabels(["Status","API","Protocol","Reachable","Auth","Credential","Models","Rate Limit","Quota","Requests"]); l.addWidget(self.results)

    def _build_settings(self):
        l=QVBoxLayout(self.settings_tab); l.addWidget(QLabel(f"DB: {self.settings.db_url}")); l.addWidget(QLabel(f"Private/local endpoints allowed: {self.settings.allow_private_networks}")); l.addWidget(QLabel(f"Default request budget: {self.settings.max_requests_per_api}")); l.addStretch()

    def refresh_all(self): self.refresh_candidates(); self.refresh_credentials(); self.refresh_results()

    def refresh_candidates(self):
        cs=self.db.list_candidates(); self._candidate_ids=[str(c.id) for c in cs]; self.candidates.setRowCount(len(cs)); self.api_list.clear()
        profiles={p.id:p.display_name for p in self.db.list_profiles()}
        for r,c in enumerate(cs):
            vals=[c.name,str(c.base_url),c.protocol_hint or "—",profiles.get(c.credential_profile_id,"None"),c.quota_endpoint or "—",str(c.source_url or "—")]
            for col,v in enumerate(vals): self.candidates.setItem(r,col,QTableWidgetItem(v))
            item_text=f"{c.name} — {c.base_url} — credential: {profiles.get(c.credential_profile_id,'None')}"; self.api_list.addItem(item_text)

    def refresh_credentials(self):
        ps=self.db.list_profiles(); self._profile_ids=[p.id for p in ps]; self.credentials.setRowCount(len(ps))
        for r,p in enumerate(ps):
            try: secret=self.cred_manager.retrieve_secret(p); state=f"Configured {fingerprint(secret)}" if secret else "Missing in keychain"
            except KeychainError as exc: state=f"Keychain error: {exc}"
            for col,v in enumerate([p.display_name,p.auth_type.value,p.header_name or "—",state]): self.credentials.setItem(r,col,QTableWidgetItem(v))

    def refresh_results(self):
        rs=self.db.list_results(); self.results.setRowCount(len(rs))
        for r,x in enumerate(rs):
            vals=[x.overall_status.value,x.base_url,x.detected_protocol,str(x.reachable),x.auth_scheme or "—","Used" if x.credential_used else ("Configured" if x.credential_configured else "None"),str(len(x.models)),str(x.rate_limit.remaining if x.rate_limit.known else "Unknown"),x.quota.status,str(x.request_count)]
            for c,v in enumerate(vals): self.results.setItem(r,c,QTableWidgetItem(v))

    def _selected_candidate(self) -> APICandidate | None:
        r=self.candidates.currentRow(); cs=self.db.list_candidates(); return cs[r] if 0<=r<len(cs) else None

    def add_candidate(self):
        d=CandidateDialog(self.db,parent=self)
        if d.exec()==QDialog.Accepted:
            try: c=d.value(); self.db.save_candidate(c); self.refresh_candidates()
            except Exception as exc: QMessageBox.warning(self,"Invalid candidate",str(exc))

    def edit_candidate(self):
        c=self._selected_candidate()
        if not c: return
        d=CandidateDialog(self.db,c,self)
        if d.exec()==QDialog.Accepted:
            try: self.db.save_candidate(d.value()); self.refresh_candidates()
            except Exception as exc: QMessageBox.warning(self,"Invalid candidate",str(exc))

    def delete_candidate(self):
        c=self._selected_candidate()
        if c: self.db.delete_candidate(str(c.id)); self.refresh_candidates()

    def import_targeter(self):
        path,_=QFileDialog.getOpenFileName(self,"Import Raven-Targeter","","JSON (*.json)")
        if not path: return
        res=ImportService().import_raven_targeter(path)
        for c in res.candidates: self.db.save_candidate(c)
        self.refresh_candidates(); QMessageBox.information(self,"Import",f"Imported {res.imported}; skipped {res.skipped}\n"+"\n".join(res.errors[:5]))

    def add_credential(self):
        d=CredentialDialog(self)
        if d.exec()!=QDialog.Accepted: return
        if not d.name.text().strip() or not d.secret.text(): return
        profile=CredentialProfile(id=str(uuid4()),display_name=d.name.text().strip(),auth_type=AuthScheme(d.auth.currentText()),header_name=d.header.text().strip() or None,keychain_username=str(uuid4()))
        try: self.cred_manager.store_secret(profile,d.secret.text()); self.db.save_profile(profile)
        except KeychainError as exc: QMessageBox.critical(self,"OS Keychain unavailable",str(exc)); return
        self.refresh_all()

    def delete_credential(self):
        r=self.credentials.currentRow(); ps=self.db.list_profiles()
        if not (0<=r<len(ps)): return
        p=ps[r]
        try: self.cred_manager.delete_secret(p)
        except KeychainError: pass
        self.db.delete_profile(p.id); self.refresh_all()

    def validate_selected(self):
        c=self._selected_candidate()
        if not c: return
        self.tabs.setCurrentWidget(self.validator_tab); self.refresh_candidates()
        for i in range(self.api_list.count()): self.api_list.item(i).setSelected(str(self.db.list_candidates()[i].id)==str(c.id))

    def _resolver(self,c:APICandidate):
        if not c.credential_profile_id: return None
        p=self.db.get_profile(c.credential_profile_id)
        if not p: return None
        try: secret=self.cred_manager.retrieve_secret(p)
        except KeychainError: return None
        return (p,secret) if secret else None

    def start_validation(self):
        cs=self.db.list_candidates(); rows={self.api_list.row(i) for i in self.api_list.selectedItems()}; selected=[c for idx,c in enumerate(cs) if idx in rows]
        if not selected: self.status.setText("Select at least one API"); return
        run_settings=self.settings.model_copy(update={"max_concurrency":self.concurrency.value()})
        opts=ValidationOptions(mode=self.mode.currentText().lower(),test_streaming=self.streaming.isChecked(),check_quota=self.quota.isChecked(),inspect_rate_limits=self.rate_limits.isChecked(),timeout_override=float(self.timeout.value()))
        service=ValidationService(run_settings,self._resolver)
        self._thread=QThread(self); self._worker=ValidationWorker(service,selected,opts); self._worker.moveToThread(self._thread); self._thread.started.connect(self._worker.run); self._worker.event.connect(self.on_event); self._worker.failed.connect(self.on_failed); self._worker.finished.connect(self._thread.quit); self._worker.finished.connect(self.on_finished); self._thread.start(); self.start.setEnabled(False); self.cancel.setEnabled(True); self.status.setText(f"Validating {len(selected)} API(s)…")

    def cancel_validation(self):
        if self._worker: self._worker.cancel(); self.status.setText("Cancelling…")

    def on_event(self,e:BatchEvent):
        if e.result: self.db.save_result(e.result); self.refresh_results()
        if e.progress: self.status.setText(f"{e.kind}: {e.progress[0]}/{e.progress[1]}")
        if e.kind in {"run_finished","run_cancelled"}: self.tabs.setCurrentWidget(self.results_tab)

    def on_failed(self,msg:str): self.status.setText(f"Validation failed: {msg}")
    def on_finished(self): self.start.setEnabled(True); self.cancel.setEnabled(False); self._worker=None; self._thread=None


def run_app(settings:AppSettings)->int:
    app=QApplication.instance() or QApplication([]); w=MainWindow(settings); w.show(); return app.exec()
