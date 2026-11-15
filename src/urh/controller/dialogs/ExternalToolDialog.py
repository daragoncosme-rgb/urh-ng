import os
import shlex

from PyQt6.QtCore import Qt, QProcess
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from urh.util import ExternalTool, KeeLoqPWM

COLUMNS = ["", "Msg", "Encrypted", "Serial", "Button"]


class ExternalToolDialog(QDialog):
    """
    Decodes the protocol messages as KeeLoq code words (same decoder as the
    KeeLoq code word decoder) and lists only the valid ones, each with a
    checkbox. Checked messages are passed to an external program as
    "encrypted:serial:button" arguments, after any extra parameters:

        <program> <extra parameters> <enc1>:<serial1>:<button1> <enc2>:<serial2>:<button2> ...

    The program's path and the extra parameters are remembered (ExternalTool
    settings) so they only need to be set once.
    """

    def __init__(self, messages, sample_rate=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Run external tool"))
        self.setMinimumSize(640, 460)
        self.sample_rate = sample_rate
        self.words = []  # valid CodeWord objects only, in table order

        for message in messages:
            word = KeeLoqPWM.decode_message(message.plain_bits_str)
            if word.ok:
                self.words.append(word)

        self._setup_ui()
        self._populate()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel(self.tr("Program:")))
        self.edit_path = QLineEdit(ExternalTool.get_executable())
        self.edit_path.setReadOnly(True)
        path_row.addWidget(self.edit_path)
        self.btn_change_path = QPushButton(self.tr("Change..."))
        self.btn_change_path.clicked.connect(self._on_change_path)
        path_row.addWidget(self.btn_change_path)
        layout.addLayout(path_row)

        self.lbl_summary = QLabel()
        self.lbl_summary.setWordWrap(True)
        layout.addWidget(self.lbl_summary)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels([self.tr(c) if c else "" for c in COLUMNS])
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        layout.addWidget(self.table)

        check_row = QHBoxLayout()
        self.btn_check_all = QPushButton(self.tr("Check all"))
        self.btn_check_all.clicked.connect(lambda: self._set_all_checked(True))
        check_row.addWidget(self.btn_check_all)
        self.btn_check_none = QPushButton(self.tr("Check none"))
        self.btn_check_none.clicked.connect(lambda: self._set_all_checked(False))
        check_row.addWidget(self.btn_check_none)
        check_row.addStretch(1)
        layout.addLayout(check_row)

        params_row = QHBoxLayout()
        params_row.addWidget(QLabel(self.tr("Extra parameters:")))
        self.edit_params = QLineEdit(ExternalTool.get_extra_parameters())
        self.edit_params.setToolTip(
            self.tr(
                "Extra command-line parameters, added before the "
                "encrypted:serial:button arguments of the checked messages. "
                "Quote a parameter that contains spaces."
            )
        )
        params_row.addWidget(self.edit_params)
        layout.addLayout(params_row)

        final_params_row = QHBoxLayout()
        final_params_row.addWidget(QLabel(self.tr("Final parameters:")))
        self.edit_final_params = QLineEdit(ExternalTool.get_final_parameters())
        self.edit_final_params.setToolTip(
            self.tr(
                "Final command-line parameters, added after the "
                "encrypted:serial:button arguments. Quote a parameter that "
                "contains spaces."
            )
        )
        final_params_row.addWidget(self.edit_final_params)
        layout.addLayout(final_params_row)

        self.lbl_hint = QLabel(
            self.tr(
                "Each checked message is passed as one "
                "encrypted:serial:button argument, in table order, between "
                "the extra parameters and the final parameters above."
            )
        )
        self.lbl_hint.setWordWrap(True)
        layout.addWidget(self.lbl_hint)

        buttons = QHBoxLayout()
        self.btn_copy = QPushButton(self.tr("Copy command line"))
        self.btn_copy.clicked.connect(self._on_copy)
        buttons.addWidget(self.btn_copy)
        buttons.addStretch(1)
        self.btn_run = QPushButton(self.tr("Run"))
        self.btn_run.setDefault(True)
        self.btn_run.clicked.connect(self._on_run)
        buttons.addWidget(self.btn_run)
        btn_close = QPushButton(self.tr("Close"))
        btn_close.clicked.connect(self.close)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)

    def _populate(self):
        self.table.setRowCount(len(self.words))
        for row, word in enumerate(self.words):
            chk_item = QTableWidgetItem()
            chk_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            chk_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, chk_item)

            values = [str(row + 1), word.encrypted_hex, word.serial_hex, word.button_text]
            for col, text in enumerate(values, start=1):
                self.table.setItem(row, col, QTableWidgetItem(text))

        if self.words:
            self.lbl_summary.setText(
                self.tr("{0} valid KeeLoq code word(s) available.").format(
                    len(self.words)
                )
            )
        else:
            self.lbl_summary.setText(
                self.tr(
                    "No valid KeeLoq code words found in these messages. Check "
                    "Samples/Symbol in the Interpretation tab (about one TE, "
                    "roughly 400 µs) and the ASK/OOK modulation."
                )
            )

        has_path = bool(self.edit_path.text())
        self.btn_run.setEnabled(has_path and bool(self.words))
        self.btn_check_all.setEnabled(bool(self.words))
        self.btn_check_none.setEnabled(bool(self.words))

    def _set_all_checked(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(state)

    def _checked_words(self):
        checked = []
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).checkState() == Qt.CheckState.Checked:
                checked.append(self.words[row])
        return checked

    @staticmethod
    def _split(text):
        text = text.strip()
        if not text:
            return []
        try:
            return shlex.split(text)
        except ValueError:
            # unbalanced quotes: fall back to a plain whitespace split
            return text.split()

    def _build_arguments(self):
        args = self._split(self.edit_params.text())
        for word in self._checked_words():
            args.append(
                "{0}:{1}:{2}".format(
                    word.encrypted_hex, word.serial_hex, word.button_text
                )
            )
        args.extend(self._split(self.edit_final_params.text()))
        return args

    def _on_change_path(self):
        current = self.edit_path.text()
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select the program to run"),
            os.path.dirname(current) if current else os.path.expanduser("~"),
            self.tr(
                "Programs and scripts (*.exe *.bat *.cmd);;"
                "Executable (*.exe);;Batch script (*.bat *.cmd);;All files (*)"
            )
            if os.name == "nt"
            else self.tr("Batch script (*.bat *.cmd);;All files (*)"),
        )
        if path:
            ExternalTool.set_executable(path)
            self.edit_path.setText(path)
            self._populate()

    @staticmethod
    def _start_detached(program, args, workdir):
        """
        Thin wrapper around QProcess.startDetached, so tests can patch this
        plain Python method instead of the real Qt/C++ static method.
        """
        return QProcess.startDetached(program, args, workdir)

    def _on_copy(self):
        path = self.edit_path.text() or "<program>"
        parts = [path] + self._build_arguments()
        QApplication.clipboard().setText(
            " ".join(shlex.quote(p) if p else '""' for p in parts)
        )

    def _on_run(self):
        path = self.edit_path.text()
        if not path:
            self._on_change_path()
            path = self.edit_path.text()
            if not path:
                return
        if not os.path.isfile(path):
            QMessageBox.warning(
                self,
                self.tr("Run external tool"),
                self.tr("{0}\n\nwas not found.").format(path),
            )
            return

        ExternalTool.set_extra_parameters(self.edit_params.text())
        ExternalTool.set_final_parameters(self.edit_final_params.text())
        args = self._build_arguments()

        # Always launch through "cmd /c start", for two reasons:
        # - QProcess (CreateProcess on Windows) cannot run a .bat/.cmd script
        #   directly, only a real executable.
        # - URH-NG itself is a windowed (GUI-subsystem, no console) build, so
        #   a child process started directly from it inherits its hidden
        #   window state and runs with no visible window, even a console
        #   .exe. "start" opens a fresh console with normal visibility,
        #   regardless of what started it. The empty "" after start is a
        #   required placeholder for the new window's title (otherwise,
        #   start treats the first quoted argument as the title).
        program = "cmd.exe"
        program_args = ["/c", "start", "", path] + args

        started = self._start_detached(program, program_args, os.path.dirname(path))
        if isinstance(started, tuple):
            started = started[0]
        if not started:
            QMessageBox.warning(
                self,
                self.tr("Run external tool"),
                self.tr("Could not start\n{0}\n{1}").format(path, " ".join(args)),
            )
