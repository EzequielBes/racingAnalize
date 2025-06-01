# -*- coding: utf-8 -*-
"""Widget para visualização e comparação interativa de voltas."""

import logging
from typing import List, Dict, Any, Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QMessageBox
from PyQt6.QtCore import pyqtSignal, Qt, QPointF

import pyqtgraph as pg

from src.core.standard_data import TelemetrySession # Importa a estrutura completa
from src.processing_analysis.telemetry_processor import TelemetryProcessor
from src.processing_analysis.lap_comparator import LapComparator

logger = logging.getLogger(__name__)

class ComparisonWidget(QWidget):
    """Widget para comparar duas voltas interativamente."""

    # Sinal para indicar que uma nova comparação foi realizada (opcional)
    # comparison_updated = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_session: Optional[TelemetrySession] = None
        self.processed_session_data: Optional[Dict[str, Any]] = None # Armazena dados processados pelo TelemetryProcessor
        self.lap1_data_processed: Optional[Dict[str, Any]] = None
        self.lap2_data_processed: Optional[Dict[str, Any]] = None
        self.comparison_results: Optional[Dict[str, Any]] = None
        self._setup_ui()
        logger.info("ComparisonWidget inicializado.")

    def _setup_ui(self):
        """Configura a interface gráfica do widget."""
        layout = QVBoxLayout(self)

        # --- Controles --- 
        control_layout = QHBoxLayout()
        self.lap1_selector = QComboBox()
        self.lap1_selector.setPlaceholderText("Selecione a Volta 1")
        self.lap2_selector = QComboBox()
        self.lap2_selector.setPlaceholderText("Selecione a Volta 2")
        self.compare_button = QPushButton("Comparar Voltas")
        self.compare_button.clicked.connect(self.run_comparison)
        self.compare_button.setEnabled(False) # Desabilitado até carregar dados

        control_layout.addWidget(QLabel("Volta 1:"))
        control_layout.addWidget(self.lap1_selector)
        control_layout.addWidget(QLabel("Volta 2:"))
        control_layout.addWidget(self.lap2_selector)
        control_layout.addWidget(self.compare_button)
        layout.addLayout(control_layout)

        # --- Área de Plots --- 
        plot_layout = QVBoxLayout() # Usar QVBoxLayout para empilhar

        # Plot 1: Mapa da Pista com Traçados Sobrepostos
        self.track_plot_widget = pg.PlotWidget(title="Traçado da Pista")
        self.track_plot_item = self.track_plot_widget.getPlotItem()
        self.track_plot_item.setAspectLocked(True)
        self.lap1_trace_plot = pg.PlotDataItem(pen=pg.mkPen("blue", width=2), name="Volta 1")
        self.lap2_trace_plot = pg.PlotDataItem(pen=pg.mkPen("red", width=2), name="Volta 2")
        self.track_plot_item.addItem(self.lap1_trace_plot)
        self.track_plot_item.addItem(self.lap2_trace_plot)
        self.track_plot_item.addLegend()
        plot_layout.addWidget(self.track_plot_widget)

        # Plot 2: Gráficos de Canais (Velocidade, Throttle, Brake, etc.) vs Distância
        self.channels_plot_widget = pg.PlotWidget(title="Canais vs Distância")
        self.channels_plot_item = self.channels_plot_widget.getPlotItem()
        self.channels_plot_item.addLegend()
        self.channel_plots = {} # Armazena os PlotDataItems dos canais
        plot_layout.addWidget(self.channels_plot_widget)

        # Plot 3: Gráfico de Delta Time vs Distância
        self.delta_plot_widget = pg.PlotWidget(title="Delta Time (Volta 2 - Volta 1)")
        self.delta_plot_item = self.delta_plot_widget.getPlotItem()
        self.delta_time_plot = pg.PlotDataItem(pen=pg.mkPen("green", width=2))
        self.delta_plot_item.addItem(self.delta_time_plot)
        self.delta_plot_item.addLine(y=0, pen=pg.mkPen("gray", style=Qt.PenStyle.DashLine))
        plot_layout.addWidget(self.delta_plot_widget)

        layout.addLayout(plot_layout)

        # --- Interatividade (Cursores Sincronizados) ---
        # Linhas verticais para indicar posição
        self.vLine_track = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("yellow", style=Qt.PenStyle.DashLine))
        self.vLine_channels = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("yellow", style=Qt.PenStyle.DashLine))
        self.vLine_delta = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("yellow", style=Qt.PenStyle.DashLine))
        # Adiciona apenas aos plots de canais e delta por enquanto
        self.channels_plot_widget.addItem(self.vLine_channels, ignoreBounds=True)
        self.delta_plot_widget.addItem(self.vLine_delta, ignoreBounds=True)

        # Conectar sinais de movimento do mouse para sincronizar cursores
        # Usar proxy para limitar a taxa de atualização
        self.proxy = pg.SignalProxy(self.channels_plot_widget.scene().sigMouseMoved, rateLimit=60, slot=self._mouse_moved)
        # self.channels_plot_widget.scene().sigMouseMoved.connect(self._mouse_moved) # Conexão direta se proxy não for usado

    def load_processed_session(self, processed_session_data, session_info):
        """Carrega dados de uma sessão JÁ PROCESSADA pelo TelemetryProcessor."""
        logger.info("Carregando dados de sessão processada no ComparisonWidget.")
        self.processed_session_data = processed_session_data
        self.session_info = session_info

        valid_laps_processed = [lap for lap in self.processed_session_data.laps if lap.is_valid]
        lap_numbers = sorted(lap.lap_number for lap in valid_laps_processed)
        self.lap1_selector.clear()
        self.lap2_selector.clear()
        for lap_num in lap_numbers:
            lap = next((l for l in valid_laps_processed if l.lap_number == lap_num), None)
            lap_time_ms = lap.lap_time_ms if lap else 0
            lap_label = f"Volta {lap_num} ({lap_time_ms / 1000:.3f}s)"
            self.lap1_selector.addItem(lap_label, userData=lap_num)
            self.lap2_selector.addItem(lap_label, userData=lap_num)

        if len(lap_numbers) >= 2:
            self.compare_button.setEnabled(True)
            self.lap1_selector.setCurrentIndex(0)
            self.lap2_selector.setCurrentIndex(1)
            logger.info(f"{len(lap_numbers)} voltas válidas carregadas. Comparação habilitada.")
        elif len(lap_numbers) == 1:
            self.lap1_selector.setCurrentIndex(0)
            self.lap2_selector.setCurrentIndex(0)
            logger.info("Apenas uma volta válida carregada. Comparação desabilitada.")
        else:
            logger.info("Nenhuma volta válida carregada.")

    def run_comparison(self):
        """Executa a comparação com base nas voltas selecionadas."""
        lap1_num = self.lap1_selector.currentData()
        lap2_num = self.lap2_selector.currentData()

        if lap1_num is None or lap2_num is None:
            QMessageBox.warning(self, "Seleção Inválida", "Selecione duas voltas para comparar.")
            return

        if lap1_num == lap2_num:
            QMessageBox.warning(self, "Seleção Inválida", "Selecione duas voltas diferentes para comparar.")
            return

        if not self.processed_session_data or not hasattr(self.processed_session_data, "laps"):
            QMessageBox.critical(self, "Erro Interno", "Dados da sessão processada não estão disponíveis.")
            return

        logger.info(f"Iniciando comparação entre Volta {lap1_num} e Volta {lap2_num}")

        valid_laps_processed = [lap for lap in self.processed_session_data.laps if lap.is_valid]
        lap1 = next((l for l in valid_laps_processed if l.lap_number == lap1_num), None)
        lap2 = next((l for l in valid_laps_processed if l.lap_number == lap2_num), None)

        if not lap1 or not lap2:
            logger.error(f"Dados processados não encontrados para as voltas {lap1_num} ou {lap2_num}.")
            QMessageBox.critical(self, "Erro Interno", f"Não foi possível encontrar os dados processados para as voltas {lap1_num} ou {lap2_num}.")
            return

        try:
            comparator = LapComparator(lap1, lap2)
            self.comparison_results = comparator.compare_laps()

            if self.comparison_results:
                logger.info("Comparação concluída. Atualizando plots.")
                self._update_plots()
            else:
                logger.error("Falha ao gerar resultados da comparação.")
                QMessageBox.critical(self, "Erro de Comparação", "Não foi possível gerar os resultados da comparação. Verifique os logs.")

        except Exception as e:
            logger.exception(f"Erro durante a comparação das voltas: {e}")
            QMessageBox.critical(self, "Erro de Comparação", f"Ocorreu um erro ao comparar as voltas:\n{e}\nVerifique os logs para detalhes.")

    def _update_plots(self):
        """Atualiza os gráficos com os resultados da comparação."""
        if not self.comparison_results:
            self._clear_plots()
            return

        common_distance = self.comparison_results.get("common_distance")
        if not common_distance or len(common_distance) == 0:
             logger.warning("Distância comum inválida ou vazia nos resultados.")
             self._clear_plots()
             return

        self._clear_plots()

        # Atualizar Plot de Traçado
        trace1 = self.comparison_results.get("traces", {}).get("lap1_xy")
        trace2 = self.comparison_results.get("traces", {}).get("lap2_xy")
        if trace1:
            try:
                x1, y1 = zip(*trace1)
                self.lap1_trace_plot.setData(x=list(x1), y=list(y1))
            except Exception as e:
                 logger.error(f"Erro ao plotar traçado da volta 1: {e}")
        if trace2:
            try:
                x2, y2 = zip(*trace2)
                self.lap2_trace_plot.setData(x=list(x2), y=list(y2))
            except Exception as e:
                 logger.error(f"Erro ao plotar traçado da volta 2: {e}")

        # Atualizar Plot de Canais
        channels_data = self.comparison_results.get("channels", {})
        pens = [pg.mkPen("blue"), pg.mkPen("red"), pg.mkPen("cyan"), pg.mkPen("magenta"), pg.mkPen("yellow"), pg.mkPen("white")]
        pen_idx = 0
        self.channels_plot_item.clear()
        self.channels_plot_item.addLegend()
        self.channel_plots.clear()

        for channel_name, data in channels_data.items():
            lap1_values = data.get("lap1")
            lap2_values = data.get("lap2")
            if lap1_values and lap2_values and len(lap1_values) == len(common_distance) and len(lap2_values) == len(common_distance):
                try:
                    pen1 = pens[pen_idx % len(pens)]
                    plot1 = self.channels_plot_item.plot(common_distance, lap1_values, pen=pen1, name=f"{channel_name} V1")
                    self.channel_plots[f"{channel_name}_lap1"] = plot1
                    pen_idx += 1

                    pen2 = pens[pen_idx % len(pens)]
                    plot2 = self.channels_plot_item.plot(common_distance, lap2_values, pen=pen2, name=f"{channel_name} V2")
                    self.channel_plots[f"{channel_name}_lap2"] = plot2
                    pen_idx += 1
                except Exception as e:
                     logger.error(f"Erro ao plotar canal '{channel_name}': {e}")
            else:
                 logger.warning(f"Dados do canal '{channel_name}' inválidos ou com tamanho incorreto para plotagem.")

        # Atualizar Plot de Delta Time
        delta_time = self.comparison_results.get("delta_time_ms")
        if delta_time and len(delta_time) == len(common_distance):
            try:
                self.delta_time_plot.setData(x=common_distance, y=delta_time)
            except Exception as e:
                 logger.error(f"Erro ao plotar delta time: {e}")
        else:
             logger.warning("Dados de delta time inválidos ou com tamanho incorreto.")
             self.delta_time_plot.clear()

    def _clear_plots(self):
         """Limpa todos os dados dos plots."""
         self.lap1_trace_plot.clear()
         self.lap2_trace_plot.clear()
         # Limpa os itens do plot de canais e o dicionário de referência
         if hasattr(self, 'channels_plot_item'):
              self.channels_plot_item.clear()
              self.channels_plot_item.addLegend() # Readiciona a legenda
         self.channel_plots.clear()
         self.delta_time_plot.clear()
         logger.debug("Plots de comparação limpos.")

    def _mouse_moved(self, event):
        """Callback para movimento do mouse sobre os plots (para cursor sincronizado)."""
        # Obtém a posição do mouse na cena do plot de canais
        pos_tuple = event # O evento pode ser uma tupla (x, y) ou QPointF dependendo da versão/config
        # Garante que temos um QPointF para o método contains
        if isinstance(pos_tuple, tuple) and len(pos_tuple) == 2:
            pos_qpoint = QPointF(pos_tuple[0], pos_tuple[1])
        elif isinstance(pos_tuple, QPointF):
            pos_qpoint = pos_tuple
        else:
            # Se o formato for inesperado, ignora o evento
            return

        if self.channels_plot_widget.sceneBoundingRect().contains(pos_qpoint):
            # Mapeia a posição da cena para as coordenadas da vista (dados)
            mouse_point = self.channels_plot_item.vb.mapSceneToView(pos_qpoint)
            x_pos = mouse_point.x() # Coordenada X (geralmente distância)

            # Atualiza a posição das linhas verticais nos plots de canais e delta
            self.vLine_channels.setPos(x_pos)
            self.vLine_delta.setPos(x_pos)

            # TODO: Atualizar a linha/marcador no plot de traçado
            # Isso requer encontrar o índice correspondente à distância x_pos
            # e depois obter as coordenadas X, Y daquele índice.
            # Exemplo:
            # if self.comparison_results and 'common_distance' in self.comparison_results:
            #     common_distance = np.array(self.comparison_results['common_distance'])
            #     index = np.abs(common_distance - x_pos).argmin() # Encontra índice mais próximo
            #     if 'traces' in self.comparison_results:
            #         trace1 = self.comparison_results['traces'].get('lap1_xy')
            #         if trace1 and index < len(trace1):
            #             track_x, track_y = trace1[index]
            #             # Atualizar um marcador em vez de uma linha infinita pode ser melhor
            #             # self.vLine_track.setPos(track_x) # Não funciona bem com linha infinita
            #             # Exemplo com marcador (requer criar o marcador em _setup_ui):
            #             # self.track_marker.setData(pos=[(track_x, track_y)])

# Para teste local (requer ambiente gráfico e dados mock)
# if __name__ == '__main__':
#     import sys
#     app = QApplication(sys.argv)
#
#     # Criar mock session data (já processada)
#     mock_processed_data = {
#         "laps": {
#             1: {
#                 'lap_number': 1, 'lap_time_ms': 90000,
#                 'distance_m': list(np.linspace(0, 4000, 100)),
#                 'timestamps_ms': list(np.linspace(0, 90000, 100)),
#                 'speed_kmh': list(150 + 50 * np.sin(np.linspace(0, 2 * np.pi, 100))),
#                 'throttle': list(np.random.rand(100)), 'brake': list(np.random.rand(100) * 0.5),
#                 'driver_trace_xy': list(zip(np.linspace(0, 1000, 100), 100 * np.sin(np.linspace(0, 4 * np.pi, 100))))
#             },
#             2: {
#                 'lap_number': 2, 'lap_time_ms': 92000,
#                 'distance_m': list(np.linspace(0, 4000, 110)), # Volta ligeiramente diferente
#                 'timestamps_ms': list(np.linspace(0, 92000, 110)),
#                 'speed_kmh': list(145 + 55 * np.sin(np.linspace(0, 2 * np.pi, 110))),
#                 'throttle': list(np.random.rand(110)), 'brake': list(np.random.rand(110) * 0.6),
#                 'driver_trace_xy': list(zip(np.linspace(0, 1000, 110), 110 * np.sin(np.linspace(0, 4 * np.pi, 110) + 0.1)))
#             }
#         }
#     }
#     mock_session_info = {'game': 'Mock', 'track': 'MockTrack'}
#
#     widget = ComparisonWidget()
#     widget.load_processed_session(mock_processed_data, mock_session_info)
#     widget.show()
#     widget.run_comparison() # Roda a comparação inicial
#     sys.exit(app.exec())

