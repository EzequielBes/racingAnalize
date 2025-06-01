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
            lap_time_str = self._format_time(lap.lap_time)
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

        # Extrai dados para os eixos
        try:
            distance = np.array([p.distance for p in points])
            speed_kmh = np.array([p.speed * 3.6 for p in points]) # Converte m/s para km/h
            throttle = np.array([p.inputs.get("throttle", 0) * 100 for p in points])
            brake = np.array([p.inputs.get("brake", 0) * 100 for p in points])
            steering = np.array([p.inputs.get("steering", 0) for p in points]) # Assume que já está em graus
        except Exception as e:
            logger.error(f"Erro ao extrair dados da volta {lap.lap_number} para plotagem", exc_info=True)
            QMessageBox.critical(self, "Erro de Dados", f"Não foi possível processar os dados da volta {lap.lap_number} para os gráficos: {e}")
            return

        # Atualiza os plots
        if "speed" in self.plot_items:
            self.plot_items["speed"].setData(distance, speed_kmh)
        if "throttle" in self.plot_items:
            self.plot_items["throttle"].setData(distance, throttle)
            self.plot_items["throttle_plot"].setYRange(0, 105) # Garante range 0-100%
        if "brake" in self.plot_items:
            self.plot_items["brake"].setData(distance, brake)
            self.plot_items["brake_plot"].setYRange(0, 105)
        if "steering" in self.plot_items:
            self.plot_items["steering"].setData(distance, steering)
            # Ajusta o range do volante dinamicamente ou usa um padrão
            max_steer = max(abs(steering.min()), abs(steering.max())) if steering.size > 0 else 270
            self.plot_items["steering_plot"].setYRange(-max_steer * 1.1, max_steer * 1.1)

        # Ajusta o range X de todos os plots para a distância total da volta
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
            # Extrai coordenadas X, Z (ou Y dependendo do jogo) e velocidade
            coords = np.array([[p.position[0], p.position[2]] for p in points if len(p.position) >= 3]) # Assume X, Z
            speed_kmh = np.array([p.speed * 3.6 for p in points])
        except Exception as e:
            logger.error(f"Erro ao extrair coordenadas/velocidade da volta {lap.lap_number} para mapa 2D", exc_info=True)
            QMessageBox.critical(self, "Erro de Dados", f"Não foi possível processar os dados da volta {lap.lap_number} para o mapa 2D: {e}")
            return

        if coords.size == 0 or speed_kmh.size == 0 or coords.shape[0] != speed_kmh.shape[0]:
            logger.warning(f"Dados de coordenadas ou velocidade inválidos ou inconsistentes para a volta {lap.lap_number}.")
            return

        # Define os pontos do traçado (usando os pontos da volta)
        self.track_view.set_track_points(coords.tolist())
        # Define os pontos da volta e colore por velocidade
        self.track_view.set_lap_points(coords.tolist(), values=speed_kmh)
        # Não define posição atual ou ponto destacado para análise estática
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
        distance_array = np.array([p.distance for p in points])
        if distance_array.size == 0:
            return
            
        # Encontra o índice mais próximo usando busca binária (ou np.searchsorted)
        index = np.searchsorted(distance_array, x_coord)
        # Garante que o índice esteja dentro dos limites
        index = np.clip(index, 0, len(points) - 1)

        # Pega o ponto de dados correspondente
        data_point = points[index]

        # Atualiza os textos com os valores do ponto
        self._update_cursor_text("speed", data_point.speed * 3.6, "km/h")
        self._update_cursor_text("throttle", data_point.inputs.get("throttle", 0) * 100, "%")
        self._update_cursor_text("brake", data_point.inputs.get("brake", 0) * 100, "%")
        self._update_cursor_text("steering", data_point.inputs.get("steering", 0), "°")

        # Destaca o ponto correspondente no mapa 2D
        if len(data_point.position) >= 3:
            map_point = [data_point.position[0], data_point.position[2]] # Assume X, Z
            self.track_view.highlight_point(map_point)
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

