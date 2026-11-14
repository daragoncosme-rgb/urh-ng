from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from urh.util import KeeLoqPWM

COLUMNS = [
    "Msg",
    "Status",
    "Encrypted",
    "Serial",
    "Button",
    "Battery",
    "Repeat",
    "TE (µs)",
    "Raw KeeLoq bits",
]


class KeeLoqCodeWordDialog(QDialog):
    """
    Decodes the messages of the protocol table as KeeLoq code words (PWM:
    encrypted portion, serial number, button code, V-Low and repeat flag).
    Based on the KeeLoq decoder of rzondr/KeeLoq_decoder for PulseView.
    """

    # encrypted, serial, encrypted2 (None if only one row selected)
    send_to_toolkit = pyqtSignal(object, object, object)

    def __init__(self, messages, sample_rate=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("KeeLoq code word decoder"))
        self.setMinimumSize(860, 420)
        self.sample_rate = sample_rate
        self.results = []  # (message index, CodeWord)

        for index, message in enumerate(messages):
            bits = message.plain_bits_str
            word = KeeLoqPWM.decode_message(bits)
            word_te = KeeLoqPWM.te_microseconds(
                word, getattr(message, "samples_per_symbol", None), sample_rate
            )
            self.results.append((index, word, word_te))

        self._setup_ui()
        self._populate()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.lbl_summary = QLabel()
        self.lbl_summary.setWordWrap(True)
        layout.addWidget(self.lbl_summary)

        self.chk_only_ok = QCheckBox(self.tr("Show only valid code words"))
        self.chk_only_ok.setChecked(True)
        self.chk_only_ok.toggled.connect(self._populate)
        layout.addWidget(self.chk_only_ok)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels([self.tr(c) for c in COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        layout.addWidget(self.table)

        self.lbl_hint = QLabel(
            self.tr(
                "Encrypted portion, serial number and button code are shown as "
                "transmitted (LSB first, converted to the usual hex value). "
                "The encrypted portion is not decrypted here: use the Crypto "
                "Toolkit with the manufacturer key."
            )
        )
        self.lbl_hint.setWordWrap(True)
        layout.addWidget(self.lbl_hint)

        self.lbl_credit = QLabel(
            self.tr(
                "Based on the KeeLoq decoder for PulseView by Andrea Orazi "
                "(<a href='https://github.com/rzondr/KeeLoq_decoder'>"
                "github.com/rzondr/KeeLoq_decoder</a>, GPL v2+)."
            )
        )
        self.lbl_credit.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_credit.setOpenExternalLinks(True)
        self.lbl_credit.setWordWrap(True)
        layout.addWidget(self.lbl_credit)

        buttons = QHBoxLayout()
        self.btn_toolkit = QPushButton(self.tr("Send to Crypto Toolkit"))
        self.btn_toolkit.setToolTip(
            self.tr(
                "Fills Encrypted #1 and the serial number from the selected row. "
                "With two rows selected the second one goes to Encrypted #2 "
                "(for the key bruteforce)."
            )
        )
        self.btn_toolkit.clicked.connect(self._on_send_to_toolkit)
        buttons.addWidget(self.btn_toolkit)

        self.btn_copy = QPushButton(self.tr("Copy"))
        self.btn_copy.clicked.connect(self._on_copy)
        buttons.addWidget(self.btn_copy)

        buttons.addStretch(1)
        btn_close = QPushButton(self.tr("Close"))
        btn_close.clicked.connect(self.close)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)
        self._update_buttons()

    def _visible_results(self):
        if self.chk_only_ok.isChecked():
            return [r for r in self.results if r[1].ok]
        return self.results

    def _populate(self):
        rows = self._visible_results()
        self.table.setRowCount(len(rows))
        for row, (index, word, te_us) in enumerate(rows):
            if word.ok:
                te_text = "" if te_us is None else "{0:.0f}".format(te_us)
                values = [
                    str(index + 1),
                    word.status,
                    word.encrypted_hex,
                    word.serial_hex,
                    word.button_text,
                    "Low" if word.v_low else "OK",
                    "Yes" if word.repeat else "No",
                    te_text,
                    word.bits,
                ]
            else:
                values = [str(index + 1), word.status, "", "", "", "", "", "", ""]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row)
                if not word.ok:
                    item.setForeground(QColor("gray"))
                elif (
                    col == 7
                    and te_us is not None
                    and not KeeLoqPWM.TE_MIN_US <= te_us <= KeeLoqPWM.TE_MAX_US
                ):
                    item.setForeground(QColor("orange"))
                    item.setToolTip(
                        self.tr("TE is outside the 280-580 µs of the HCS datasheets")
                    )
                self.table.setItem(row, col, item)

        valid = sum(1 for r in self.results if r[1].ok)
        preambles = sum(1 for r in self.results if r[1].status == "Preamble only")
        self.lbl_summary.setText(
            self.tr(
                "{0} of {1} messages are valid KeeLoq code words ({2} preamble-only)."
            ).format(valid, len(self.results), preambles)
            + (
                ""
                if valid
                else " "
                + self.tr(
                    "Check Samples/Symbol in the Interpretation tab: one symbol "
                    "should be about one TE (roughly 400 µs) and the modulation "
                    "ASK/OOK."
                )
            )
        )
        self._update_buttons()

    def _selected_words(self):
        rows = self._visible_results()
        selected = sorted({i.row() for i in self.table.selectedIndexes()})
        return [rows[r][1] for r in selected if r < len(rows) and rows[r][1].ok]

    def _update_buttons(self):
        words = self._selected_words()
        self.btn_toolkit.setEnabled(len(words) >= 1)
        self.btn_copy.setEnabled(self.table.rowCount() > 0)

    def _on_send_to_toolkit(self):
        words = self._selected_words()
        if not words:
            return
        second = words[1].encrypted if len(words) > 1 else None
        self.send_to_toolkit.emit(words[0].encrypted, words[0].serial, second)

    def _on_copy(self):
        lines = ["\t".join(COLUMNS)]
        for row in range(self.table.rowCount()):
            lines.append(
                "\t".join(
                    self.table.item(row, c).text()
                    for c in range(self.table.columnCount())
                )
            )
        QApplication.clipboard().setText("\n".join(lines))
