"""
Widget de comparação de voltas para o Race Telemetry Analyzer.
Permite comparar duas voltas e identificar diferenças de desempenho.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QSplitter, QFrame, QGroupBox, QGridLayout,
    QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView
)
from PyQt6.QtGui import QIcon, QFont, QColor, QPalette, QPainter, QPen
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QSize, QRectF
from typing import Dict, List, Any, Optional

import numpy as np
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from .track_view import TrackViewWidget
from .telemetry_widget import TelemetryChart


class LapSelector(QWidget):
    """Widget para seleção de voltas."""
    
    lap_selected = pyqtSignal(dict)
    
    def __init__(self, title: str, parent=None):
        """
        Inicializa o seletor de voltas.
        
        Args:
            title: Título do seletor
            parent: Widget pai
        """
        super().__init__(parent)
        
        # Layout
        layout = QVBoxLayout(self)
        
        # Título
        title_label = QLabel(title)
        title_label.setObjectName("section-title")
        layout.addWidget(title_label)
        
        # Seleção de sessão
        session_layout = QHBoxLayout()
        session_layout.addWidget(QLabel("Sessão:"))
        
        self.session_combo = QComboBox()
        self.session_combo.setMinimumWidth(200)
        session_layout.addWidget(self.session_combo)
        session_layout.addStretch()
        
        layout.addLayout(session_layout)
        
        # Seleção de volta
        lap_layout = QHBoxLayout()
        lap_layout.addWidget(QLabel("Volta:"))
        
        self.lap_combo = QComboBox()
        self.lap_combo.setMinimumWidth(200)
        lap_layout.addWidget(self.lap_combo)
        lap_layout.addStretch()
        
        layout.addLayout(lap_layout)
        
        # Conecta sinais
        self.session_combo.currentIndexChanged.connect(self._on_session_selected)
        self.lap_combo.currentIndexChanged.connect(self._on_lap_selected)
        
        # Dados
        self.sessions = []
        self.current_session = None
        self.laps = []
    
    def set_sessions(self, sessions: List[Dict[str, Any]]):
        """
        Define a lista de sessões disponíveis.
        
        Args:
            sessions: Lista de dicionários com dados das sessões
        """
        self.sessions = sessions
        
        # Atualiza o combo box
        self.session_combo.clear()
        
        for session in sessions:
            session_name = f"{session.get('track', 'Desconhecido')} - {session.get('car', 'Desconhecido')}"
            self.session_combo.addItem(session_name, session.get('id', ''))
        
        # Seleciona a primeira sessão
        if self.session_combo.count() > 0:
            self.session_combo.setCurrentIndex(0)
    
    def set_laps(self, laps: List[Dict[str, Any]]):
        """
        Define a lista de voltas disponíveis.
        
        Args:
            laps: Lista de dicionários com dados das voltas
        """
        self.laps = laps
        
        # Atualiza o combo box
        self.lap_combo.clear()
        
        for lap in laps:
            lap_num = lap.get("lap_number", 0)
            lap_time = lap.get("lap_time", 0)
            
            minutes = int(lap_time // 60)
            seconds = int(lap_time % 60)
            milliseconds = int((lap_time % 1) * 1000)
            
            lap_text = f"Volta {lap_num} - {minutes:02d}:{seconds:02d}.{milliseconds:03d}"
            self.lap_combo.addItem(lap_text, lap_num)
        
        # Seleciona a melhor volta
        best_lap_idx = 0
        best_time = float('inf')
        
        for i, lap in enumerate(laps):
            if lap.get("lap_time", float('inf')) < best_time:
                best_time = lap.get("lap_time", float('inf'))
                best_lap_idx = i
        
        if self.lap_combo.count() > 0:
            self.lap_combo.setCurrentIndex(best_lap_idx)
    
    def get_selected_lap(self) -> Optional[Dict[str, Any]]:
        """
        Retorna a volta selecionada.
        
        Returns:
            Dicionário com dados da volta ou None se nenhuma volta estiver selecionada
        """
        current_index = self.lap_combo.currentIndex()
        if current_index >= 0 and current_index < len(self.laps):
            return self.laps[current_index]
        return None
    
    def _on_session_selected(self, index: int):
        """
        Manipula a seleção de uma sessão no combo box.
        
        Args:
            index: Índice da sessão selecionada
        """
        if index >= 0 and index < len(self.sessions):
            self.current_session = self.sessions[index]
            # Aqui carregaríamos as voltas da sessão selecionada
            # Por enquanto, vamos apenas limpar o combo de voltas
            self.lap_combo.clear()
    
    def _on_lap_selected(self, index: int):
        """
        Manipula a seleção de uma volta no combo box.
        
        Args:
            index: Índice da volta selecionada
        """
        if index >= 0 and index < len(self.laps):
            self.lap_selected.emit(self.laps[index])


class ComparisonResultsPanel(QFrame):
    """Painel para exibir resultados da comparação entre voltas."""
    
    def __init__(self, parent=None):
        """
        Inicializa o painel de resultados de comparação.
        
        Args:
            parent: Widget pai
        """
        super().__init__(parent)
        
        # Configuração do frame
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        
        # Layout
        layout = QVBoxLayout(self)
        
        # Título
        title = QLabel("Resultados da Comparação")
        title.setObjectName("section-title")
        layout.addWidget(title)
        
        # Diferença de tempo
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Diferença de Tempo:"))
        
        self.time_diff_label = QLabel("0.000s")
        self.time_diff_label.setObjectName("metric-value")
        time_layout.addWidget(self.time_diff_label)
        time_layout.addStretch()
        
        layout.addLayout(time_layout)
        
        # Tabela de setores
        layout.addWidget(QLabel("Setores:"))
        
        self.sectors_table = QTableWidget()
        self.sectors_table.setColumnCount(4)
        self.sectors_table.setHorizontalHeaderLabels(["Setor", "Referência", "Comparação", "Diferença"])
        
        # Ajusta o comportamento da tabela
        self.sectors_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.sectors_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sectors_table.setAlternatingRowColors(True)
        
        # Ajusta o tamanho das colunas
        header = self.sectors_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.sectors_table)
        
        # Tabela de pontos de melhoria
        layout.addWidget(QLabel("Pontos de Melhoria:"))
        
        self.improvements_table = QTableWidget()
        self.improvements_table.setColumnCount(4)
        self.improvements_table.setHorizontalHeaderLabels(["Tipo", "Severidade", "Posição", "Sugestão"])
        
        # Ajusta o comportamento da tabela
        self.improvements_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.improvements_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.improvements_table.setAlternatingRowColors(True)
        
        # Ajusta o tamanho das colunas
        header = self.improvements_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.improvements_table)
    
    def update_comparison_results(self, comparison_results: Dict[str, Any]):
        """
        Atualiza os resultados da comparação.
        
        Args:
            comparison_results: Dicionário com resultados da comparação
        """
        if not comparison_results:
            return
        
        # Diferença de tempo
        time_delta = comparison_results.get("time_delta", 0)
        sign = "+" if time_delta > 0 else ""
        self.time_diff_label.setText(f"{sign}{time_delta:.3f}s")
        
        # Cor da diferença de tempo
        if time_delta > 0:
            self.time_diff_label.setStyleSheet("color: red;")
        elif time_delta < 0:
            self.time_diff_label.setStyleSheet("color: green;")
        else:
            self.time_diff_label.setStyleSheet("")
        
        # Setores
        sectors = comparison_results.get("sectors", [])
        
        # Limpa a tabela
        self.sectors_table.setRowCount(0)
        
        for sector in sectors:
            row = self.sectors_table.rowCount()
            self.sectors_table.insertRow(row)
            
            # Setor
            self.sectors_table.setItem(row, 0, QTableWidgetItem(f"Setor {sector.get('sector', row+1)}"))
            
            # Referência
            ref_time = sector.get("ref_time", 0)
            self.sectors_table.setItem(row, 1, QTableWidgetItem(self._format_time(ref_time)))
            
            # Comparação
            comp_time = sector.get("comp_time", 0)
            self.sectors_table.setItem(row, 2, QTableWidgetItem(self._format_time(comp_time)))
            
            # Diferença
            delta = sector.get("delta", 0)
            sign = "+" if delta > 0 else ""
            delta_item = QTableWidgetItem(f"{sign}{delta:.3f}s")
            
            if delta > 0:
                delta_item.setForeground(QColor(255, 0, 0))  # Vermelho
            elif delta < 0:
                delta_item.setForeground(QColor(0, 255, 0))  # Verde
            
            self.sectors_table.setItem(row, 3, delta_item)
        
        # Pontos de melhoria
        improvements = comparison_results.get("improvement_suggestions", [])
        
        # Limpa a tabela
        self.improvements_table.setRowCount(0)
        
        for improvement in improvements:
            row = self.improvements_table.rowCount()
            self.improvements_table.insertRow(row)
            
            # Tipo
            type_text = {
                "braking": "Frenagem",
                "apex": "Ápice",
                "acceleration": "Aceleração",
                "line": "Trajetória",
                "speed": "Velocidade",
                "loss": "Perda de Tempo",
                "inconsistent_line": "Linha Inconsistente"
            }.get(improvement.get("type", ""), improvement.get("type", ""))
            
            self.improvements_table.setItem(row, 0, QTableWidgetItem(type_text))
            
            # Severidade
            severity_text = {
                "low": "Baixa",
                "medium": "Média",
                "high": "Alta"
            }.get(improvement.get("severity", ""), improvement.get("severity", ""))
            
            severity_item = QTableWidgetItem(severity_text)
            
            if improvement.get("severity") == "high":
                severity_item.setForeground(QColor(255, 0, 0))  # Vermelho
            elif improvement.get("severity") == "medium":
                severity_item.setForeground(QColor(255, 165, 0))  # Laranja
            
            self.improvements_table.setItem(row, 1, severity_item)
            
            # Posição
            position = improvement.get("position", [0, 0])
            pos_text = f"({position[0]:.1f}, {position[1]:.1f})"
            self.improvements_table.setItem(row, 2, QTableWidgetItem(pos_text))
            
            # Sugestão
            self.improvements_table.setItem(row, 3, QTableWidgetItem(improvement.get("suggestion", "")))
    
    def _format_time(self, time_seconds: float) -> str:
        """
        Formata um tempo em segundos para o formato MM:SS.mmm.
        
        Args:
            time_seconds: Tempo em segundos
            
        Returns:
            String formatada
        """
        if time_seconds <= 0:
            return "00:00.000"
        
        minutes = int(time_seconds // 60)
        seconds = int(time_seconds % 60)
        milliseconds = int((time_seconds % 1) * 1000)
        
        return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


class ComparisonWidget(QWidget):
    """Widget principal de comparação de voltas."""
    
    def __init__(self, parent=None):
        """
        Inicializa o widget de comparação.
        
        Args:
            parent: Widget pai
        """
        super().__init__(parent)
        
        # Layout principal
        layout = QVBoxLayout(self)
        
        # Seletores de voltas
        selectors_layout = QHBoxLayout()
        
        self.reference_selector = LapSelector("Volta de Referência")
        self.comparison_selector = LapSelector("Volta de Comparação")
        
        selectors_layout.addWidget(self.reference_selector)
        selectors_layout.addWidget(self.comparison_selector)
        
        layout.addLayout(selectors_layout)
        
        # Botão de comparação
        compare_layout = QHBoxLayout()
        compare_layout.addStretch()
        
        self.compare_button = QPushButton("Comparar Voltas")
        self.compare_button.setMinimumWidth(200)
        compare_layout.addWidget(self.compare_button)
        
        compare_layout.addStretch()
        
        layout.addLayout(compare_layout)
        
        # Splitter principal
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Painel esquerdo: Visualização da pista
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Visualização da pista
        self.track_view = TrackViewWidget()
        left_layout.addWidget(self.track_view)
        
        # Painel direito: Resultados da comparação e gráficos
        right_panel = QSplitter(Qt.Orientation.Vertical)
        
        # Resultados da comparação
        self.results_panel = ComparisonResultsPanel()
        
        # Gráficos de comparação
        charts_widget = QTabWidget()
        
        # Tab de delta de tempo
        delta_tab = QWidget()
        delta_layout = QVBoxLayout(delta_tab)
        self.delta_chart = TelemetryChart()
        delta_layout.addWidget(self.delta_chart)
        charts_widget.addTab(delta_tab, "Delta de Tempo")
        
        # Tab de velocidade
        speed_tab = QWidget()
        speed_layout = QVBoxLayout(speed_tab)
        self.speed_chart = TelemetryChart()
        speed_layout.addWidget(self.speed_chart)
        charts_widget.addTab(speed_tab, "Velocidade")
        
        # Tab de pedais
        pedals_tab = QWidget()
        pedals_layout = QVBoxLayout(pedals_tab)
        self.pedals_chart = TelemetryChart()
        pedals_layout.addWidget(self.pedals_chart)
        charts_widget.addTab(pedals_tab, "Pedais")
        
        # Adiciona widgets ao splitter direito
        right_panel.addWidget(self.results_panel)
        right_panel.addWidget(charts_widget)
        
        # Define proporções iniciais do splitter direito
        right_panel.setSizes([300, 400])
        
        # Adiciona painéis ao splitter principal
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        
        # Define proporções iniciais do splitter principal
        main_splitter.setSizes([400, 600])
        
        layout.addWidget(main_splitter)
        
        # Conecta sinais
        self.compare_button.clicked.connect(self._compare_laps)
        self.reference_selector.lap_selected.connect(self._on_reference_lap_selected)
        self.comparison_selector.lap_selected.connect(self._on_comparison_lap_selected)
        
        # Estado
        self.reference_lap = None
        self.comparison_lap = None
        self.comparison_results = None
    
    def add_reference_lap(self, telemetry_data: Dict[str, Any]):
        """
        Adiciona uma volta de referência.
        
        Args:
            telemetry_data: Dicionário com dados de telemetria
        """
        # Extrai as voltas
        laps = telemetry_data.get("laps", [])
        
        # Atualiza o seletor de voltas
        self.reference_selector.set_laps(laps)
        
        # Atualiza o traçado da pista
        track_points = []
        for lap in laps:
            for point in lap.get("data_points", []):
                if "position" in point:
                    track_points.append(point["position"])
        
        if track_points:
            self.track_view.set_track_points(track_points)
    
    def add_comparison_lap(self, telemetry_data: Dict[str, Any]):
        """
        Adiciona uma volta de comparação.
        
        Args:
            telemetry_data: Dicionário com dados de telemetria
        """
        # Extrai as voltas
        laps = telemetry_data.get("laps", [])
        
        # Atualiza o seletor de voltas
        self.comparison_selector.set_laps(laps)
    
    @pyqtSlot()
    def refresh_data(self):
        """Atualiza todos os dados do widget."""
        # Recarrega as voltas selecionadas
        reference_lap = self.reference_selector.get_selected_lap()
        comparison_lap = self.comparison_selector.get_selected_lap()
        
        if reference_lap and comparison_lap:
            self._compare_laps()
    
    def _on_reference_lap_selected(self, lap_data: Dict[str, Any]):
        """
        Manipula a seleção de uma volta de referência.
        
        Args:
            lap_data: Dicionário com dados da volta
        """
        self.reference_lap = lap_data
        
        # Atualiza o traçado da volta
        lap_points = []
        for point in lap_data.get("data_points", []):
            if "position" in point:
                lap_points.append(point["position"])
        
        if lap_points:
            self.track_view.set_lap_points(lap_points)
    
    def _on_comparison_lap_selected(self, lap_data: Dict[str, Any]):
        """
        Manipula a seleção de uma volta de comparação.
        
        Args:
            lap_data: Dicionário com dados da volta
        """
        self.comparison_lap = lap_data
    
    def _compare_laps(self):
        """Compara as voltas selecionadas."""
        if not self.reference_lap or not self.comparison_lap:
            return
        
        # Aqui usaríamos o comparador de telemetria para obter os resultados
        # Por enquanto, vamos simular alguns resultados
        
        # Diferença de tempo
        time_delta = self.comparison_lap.get("lap_time", 0) - self.reference_lap.get("lap_time", 0)
        
        # Setores
        sectors = []
        ref_sectors = self.reference_lap.get("sectors", [])
        comp_sectors = self.comparison_lap.get("sectors", [])
        
        for i in range(min(len(ref_sectors), len(comp_sectors))):
            ref_sector = ref_sectors[i]
            comp_sector = comp_sectors[i]
            
            delta = comp_sector.get("time", 0) - ref_sector.get("time", 0)
            
            sectors.append({
                "sector": i + 1,
                "ref_time": ref_sector.get("time", 0),
                "comp_time": comp_sector.get("time", 0),
                "delta": delta,
                "percentage": (delta / ref_sector.get("time", 1)) * 100
            })
        
        # Pontos de melhoria
        improvements = []
        
        # Simula alguns pontos de melhoria
        # Na implementação real, estes viriam do comparador de telemetria
        
        # Frenagem tardia
        improvements.append({
            "type": "braking",
            "severity": "high",
            "position": [100, 200],
            "suggestion": "Frear mais cedo para manter mais velocidade na entrada da curva"
        })
        
        # Ápice lento
        improvements.append({
            "type": "apex",
            "severity": "medium",
            "position": [150, 250],
            "suggestion": "Ajustar trajetória para manter mais velocidade no ápice da curva"
        })
        
        # Aceleração tardia
        improvements.append({
            "type": "acceleration",
            "severity": "low",
            "position": [200, 300],
            "suggestion": "Antecipar a aceleração na saída da curva"
        })
        
        # Monta o resultado da comparação
        self.comparison_results = {
            "reference_lap": self.reference_lap.get("lap_number", 0),
            "comparison_lap": self.comparison_lap.get("lap_number", 0),
            "time_delta": time_delta,
            "sectors": sectors,
            "improvement_suggestions": improvements
        }
        
        # Atualiza a interface
        self._update_comparison_ui()
    
    def _update_comparison_ui(self):
        """Atualiza a interface com os resultados da comparação."""
        if not self.comparison_results:
            return
        
        # Atualiza o painel de resultados
        self.results_panel.update_comparison_results(self.comparison_results)
        
        # Atualiza os gráficos
        self._update_charts()
        
        # Atualiza o traçado
        self._update_track_view()
    
    def _update_charts(self):
        """Atualiza os gráficos com os dados da comparação."""
        if not self.reference_lap or not self.comparison_lap:
            return
        
        # Gráfico de delta de tempo
        # Na implementação real, estes dados viriam do comparador de telemetria
        # Por enquanto, vamos simular um delta
        
        ref_points = self.reference_lap.get("data_points", [])
        comp_points = self.comparison_lap.get("data_points", [])
        
        if ref_points and comp_points:
            # Simula um delta de tempo
            distances = [p.get("distance", 0) for p in ref_points]
            delta_times = np.random.normal(0, 0.1, len(distances))  # Simula um delta aleatório
            delta_times = np.cumsum(delta_times)  # Acumula para simular tendência
            
            # Plota o delta
            self.delta_chart.plot_data(distances, delta_times, "Delta de Tempo", "blue")
            self.delta_chart.set_labels("Distância (m)", "Delta (s)", "Delta de Tempo")
            
            # Adiciona linha de referência (zero)
            self.delta_chart.axes.axhline(y=0, color='r', linestyle='-', alpha=0.3)
            self.delta_chart.draw()
        
        # Gráfico de velocidade
        if ref_points and comp_points:
            # Extrai dados para os gráficos
            ref_distances = [p.get("distance", 0) for p in ref_points]
            ref_speeds = [p.get("speed", 0) for p in ref_points]
            
            comp_distances = [p.get("distance", 0) for p in comp_points]
            comp_speeds = [p.get("speed", 0) for p in comp_points]
            
            # Plota as velocidades
            self.speed_chart.plot_data(ref_distances, ref_speeds, "Referência", "blue")
            self.speed_chart.add_series(comp_distances, comp_speeds, "Comparação", "red")
            self.speed_chart.set_labels("Distância (m)", "Velocidade (km/h)", "Comparação de Velocidade")
        
        # Gráfico de pedais
        if ref_points and comp_points:
            # Extrai dados para os gráficos
            ref_distances = [p.get("distance", 0) for p in ref_points]
            ref_throttles = [p.get("throttle", 0) * 100 for p in ref_points if "throttle" in p]  # Converte para porcentagem
            ref_brakes = [p.get("brake", 0) * 100 for p in ref_points if "brake" in p]  # Converte para porcentagem
            
            comp_distances = [p.get("distance", 0) for p in comp_points]
            comp_throttles = [p.get("throttle", 0) * 100 for p in comp_points if "throttle" in p]
            comp_brakes = [p.get("brake", 0) * 100 for p in comp_points if "brake" in p]
            
            # Garante que os arrays tenham o mesmo tamanho
            min_len = min(len(ref_distances), len(ref_throttles), len(ref_brakes))
            ref_distances = ref_distances[:min_len]
            ref_throttles = ref_throttles[:min_len]
            ref_brakes = ref_brakes[:min_len]
            
            min_len = min(len(comp_distances), len(comp_throttles), len(comp_brakes))
            comp_distances = comp_distances[:min_len]
            comp_throttles = comp_throttles[:min_len]
            comp_brakes = comp_brakes[:min_len]
            
            # Plota os pedais
            self.pedals_chart.plot_data(ref_distances, ref_throttles, "Acelerador (Ref)", "green")
            self.pedals_chart.add_series(ref_distances, ref_brakes, "Freio (Ref)", "red")
            self.pedals_chart.add_series(comp_distances, comp_throttles, "Acelerador (Comp)", "lightgreen")
            self.pedals_chart.add_series(comp_distances, comp_brakes, "Freio (Comp)", "pink")
            self.pedals_chart.set_labels("Distância (m)", "Porcentagem (%)", "Comparação de Pedais")
    
    def _update_track_view(self):
        """Atualiza a visualização do traçado com os dados da comparação."""
        if not self.reference_lap or not self.comparison_lap:
            return
        
        # Extrai os pontos das voltas
        ref_points = []
        for point in self.reference_lap.get("data_points", []):
            if "position" in point:
                ref_points.append(point["position"])
        
        comp_points = []
        for point in self.comparison_lap.get("data_points", []):
            if "position" in point:
                comp_points.append(point["position"])
        
        # Atualiza o traçado
        if ref_points:
            self.track_view.set_lap_points(ref_points)
        
        # Destaca pontos de melhoria
        if self.comparison_results and "improvement_suggestions" in self.comparison_results:
            for suggestion in self.comparison_results["improvement_suggestions"]:
                if "position" in suggestion:
                    self.track_view.highlight_point(suggestion["position"])
