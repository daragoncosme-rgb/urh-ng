from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QAbstractItemView,
    QGroupBox,
    QTextEdit,
    QSplitter,
    QWidget,
    QProgressBar,
    QComboBox,
)

from urh import settings

from urh.awre.ProtocolMatcher import ProtocolMatch


class ProtocolMatchDialog(QDialog):
    """Dialog showing protocol matching results with confidence scores."""

    match_selected = pyqtSignal(object)  # Emits the selected ProtocolMatch

    # Filter entries: (label, categories shown or None for all)
    FILTERS = [
        ("Remote controls (gates, garages, car keys)", ("remote", "car key")),
        ("Remote controls and alarms", ("remote", "car key", "security")),
        ("Sensors, meters and TPMS", ("sensor", "meter", "tpms", "other")),
        ("All devices", None),
    ]
    SETTINGS_KEY = "ProtocolMatchDialog/filter"

    def __init__(self, matches: list, parent=None):
        super().__init__(parent)
        self.all_matches = matches
        self.matches = matches
        self.selected_match = None
        self.setWindowTitle("Auto Protocol Identification")
        self.setMinimumSize(750, 500)
        self.setup_ui()
        self.populate()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel(
            "Protocol matches found from the PHZ database (327 protocols).\n"
            "Select a protocol to apply its field labels, or cancel to skip."
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Show:"))
        self.combo_filter = QComboBox()
        for label, _ in self.FILTERS:
            self.combo_filter.addItem(label)
        self.combo_filter.setCurrentIndex(
            min(
                max(settings.read(self.SETTINGS_KEY, 0, int), 0),
                len(self.FILTERS) - 1,
            )
        )
        self.combo_filter.setToolTip(
            "Most of the database are sensors (weather stations, thermometers). "
            "Show only the device types you are looking for."
        )
        self.combo_filter.currentIndexChanged.connect(self.on_filter_changed)
        filter_row.addWidget(self.combo_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Splitter for table + details
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Confidence", "Protocol Name", "Type", "Modulation", "Fields"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self.table.setAlternatingRowColors(True)
        self.table.currentCellChanged.connect(self.on_selection_changed)
        splitter.addWidget(self.table)

        # Details panel
        details_group = QGroupBox("Match Details")
        details_layout = QVBoxLayout(details_group)
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        details_layout.addWidget(self.details_text)
        splitter.addWidget(details_group)

        layout.addWidget(splitter)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_apply = QPushButton("Apply Selected Protocol")
        self.btn_apply.setEnabled(False)
        self.btn_apply.setDefault(True)
        self.btn_apply.clicked.connect(self.on_apply)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def on_filter_changed(self, index: int):
        settings.write(self.SETTINGS_KEY, index)
        self.populate()

    def populate(self):
        categories = self.FILTERS[self.combo_filter.currentIndex()][1]
        self.matches = [
            m
            for m in self.all_matches
            if categories is None or getattr(m, "category", "other") in categories
        ]
        self.selected_match = None
        self.btn_apply.setEnabled(False)
        self.details_text.clear()
        self.table.clearContents()
        self.table.setRowCount(len(self.matches))
        for row, match in enumerate(self.matches):
            # Confidence with color-coded progress bar
            conf_widget = QWidget()
            conf_layout = QHBoxLayout(conf_widget)
            conf_layout.setContentsMargins(4, 2, 4, 2)
            pbar = QProgressBar()
            pbar.setRange(0, 100)
            pbar.setValue(match.percentage)
            pbar.setTextVisible(True)
            pbar.setFormat(f"{match.percentage}%")
            if match.percentage >= 60:
                pbar.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")
            elif match.percentage >= 30:
                pbar.setStyleSheet("QProgressBar::chunk { background-color: #FFC107; }")
            else:
                pbar.setStyleSheet("QProgressBar::chunk { background-color: #FF5722; }")
            pbar.setFixedHeight(20)
            conf_layout.addWidget(pbar)
            self.table.setCellWidget(row, 0, conf_widget)

            # Protocol name
            name_item = QTableWidgetItem(match.name)
            name_item.setFont(QFont("", -1, QFont.Weight.Bold))
            self.table.setItem(row, 1, name_item)

            # Modulation
            mod = match.entry.get("modulation", "")
            mod_short = mod.replace("OOK_PULSE_", "OOK/").replace("FSK_PULSE_", "FSK/")
            self.table.setItem(row, 2, QTableWidgetItem(getattr(match, "category", "")))
            self.table.setItem(row, 3, QTableWidgetItem(mod_short))

            # Fields
            fields = match.entry.get("fields", [])
            fields_str = ", ".join(f for f in fields if f != "model")
            self.table.setItem(row, 4, QTableWidgetItem(fields_str))

        self.table.resizeColumnToContents(0)
        self.table.resizeColumnToContents(2)
        self.table.resizeColumnToContents(3)

        hidden = len(self.all_matches) - len(self.matches)
        if hidden and not self.matches:
            self.details_text.setHtml(
                f"No match of this type. {hidden} other matches are hidden: "
                f"choose <b>All devices</b> to see them."
            )

    def on_selection_changed(self, row, col, prev_row, prev_col):
        if 0 <= row < len(self.matches):
            match = self.matches[row]
            self.selected_match = match
            self.btn_apply.setEnabled(True)

            # Build details text
            lines = [f"<b>{match.name}</b>"]
            lines.append(f"Confidence: <b>{match.percentage}%</b>")
            lines.append("")

            entry = match.entry
            if entry.get("modulation"):
                lines.append(f"Modulation: {entry['modulation']}")
            if entry.get("short_width"):
                lines.append(
                    f"Pulse widths: short={entry['short_width']}us, "
                    f"long={entry.get('long_width', '?')}us"
                )
            if entry.get("msg_len_bits"):
                lines.append(f"Expected message length: {entry['msg_len_bits']} bits")
            if entry.get("checksum"):
                lines.append(f"Checksum: {entry['checksum']}")
            if entry.get("preamble_bits"):
                lines.append(f"Preamble: 0x{entry['preamble_bits']}")
            if entry.get("sync_bytes"):
                lines.append(f"Sync word: 0x{entry['sync_bytes']}")

            if match.recommended_decoder:
                lines.append(
                    f"<br><b>Recommended decoder:</b>"
                    f" {match.recommended_decoder.name}"
                )
            if match.leading_zeros_count > 0:
                lines.append(
                    f"<b>Leading zeros:</b>"
                    f" {match.leading_zeros_count} bits"
                    f" (will be labeled as noise)"
                )
            if match.cipher:
                lines.append(
                    f"<b>Cipher:</b> {match.cipher}" f" (available in Crypto Toolkit)"
                )

            lines.append("")
            lines.append("<b>Scoring details:</b>")
            for key, val in match.details.items():
                lines.append(f"  {key}: {val}")

            self.details_text.setHtml("<br>".join(lines))
        else:
            self.btn_apply.setEnabled(False)
            self.details_text.clear()

    def on_apply(self):
        if self.selected_match:
            self.match_selected.emit(self.selected_match)
            self.accept()
