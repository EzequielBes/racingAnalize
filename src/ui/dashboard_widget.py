"""
Widget de Dashboard para o Race Telemetry Analyzer.
Exibe visão geral dos dados de telemetria e controles de captura.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QSplitter, QFrame, QGroupBox, QGridLayout,
    QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QFileDialog
)
from PyQt6.QtGui import QIcon, QFont, QColor, QPalette
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QSize, QTimer

import os
import sys
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

# Importações condicionais para os módulos de captura
try:
    from src.data_capture.capture_manager import CaptureManager
    capture_available = True
except ImportError:
    capture_available = False
    print("Módulos de captura não encontrados. Usando stubs.")

# Importação do widget de visualização do traçado
from src.ui.track_view import TrackViewWidget


class StatusPanel(QFrame):
    """Painel de status da captura de telemetria."""
    
    def __init__(self, parent=None):
        """
        Inicializa o painel de status.
        
        Args:
            parent: Widget pai
        """
        super().__init__(parent)
        
        # Configuração do frame
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setMinimumHeight(100)
        
        # Layout
        layout = QVBoxLayout(self)
        
        # Título
        title = QLabel("Status da Captura")
        title.setObjectName("section-title")
        layout.addWidget(title)
        
        # Status de conexão
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Status:"))
        
        self.status_label = QLabel("Desconectado")
        self.status_label.setObjectName("metric-value")
        self.status_label.setStyleSheet("color: red;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        
        layout.addLayout(status_layout)
        
        # Simulador conectado
        sim_layout = QHBoxLayout()
        sim_layout.addWidget(QLabel("Simulador:"))
        
        self.sim_label = QLabel("Nenhum")
        self.sim_label.setObjectName("metric-value")
        sim_layout.addWidget(self.sim_label)
        sim_layout.addStretch()
        
        layout.addLayout(sim_layout)
        
        # Modo de dados
        data_mode_layout = QHBoxLayout()
        data_mode_layout.addWidget(QLabel("Modo de dados:"))
        
        self.data_mode_label = QLabel("Nenhum")
        self.data_mode_label.setObjectName("metric-value")
        data_mode_layout.addWidget(self.data_mode_label)
        data_mode_layout.addStretch()
        
        layout.addLayout(data_mode_layout)
        
        # Tempo de captura
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Tempo de captura:"))
        
        self.time_label = QLabel("00:00:00")
        self.time_label.setObjectName("metric-value")
        time_layout.addWidget(self.time_label)
        time_layout.addStretch()
        
        layout.addLayout(time_layout)
        
        # Estado
        self.capture_active = False
        self.start_time = None
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_time)
    
    def set_connected(self, connected: bool, simulator: str = "", is_real_data: bool = True):
        """
        Atualiza o status de conexão.
        
        Args:
            connected: Se True, indica que está conectado
            simulator: Nome do simulador conectado
            is_real_data: Se True, indica que está usando dados reais
        """
        if connected:
            self.status_label.setText("Conectado")
            self.status_label.setStyleSheet("color: green;")
            self.sim_label.setText(simulator)
            
            # Atualiza o modo de dados
            if is_real_data:
                self.data_mode_label.setText("Dados Reais")
                self.data_mode_label.setStyleSheet("color: green;")
            else:
                self.data_mode_label.setText("Simulação")
                self.data_mode_label.setStyleSheet("color: orange;")
        else:
            self.status_label.setText("Desconectado")
            self.status_label.setStyleSheet("color: red;")
            self.sim_label.setText("Nenhum")
            self.data_mode_label.setText("Nenhum")
            self.data_mode_label.setStyleSheet("")
    
    def start_capture(self):
        """Inicia a captura de telemetria."""
        self.capture_active = True
        self.start_time = time.time()
        self.timer.start(1000)  # Atualiza a cada segundo
    
    def stop_capture(self):
        """Para a captura de telemetria."""
        self.capture_active = False
        self.timer.stop()
    
    def _update_time(self):
        """Atualiza o tempo de captura."""
        if not self.capture_active or not self.start_time:
            return
        
        elapsed = time.time() - self.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        self.time_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")


class SessionInfoPanel(QFrame):
    """Painel de informações da sessão atual."""
    
    def __init__(self, parent=None):
        """
        Inicializa o painel de informações da sessão.
        
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
        title = QLabel("Informações da Sessão")
        title.setObjectName("section-title")
        layout.addWidget(title)
        
        # Grid de informações
        info_layout = QGridLayout()
        
        # Pista
        info_layout.addWidget(QLabel("Pista:"), 0, 0)
        self.track_label = QLabel("--")
        self.track_label.setObjectName("metric-value")
        info_layout.addWidget(self.track_label, 0, 1)
        
        # Carro
        info_layout.addWidget(QLabel("Carro:"), 1, 0)
        self.car_label = QLabel("--")
        self.car_label.setObjectName("metric-value")
        info_layout.addWidget(self.car_label, 1, 1)
        
        # Condições
        info_layout.addWidget(QLabel("Condições:"), 2, 0)
        self.conditions_label = QLabel("--")
        self.conditions_label.setObjectName("metric-value")
        info_layout.addWidget(self.conditions_label, 2, 1)
        
        # Temperatura
        info_layout.addWidget(QLabel("Temperatura:"), 3, 0)
        self.temp_label = QLabel("--")
        self.temp_label.setObjectName("metric-value")
        info_layout.addWidget(self.temp_label, 3, 1)
        
        layout.addLayout(info_layout)
        
        # Adiciona espaço no final
        layout.addStretch()
    
    def update_session_info(self, session_info: Dict[str, Any]):
        """
        Atualiza as informações da sessão.
        
        Args:
            session_info: Dicionário com informações da sessão
        """
        self.track_label.setText(session_info.get("track", "--"))
        self.car_label.setText(session_info.get("car", "--"))
        self.conditions_label.setText(session_info.get("conditions", "--"))
        
        temp = session_info.get("temperature", {})
        if isinstance(temp, dict):
            air_temp = temp.get("air", "--")
            track_temp = temp.get("track", "--")
            self.temp_label.setText(f"Ar: {air_temp}°C, Pista: {track_temp}°C")
        else:
            self.temp_label.setText(f"{temp}°C")


class LapTimesPanel(QFrame):
    """Painel de tempos de volta."""
    
    lap_selected = pyqtSignal(int)  # Sinal emitido quando uma volta é selecionada
    
    def __init__(self, parent=None):
        """
        Inicializa o painel de tempos de volta.
        
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
        title = QLabel("Tempos de Volta")
        title.setObjectName("section-title")
        layout.addWidget(title)
        
        # Tabela de tempos
        self.times_table = QTableWidget()
        self.times_table.setColumnCount(5)
        self.times_table.setHorizontalHeaderLabels(["Volta", "Tempo", "S1", "S2", "S3"])
        
        # Ajusta o comportamento da tabela
        self.times_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.times_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.times_table.setAlternatingRowColors(True)
        
        # Ajusta o tamanho das colunas
        header = self.times_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        
        # Conecta o sinal de seleção
        self.times_table.itemSelectionChanged.connect(self._on_selection_changed)
        
        layout.addWidget(self.times_table)
    
    def add_lap_time(self, lap_number: int, lap_time: float, sectors: List[float] = None):
        """
        Adiciona um tempo de volta à tabela.
        
        Args:
            lap_number: Número da volta
            lap_time: Tempo da volta em segundos
            sectors: Lista de tempos de setor em segundos
        """
        row = self.times_table.rowCount()
        self.times_table.insertRow(row)
        
        # Número da volta
        self.times_table.setItem(row, 0, QTableWidgetItem(str(lap_number)))
        
        # Tempo da volta
        time_str = self._format_time(lap_time)
        self.times_table.setItem(row, 1, QTableWidgetItem(time_str))
        
        # Tempos de setor
        if sectors:
            for i, sector_time in enumerate(sectors[:3]):
                sector_str = self._format_time(sector_time)
                self.times_table.setItem(row, i + 2, QTableWidgetItem(sector_str))
    
    def clear_lap_times(self):
        """Limpa a tabela de tempos de volta."""
        self.times_table.setRowCount(0)
    
    def _format_time(self, time_seconds: float) -> str:
        """
        Formata um tempo em segundos para o formato MM:SS.mmm.
        
        Args:
            time_seconds: Tempo em segundos
            
        Returns:
            String formatada
        """
        if time_seconds <= 0:
            return "--"
        
        minutes = int(time_seconds // 60)
        seconds = int(time_seconds % 60)
        milliseconds = int((time_seconds % 1) * 1000)
        
        return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
    
    def _on_selection_changed(self):
        """Manipula a mudança de seleção na tabela."""
        selected_items = self.times_table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            lap_number_item = self.times_table.item(row, 0)
            if lap_number_item:
                try:
                    lap_number = int(lap_number_item.text())
                    self.lap_selected.emit(lap_number)
                except ValueError:
                    pass


class TrackPanel(QFrame):
    """Painel de visualização do traçado da pista."""
    
    def __init__(self, parent=None):
        """
        Inicializa o painel de visualização do traçado.
        
        Args:
            parent: Widget pai
        """
        super().__init__(parent)
        
        # Configuração do frame
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setMinimumHeight(300)
        
        # Layout
        layout = QVBoxLayout(self)
        
        # Título
        title = QLabel("Traçado da Pista")
        title.setObjectName("section-title")
        layout.addWidget(title)
        
        # Widget de visualização do traçado
        self.track_view = TrackViewWidget()
        layout.addWidget(self.track_view)
    
    def update_track_view(self, lap_data: Dict[str, Any] = None):
        """
        Atualiza a visualização do traçado.
        
        Args:
            lap_data: Dados da volta selecionada
        """
        if not lap_data:
            # Limpa a visualização
            self.track_view.set_track_points([])
            self.track_view.set_lap_points([])
            self.track_view.update_current_position(None)
            self.track_view.highlight_point(None)
            return
        
        # Extrai os pontos do traçado
        track_points = []
        lap_points = []
        
        # Processa os pontos de dados
        for point in lap_data.get("data_points", []):
            position = point.get("position", [0, 0])
            if len(position) >= 2:
                lap_points.append([position[0], position[1]])
        
        # Se não houver pontos de traçado específicos, usa os pontos da volta
        if not track_points and lap_points:
            track_points = lap_points
        
        # Atualiza a visualização
        self.track_view.set_track_points(track_points)
        self.track_view.set_lap_points(lap_points)
        
        # Atualiza a posição atual (último ponto)
        if lap_points:
            self.track_view.update_current_position(lap_points[-1])
    
    def highlight_point(self, point_index: int):
        """
        Destaca um ponto específico no traçado.
        
        Args:
            point_index: Índice do ponto a destacar
        """
        # Obtém os pontos atuais
        lap_points = self.track_view.lap_points
        
        if lap_points and 0 <= point_index < len(lap_points):
            self.track_view.highlight_point(lap_points[point_index])
        else:
            self.track_view.highlight_point(None)


class CaptureControlPanel(QFrame):
    """Painel de controle de captura de telemetria."""
    
    # Sinais
    connect_requested = pyqtSignal(str)
    disconnect_requested = pyqtSignal()
    start_capture_requested = pyqtSignal()
    stop_capture_requested = pyqtSignal()
    import_requested = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """
        Inicializa o painel de controle de captura.
        
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
        title = QLabel("Controle de Captura")
        title.setObjectName("section-title")
        layout.addWidget(title)
        
        # Seleção de simulador
        sim_layout = QHBoxLayout()
        sim_layout.addWidget(QLabel("Simulador:"))
        
        self.sim_combo = QComboBox()
        self.sim_combo.addItem("Assetto Corsa Competizione")
        self.sim_combo.addItem("Le Mans Ultimate")
        sim_layout.addWidget(self.sim_combo)
        
        layout.addLayout(sim_layout)
        
        # Botões de conexão
        conn_layout = QHBoxLayout()
        
        self.connect_button = QPushButton("Conectar")
        self.disconnect_button = QPushButton("Desconectar")
        self.disconnect_button.setEnabled(False)
        
        conn_layout.addWidget(self.connect_button)
        conn_layout.addWidget(self.disconnect_button)
        
        layout.addLayout(conn_layout)
        
        # Botões de captura
        capture_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Iniciar Captura")
        self.start_button.setEnabled(False)
        self.stop_button = QPushButton("Parar Captura")
        self.stop_button.setEnabled(False)
        
        capture_layout.addWidget(self.start_button)
        capture_layout.addWidget(self.stop_button)
        
        layout.addLayout(capture_layout)
        
        # Botões de importação
        import_layout = QHBoxLayout()
        
        self.import_button = QPushButton("Importar Telemetria")
        self.load_example_button = QPushButton("Carregar Exemplo")
        
        import_layout.addWidget(self.import_button)
        import_layout.addWidget(self.load_example_button)
        
        layout.addLayout(import_layout)
        
        # Conecta sinais
        self.connect_button.clicked.connect(self._on_connect_clicked)
        self.disconnect_button.clicked.connect(self._on_disconnect_clicked)
        self.start_button.clicked.connect(self._on_start_clicked)
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.import_button.clicked.connect(self._on_import_clicked)
        self.load_example_button.clicked.connect(self._on_load_example_clicked)
        
        # Estado
        self.connected = False
        self.capturing = False
    
    def set_connected(self, connected: bool):
        """
        Atualiza o estado de conexão.
        
        Args:
            connected: Se True, indica que está conectado
        """
        self.connected = connected
        
        # Atualiza os botões
        self.connect_button.setEnabled(not connected)
        self.disconnect_button.setEnabled(connected)
        self.start_button.setEnabled(connected and not self.capturing)
        self.sim_combo.setEnabled(not connected)
    
    def set_capturing(self, capturing: bool):
        """
        Atualiza o estado de captura.
        
        Args:
            capturing: Se True, indica que está capturando
        """
        self.capturing = capturing
        
        # Atualiza os botões
        self.start_button.setEnabled(self.connected and not capturing)
        self.stop_button.setEnabled(capturing)
        self.disconnect_button.setEnabled(self.connected and not capturing)
    
    def _on_connect_clicked(self):
        """Manipula o clique no botão 'Conectar'."""
        simulator = self.sim_combo.currentText()
        self.connect_requested.emit(simulator)
    
    def _on_disconnect_clicked(self):
        """Manipula o clique no botão 'Desconectar'."""
        self.disconnect_requested.emit()
    
    def _on_start_clicked(self):
        """Manipula o clique no botão 'Iniciar Captura'."""
        self.start_capture_requested.emit()
    
    def _on_stop_clicked(self):
        """Manipula o clique no botão 'Parar Captura'."""
        self.stop_capture_requested.emit()
    
    def _on_import_clicked(self):
        """Manipula o clique no botão 'Importar Telemetria'."""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self,
            "Importar Telemetria",
            "",
            "Arquivos de Telemetria (*.json *.csv);;Todos os Arquivos (*)"
        )
        
        if file_path:
            self.import_requested.emit(file_path)
    
    def _on_load_example_clicked(self):
        """Manipula o clique no botão 'Carregar Exemplo'."""
        # Carrega dados de exemplo
        example_data = self._generate_example_data()
        
        # Salva em um arquivo temporário
        temp_dir = os.path.join(os.path.expanduser("~"), "RaceTelemetryAnalyzer", "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_file = os.path.join(temp_dir, "example_data.json")
        
        with open(temp_file, "w") as f:
            json.dump(example_data, f)
        
        # Emite o sinal de importação
        self.import_requested.emit(temp_file)
    
    def _generate_example_data(self) -> Dict[str, Any]:
        """
        Gera dados de exemplo para demonstração.
        
        Returns:
            Dicionário com dados de exemplo
        """
        import random
        import math
        
        # Dados da sessão
        session = {
            "track": "Monza",
            "car": "Ford Mustang GT3",
            "conditions": "Ensolarado",
            "temperature": {
                "air": 25,
                "track": 30
            }
        }
        
        # Voltas
        laps = []
        
        # Gera 5 voltas de exemplo
        for lap_num in range(1, 6):
            # Tempo base da volta (1:50.000)
            base_time = 110.0
            
            # Variação aleatória
            variation = random.uniform(-2.0, 2.0)
            lap_time = base_time + variation
            
            # Setores (aproximadamente 1/3 do tempo total cada)
            sector1 = lap_time / 3 + random.uniform(-0.5, 0.5)
            sector2 = lap_time / 3 + random.uniform(-0.5, 0.5)
            sector3 = lap_time - sector1 - sector2
            
            # Pontos de dados
            data_points = []
            
            # Gera pontos ao longo da volta
            num_points = 1000
            for i in range(num_points):
                # Progresso na volta (0 a 1)
                progress = i / num_points
                
                # Distância percorrida
                distance = progress * 5800  # Comprimento aproximado de Monza
                
                # Posição (simplificada para um traçado mais realista de Monza)
                # Cria uma forma que se assemelha ao traçado de Monza
                t = progress * 2 * math.pi
                
                # Reta principal e variante
                if progress < 0.2:
                    x = 1000 * progress * 5
                    y = 0
                # Curva Biassono
                elif progress < 0.3:
                    angle = (progress - 0.2) * 10 * math.pi / 2
                    x = 1000 + 300 * math.cos(angle)
                    y = 300 * math.sin(angle)
                # Lesmo 1 e 2
                elif progress < 0.5:
                    x = 1000 - (progress - 0.3) * 2000
                    y = 300 + math.sin((progress - 0.3) * 20) * 100
                # Curva Ascari
                elif progress < 0.7:
                    angle = (progress - 0.5) * 10 * math.pi
                    x = 0 - 300 * math.cos(angle)
                    y = 300 - 300 * math.sin(angle)
                # Parabolica e reta final
                else:
                    angle = (progress - 0.7) * 5 * math.pi / 2
                    radius = 500 - (progress - 0.7) * 1500
                    x = -300 + radius * math.cos(angle)
                    y = 0 + radius * math.sin(angle)
                
                # Adiciona ruído para tornar mais realista
                x += random.uniform(-10, 10)
                y += random.uniform(-10, 10)
                
                # Velocidade (varia ao longo da volta)
                speed_factor = 1.0 + 0.2 * math.sin(progress * 2 * math.pi * 4)
                speed = 200 * speed_factor  # Velocidade média de 200 km/h
                
                # RPM
                rpm = 5000 + 3000 * speed_factor
                
                # Marcha
                gear = min(6, max(1, int(speed / 50) + 1))
                
                # Pedais
                throttle = 0.8 + 0.2 * math.sin(progress * 2 * math.pi * 8)
                brake = max(0, 0.5 - throttle)
                
                # Ponto de dados
                data_point = {
                    "time": progress * lap_time,
                    "distance": distance,
                    "position": [x, y],
                    "speed": speed,
                    "rpm": rpm,
                    "gear": gear,
                    "throttle": throttle,
                    "brake": brake
                }
                
                data_points.append(data_point)
            
            # Volta
            lap = {
                "lap_number": lap_num,
                "lap_time": lap_time,
                "sectors": [
                    {"sector": 1, "time": sector1},
                    {"sector": 2, "time": sector2},
                    {"sector": 3, "time": sector3}
                ],
                "data_points": data_points
            }
            
            laps.append(lap)
        
        # Dados completos
        return {
            "session": session,
            "laps": laps
        }


class DashboardWidget(QWidget):
    """Widget principal de Dashboard."""
    
    def __init__(self, parent=None):
        """
        Inicializa o widget de Dashboard.
        
        Args:
            parent: Widget pai
        """
        super().__init__(parent)
        
        # Layout principal
        layout = QVBoxLayout(self)
        
        # Painel de controle
        self.control_panel = CaptureControlPanel()
        layout.addWidget(self.control_panel)
        
        # Splitter principal
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Painel esquerdo
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Status
        self.status_panel = StatusPanel()
        left_layout.addWidget(self.status_panel)
        
        # Informações da sessão
        self.session_panel = SessionInfoPanel()
        left_layout.addWidget(self.session_panel)
        
        # Visualização do traçado
        self.track_panel = TrackPanel()
        left_layout.addWidget(self.track_panel)
        
        # Painel direito
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Tempos de volta
        self.lap_times_panel = LapTimesPanel()
        right_layout.addWidget(self.lap_times_panel)
        
        # Adiciona painéis ao splitter
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        
        # Define proporções iniciais
        main_splitter.setSizes([400, 600])
        
        layout.addWidget(main_splitter)
        
        # Conecta sinais
        self.control_panel.connect_requested.connect(self._on_connect_requested)
        self.control_panel.disconnect_requested.connect(self._on_disconnect_requested)
        self.control_panel.start_capture_requested.connect(self._on_start_capture_requested)
        self.control_panel.stop_capture_requested.connect(self._on_stop_capture_requested)
        self.control_panel.import_requested.connect(self._on_import_requested)
        self.lap_times_panel.lap_selected.connect(self._on_lap_selected)
        
        # Timer para atualização periódica
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_telemetry_data)
        
        # Inicializa o gerenciador de captura
        self.capture_manager = None
        if capture_available:
            try:
                self.capture_manager = CaptureManager()
            except Exception as e:
                print(f"Erro ao inicializar o gerenciador de captura: {str(e)}")
        
        # Estado
        self.connected = False
        self.capturing = False
        self.current_simulator = ""
        self.telemetry_data = None
        self.is_real_data = False
        self.selected_lap = None
    
    def _on_connect_requested(self, simulator: str):
        """
        Manipula a solicitação de conexão.
        
        Args:
            simulator: Nome do simulador
        """
        if not self.capture_manager:
            QMessageBox.warning(
                self,
                "Aviso",
                "Módulos de captura não disponíveis. Usando modo de demonstração."
            )
            # Simula conexão bem-sucedida
            self._handle_connection_success(simulator, False)
            return
        
        try:
            # Tenta conectar ao simulador
            success = self.capture_manager.connect(simulator)
            
            if success:
                # Verifica se está usando dados reais ou simulação
                is_real_data = hasattr(self.capture_manager, 'capture_module') and self.capture_manager.capture_module is not None
                
                self._handle_connection_success(simulator, is_real_data)
            else:
                QMessageBox.warning(
                    self,
                    "Erro de Conexão",
                    f"Não foi possível conectar ao simulador {simulator}.\n\n"
                    "Verifique se o simulador está em execução."
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro",
                f"Ocorreu um erro ao tentar conectar:\n\n{str(e)}"
            )
    
    def _handle_connection_success(self, simulator: str, is_real_data: bool):
        """
        Manipula uma conexão bem-sucedida.
        
        Args:
            simulator: Nome do simulador
            is_real_data: Se True, indica que está usando dados reais
        """
        self.connected = True
        self.current_simulator = simulator
        self.is_real_data = is_real_data
        
        # Atualiza a interface
        self.control_panel.set_connected(True)
        self.status_panel.set_connected(True, simulator, is_real_data)
        
        # Atualiza as informações da sessão
        if self.capture_manager:
            session_info = self.capture_manager.get_telemetry_data().get("session", {})
            self.session_panel.update_session_info(session_info)
        
        # Exibe mensagem de aviso se estiver usando simulação
        if not is_real_data:
            QMessageBox.information(
                self,
                "Modo de Simulação",
                f"Conectado ao {simulator} em modo de simulação.\n\n"
                "Os dados exibidos são simulados e não representam telemetria real."
            )
    
    def _on_disconnect_requested(self):
        """Manipula a solicitação de desconexão."""
        if self.capturing:
            self._on_stop_capture_requested()
        
        if self.capture_manager:
            try:
                self.capture_manager.disconnect()
            except Exception as e:
                print(f"Erro ao desconectar: {str(e)}")
        
        # Atualiza o estado
        self.connected = False
        self.current_simulator = ""
        self.is_real_data = False
        
        # Atualiza a interface
        self.control_panel.set_connected(False)
        self.status_panel.set_connected(False)
        self.lap_times_panel.clear_lap_times()
        self.track_panel.update_track_view(None)
    
    def _on_start_capture_requested(self):
        """Manipula a solicitação de início de captura."""
        if not self.connected:
            return
        
        if self.capture_manager:
            try:
                success = self.capture_manager.start_capture()
                
                if success:
                    self.capturing = True
                    self.control_panel.set_capturing(True)
                    self.status_panel.start_capture()
                    
                    # Inicia o timer de atualização
                    self.update_timer.start(500)  # Atualiza a cada 500ms
                else:
                    QMessageBox.warning(
                        self,
                        "Erro",
                        "Não foi possível iniciar a captura de telemetria."
                    )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Erro",
                    f"Ocorreu um erro ao iniciar a captura:\n\n{str(e)}"
                )
        else:
            # Simula captura bem-sucedida
            self.capturing = True
            self.control_panel.set_capturing(True)
            self.status_panel.start_capture()
            
            # Carrega dados de exemplo
            self._on_load_example_clicked()
    
    def _on_stop_capture_requested(self):
        """Manipula a solicitação de parada de captura."""
        if not self.capturing:
            return
        
        if self.capture_manager:
            try:
                success = self.capture_manager.stop_capture()
                
                if not success:
                    QMessageBox.warning(
                        self,
                        "Aviso",
                        "Houve um problema ao parar a captura de telemetria."
                    )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Erro",
                    f"Ocorreu um erro ao parar a captura:\n\n{str(e)}"
                )
        
        # Atualiza o estado
        self.capturing = False
        self.control_panel.set_capturing(False)
        self.status_panel.stop_capture()
        
        # Para o timer de atualização
        self.update_timer.stop()
    
    def _on_import_requested(self, file_path: str):
        """
        Manipula a solicitação de importação de telemetria.
        
        Args:
            file_path: Caminho para o arquivo de telemetria
        """
        try:
            # Carrega o arquivo
            with open(file_path, "r") as f:
                self.telemetry_data = json.load(f)
            
            # Atualiza as informações da sessão
            session_info = self.telemetry_data.get("session", {})
            self.session_panel.update_session_info(session_info)
            
            # Atualiza os tempos de volta
            self.lap_times_panel.clear_lap_times()
            for lap in self.telemetry_data.get("laps", []):
                lap_number = lap.get("lap_number", 0)
                lap_time = lap.get("lap_time", 0)
                
                sectors = []
                for sector in lap.get("sectors", []):
                    sectors.append(sector.get("time", 0))
                
                self.lap_times_panel.add_lap_time(lap_number, lap_time, sectors)
            
            # Atualiza a visualização do traçado com a primeira volta
            if self.telemetry_data.get("laps"):
                self.track_panel.update_track_view(self.telemetry_data["laps"][0])
            
            QMessageBox.information(
                self,
                "Importação Concluída",
                f"Arquivo de telemetria importado com sucesso.\n\n"
                f"Voltas carregadas: {len(self.telemetry_data.get('laps', []))}"
            )
        
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro",
                f"Ocorreu um erro ao importar o arquivo:\n\n{str(e)}"
            )
    
    def _on_load_example_clicked(self):
        """Manipula o clique no botão 'Carregar Exemplo'."""
        # Usa o método do painel de controle
        self.control_panel._on_load_example_clicked()
    
    def _update_telemetry_data(self):
        """Atualiza os dados de telemetria periodicamente."""
        if not self.capturing or not self.capture_manager:
            return
        
        try:
            # Obtém os dados mais recentes
            new_data = self.capture_manager.get_telemetry_data()
            
            if not new_data:
                return
            
            # Atualiza os dados
            self.telemetry_data = new_data
            
            # Atualiza as informações da sessão
            session_info = new_data.get("session", {})
            self.session_panel.update_session_info(session_info)
            
            # Atualiza os tempos de volta
            self.lap_times_panel.clear_lap_times()
            for lap in new_data.get("laps", []):
                lap_number = lap.get("lap_number", 0)
                lap_time = lap.get("lap_time", 0)
                
                sectors = []
                for sector in lap.get("sectors", []):
                    sectors.append(sector.get("time", 0))
                
                self.lap_times_panel.add_lap_time(lap_number, lap_time, sectors)
            
            # Atualiza a visualização do traçado com a última volta
            if new_data.get("laps"):
                last_lap = new_data["laps"][-1]
                self.track_panel.update_track_view(last_lap)
        
        except Exception as e:
            print(f"Erro ao atualizar dados de telemetria: {str(e)}")
    
    def _on_lap_selected(self, lap_number: int):
        """
        Manipula a seleção de uma volta.
        
        Args:
            lap_number: Número da volta selecionada
        """
        if not self.telemetry_data:
            return
        
        # Procura a volta selecionada
        selected_lap = None
        for lap in self.telemetry_data.get("laps", []):
            if lap.get("lap_number") == lap_number:
                selected_lap = lap
                break
        
        if selected_lap:
            self.selected_lap = selected_lap
            self.track_panel.update_track_view(selected_lap)
