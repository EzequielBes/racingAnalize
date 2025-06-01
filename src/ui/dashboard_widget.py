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
import logging # Adicionado
from datetime import datetime
from typing import Dict, List, Any, Optional

# Importações condicionais para os módulos de captura
try:
    from src.data_capture.capture_manager import CaptureManager
    capture_available = True
except ImportError:
    capture_available = False
    # Usar logging em vez de print
    logging.warning("Módulos de captura não encontrados. Funcionalidade de tempo real desabilitada.")
    CaptureManager = None # Define como None para verificações

# Importação do widget de visualização do traçado
from src.ui.track_view import TrackViewWidget

logger = logging.getLogger(__name__) # Adicionado logger


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
    
    @pyqtSlot(bool, str)
    def set_connected(self, connected: bool, simulator: str = ""):
        """
        Atualiza o status de conexão.
        
        Args:
            connected: Se True, indica que está conectado
            simulator: Nome do simulador conectado
        """
        if connected:
            self.status_label.setText("Capturando") # Mudado para "Capturando"
            self.status_label.setStyleSheet("color: green;")
            self.sim_label.setText(simulator)
            self.data_mode_label.setText("Tempo Real") # Assumindo tempo real
            self.data_mode_label.setStyleSheet("color: green;")
            self._start_timer()
        else:
            self.status_label.setText("Desconectado")
            self.status_label.setStyleSheet("color: red;")
            self.sim_label.setText("Nenhum")
            self.data_mode_label.setText("Nenhum")
            self.data_mode_label.setStyleSheet("")
            self._stop_timer()
            self.time_label.setText("00:00:00") # Reseta o tempo
    
    def _start_timer(self):
        """Inicia o timer de captura."""
        if not self.capture_active:
            self.capture_active = True
            self.start_time = time.time()
            self.timer.start(1000)  # Atualiza a cada segundo
            self._update_time() # Atualiza imediatamente
    
    def _stop_timer(self):
        """Para o timer de captura."""
        if self.capture_active:
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
        title = QLabel("Informações da Sessão (Tempo Real)") # Título ajustado
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
        
        # Condições (placeholder)
        # info_layout.addWidget(QLabel("Condições:"), 2, 0)
        # self.conditions_label = QLabel("--")
        # self.conditions_label.setObjectName("metric-value")
        # info_layout.addWidget(self.conditions_label, 2, 1)
        
        # Temperatura
        info_layout.addWidget(QLabel("Temperatura (Ar/Pista):"), 2, 0) # Ajustado
        self.temp_label = QLabel("-- / --")
        self.temp_label.setObjectName("metric-value")
        info_layout.addWidget(self.temp_label, 2, 1)

        # Volta Atual / Total
        info_layout.addWidget(QLabel("Volta:"), 3, 0)
        self.lap_label = QLabel("-- / --")
        self.lap_label.setObjectName("metric-value")
        info_layout.addWidget(self.lap_label, 3, 1)
        
        layout.addLayout(info_layout)
        
        # Adiciona espaço no final
        layout.addStretch()
    
    @pyqtSlot(dict)
    def update_session_info(self, physics_data: Dict[str, Any]):
        """
        Atualiza as informações da sessão com base nos dados de física.
        
        Args:
            physics_data: Dicionário com dados de física (ACC)
        """
        # Adaptação para nomes de campos do ACC Shared Memory (exemplo)
        self.track_label.setText(physics_data.get("track", "--"))
        self.car_label.setText(physics_data.get("carModel", "--"))
        
        air_temp = physics_data.get("airTemp", "--")
        track_temp = physics_data.get("roadTemp", "--")
        self.temp_label.setText(f"{air_temp}°C / {track_temp}°C")

        current_lap = physics_data.get("currentLap", 0)
        total_laps = physics_data.get("numberOfLaps", 0)
        self.lap_label.setText(f"{current_lap} / {total_laps}")

    @pyqtSlot(dict)
    def update_lmu_session_info(self, telemetry_data: Dict[str, Any]):
        """
        Atualiza as informações da sessão com base nos dados de telemetria do LMU/rF2.
        
        Args:
            telemetry_data: Dicionário com dados de telemetria (LMU/rF2)
        """
        # Adaptação para nomes de campos do LMU/rF2 Shared Memory (exemplo)
        self.track_label.setText(telemetry_data.get("mTrackName", "--"))
        self.car_label.setText(telemetry_data.get("mVehicleName", "--"))
        
        air_temp = telemetry_data.get("mAmbientTemp", "--")
        track_temp = telemetry_data.get("mTrackTemp", "--")
        self.temp_label.setText(f"{air_temp}°C / {track_temp}°C")

        # LMU/rF2 não tem um campo direto para volta atual/total na estrutura principal de telemetria
        # Pode ser necessário obter de outra estrutura ou calcular
        self.lap_label.setText("-- / --") # Placeholder


class LapTimesPanel(QFrame):
    """Painel de tempos de volta (pode ser usado para tempo real também)."""
    
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
        title = QLabel("Tempos de Volta (Tempo Real)") # Título ajustado
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
        self.lap_times_data = {} # Armazena dados das voltas
    
    @pyqtSlot(dict)
    def update_lap_time(self, graphics_data: Dict[str, Any]):
        """
        Adiciona ou atualiza um tempo de volta na tabela (baseado em dados gráficos do ACC).
        
        Args:
            graphics_data: Dicionário com dados gráficos (ACC)
        """
        lap_number = graphics_data.get("completedLaps", 0) + 1 # Volta atual
        last_lap_time_ms = graphics_data.get("lastLap", 0)
        last_s1_ms = graphics_data.get("lastSplits", [0, 0, 0])[0]
        last_s2_ms = graphics_data.get("lastSplits", [0, 0, 0])[1]
        last_s3_ms = graphics_data.get("lastSplits", [0, 0, 0])[2]

        # Adiciona a volta anterior se o tempo for válido
        if last_lap_time_ms > 0:
            prev_lap_number = lap_number - 1
            if prev_lap_number > 0 and prev_lap_number not in self.lap_times_data:
                lap_time_s = last_lap_time_ms / 1000.0
                sectors_s = [last_s1_ms / 1000.0, last_s2_ms / 1000.0, last_s3_ms / 1000.0]
                self._add_or_update_row(prev_lap_number, lap_time_s, sectors_s)
                self.lap_times_data[prev_lap_number] = {"time": lap_time_s, "sectors": sectors_s}

    @pyqtSlot(dict)
    def update_lmu_lap_time(self, scoring_data: Dict[str, Any]):
        """
        Adiciona ou atualiza um tempo de volta na tabela (baseado em dados de scoring do LMU/rF2).
        
        Args:
            scoring_data: Dicionário com dados de scoring (LMU/rF2)
        """
        # Encontrar os dados do jogador (mIsPlayer == 1)
        player_vehicle = next((v for v in scoring_data.get("mVehicles", []) if v.get("mIsPlayer") == 1), None)
        if not player_vehicle:
            return

        lap_number = player_vehicle.get("mTotalLaps", 0) # Número de voltas completas
        last_lap_time_s = player_vehicle.get("mLastLapTime", 0)
        last_s1_s = player_vehicle.get("mLastSector1", 0)
        last_s2_s = player_vehicle.get("mLastSector2", 0)
        # O tempo do setor 3 precisa ser calculado (TempoVolta - S1 - S2)
        last_s3_s = 0
        if last_lap_time_s > 0 and last_s1_s > 0 and last_s2_s > 0:
             last_s3_s = last_lap_time_s - last_s1_s - last_s2_s
             if last_s3_s < 0: last_s3_s = 0 # Evita tempos negativos

        # Adiciona a volta anterior se o tempo for válido
        if last_lap_time_s > 0 and lap_number > 0:
            if lap_number not in self.lap_times_data:
                sectors_s = [last_s1_s, last_s2_s, last_s3_s]
                self._add_or_update_row(lap_number, last_lap_time_s, sectors_s)
                self.lap_times_data[lap_number] = {"time": last_lap_time_s, "sectors": sectors_s}

    def _add_or_update_row(self, lap_number: int, lap_time: float, sectors: List[float]):
        """Adiciona ou atualiza uma linha na tabela."""
        # Verifica se a volta já existe
        for row in range(self.times_table.rowCount()):
            item = self.times_table.item(row, 0)
            if item and item.text() == str(lap_number):
                # Atualiza a linha existente
                self.times_table.setItem(row, 1, QTableWidgetItem(self._format_time(lap_time)))
                for i, sector_time in enumerate(sectors[:3]):
                    self.times_table.setItem(row, i + 2, QTableWidgetItem(self._format_time(sector_time)))
                return

        # Adiciona nova linha se não existir
        row = self.times_table.rowCount()
        self.times_table.insertRow(row)
        self.times_table.setItem(row, 0, QTableWidgetItem(str(lap_number)))
        self.times_table.setItem(row, 1, QTableWidgetItem(self._format_time(lap_time)))
        for i, sector_time in enumerate(sectors[:3]):
            self.times_table.setItem(row, i + 2, QTableWidgetItem(self._format_time(sector_time)))
        self.times_table.scrollToBottom() # Garante visibilidade da última volta

    def clear_lap_times(self):
        """Limpa a tabela de tempos de volta."""
        self.times_table.setRowCount(0)
        self.lap_times_data.clear()
    
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
        title = QLabel("Traçado da Pista (Tempo Real)") # Título ajustado
        title.setObjectName("section-title")
        layout.addWidget(title)
        
        # Widget de visualização do traçado
        self.track_view = TrackViewWidget()
        layout.addWidget(self.track_view)
        self.current_lap_points = [] # Armazena pontos da volta atual
    
    @pyqtSlot(dict)
    def update_track_view(self, physics_data: Dict[str, Any]):
        """
        Atualiza a visualização do traçado com base nos dados de física (ACC).
        
        Args:
            physics_data: Dicionário com dados de física (ACC)
        """
        pos_x = physics_data.get("carCoordinates", [0, 0, 0])[0]
        pos_z = physics_data.get("carCoordinates", [0, 0, 0])[2] # ACC usa Z para o plano horizontal
        current_pos = [pos_x, pos_z]

        # Adiciona ponto à volta atual (simplificado, sem lógica de nova volta)
        # Idealmente, limparia em nova volta
        self.current_lap_points.append(current_pos)
        
        # Limita o número de pontos para performance
        max_points = 5000 
        if len(self.current_lap_points) > max_points:
            self.current_lap_points = self.current_lap_points[-max_points:]

        # Atualiza a visualização
        # self.track_view.set_track_points([]) # Não temos traçado base em tempo real ainda
        self.track_view.set_lap_points(self.current_lap_points)
        self.track_view.update_current_position(current_pos)

    @pyqtSlot(dict)
    def update_lmu_track_view(self, telemetry_data: Dict[str, Any]):
        """
        Atualiza a visualização do traçado com base nos dados de telemetria (LMU/rF2).
        
        Args:
            telemetry_data: Dicionário com dados de telemetria (LMU/rF2)
        """
        # Encontrar os dados do jogador (mIsPlayer == 1)
        player_vehicle = next((v for v in telemetry_data.get("mVehicles", []) if v.get("mIsPlayer") == 1), None)
        if not player_vehicle:
            return
            
        pos_x = player_vehicle.get("mPos", [0, 0, 0])[0]
        pos_z = player_vehicle.get("mPos", [0, 0, 0])[2] # rF2 também usa Z para o plano horizontal
        current_pos = [pos_x, pos_z]

        # Adiciona ponto à volta atual (simplificado)
        self.current_lap_points.append(current_pos)
        
        # Limita o número de pontos para performance
        max_points = 5000 
        if len(self.current_lap_points) > max_points:
            self.current_lap_points = self.current_lap_points[-max_points:]

        # Atualiza a visualização
        self.track_view.set_lap_points(self.current_lap_points)
        self.track_view.update_current_position(current_pos)

    def clear_track_view(self):
        """Limpa a visualização do traçado."""
        self.current_lap_points = []
        self.track_view.set_track_points([])
        self.track_view.set_lap_points([])
        self.track_view.update_current_position(None)
        self.track_view.highlight_point(None)
    
    # highlight_point não é usado em tempo real por enquanto
    # def highlight_point(self, point_index: int):
    #     ...


class CaptureControlPanel(QFrame):
    """Painel de controle de captura de telemetria."""
    
    # Sinais
    # connect_requested = pyqtSignal(str) # Removido - Usaremos Start/Stop
    # disconnect_requested = pyqtSignal() # Removido
    start_capture_requested = pyqtSignal(str) # Emite o nome do simulador selecionado
    stop_capture_requested = pyqtSignal()
    # import_requested = pyqtSignal(str) # Movido para o menu principal
    
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
        title = QLabel("Controle de Captura (Tempo Real)") # Título ajustado
        title.setObjectName("section-title")
        layout.addWidget(title)
        
        # Seleção de simulador
        sim_layout = QHBoxLayout()
        sim_layout.addWidget(QLabel("Simulador:"))
        
        self.sim_combo = QComboBox()
        # Adiciona apenas se CaptureManager estiver disponível
        if CaptureManager:
            supported_sims = CaptureManager.get_supported_simulators()
            self.sim_combo.addItems(supported_sims)
        else:
            self.sim_combo.addItem("Nenhum disponível")
            self.sim_combo.setEnabled(False)
            
        sim_layout.addWidget(self.sim_combo)
        layout.addLayout(sim_layout)
        
        # Botões de controle
        control_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Iniciar Captura")
        self.stop_button = QPushButton("Parar Captura")
        self.stop_button.setEnabled(False)
        
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        layout.addLayout(control_layout)

        # Conecta os botões aos slots internos
        self.start_button.clicked.connect(self._on_start_clicked)
        self.stop_button.clicked.connect(self._on_stop_clicked)

        # Desabilita botões se captura não estiver disponível
        if not capture_available:
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            # Adiciona uma label informativa
            info_label = QLabel("Módulos de captura não encontrados.")
            info_label.setStyleSheet("color: orange;")
            layout.addWidget(info_label)

        layout.addStretch() # Adiciona espaço

    @pyqtSlot()
    def _on_start_clicked(self):
        """Slot para o clique no botão Iniciar Captura."""
        selected_sim = self.sim_combo.currentText()
        if selected_sim and selected_sim != "Nenhum disponível":
            logger.info(f"Solicitando início da captura para: {selected_sim}")
            self.start_capture_requested.emit(selected_sim)
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.sim_combo.setEnabled(False) # Impede troca durante captura

    @pyqtSlot()
    def _on_stop_clicked(self):
        """Slot para o clique no botão Parar Captura."""
        logger.info("Solicitando parada da captura.")
        self.stop_capture_requested.emit()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.sim_combo.setEnabled(True) # Libera troca após parar

    # Slot para ser chamado externamente quando a captura é parada (ex: erro)
    @pyqtSlot()
    def force_stop_ui_update(self):
         """Atualiza a UI para o estado parado, chamado externamente."""
         logger.info("Atualizando UI para estado de captura parada (forçado).")
         self.start_button.setEnabled(True)
         self.stop_button.setEnabled(False)
         self.sim_combo.setEnabled(True)


class DashboardWidget(QWidget):
    """Widget principal do Dashboard."""
    
    # Sinal para solicitar início/parada da captura no backend
    start_capture_signal = pyqtSignal(str)
    stop_capture_signal = pyqtSignal()

    def __init__(self, parent=None):
        """
        Inicializa o widget do Dashboard.
        
        Args:
            parent: Widget pai
        """
        super().__init__(parent)
        
        # Layout principal
        main_layout = QHBoxLayout(self)
        
        # Coluna Esquerda (Controles e Status)
        left_column = QVBoxLayout()
        
        # Painel de Controle de Captura
        self.capture_control_panel = CaptureControlPanel()
        left_column.addWidget(self.capture_control_panel)
        
        # Painel de Status
        self.status_panel = StatusPanel()
        left_column.addWidget(self.status_panel)
        
        # Painel de Informações da Sessão
        self.session_info_panel = SessionInfoPanel()
        left_column.addWidget(self.session_info_panel)
        
        # Painel de Tempos de Volta
        self.lap_times_panel = LapTimesPanel()
        left_column.addWidget(self.lap_times_panel)
        
        left_column.addStretch()
        main_layout.addLayout(left_column, 1) # Coluna esquerda com peso 1
        
        # Coluna Direita (Visualização)
        right_column = QVBoxLayout()
        
        # Painel do Traçado
        self.track_panel = TrackPanel()
        right_column.addWidget(self.track_panel)
        
        # Adicionar outros painéis de visualização aqui (ex: gráficos tempo real)
        # placeholder_graph = QLabel("Gráficos Tempo Real (Placeholder)")
        # placeholder_graph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # placeholder_graph.setFrameShape(QFrame.Shape.StyledPanel)
        # right_column.addWidget(placeholder_graph)
        
        right_column.addStretch()
        main_layout.addLayout(right_column, 3) # Coluna direita com peso 3

        # Conecta sinais do painel de controle aos sinais do widget
        self.capture_control_panel.start_capture_requested.connect(self.start_capture_signal)
        self.capture_control_panel.stop_capture_requested.connect(self.stop_capture_signal)

        # Conecta sinais de atualização de dados aos slots dos painéis
        # Estes sinais devem ser emitidos pelo CaptureManager ou pela MainWindow
        # self.data_updated_signal.connect(self.status_panel.set_connected)
        # self.physics_updated_signal.connect(self.session_info_panel.update_session_info)
        # self.graphics_updated_signal.connect(self.lap_times_panel.update_lap_time)
        # self.physics_updated_signal.connect(self.track_panel.update_track_view)
        # self.telemetry_updated_signal.connect(self.session_info_panel.update_lmu_session_info)
        # self.scoring_updated_signal.connect(self.lap_times_panel.update_lmu_lap_time)
        # self.telemetry_updated_signal.connect(self.track_panel.update_lmu_track_view)

        logger.info("DashboardWidget inicializado.")

    # Slots para receber atualizações do backend/CaptureManager
    @pyqtSlot(bool, str)
    def update_connection_status(self, connected: bool, simulator: str):
        """Atualiza o status de conexão em todos os painéis relevantes."""
        logger.debug(f"Atualizando status de conexão UI: Conectado={connected}, Sim={simulator}")
        self.status_panel.set_connected(connected, simulator)
        if not connected:
            # Limpa painéis se desconectado
            self.session_info_panel.update_session_info({}) # Limpa info da sessão
            self.lap_times_panel.clear_lap_times()
            self.track_panel.clear_track_view()
            self.capture_control_panel.force_stop_ui_update() # Garante que botões voltem ao normal

    @pyqtSlot(dict)
    def update_acc_physics_data(self, data: dict):
        """Atualiza painéis com dados de física do ACC."""
        # logger.debug("Atualizando UI com dados de física ACC")
        self.session_info_panel.update_session_info(data)
        self.track_panel.update_track_view(data)

    @pyqtSlot(dict)
    def update_acc_graphics_data(self, data: dict):
        """Atualiza painéis com dados gráficos do ACC."""
        # logger.debug("Atualizando UI com dados gráficos ACC")
        self.lap_times_panel.update_lap_time(data)

    @pyqtSlot(dict)
    def update_lmu_telemetry_data(self, data: dict):
        """Atualiza painéis com dados de telemetria do LMU."""
        # logger.debug("Atualizando UI com dados de telemetria LMU")
        self.session_info_panel.update_lmu_session_info(data)
        self.track_panel.update_lmu_track_view(data)

    @pyqtSlot(dict)
    def update_lmu_scoring_data(self, data: dict):
        """Atualiza painéis com dados de scoring do LMU."""
        # logger.debug("Atualizando UI com dados de scoring LMU")
        self.lap_times_panel.update_lmu_lap_time(data)

# Exemplo de uso (para teste isolado do Dashboard)
if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication
    import sys

    # Configuração básica de logging para teste
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    app = QApplication(sys.argv)
    
    # Simula CaptureManager se não estiver disponível
    if not CaptureManager:
        class MockCaptureManager:
            def get_supported_simulators(self):
                return ["ACC (Mock)", "LMU (Mock)"]
            # Adicione outros métodos mock se necessário
        CaptureManager = MockCaptureManager

    dashboard = DashboardWidget()
    dashboard.setWindowTitle("Teste do Dashboard Widget")
    dashboard.setGeometry(100, 100, 1200, 700)

    # Simula sinais para teste
    def simulate_connect():
        dashboard.update_connection_status(True, "ACC (Mock)")

    def simulate_disconnect():
        dashboard.update_connection_status(False, "")

    def simulate_acc_data():
        physics = {"track": "Monza", "carModel": "Ferrari 488 GT3 Evo", "airTemp": 25, "roadTemp": 35, "currentLap": 3, "numberOfLaps": 10, "carCoordinates": [time.time() % 100, 0, (time.time()*2) % 150]}
        graphics = {"completedLaps": 2, "lastLap": 95500, "lastSplits": [31200, 30100, 34200]}
        dashboard.update_acc_physics_data(physics)
        dashboard.update_acc_graphics_data(graphics)

    # Conecta botões de teste (apenas para este exemplo)
    test_button_connect = QPushButton("Simular Conexão")
    test_button_connect.clicked.connect(simulate_connect)
    
    test_button_disconnect = QPushButton("Simular Desconexão")
    test_button_disconnect.clicked.connect(simulate_disconnect)

    test_button_data = QPushButton("Simular Dados ACC")
    test_button_data.clicked.connect(simulate_acc_data)

    # Adiciona botões de teste ao layout (não ideal, mas funciona para teste)
    test_layout = QHBoxLayout()
    test_layout.addWidget(test_button_connect)
    test_layout.addWidget(test_button_disconnect)
    test_layout.addWidget(test_button_data)
    
    # Encontra o layout da coluna esquerda para adicionar os botões de teste
    left_layout = dashboard.layout().itemAt(0).layout()
    if left_layout:
        left_layout.addLayout(test_layout)

    dashboard.show()
    sys.exit(app.exec())

