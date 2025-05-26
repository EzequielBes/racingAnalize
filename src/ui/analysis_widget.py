# -*- coding: utf-8 -*-
"""Widget para análise detalhada de uma única volta."""

import logging
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSplitter, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
import pyqtgraph as pg

# Importa estruturas de dados
from src.core.standard_data import TelemetrySession, LapData, DataPoint

logger = logging.getLogger(__name__)

class AnalysisWidget(QWidget):
    """Widget que exibe o mapa 2D da pista e dados detalhados de uma volta selecionada."""

    # Sinal emitido quando um ponto de dados é selecionado no gráfico
    data_point_selected = pyqtSignal(object) # Emite o objeto DataPoint

    def __init__(self, parent=None):
        super().__init__(parent)
        self.telemetry_session: Optional[TelemetrySession] = None
        self.current_lap_data: Optional[LapData] = None

        # --- Configuração da UI ---
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)

        # Layout superior para controles (seleção de volta)
        self.controls_layout = QHBoxLayout()
        self.lap_selector_label = QLabel("Selecionar Volta:")
        self.lap_selector_combo = QComboBox()
        self.lap_selector_combo.setMinimumWidth(150)
        self.lap_selector_combo.setEnabled(False)
        self.lap_selector_combo.currentIndexChanged.connect(self._on_lap_selected)
        self.controls_layout.addWidget(self.lap_selector_label)
        self.controls_layout.addWidget(self.lap_selector_combo)
        self.controls_layout.addStretch()
        self.main_layout.addLayout(self.controls_layout)

        # Splitter para dividir mapa e gráficos/dados
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(self.splitter)

        # --- Painel Esquerdo: Mapa 2D ---
        self.map_widget = pg.PlotWidget(title="Mapa da Pista (Traçado da Volta)")
        self.map_plot_item = self.map_widget.getPlotItem()
        self.map_plot_item.setAspectLocked(True)
        self.map_plot_item.showGrid(x=True, y=True, alpha=0.3)
        self.map_plot_item.setLabel("left", "Posição Y (m)")
        self.map_plot_item.setLabel("bottom", "Posição X (m)")
        self.lap_path_item = pg.PlotDataItem(pen=pg.mkPen(color="w", width=2)) # Traçado base
        self.colored_lap_path_item = pg.ScatterPlotItem(size=5, pen=None) # Traçado colorido por velocidade
        self.cursor_item = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("y", width=1, style=Qt.PenStyle.DashLine))
        self.cursor_item_map = pg.ScatterPlotItem(size=10, symbol="x", pen="y", brush="y") # Marca no mapa
        self.map_plot_item.addItem(self.lap_path_item)
        self.map_plot_item.addItem(self.colored_lap_path_item)
        self.map_plot_item.addItem(self.cursor_item_map)
        self.splitter.addWidget(self.map_widget)

        # --- Painel Direito: Gráficos Detalhados e Métricas ---
        self.details_widget = QWidget()
        self.details_layout = QVBoxLayout(self.details_widget)
        self.details_layout.setContentsMargins(0, 0, 0, 0)

        # Gráfico de Velocidade vs Distância
        self.speed_plot_widget = pg.PlotWidget(title="Velocidade vs. Distância")
        self.speed_plot_item = self.speed_plot_widget.getPlotItem()
        self.speed_plot_item.showGrid(x=True, y=True, alpha=0.3)
        self.speed_plot_item.setLabel("left", "Velocidade (km/h)")
        self.speed_plot_item.setLabel("bottom", "Distância (m)")
        self.speed_curve = self.speed_plot_item.plot(pen=pg.mkPen("c", width=2))
        self.speed_plot_item.addItem(self.cursor_item) # Adiciona o mesmo cursor aqui
        self.details_layout.addWidget(self.speed_plot_widget)

        # Gráfico de Pedais vs Distância
        self.inputs_plot_widget = pg.PlotWidget(title="Pedais e Volante vs. Distância")
        self.inputs_plot_item = self.inputs_plot_widget.getPlotItem()
        self.inputs_plot_item.showGrid(x=True, y=True, alpha=0.3)
        self.inputs_plot_item.setLabel("left", "Input (% ou Graus)")
        self.inputs_plot_item.setLabel("bottom", "Distância (m)")
        self.inputs_plot_item.addLegend()
        self.throttle_curve = self.inputs_plot_item.plot(pen="g", name="Acelerador (%)")
        self.brake_curve = self.inputs_plot_item.plot(pen="r", name="Freio (%)")
        self.steer_curve = self.inputs_plot_item.plot(pen="y", name="Volante (deg)")
        # Linkar eixos X dos gráficos de detalhes
        self.inputs_plot_item.setXLink(self.speed_plot_item)
        self.inputs_plot_item.addItem(self.cursor_item) # Adiciona o mesmo cursor aqui
        self.details_layout.addWidget(self.inputs_plot_widget)

        # Área para exibir dados do ponto selecionado
        self.data_point_layout = QHBoxLayout()
        self.data_point_label = QLabel("Dados no Cursor:")
        self.data_point_dist_label = QLabel("Dist: --- m")
        self.data_point_speed_label = QLabel("Vel: --- km/h")
        self.data_point_gear_label = QLabel("Marcha: -")
        self.data_point_rpm_label = QLabel("RPM: ----")
        self.data_point_throttle_label = QLabel("Acel: --%")
        self.data_point_brake_label = QLabel("Freio: --%")
        self.data_point_steer_label = QLabel("Vol: ---°")
        self.data_point_layout.addWidget(self.data_point_label)
        self.data_point_layout.addWidget(self.data_point_dist_label)
        self.data_point_layout.addWidget(self.data_point_speed_label)
        self.data_point_layout.addWidget(self.data_point_gear_label)
        self.data_point_layout.addWidget(self.data_point_rpm_label)
        self.data_point_layout.addWidget(self.data_point_throttle_label)
        self.data_point_layout.addWidget(self.data_point_brake_label)
        self.data_point_layout.addWidget(self.data_point_steer_label)
        self.data_point_layout.addStretch()
        self.details_layout.addLayout(self.data_point_layout)

        self.splitter.addWidget(self.details_widget)
        self.splitter.setSizes([int(self.width() * 0.4), int(self.width() * 0.6)]) # Tamanho inicial

        # --- Conexões de Sinais ---
        # Conecta o movimento do mouse nos gráficos de detalhes ao cursor
        self.speed_plot_widget.scene().sigMouseMoved.connect(self._mouse_moved_details_plot)
        self.inputs_plot_widget.scene().sigMouseMoved.connect(self._mouse_moved_details_plot)

        logger.info("AnalysisWidget inicializado.")

    def load_session_data(self, session_data: TelemetrySession):
        """Carrega os dados de uma sessão de telemetria no widget."""
        logger.info(f"Carregando dados da sessão: {session_data.session_info.track} - {session_data.session_info.date}")
        self.telemetry_session = session_data
        self.current_lap_data = None
        self.lap_selector_combo.clear()

        if not session_data or not session_data.laps:
            logger.warning("Sessão de telemetria vazia ou sem voltas.")
            self.lap_selector_combo.setEnabled(False)
            self._clear_plots()
            return

        # Popula o seletor de voltas
        valid_laps = [lap for lap in session_data.laps if lap.is_valid and lap.data_points]
        if not valid_laps:
             logger.warning("Nenhuma volta válida com pontos de dados encontrada na sessão.")
             self.lap_selector_combo.setEnabled(False)
             self._clear_plots()
             return

        for i, lap in enumerate(valid_laps):
            time_str = f"{lap.lap_time_ms / 1000:.3f}"
            self.lap_selector_combo.addItem(f"Volta {lap.lap_number} ({time_str}s)", userData=i) # Armazena índice na lista filtrada

        self.lap_selector_combo.setEnabled(True)
        # Seleciona a primeira volta válida por padrão
        if self.lap_selector_combo.count() > 0:
            self.lap_selector_combo.setCurrentIndex(0)
            self._on_lap_selected(0)
        else:
             self._clear_plots()

    def _on_lap_selected(self, index: int):
        """Chamado quando uma volta é selecionada no ComboBox."""
        if not self.telemetry_session or not self.telemetry_session.laps:
            return

        user_data_index = self.lap_selector_combo.itemData(index)
        if user_data_index is None:
            self._clear_plots()
            return

        valid_laps = [lap for lap in self.telemetry_session.laps if lap.is_valid and lap.data_points]
        if 0 <= user_data_index < len(valid_laps):
            self.current_lap_data = valid_laps[user_data_index]
            logger.info(f"Volta {self.current_lap_data.lap_number} selecionada.")
            self._update_plots()
        else:
            logger.warning(f"Índice de volta selecionado inválido: {user_data_index}")
            self._clear_plots()

    def _clear_plots(self):
        """Limpa todos os gráficos e dados exibidos."""
        self.lap_path_item.setData([], [])
        self.colored_lap_path_item.setData([], [])
        self.speed_curve.setData([], [])
        self.throttle_curve.setData([], [])
        self.brake_curve.setData([], [])
        self.steer_curve.setData([], [])
        self.cursor_item.setPos(0)
        self.cursor_item_map.setData([], [])
        self._update_data_point_display(None)
        self.current_lap_data = None

    def _update_plots(self):
        """Atualiza os gráficos com os dados da volta selecionada."""
        if not self.current_lap_data or not self.current_lap_data.data_points:
            self._clear_plots()
            return

        lap = self.current_lap_data
        data = lap.data_points

        # Extrai dados para plotagem (ignora pontos com NaN por enquanto)
        # Idealmente, tratar NaNs com interpolação ou removendo linhas
        try:
            dist = np.array([dp.distance_m for dp in data if dp.distance_m is not None and not np.isnan(dp.distance_m)])
            pos_x = np.array([dp.pos_x for dp in data if dp.pos_x is not None and not np.isnan(dp.pos_x)])
            pos_y = np.array([dp.pos_y for dp in data if dp.pos_y is not None and not np.isnan(dp.pos_y)])
            speed = np.array([dp.speed_kmh for dp in data if dp.speed_kmh is not None and not np.isnan(dp.speed_kmh)])
            throttle = np.array([dp.throttle * 100 for dp in data if dp.throttle is not None and not np.isnan(dp.throttle)])
            brake = np.array([dp.brake * 100 for dp in data if dp.brake is not None and not np.isnan(dp.brake)])
            steer = np.array([dp.steer_angle for dp in data if dp.steer_angle is not None and not np.isnan(dp.steer_angle)])

            # Verifica se os arrays têm tamanhos consistentes após remover NaNs
            # Esta é uma simplificação; o ideal é alinhar os dados
            min_len = min(len(dist), len(pos_x), len(pos_y), len(speed), len(throttle), len(brake), len(steer))
            if min_len < len(data) * 0.9: # Se perdeu muitos dados
                 logger.warning(f"Muitos NaNs encontrados na volta {lap.lap_number}, plotagem pode estar incompleta.")
            if min_len == 0:
                 logger.error(f"Nenhum dado válido para plotar na volta {lap.lap_number}.")
                 self._clear_plots()
                 return

            # Trunca todos os arrays para o menor tamanho válido
            dist = dist[:min_len]
            pos_x = pos_x[:min_len]
            pos_y = pos_y[:min_len]
            speed = speed[:min_len]
            throttle = throttle[:min_len]
            brake = brake[:min_len]
            steer = steer[:min_len]

        except Exception as e:
            logger.exception(f"Erro ao extrair dados da volta {lap.lap_number}: {e}")
            self._clear_plots()
            return

        # --- Atualiza Mapa 2D ---
        self.lap_path_item.setData(pos_x, pos_y)
        # Colore o traçado pela velocidade
        cmap = pg.colormap.get("viridis") # Ou "plasma", "inferno", etc.
        brushes = cmap.map(speed / max(speed) if max(speed) > 0 else 0, "qcolor")
        self.colored_lap_path_item.setData(pos_x, pos_y, brush=brushes)
        # Ajusta limites do mapa automaticamente (pode precisar de ajuste manual depois)
        # self.map_plot_item.autoRange()

        # --- Atualiza Gráficos de Detalhes ---
        self.speed_curve.setData(dist, speed)
        self.throttle_curve.setData(dist, throttle)
        self.brake_curve.setData(dist, brake)
        self.steer_curve.setData(dist, steer)

        # Ajusta limites dos gráficos de detalhes
        # self.speed_plot_item.autoRange()
        # self.inputs_plot_item.autoRange()
        # Define limites Y para inputs para melhor visualização
        self.inputs_plot_item.setYRange(-100, 110) # Ex: -90 a 90 para volante, 0 a 100 para pedais

        # Reseta a posição do cursor e dados exibidos
        if dist.size > 0:
            self.cursor_item.setBounds((dist.min(), dist.max()))
            self.cursor_item.setPos(dist.min())
            self._update_cursor(dist.min())
        else:
             self._update_data_point_display(None)
             self.cursor_item_map.setData([], [])

    def _mouse_moved_details_plot(self, pos):
        """Chamado quando o mouse se move sobre os gráficos de detalhes."""
        if not self.speed_plot_item.sceneBoundingRect().contains(pos):
            return # Ignora se o mouse estiver fora da área do gráfico

        mouse_point = self.speed_plot_item.vb.mapSceneToView(pos)
        x_pos = mouse_point.x()
        self._update_cursor(x_pos)

    def _update_cursor(self, distance_m: float):
        """Move o cursor e atualiza os dados exibidos para a distância dada."""
        if not self.current_lap_data or not self.current_lap_data.data_points:
            return

        self.cursor_item.setPos(distance_m)

        # Encontra o índice do ponto de dados mais próximo da distância do cursor
        data = self.current_lap_data.data_points
        dist_array = np.array([dp.distance_m for dp in data if dp.distance_m is not None])
        if dist_array.size == 0:
            self._update_data_point_display(None)
            self.cursor_item_map.setData([], [])
            return

        # Encontra o índice mais próximo usando busca binária ou argmin
        idx = np.argmin(np.abs(dist_array - distance_m))

        # Garante que o índice corresponde a um ponto válido na lista original `data`
        # Isso é necessário se filtramos NaNs ao criar dist_array
        # Simplificação: Assume que dist_array tem os mesmos índices que `data` por enquanto
        # Uma solução robusta mapearia os índices.
        if 0 <= idx < len(data):
            selected_dp = data[idx]
            self._update_data_point_display(selected_dp)
            # Atualiza posição do cursor no mapa
            if selected_dp.pos_x is not None and selected_dp.pos_y is not None:
                 self.cursor_item_map.setData([selected_dp.pos_x], [selected_dp.pos_y])
            else:
                 self.cursor_item_map.setData([], [])
            # Emite o sinal
            self.data_point_selected.emit(selected_dp)
        else:
            self._update_data_point_display(None)
            self.cursor_item_map.setData([], [])

    def _update_data_point_display(self, dp: Optional[DataPoint]):
        """Atualiza os labels com os dados do DataPoint fornecido."""
        if dp:
            self.data_point_dist_label.setText(f"Dist: {dp.distance_m:.1f} m" if dp.distance_m is not None else "Dist: --- m")
            self.data_point_speed_label.setText(f"Vel: {dp.speed_kmh:.1f} km/h" if dp.speed_kmh is not None else "Vel: --- km/h")
            self.data_point_gear_label.setText(f"Marcha: {dp.gear}" if dp.gear is not None else "Marcha: -")
            self.data_point_rpm_label.setText(f"RPM: {int(dp.rpm)}" if dp.rpm is not None else "RPM: ----")
            self.data_point_throttle_label.setText(f"Acel: {int(dp.throttle*100)}%" if dp.throttle is not None else "Acel: --%")
            self.data_point_brake_label.setText(f"Freio: {int(dp.brake*100)}%" if dp.brake is not None else "Freio: --%")
            self.data_point_steer_label.setText(f"Vol: {dp.steer_angle:.1f}°" if dp.steer_angle is not None else "Vol: ---°")
        else:
            self.data_point_dist_label.setText("Dist: --- m")
            self.data_point_speed_label.setText("Vel: --- km/h")
            self.data_point_gear_label.setText("Marcha: -")
            self.data_point_rpm_label.setText("RPM: ----")
            self.data_point_throttle_label.setText("Acel: --%")
            self.data_point_brake_label.setText("Freio: --%")
            self.data_point_steer_label.setText("Vol: ---°")

# Exemplo de uso (requer execução dentro de uma aplicação QApplication)
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication

    # Dados de exemplo (simulados)
    def create_dummy_session():
        session_info = SessionInfo(game="Dummy", track="DummyTrack", vehicle="DummyCar", driver="DummyDriver", session_type="Practice", date=datetime.now())
        track_data = TrackData(track_name="DummyTrack", length_m=5000, sector_markers_m=[1500, 3500])
        laps = []
        num_points = 500
        for lap_num in range(1, 4):
            dps = []
            dist_lap = track_data.length_m * lap_num
            for i in range(num_points):
                dist = (dist_lap - track_data.length_m) + (i / num_points) * track_data.length_m
                angle = (dist / track_data.length_m) * 2 * np.pi
                radius = 1000 / (2 * np.pi)
                dp = DataPoint(
                    timestamp_ms=int((lap_num * 60 + i * 0.1) * 1000),
                    distance_m=dist,
                    speed_kmh=150 + 50 * np.sin(angle * 2) + np.random.rand() * 10,
                    rpm=4000 + 2000 * np.sin(angle * 4) + np.random.rand() * 500,
                    gear=int(3 + 2 * np.sin(angle * 4)),
                    throttle=0.7 + 0.3 * np.sin(angle * 2 + np.pi/2),
                    brake=0.1 + 0.1 * np.cos(angle * 2 + np.pi/2),
                    steer_angle=30 * np.cos(angle),
                    clutch=0.0,
                    pos_x=radius * np.cos(angle),
                    pos_y=radius * np.sin(angle),
                    pos_z=0,
                    lap_number=lap_num,
                    sector=1 + int(dist / (track_data.length_m / 3)),
                    # ... outros campos
                )
                dps.append(dp)
            lap_data = LapData(lap_number=lap_num, lap_time_ms=int(60000 + np.random.rand()*5000), sector_times_ms=[], is_valid=True, data_points=dps)
            laps.append(lap_data)
        return TelemetrySession(session_info=session_info, track_data=track_data, laps=laps)

    app = QApplication(sys.argv)
    main_window = QWidget() # Simula janela principal
    layout = QVBoxLayout(main_window)
    analysis_widget = AnalysisWidget()
    layout.addWidget(analysis_widget)

    dummy_session = create_dummy_session()
    analysis_widget.load_session_data(dummy_session)

    main_window.setWindowTitle("Teste AnalysisWidget")
    main_window.setGeometry(100, 100, 1200, 700)
    main_window.show()
    sys.exit(app.exec())

