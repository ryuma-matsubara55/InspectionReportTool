from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QGridLayout, QProgressBar
)
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
from datetime import datetime

from ui import styles

# カラー定義（styles.pyと同等）
SUCCESS = "#4caf50"
ERROR = "#f44336"
WARNING = "#ff9800"
INFO = "#2196f3"
NEUTRAL = "#6b7280"  # 未実施

STATUS_ORDER = ("OK", "NG", "未実施")
STATUS_COLORS = {"OK": SUCCESS, "NG": ERROR, "未実施": NEUTRAL}


class PieChartWidget(QWidget):
    """フラットなドーナツチャートウィジェット"""
    def __init__(self, parent=None, size=200):
        super().__init__(parent)
        self.setMinimumSize(size, size)
        self.data = {"OK": 0, "NG": 0, "未実施": 1}  # デフォルト
        self.colors = {key: QColor(color) for key, color in STATUS_COLORS.items()}
        self.bg_override = None  # 指定時は背景（穴）色として使用

    def set_data(self, data, title=""):
        self.data = data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        side = min(rect.width(), rect.height()) - 16
        chart_rect = QRectF((rect.width() - side) / 2, (rect.height() - side) / 2, side, side)

        total = sum(self.data.values())

        if self.bg_override is not None:
            bg_color = QColor(self.bg_override)
        else:
            bg_color = self.palette().color(self.backgroundRole())

        # データなしの場合は中立色のフルリングを描画
        if total == 0:
            painter.setPen(Qt.NoPen)
            painter.setBrush(self.colors["未実施"])
            painter.drawEllipse(chart_rect)
            inner_side = side * 0.66
            inner_rect = QRectF(
                (rect.width() - inner_side) / 2,
                (rect.height() - inner_side) / 2,
                inner_side, inner_side
            )
            painter.setBrush(bg_color)
            painter.drawEllipse(inner_rect)
            return

        start_angle = 90 * 16  # 12時方向から開始
        painter.setPen(QPen(bg_color, 2))  # セグメント境界は背景色の細線で分割
        for label, value in self.data.items():
            if value == 0:
                continue
            span_angle = int((value / total) * 360 * 16)
            painter.setBrush(self.colors.get(label, QColor("#888888")))
            painter.drawPie(chart_rect, start_angle, -span_angle)
            start_angle -= span_angle

        # 中央をくり抜いたドーナツ形状
        inner_side = side * 0.66
        inner_rect = QRectF(
            (rect.width() - inner_side) / 2,
            (rect.height() - inner_side) / 2,
            inner_side, inner_side
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg_color)
        painter.drawEllipse(inner_rect)

        # 中央に達成率を表示
        if "OK" in self.data and total > 0:
            ok_percent = int((self.data["OK"] / total) * 100)
            fg_color = self.palette().color(self.foregroundRole())

            painter.setPen(fg_color)
            painter.setFont(QFont("Segoe UI", 17, QFont.Bold))
            painter.drawText(inner_rect.adjusted(0, -10, 0, -10), Qt.AlignCenter, f"{ok_percent}%")

            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(inner_rect.adjusted(0, 24, 0, 24), Qt.AlignCenter, "達成率")

class DashboardWidget(QWidget):
    """ダッシュボード画面"""
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.legend_labels = {}
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 20, 24, 20)
        self.layout.setSpacing(18)

        # ---- ヘッダー ----
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title_label = QLabel("ダッシュボード")
        title_label.setObjectName("DashboardTitle")
        subtitle_label = QLabel("検査進捗サマリー")
        subtitle_label.setObjectName("DashboardSubtitle")

        title_box.addWidget(title_label)
        title_box.addWidget(subtitle_label)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        self.last_update_label = QLabel("Last update: -")
        self.last_update_label.setObjectName("DashboardMeta")
        header_layout.addWidget(self.last_update_label)
        self.layout.addLayout(header_layout)

        # ---- サマリーカード ----
        stats_cards_layout = QHBoxLayout()
        stats_cards_layout.setSpacing(14)

        self.total_card = self._create_summary_card("合計", "0", INFO)
        self.ok_card = self._create_summary_card("OK", "0", SUCCESS)
        self.ng_card = self._create_summary_card("NG", "0", ERROR)
        self.pending_card = self._create_summary_card("未実施", "0", NEUTRAL)

        for card in (self.total_card, self.ok_card, self.ng_card, self.pending_card):
            stats_cards_layout.addWidget(card, 1)
        self.layout.addLayout(stats_cards_layout)

        # ---- 中段：全体グラフと達成率 ----
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(18)

        # 全体ドーナツチャートカード
        overall_card = QFrame()
        overall_card.setObjectName("DashboardCard")
        overall_layout = QVBoxLayout(overall_card)
        overall_layout.setContentsMargins(20, 16, 20, 16)
        overall_layout.setSpacing(8)

        chart_title = QLabel("全体の進捗")
        chart_title.setObjectName("CardTitle")
        overall_layout.addWidget(chart_title)

        self.overall_chart = PieChartWidget(size=240)
        self._apply_surface_color(self.overall_chart)
        overall_layout.addWidget(self.overall_chart, alignment=Qt.AlignCenter)

        legend_row, self.legend_labels = self._make_legend_row()
        overall_layout.addWidget(legend_row)

        middle_layout.addWidget(overall_card, 3)

        # 達成率カード
        rate_card = QFrame()
        rate_card.setObjectName("DashboardCard")
        rate_layout = QVBoxLayout(rate_card)
        rate_layout.setContentsMargins(20, 16, 20, 16)
        rate_layout.setSpacing(8)

        rate_title = QLabel("達成率")
        rate_title.setObjectName("CardTitle")
        rate_layout.addWidget(rate_title)

        rate_layout.addStretch()
        self.rate_value = QLabel("0%")
        self.rate_value.setObjectName("RateValue")
        rate_layout.addWidget(self.rate_value)
        rate_layout.addSpacing(10)

        self.rate_bar = QProgressBar()
        self.rate_bar.setObjectName("DashboardProgress")
        self.rate_bar.setTextVisible(False)
        self.rate_bar.setRange(0, 100)
        self.rate_bar.setFixedHeight(6)
        rate_layout.addWidget(self.rate_bar)
        rate_layout.addSpacing(6)

        rate_caption = QLabel("OK / 全項目（期待結果単位）")
        rate_caption.setObjectName("DashboardMeta")
        rate_layout.addWidget(rate_caption)

        middle_layout.addWidget(rate_card, 1)
        self.layout.addLayout(middle_layout)

        # ---- シート別進捗 ----
        sheet_header = QLabel("シート別進捗")
        sheet_header.setObjectName("SectionTitle")
        self.layout.addWidget(sheet_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self.sheet_container = QWidget()
        self.sheet_container.setStyleSheet("background: transparent;")
        self.sheet_grid = QGridLayout(self.sheet_container)
        self.sheet_grid.setSpacing(16)

        scroll.setWidget(self.sheet_container)
        self.layout.addWidget(scroll)

    def _apply_surface_color(self, chart):
        """テーマに応じてチャートの穴（背景）色をカード表面色に合わせる"""
        theme = getattr(self.main_window, "current_theme", "dark")
        chart.bg_override = styles.LIGHT_SURFACE if theme == "light" else styles.DARK_SURFACE

    def _create_summary_card(self, title, value, color):
        """左端にアクセントバーを置いたサマリーカード"""
        card = QFrame()
        card.setObjectName("DashboardCard")
        card.setMinimumHeight(92)

        row = QHBoxLayout(card)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(14)

        accent = QFrame()
        accent.setFixedSize(4, 44)
        accent.setStyleSheet(f"background-color: {color}; border-radius: 2px;")

        col = QVBoxLayout()
        col.setSpacing(2)

        t = QLabel(title)
        t.setObjectName("StatLabel")

        v = QLabel(value)
        v.setObjectName("StatValue")
        v.setStyleSheet(f"color: {color};")

        col.addWidget(t)
        col.addWidget(v)

        row.addWidget(accent)
        row.addLayout(col)
        row.addStretch()

        # 値を後で更新できるようにQLabelを保持
        card.value_label = v
        return card

    def _make_legend_row(self, stats=None):
        """色ドット + ラベル + 件数の凡例行。count_labelsで後から件数を更新可能"""
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(18)

        count_labels = {}
        for key in STATUS_ORDER:
            dot = QFrame()
            dot.setFixedSize(9, 9)
            dot.setStyleSheet(f"background-color: {STATUS_COLORS[key]}; border-radius: 4px;")

            name = QLabel(key)
            name.setObjectName("LegendText")

            count = QLabel(str(stats[key]) if stats else "0")
            count.setObjectName("LegendValue")

            row.addWidget(dot, 0, Qt.AlignVCenter)
            row.addWidget(name)
            row.addWidget(count)
            count_labels[key] = count

        row.addStretch()
        return holder, count_labels

    def refresh(self):
        """期待結果単位で統計データを再計算"""
        total_stats = {"OK": 0, "NG": 0, "未実施": 0}
        sheet_stats = []

        for sheet_name, view in self.main_window.sheet_views.items():
            stats = {"OK": 0, "NG": 0, "未実施": 0}
            data = view.get_all_data()
            for item in data:
                expected_results = item.get("expected_results", [])
                if not expected_results:
                    # 期待結果がない場合も1件としてカウント（旧データや初期状態対応）
                    res = item.get("result", "未実施")
                    stats[res] += 1
                    total_stats[res] += 1
                    continue

                for r in expected_results:
                    res = r.get("result", "未実施")
                    if res in stats:
                        stats[res] += 1
                        total_stats[res] += 1
                    else:
                        stats["未実施"] += 1
                        total_stats["未実施"] += 1

            sheet_stats.append((sheet_name, stats))

        # 全体表示の更新
        self._apply_surface_color(self.overall_chart)
        self.overall_chart.set_data(total_stats)
        self.total_card.value_label.setText(str(sum(total_stats.values())))
        self.ok_card.value_label.setText(str(total_stats["OK"]))
        self.ng_card.value_label.setText(str(total_stats["NG"]))
        self.pending_card.value_label.setText(str(total_stats["未実施"]))

        for key, label in self.legend_labels.items():
            label.setText(str(total_stats[key]))

        # 達成率
        total = sum(total_stats.values())
        pct = int((total_stats["OK"] / total) * 100) if total > 0 else 0
        self.rate_value.setText(f"{pct}%")
        self.rate_bar.setValue(pct)

        self.last_update_label.setText(f"Last update: {datetime.now().strftime('%H:%M:%S')}")

        # シート別表示のクリア
        for i in reversed(range(self.sheet_grid.count())):
            self.sheet_grid.itemAt(i).widget().setParent(None)

        # シート別表示の追加
        cols = 3  # 1行に表示するカード数
        for i, (name, stats) in enumerate(sheet_stats):
            card = QFrame()
            card.setObjectName("DashboardCard")
            card.setMinimumHeight(180)

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 14)
            card_layout.setSpacing(4)

            name_label = QLabel(name)
            name_label.setObjectName("CardTitle")
            card_layout.addWidget(name_label)

            chart = PieChartWidget(size=110)
            self._apply_surface_color(chart)
            chart.set_data(stats)
            card_layout.addWidget(chart, alignment=Qt.AlignCenter)

            legend_row, _ = self._make_legend_row(stats)
            card_layout.addWidget(legend_row)

            self.sheet_grid.addWidget(card, i // cols, i % cols)