"""
Widget de visualização de telemetria para o Race Telemetry Analyzer.
Exibe gráficos detalhados e análise de telemetria.
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


class TelemetryChart(FigureCanvas):
    """Widget para exibir gráficos de telemetria."""
    
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        """
        Inicializa o widget de gráfico.
        
        Args:
            parent: Widget pai
            width: Largura da figura em polegadas
            height: Altura da figura em polegadas
            dpi: Resolução da figura
        """
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        
        super().__init__(self.fig)
        self.setParent(parent)
        
        # Configuração do gráfico
        self.fig.tight_layout()
        self.fig.patch.set_alpha(0.0)
        self.axes.patch.set_alpha(0.0)
        
        # Dados
        self.x_data = []
        self.y_data = []
        self.line = None
    
    def plot_data(self, x_data: List[float], y_data: List[float], 
                 label: str = "", color: str = "blue", clear: bool = True):
        """
        Plota dados no gráfico.
        
        Args:
            x_data: Dados do eixo X
            y_data: Dados do eixo Y
            label: Rótulo da série
            color: Cor da linha
            clear: Se True, limpa o gráfico antes de plotar
        """
        if clear:
            self.axes.clear()
        
        self.x_data = x_data
        self.y_data = y_data
        
        self.line, = self.axes.plot(x_data, y_data, color=color, label=label)
        
        if label:
            self.axes.legend()
        
        self.axes.grid(True, linestyle='--', alpha=0.7)
        self.draw()
    
    def add_series(self, x_data: List[float], y_data: List[float], 
                  label: str = "", color: str = "red"):
        """
        Adiciona uma série de dados ao gráfico existente.
        
        Args:
            x_data: Dados do eixo X
            y_data: Dados do eixo Y
            label: Rótulo da série
            color: Cor da linha
        """
        self.plot_data(x_data, y_data, label, color, clear=False)
    
    def set_labels(self, x_label: str, y_label: str, title: str = ""):
        """
        Define os rótulos dos eixos e o título do gráfico.
        
        Args:
            x_label: Rótulo do eixo X
            y_label: Rótulo do eixo Y
            title: Título do gráfico
        """
        self.axes.set_xlabel(x_label)
        self.axes.set_ylabel(y_label)
        if title:
            self.axes.set_title(title)
        self.draw()
    
    def clear(self):
        """Limpa o gráfico."""
        self.axes.clear()
        self.x_data = []
        self.y_data = []
        self.line = None
        self.draw()


class LapInfoPanel(QFrame):
    """Painel para exibir informações detalhadas de uma volta."""
    
    def __init__(self, parent=None):
        """
        Inicializa o painel de informações de volta.
        
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
        title = QLabel("Informações da Volta")
        title.setObjectName("section-title")
        layout.addWidget(title)
        
        # Grid de métricas
        metrics_grid = QGridLayout()
        
        # Tempo da volta
        self.lap_time_label = QLabel("00:00.000")
        self.lap_time_label.setObjectName("metric-value")
        metrics_grid.addWidget(QLabel("Tempo:"), 0, 0)
        metrics_grid.addWidget(self.lap_time_label, 0, 1)
        
        # Setores
        self.sector1_label = QLabel("00:00.000")
        self.sector1_label.setObjectName("metric-value")
        metrics_grid.addWidget(QLabel("Setor 1:"), 1, 0)
        metrics_grid.addWidget(self.sector1_label, 1, 1)
        
        self.sector2_label = QLabel("00:00.000")
        self.sector2_label.setObjectName("metric-value")
        metrics_grid.addWidget(QLabel("Setor 2:"), 2, 0)
        metrics_grid.addWidget(self.sector2_label, 2, 1)
        
        self.sector3_label = QLabel("00:00.000")
        self.sector3_label.setObjectName("metric-value")
        metrics_grid.addWidget(QLabel("Setor 3:"), 3, 0)
        metrics_grid.addWidget(self.sector3_label, 3, 1)
        
        # Velocidade máxima
        self.max_speed_label = QLabel("0 km/h")
        self.max_speed_label.setObjectName("metric-value")
        metrics_grid.addWidget(QLabel("Vel. Máxima:"), 4, 0)
        metrics_grid.addWidget(self.max_speed_label, 4, 1)
        
        # Velocidade média
        self.avg_speed_label = QLabel("0 km/h")
        self.avg_speed_label.setObjectName("metric-value")
        metrics_grid.addWidget(QLabel("Vel. Média:"), 5, 0)
        metrics_grid.addWidget(self.avg_speed_label, 5, 1)
        
        # RPM máximo
        self.max_rpm_label = QLabel("0")
        self.max_rpm_label.setObjectName("metric-value")
        metrics_grid.addWidget(QLabel("RPM Máximo:"), 6, 0)
        metrics_grid.addWidget(self.max_rpm_label, 6, 1)
        
        layout.addLayout(metrics_grid)
        layout.addStretch()
    
    def update_lap_info(self, lap_data: Dict[str, Any]):
        """
        Atualiza as informações da volta.
        
        Args:
            lap_data: Dicionário com dados da volta
        """
        if not lap_data:
            return
        
        # Tempo da volta
        lap_time = lap_data.get("lap_time", 0)
        self.lap_time_label.setText(self._format_time(lap_time))
        
        # Setores
        sectors = lap_data.get("sectors", [])
        if len(sectors) >= 1:
            self.sector1_label.setText(self._format_time(sectors[0].get("time", 0)))
        if len(sectors) >= 2:
            self.sector2_label.setText(self._format_time(sectors[1].get("time", 0)))
        if len(sectors) >= 3:
            self.sector3_label.setText(self._format_time(sectors[2].get("time", 0)))
        
        # Velocidade máxima e média
        data_points = lap_data.get("data_points", [])
        if data_points:
            speeds = [p.get("speed", 0) for p in data_points]
            max_speed = max(speeds) if speeds else 0
            avg_speed = sum(speeds) / len(speeds) if speeds else 0
            
            self.max_speed_label.setText(f"{max_speed:.1f} km/h")
            self.avg_speed_label.setText(f"{avg_speed:.1f} km/h")
        
        # RPM máximo
        rpms = [p.get("rpm", 0) for p in data_points if "rpm" in p]
        max_rpm = max(rpms) if rpms else 0
        self.max_rpm_label.setText(f"{max_rpm:.0f}")
    
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


class LapSelector(QWidget):
    """Widget para seleção de voltas."""
    
    lap_selected = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        """
        Inicializa o seletor de voltas.
        
        Args:
            parent: Widget pai
        """
        super().__init__(parent)
        
        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Label
        label = QLabel("Volta:")
        layout.addWidget(label)
        
        # Combo box
        self.lap_combo = QComboBox()
        self.lap_combo.setMinimumWidth(150)
        layout.addWidget(self.lap_combo)
        
        # Botões de navegação
        self.prev_button = QPushButton("Anterior")
        self.next_button = QPushButton("Próxima")
        
        layout.addWidget(self.prev_button)
        layout.addWidget(self.next_button)
        
        layout.addStretch()
        
        # Conecta sinais
        self.lap_combo.currentIndexChanged.connect(self._on_lap_selected)
        self.prev_button.clicked.connect(self._on_prev_clicked)
        self.next_button.clicked.connect(self._on_next_clicked)
        
        # Dados
        self.laps = []
    
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
    
    def _on_lap_selected(self, index: int):
        """
        Manipula a seleção de uma volta no combo box.
        
        Args:
            index: Índice da volta selecionada
        """
        if index >= 0 and index < len(self.laps):
            self.lap_selected.emit(self.laps[index])
    
    def _on_prev_clicked(self):
        """Manipula o clique no botão 'Anterior'."""
        current_index = self.lap_combo.currentIndex()
        if current_index > 0:
            self.lap_combo.setCurrentIndex(current_index - 1)
    
    def _on_next_clicked(self):
        """Manipula o clique no botão 'Próxima'."""
        current_index = self.lap_combo.currentIndex()
        if current_index < self.lap_combo.count() - 1:
            self.lap_combo.setCurrentIndex(current_index + 1)


class TelemetryWidget(QWidget):
    """Widget principal de visualização de telemetria."""
    
    def __init__(self, parent=None):
        """
        Inicializa o widget de telemetria.
        
        Args:
            parent: Widget pai
        """
        super().__init__(parent)
        
        # Layout principal
        layout = QVBoxLayout(self)
        
        # Seletor de voltas
        self.lap_selector = LapSelector()
        layout.addWidget(self.lap_selector)
        
        # Splitter principal
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Painel esquerdo: Visualização da pista e informações da volta
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Visualização da pista
        self.track_view = TrackViewWidget()
        left_layout.addWidget(self.track_view, 2)  # 2 = stretch factor
        
        # Informações da volta
        self.lap_info_panel = LapInfoPanel()
        left_layout.addWidget(self.lap_info_panel, 1)  # 1 = stretch factor
        
        # Painel direito: Gráficos de telemetria
        right_panel = QTabWidget()
        
        # Tab de velocidade
        speed_tab = QWidget()
        speed_layout = QVBoxLayout(speed_tab)
        self.speed_chart = TelemetryChart()
        speed_layout.addWidget(self.speed_chart)
        right_panel.addTab(speed_tab, "Velocidade")
        
        # Tab de RPM
        rpm_tab = QWidget()
        rpm_layout = QVBoxLayout(rpm_tab)
        self.rpm_chart = TelemetryChart()
        rpm_layout.addWidget(self.rpm_chart)
        right_panel.addTab(rpm_tab, "RPM")
        
        # Tab de pedais
        pedals_tab = QWidget()
        pedals_layout = QVBoxLayout(pedals_tab)
        self.pedals_chart = TelemetryChart()
        pedals_layout.addWidget(self.pedals_chart)
        right_panel.addTab(pedals_tab, "Pedais")
        
        # Tab de análise
        analysis_tab = QWidget()
        analysis_layout = QVBoxLayout(analysis_tab)
        
        # Tabela de pontos-chave
        self.key_points_table = QTableWidget()
        self.key_points_table.setColumnCount(5)
        self.key_points_table.setHorizontalHeaderLabels(["Tipo", "Distância", "Tempo", "Velocidade", "Ação"])
        
        # Ajusta o comportamento da tabela
        self.key_points_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.key_points_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.key_points_table.setAlternatingRowColors(True)
        
        # Ajusta o tamanho das colunas
        header = self.key_points_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        
        analysis_layout.addWidget(QLabel("Pontos-Chave:"))
        analysis_layout.addWidget(self.key_points_table)
        
        # Tabela de erros detectados
        self.errors_table = QTableWidget()
        self.errors_table.setColumnCount(4)
        self.errors_table.setHorizontalHeaderLabels(["Tipo", "Severidade", "Posição", "Descrição"])
        
        # Ajusta o comportamento da tabela
        self.errors_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.errors_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.errors_table.setAlternatingRowColors(True)
        
        # Ajusta o tamanho das colunas
        header = self.errors_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        analysis_layout.addWidget(QLabel("Erros Detectados:"))
        analysis_layout.addWidget(self.errors_table)
        
        right_panel.addTab(analysis_tab, "Análise")
        
        # Adiciona painéis ao splitter
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        
        # Define proporções iniciais
        main_splitter.setSizes([400, 600])
        
        layout.addWidget(main_splitter)
        
        # Conecta sinais
        self.lap_selector.lap_selected.connect(self._on_lap_selected)
        
        # Estado
        self.current_telemetry = None
        self.current_lap = None
    
    def load_telemetry(self, telemetry_data: Dict[str, Any]):
        """
        Carrega dados de telemetria.
        
        Args:
            telemetry_data: Dicionário com dados de telemetria
        """
        self.current_telemetry = telemetry_data
        
        # Extrai as voltas
        laps = telemetry_data.get("laps", [])
        
        # Atualiza o seletor de voltas
        self.lap_selector.set_laps(laps)
        
        # Atualiza o traçado da pista
        track_points = []
        for lap in laps:
            for point in lap.get("data_points", []):
                if "position" in point:
                    track_points.append(point["position"])
        
        if track_points:
            self.track_view.set_track_points(track_points)
    
    def update_live_telemetry(self, telemetry_data: Dict[str, Any]):
        """
        Atualiza os dados de telemetria em tempo real.
        
        Args:
            telemetry_data: Dicionário com dados de telemetria
        """
        # Atualiza o traçado da pista
        if "current_position" in telemetry_data:
            self.track_view.update_current_position(telemetry_data["current_position"])
        
        # Atualiza os gráficos
        if "current_data" in telemetry_data:
            current_data = telemetry_data["current_data"]
            
            # Adiciona ponto ao gráfico de velocidade
            if "speed" in current_data and "time" in current_data:
                self.speed_chart.add_series([current_data["time"]], [current_data["speed"]], "", "blue")
            
            # Adiciona ponto ao gráfico de RPM
            if "rpm" in current_data and "time" in current_data:
                self.rpm_chart.add_series([current_data["time"]], [current_data["rpm"]], "", "red")
            
            # Adiciona ponto ao gráfico de pedais
            if ("throttle" in current_data or "brake" in current_data) and "time" in current_data:
                throttle = current_data.get("throttle", 0)
                brake = current_data.get("brake", 0)
                
                self.pedals_chart.add_series([current_data["time"]], [throttle * 100], "", "green")
                self.pedals_chart.add_series([current_data["time"]], [brake * 100], "", "red")
    
    def get_current_telemetry(self) -> Dict[str, Any]:
        """
        Retorna os dados de telemetria atuais.
        
        Returns:
            Dicionário com dados de telemetria
        """
        return self.current_telemetry or {}
    
    @pyqtSlot()
    def refresh_data(self):
        """Atualiza todos os dados do widget."""
        # Recarrega a volta selecionada
        selected_lap = self.lap_selector.get_selected_lap()
        if selected_lap:
            self._on_lap_selected(selected_lap)
    
    def _on_lap_selected(self, lap_data: Dict[str, Any]):
        """
        Manipula a seleção de uma volta.
        
        Args:
            lap_data: Dicionário com dados da volta
        """
        self.current_lap = lap_data
        
        # Atualiza as informações da volta
        self.lap_info_panel.update_lap_info(lap_data)
        
        # Atualiza o traçado da volta
        lap_points = []
        for point in lap_data.get("data_points", []):
            if "position" in point:
                lap_points.append(point["position"])
        
        if lap_points:
            self.track_view.set_lap_points(lap_points)
        
        # Atualiza os gráficos
        self._update_charts(lap_data)
        
        # Atualiza a análise
        self._update_analysis(lap_data)
    
    def _update_charts(self, lap_data: Dict[str, Any]):
        """
        Atualiza os gráficos com os dados da volta.
        
        Args:
            lap_data: Dicionário com dados da volta
        """
        data_points = lap_data.get("data_points", [])
        if not data_points:
            return
        
        # Extrai dados para os gráficos
        times = [p.get("time", 0) for p in data_points]
        distances = [p.get("distance", 0) for p in data_points]
        speeds = [p.get("speed", 0) for p in data_points]
        rpms = [p.get("rpm", 0) for p in data_points if "rpm" in p]
        throttles = [p.get("throttle", 0) * 100 for p in data_points if "throttle" in p]  # Converte para porcentagem
        brakes = [p.get("brake", 0) * 100 for p in data_points if "brake" in p]  # Converte para porcentagem
        
        # Gráfico de velocidade
        if times and speeds:
            self.speed_chart.plot_data(times, speeds, "Velocidade", "blue")
            self.speed_chart.set_labels("Tempo (s)", "Velocidade (km/h)", "Velocidade x Tempo")
        
        # Gráfico de RPM
        if times and rpms:
            self.rpm_chart.plot_data(times, rpms, "RPM", "red")
            self.rpm_chart.set_labels("Tempo (s)", "RPM", "RPM x Tempo")
        
        # Gráfico de pedais
        if times and (throttles or brakes):
            # Garante que os arrays tenham o mesmo tamanho
            min_len = min(len(times), len(throttles), len(brakes))
            times = times[:min_len]
            throttles = throttles[:min_len]
            brakes = brakes[:min_len]
            
            self.pedals_chart.plot_data(times, throttles, "Acelerador", "green")
            self.pedals_chart.add_series(times, brakes, "Freio", "red")
            self.pedals_chart.set_labels("Tempo (s)", "Porcentagem (%)", "Uso dos Pedais")
    
    def _update_analysis(self, lap_data: Dict[str, Any]):
        """
        Atualiza as tabelas de análise com os dados da volta.
        
        Args:
            lap_data: Dicionário com dados da volta
        """
        # Limpa as tabelas
        self.key_points_table.setRowCount(0)
        self.errors_table.setRowCount(0)
        
        # Pontos-chave
        key_points = {}
        
        # Pontos de frenagem
        braking_points = []
        for i, point in enumerate(lap_data.get("data_points", [])):
            if i > 0 and i < len(lap_data["data_points"]) - 1:
                prev_point = lap_data["data_points"][i-1]
                next_point = lap_data["data_points"][i+1]
                
                # Detecta início de frenagem forte
                if "brake" in point and "brake" in prev_point:
                    if point["brake"] > 0.5 and point["brake"] > prev_point["brake"]:
                        braking_points.append({
                            "type": "braking",
                            "distance": point.get("distance", 0),
                            "time": point.get("time", 0),
                            "speed": point.get("speed", 0),
                            "position": point.get("position", [0, 0])
                        })
        
        key_points["braking"] = braking_points
        
        # Pontos de ápice
        apex_points = []
        for i, point in enumerate(lap_data.get("data_points", [])):
            if i > 0 and i < len(lap_data["data_points"]) - 1:
                prev_point = lap_data["data_points"][i-1]
                next_point = lap_data["data_points"][i+1]
                
                # Detecta mínimo local de velocidade
                if point["speed"] < prev_point["speed"] and point["speed"] <= next_point["speed"]:
                    # Verifica se é uma redução significativa de velocidade
                    if prev_point["speed"] - point["speed"] > 10:  # Pelo menos 10 unidades de velocidade
                        apex_points.append({
                            "type": "apex",
                            "distance": point.get("distance", 0),
                            "time": point.get("time", 0),
                            "speed": point.get("speed", 0),
                            "position": point.get("position", [0, 0])
                        })
        
        key_points["apex"] = apex_points
        
        # Pontos de aceleração
        acceleration_points = []
        for i, point in enumerate(lap_data.get("data_points", [])):
            if i > 0 and i < len(lap_data["data_points"]) - 1:
                prev_point = lap_data["data_points"][i-1]
                next_point = lap_data["data_points"][i+1]
                
                # Detecta início de aceleração forte após uma curva
                if "throttle" in point and "throttle" in prev_point:
                    if point["throttle"] > 0.7 and point["throttle"] > prev_point["throttle"]:
                        # Verifica se havia frenagem antes
                        if prev_point.get("brake", 0) > 0.1:
                            acceleration_points.append({
                                "type": "acceleration",
                                "distance": point.get("distance", 0),
                                "time": point.get("time", 0),
                                "speed": point.get("speed", 0),
                                "position": point.get("position", [0, 0])
                            })
        
        key_points["acceleration"] = acceleration_points
        
        # Preenche a tabela de pontos-chave
        all_points = []
        all_points.extend(braking_points)
        all_points.extend(apex_points)
        all_points.extend(acceleration_points)
        
        # Ordena por distância
        all_points.sort(key=lambda x: x["distance"])
        
        for i, point in enumerate(all_points):
            row = self.key_points_table.rowCount()
            self.key_points_table.insertRow(row)
            
            # Tipo
            type_text = {
                "braking": "Frenagem",
                "apex": "Ápice",
                "acceleration": "Aceleração"
            }.get(point["type"], point["type"])
            
            self.key_points_table.setItem(row, 0, QTableWidgetItem(type_text))
            
            # Distância
            self.key_points_table.setItem(row, 1, QTableWidgetItem(f"{point['distance']:.1f} m"))
            
            # Tempo
            self.key_points_table.setItem(row, 2, QTableWidgetItem(f"{point['time']:.3f} s"))
            
            # Velocidade
            self.key_points_table.setItem(row, 3, QTableWidgetItem(f"{point['speed']:.1f} km/h"))
            
            # Botão de ação
            view_button = QPushButton("Ver")
            view_button.clicked.connect(lambda checked, p=point: self._show_point_on_track(p))
            
            self.key_points_table.setCellWidget(row, 4, view_button)
        
        # Erros detectados
        # Aqui usaríamos o analisador de telemetria para detectar erros
        # Por enquanto, vamos simular alguns erros
        errors = []
        
        # Frenagem tardia
        for point in braking_points:
            # Encontra o próximo ápice
            next_apex = None
            for ap in apex_points:
                if ap["distance"] > point["distance"]:
                    next_apex = ap
                    break
            
            if next_apex:
                # Verifica se a velocidade no ápice é muito baixa após a frenagem
                speed_at_apex = next_apex["speed"]
                speed_at_braking = point["speed"]
                
                # Heurística: Se a velocidade no ápice for < 50% da velocidade na frenagem
                if speed_at_apex < speed_at_braking * 0.5 and speed_at_braking > 100:
                    errors.append({
                        "type": "late_braking",
                        "severity": "medium",
                        "position": point["position"],
                        "description": "Possível frenagem tardia ou excessiva, resultando em baixa velocidade no ápice"
                    })
        
        # Preenche a tabela de erros
        for error in errors:
            row = self.errors_table.rowCount()
            self.errors_table.insertRow(row)
            
            # Tipo
            type_text = {
                "late_braking": "Frenagem Tardia",
                "early_acceleration": "Aceleração Prematura",
                "traction_loss": "Perda de Tração",
                "inconsistent_line": "Linha Inconsistente"
            }.get(error["type"], error["type"])
            
            self.errors_table.setItem(row, 0, QTableWidgetItem(type_text))
            
            # Severidade
            severity_text = {
                "low": "Baixa",
                "medium": "Média",
                "high": "Alta"
            }.get(error["severity"], error["severity"])
            
            self.errors_table.setItem(row, 1, QTableWidgetItem(severity_text))
            
            # Posição
            pos_text = f"({error['position'][0]:.1f}, {error['position'][1]:.1f})"
            self.errors_table.setItem(row, 2, QTableWidgetItem(pos_text))
            
            # Descrição
            self.errors_table.setItem(row, 3, QTableWidgetItem(error["description"]))
    
    def _show_point_on_track(self, point: Dict[str, Any]):
        """
        Destaca um ponto no traçado da pista.
        
        Args:
            point: Dicionário com dados do ponto
        """
        if "position" in point:
            self.track_view.highlight_point(point["position"])
