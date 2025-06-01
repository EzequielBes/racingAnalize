# -*- coding: utf-8 -*-
"""Widget para análise detalhada de uma única volta."""

import logging
from typing import Optional, List, Dict, Any

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSplitter, 
    QMessageBox, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QPointF

from src.core.standard_data import TelemetrySession, LapData, DataPoint
from src.ui.track_view import TrackViewWidget # Reutiliza o widget de visualização 2D

logger = logging.getLogger(__name__)

class AnalysisWidget(QWidget):
    """Widget para análise detalhada de uma única volta."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.session_data: Optional[TelemetrySession] = None
        self.current_lap_data: Optional[LapData] = None
        self.plot_items = {} # Armazena os itens de plotagem para atualização
        self.vlines = {} # Armazena as linhas verticais (cursores)

        # Configuração do pyqtgraph
        pg.setConfigOption("background", (30, 30, 30))
        pg.setConfigOption("foreground", "w")

        # Layout principal (Splitter horizontal)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setLayout(QVBoxLayout()) # Layout externo para conter o splitter
        self.layout().addWidget(main_splitter)
        self.layout().setContentsMargins(5, 5, 5, 5)

        # --- Painel Esquerdo (Seleção de Volta e Mapa 2D) ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Seleção de Volta
        lap_selection_layout = QHBoxLayout()
        lap_selection_layout.addWidget(QLabel("Selecionar Volta:"))
        self.lap_combo = QComboBox()
        self.lap_combo.setMinimumWidth(150)
        self.lap_combo.setEnabled(False)
        self.lap_combo.currentIndexChanged.connect(self._on_lap_selected)
        lap_selection_layout.addWidget(self.lap_combo)
        lap_selection_layout.addStretch()
        left_layout.addLayout(lap_selection_layout)

        # Mapa 2D
        track_frame = QFrame()
        track_frame.setFrameShape(QFrame.Shape.StyledPanel)
        track_layout = QVBoxLayout(track_frame)
        track_layout.addWidget(QLabel("Mapa 2D (Traçado colorido por Velocidade)"))
        self.track_view = TrackViewWidget()
        self.track_view.setMinimumHeight(300)
        track_layout.addWidget(self.track_view)
        left_layout.addWidget(track_frame, 1) # Ocupa espaço restante

        main_splitter.addWidget(left_panel)

        # --- Painel Direito (Gráficos Detalhados) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Layout para os gráficos
        self.charts_layout = pg.GraphicsLayoutWidget()
        right_layout.addWidget(self.charts_layout)

        # Adiciona os gráficos
        self._setup_charts()

        main_splitter.addWidget(right_panel)

        # Ajusta os tamanhos iniciais do splitter
        main_splitter.setSizes([400, 800])

        logger.info("AnalysisWidget inicializado.")

    def _setup_charts(self):
        """Configura os gráficos de telemetria detalhada."""
        plot_configs = [
            {"id": "speed", "title": "Velocidade (km/h)", "color": "#1f77b4"},
            {"id": "throttle", "title": "Acelerador (%)", "color": "#2ca02c"},
            {"id": "brake", "title": "Freio (%)", "color": "#d62728"},
            {"id": "steering", "title": "Volante (°)", "color": "#9467bd"},
            # Adicionar mais gráficos conforme necessário (RPM, Marcha, etc.)
        ]

        # Cria um proxy para sincronizar o eixo X e os cursores
        self.proxy = pg.SignalProxy(self.charts_layout.scene().sigMouseMoved, rateLimit=60, slot=self._mouse_moved)

        for i, config in enumerate(plot_configs):
            plot_id = config["id"]
            plot = self.charts_layout.addPlot(row=i, col=0, title=config["title"])
            plot.showGrid(x=True, y=True, alpha=0.3)
            plot.setLabel("bottom", "Distância (m)")
            plot.setXLink(plot_configs[0]["id"] if i > 0 else None) # Linka eixos X
            
            # Adiciona o item de plotagem (curva)
            curve = plot.plot(pen=pg.mkPen(config["color"], width=2))
            self.plot_items[plot_id] = curve

            # Adiciona a linha vertical (cursor)
            vline = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("y", style=Qt.PenStyle.DashLine))
            plot.addItem(vline, ignoreBounds=True)
            self.vlines[plot_id] = vline
            vline.setVisible(False) # Inicialmente invisível

            # Adiciona texto para exibir valor no cursor
            text_item = pg.TextItem(anchor=(0, 1))
            plot.addItem(text_item)
            text_item.setPos(0, plot.getAxis("left").range[1]) # Posição inicial
            text_item.setVisible(False)
            self.plot_items[f"{plot_id}_text"] = text_item

            # Armazena referência ao plot para acesso posterior
            self.plot_items[f"{plot_id}_plot"] = plot

        # Adiciona um espaço extra abaixo do último gráfico
        self.charts_layout.ci.layout.setRowStretchFactor(len(plot_configs), 1)

    def load_session_data(self, session_data: TelemetrySession):
        """Carrega os dados de uma sessão completa."""
        logger.info(f"Carregando dados da sessão para análise: {session_data.session_info.track} - {len(session_data.laps)} voltas")
        self.session_data = session_data
        self.current_lap_data = None
        self.lap_combo.clear()
        self.lap_combo.setEnabled(False)
        self._clear_plots()
        self.track_view.clear_view()

        if not session_data or not session_data.laps:
            logger.warning("Nenhuma volta encontrada na sessão.")
            QMessageBox.information(self, "Sem Voltas", "A sessão carregada não contém dados de voltas completas.")
            return

        # Popula o ComboBox com as voltas disponíveis
        lap_items = []
        for i, lap in enumerate(session_data.laps):
            lap_time_str = self._format_time(lap.lap_time_ms / 1000 if hasattr(lap, "lap_time_ms") else lap.lap_time if hasattr(lap, "lap_time") else 0)
            lap_items.append(f"Volta {lap.lap_number}: {lap_time_str}")
        
        self.lap_combo.addItems(lap_items)
        self.lap_combo.setEnabled(True)
        
        # Seleciona a primeira volta por padrão (se houver)
        if lap_items:
            self.lap_combo.setCurrentIndex(0)
            # O evento currentIndexChanged chamará _on_lap_selected
        else:
             logger.warning("ComboBox de voltas vazio após processamento.")

    def _on_lap_selected(self, index: int):
        """Chamado quando uma volta é selecionada no ComboBox."""
        if not self.session_data or index < 0 or index >= len(self.session_data.laps):
            self.current_lap_data = None
            self._clear_plots()
            self.track_view.clear_view()
            return

        self.current_lap_data = self.session_data.laps[index]
        logger.info(f"Volta {self.current_lap_data.lap_number} selecionada para análise.")
        self._update_plots()
        self._update_track_view()

    def _update_plots(self):
        """Atualiza os gráficos com os dados da volta selecionada."""
        self._clear_plots()
        if not self.current_lap_data or not self.current_lap_data.data_points:
            logger.warning("Dados da volta selecionada estão vazios.")
            return

        lap = self.current_lap_data
        points = lap.data_points

        try:
            # Suporte tanto para DataPoint (objeto) quanto dict (CSV puro)
            def get_val(p, attr, default=0.0):
                if hasattr(p, attr):
                    return getattr(p, attr, default)
                elif isinstance(p, dict):
                    return p.get(attr, default)
                return default

            distance = np.array([get_val(p, "distance_m") for p in points])
            speed_kmh = np.array([get_val(p, "speed_kmh") for p in points])
            throttle = np.array([get_val(p, "throttle") * 100 for p in points])
            brake = np.array([get_val(p, "brake") * 100 for p in points])
            steering = np.array([get_val(p, "steer_angle") for p in points])
        except Exception as e:
            logger.error(f"Erro ao extrair dados da volta {lap.lap_number} para plotagem", exc_info=True)
            QMessageBox.critical(self, "Erro de Dados", f"Não foi possível processar os dados da volta {lap.lap_number} para os gráficos: {e}")
            return

        # Atualiza os plots
        if "speed" in self.plot_items:
            self.plot_items["speed"].setData(distance, speed_kmh)
        if "throttle" in self.plot_items:
            self.plot_items["throttle"].setData(distance, throttle)
            self.plot_items["throttle_plot"].setYRange(0, 105)
        if "brake" in self.plot_items:
            self.plot_items["brake"].setData(distance, brake)
            self.plot_items["brake_plot"].setYRange(0, 105)
        if "steering" in self.plot_items:
            self.plot_items["steering"].setData(distance, steering)
            max_steer = max(abs(steering.min()), abs(steering.max())) if steering.size > 0 else 270
            self.plot_items["steering_plot"].setYRange(-max_steer * 1.1, max_steer * 1.1)

        max_distance = distance[-1] if distance.size > 0 else 1
        for plot_id in self.plot_items:
            if plot_id.endswith("_plot"):
                self.plot_items[plot_id].setXRange(0, max_distance)

        logger.debug(f"Gráficos atualizados para a volta {lap.lap_number}.")

    def _update_track_view(self):
        """Atualiza o mapa 2D com o traçado da volta selecionada."""
        self.track_view.clear_view()
        if not self.current_lap_data or not self.current_lap_data.data_points:
            return

        lap = self.current_lap_data
        points = lap.data_points

        try:
            def get_val(p, attr, default=0.0):
                if hasattr(p, attr):
                    return getattr(p, attr, default)
                elif isinstance(p, dict):
                    return p.get(attr, default)
                return default

            coords = np.array([[get_val(p, "pos_x"), get_val(p, "pos_z")] for p in points])
            speed_kmh = np.array([get_val(p, "speed_kmh") for p in points])
        except Exception as e:
            logger.error(f"Erro ao extrair coordenadas/velocidade da volta {lap.lap_number} para mapa 2D", exc_info=True)
            QMessageBox.critical(self, "Erro de Dados", f"Não foi possível processar os dados da volta {lap.lap_number} para o mapa 2D: {e}")
            return

        if coords.size == 0 or speed_kmh.size == 0 or coords.shape[0] != speed_kmh.shape[0]:
            logger.warning(f"Dados de coordenadas ou velocidade inválidos ou inconsistentes para a volta {lap.lap_number}.")
            return

        self.track_view.set_track_points(coords.tolist())
        self.track_view.set_lap_points(coords.tolist(), values=speed_kmh)
        self.track_view.update_current_position(None)
        self.track_view.highlight_point(None)

        logger.debug(f"Mapa 2D atualizado para a volta {lap.lap_number}.")

    def _clear_plots(self):
        """Limpa os dados de todos os gráficos."""
        for plot_id, item in self.plot_items.items():
            if isinstance(item, pg.PlotDataItem):
                item.clear()
            elif isinstance(item, pg.TextItem):
                item.setVisible(False)
        for vline in self.vlines.values():
            vline.setVisible(False)
        logger.debug("Gráficos de análise limpos.")

    def _mouse_moved(self, event):
        """Atualiza os cursores verticais e os valores exibidos."""
        if not self.current_lap_data or not self.current_lap_data.data_points:
            return

        pos = event[0] # Posição do mouse na cena
        
        # Verifica se o mouse está sobre algum dos plots
        plot_under_mouse = None
        for plot_id, plot in self.plot_items.items():
            if plot_id.endswith("_plot") and isinstance(plot, pg.PlotItem):
                 # Mapeia a posição da cena para as coordenadas do plot
                mouse_point = plot.vb.mapSceneToView(pos)
                if plot.vb.sceneBoundingRect().contains(pos):
                    plot_under_mouse = plot
                    x_coord = mouse_point.x()
                    break
        
        if plot_under_mouse is None:
            # Esconde cursores se o mouse não estiver sobre nenhum plot
            for vline in self.vlines.values():
                vline.setVisible(False)
            for plot_id, item in self.plot_items.items():
                 if plot_id.endswith("_text"):
                     item.setVisible(False)
            self.track_view.highlight_point(None) # Limpa destaque no mapa
            return

        # Atualiza a posição de todas as linhas verticais
        for vline in self.vlines.values():
            vline.setPos(x_coord)
            vline.setVisible(True)

        # Encontra o índice do ponto de dados mais próximo da coordenada X
        lap = self.current_lap_data
        points = lap.data_points
        distance_array = np.array([p.distance_m for p in points])
        if distance_array.size == 0:
            return
            
        # Encontra o índice mais próximo usando busca binária (ou np.searchsorted)
        index = np.searchsorted(distance_array, x_coord)
        # Garante que o índice esteja dentro dos limites
        index = np.clip(index, 0, len(points) - 1)

        # Pega o ponto de dados correspondente
        data_point = points[index]

        # Atualiza os textos com os valores do ponto
        self._update_cursor_text("speed", data_point.speed_kmh, "km/h")
        self._update_cursor_text("throttle", data_point.throttle * 100, "%")
        self._update_cursor_text("brake", data_point.brake * 100, "%")
        self._update_cursor_text("steering", data_point.steer_angle, "°")

        # Destaca o ponto correspondente no mapa 2D usando pos_x/pos_z
        pos_x = getattr(data_point, "pos_x", None)
        pos_z = getattr(data_point, "pos_z", None)
        if pos_x is not None and pos_z is not None:
            self.track_view.highlight_point([pos_x, pos_z])
        else:
            self.track_view.highlight_point(None)

    def _update_cursor_text(self, plot_id: str, value: float, unit: str):
        """Atualiza o texto de valor para um gráfico específico."""
        text_item_id = f"{plot_id}_text"
        plot_item_id = f"{plot_id}_plot"
        if text_item_id in self.plot_items and plot_item_id in self.plot_items:
            text_item = self.plot_items[text_item_id]
            plot = self.plot_items[plot_item_id]
            vline = self.vlines.get(plot_id)

            if text_item and plot and vline:
                text_item.setText(f"{value:.1f} {unit}")
                # Posiciona o texto perto do cursor vertical
                # Tenta posicionar à direita do cursor, ajustando para não sair da tela
                x_pos = vline.value()
                y_pos = plot.getAxis("left").range[1] # Topo do gráfico
                
                # Lógica simples para tentar manter o texto visível
                view_range_x = plot.vb.viewRange()[0]
                if x_pos > (view_range_x[0] + view_range_x[1]) / 2: # Se cursor está na metade direita
                    text_item.setAnchor((1, 1)) # Ancora no canto superior direito do texto
                else:
                    text_item.setAnchor((0, 1)) # Ancora no canto superior esquerdo
                    
                text_item.setPos(x_pos, y_pos)
                text_item.setVisible(True)

    def _format_time(self, time_seconds: Optional[float]) -> str:
        """Formata um tempo em segundos para MM:SS.mmm ou retorna '--'."""
        if time_seconds is None or time_seconds <= 0:
            return "--"
        minutes = int(time_seconds // 60)
        seconds = int(time_seconds % 60)
        milliseconds = int((time_seconds % 1) * 1000)
        return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

class TrackViewWidget(QWidget):
    """Widget para exibir o traçado da pista em 2D."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # ... inicialização existente ...
        self._track_points = []
        self._lap_points = []
        self._lap_values = []
        # Se desejar, adicione um canvas/plot aqui para desenhar

    def set_track_points(self, points):
        """Define os pontos do traçado da pista (lista de [x, y])."""
        self._track_points = points
        # Aqui você pode adicionar lógica para desenhar o traçado se desejar
        # Exemplo: atualizar um plot/canvas, se implementado

    def set_lap_points(self, points, values=None):
        """Define os pontos da volta e valores para colorir (ex: velocidade)."""
        self._lap_points = points
        self._lap_values = values if values is not None else []
        # Aqui você pode adicionar lógica para desenhar a volta colorida

    def clear_view(self):
        """Limpa a visualização do traçado da pista."""
        self._track_points = []
        self._lap_points = []
        self._lap_values = []
        # Limpe o canvas/plot se implementado

    def highlight_point(self, idx):
        """Destaca um ponto no mapa (ou limpa se idx=None)."""
        # Implemente a lógica de destaque ou deixe vazio para não dar erro
        pass

    def update_current_position(self, pos):
        """Atualiza a posição atual do carro no traçado (placeholder)."""
        # Implemente a lógica de atualização visual se desejar
        pass

# Exemplo de uso (para teste isolado)
if __name__ == '__main__':
    app = QApplication(sys.argv)
    logging.basicConfig(level=logging.DEBUG)

    # Cria dados de sessão de exemplo
    session = TelemetrySession(
        session_info=SessionInfo(game="ExampleSim", track="ExampleTrack", date="2024-01-01", time="12:00:00"),
        track_data=TrackData(track_name="ExampleTrack", length=5000, corners=[]),
        laps=[]
    )
    # Adiciona 2 voltas de exemplo
    for lap_num in range(1, 3):
        points = []
        for i in range(500):
            dist = i * 10
            angle = (dist / 5000) * 2 * np.pi * (1 + lap_num * 0.1) # Traçado ligeiramente diferente
            radius = 100 + (i / 50) * (1 + np.sin(angle * 3))
            pos_x = radius * np.cos(angle)
            pos_z = radius * np.sin(angle)
            speed_mps = 50 + 20 * np.sin(angle * 2) + lap_num * 5
            throttle = (np.sin(angle * 4) + 1) / 2
            brake = (np.cos(angle * 5) + 1) / 4
            steering = 90 * np.sin(angle * 6)
            points.append(DataPoint(
                timestamp=i * 0.1,
                distance=dist,
                position=[pos_x, 1.0, pos_z],
                speed=speed_mps,
                inputs={"throttle": throttle, "brake": brake, "steering": steering}
            ))
        session.laps.append(LapData(lap_number=lap_num, lap_time=100.0 + lap_num * 5, data_points=points))

    window = QMainWindow()
    analysis_widget = AnalysisWidget()
    window.setCentralWidget(analysis_widget)
    window.setWindowTitle("Teste AnalysisWidget")
    window.setGeometry(100, 100, 1200, 700)
    
    # Carrega os dados de exemplo
    analysis_widget.load_session_data(session)
    
    window.show()
    sys.exit(app.exec())

