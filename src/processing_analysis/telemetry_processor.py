# -*- coding: utf-8 -*-
"""Módulo responsável pelo processamento e análise dos dados de telemetria padronizados."""

import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd # Usar pandas pode facilitar manipulações

# Importa as estruturas de dados padronizadas
from src.core.standard_data import TelemetrySession, LapData, DataPoint, TrackData

logger = logging.getLogger(__name__)

class TelemetryProcessor:
    """Processa e analisa dados de uma sessão de telemetria padronizada."""

    def __init__(self, session: TelemetrySession):
        """Inicializa o processador com uma sessão de telemetria."""
        if not isinstance(session, TelemetrySession):
            raise TypeError("Input must be a TelemetrySession object")
        self.session = session
        self.processed_data = {}
        logger.info(f"TelemetryProcessor inicializado para a sessão: {session.session_info.game} - {session.session_info.track}")

    def process_all_laps(self):
        """Processa todas as voltas válidas na sessão."""
        logger.info(f"Iniciando processamento de {len(self.session.laps)} voltas.")
        self.processed_data['laps'] = {}
        for i, lap in enumerate(self.session.laps):
            if lap.is_valid:
                logger.debug(f"Processando volta {lap.lap_number}")
                processed_lap_data = self._process_lap(lap)
                self.processed_data['laps'][lap.lap_number] = processed_lap_data
            else:
                logger.debug(f"Ignorando volta inválida {lap.lap_number}")
        logger.info("Processamento de voltas concluído.")
        # Processamentos adicionais a nível de sessão podem ser adicionados aqui
        self._generate_track_map()

    def _process_lap(self, lap: LapData) -> Dict[str, Any]:
        """Processa os dados de uma única volta."""
        if not lap.data_points:
            # Aqui, futuramente, carregaria de lap.data_points_ref se necessário
            logger.warning(f"Volta {lap.lap_number} sem data_points para processar.")
            return {}

        # Converte data_points para DataFrame para facilitar cálculos
        df = pd.DataFrame([vars(p) for p in lap.data_points])

        if df.empty:
             logger.warning(f"DataFrame vazio para a volta {lap.lap_number}.")
             return {}

        processed = {}

        # 1. Extração de Canais Essenciais (já estão no formato padronizado)
        processed['timestamps_ms'] = df['timestamp_ms'].to_list()
        processed['distance_m'] = df['distance_m'].to_list()
        processed['speed_kmh'] = df['speed_kmh'].to_list()
        processed['rpm'] = df['rpm'].to_list()
        processed['gear'] = df['gear'].to_list()
        processed['throttle'] = df['throttle'].to_list()
        processed['brake'] = df['brake'].to_list()
        processed['steer_angle'] = df['steer_angle'].to_list()
        processed['clutch'] = df['clutch'].to_list()

        # 2. Geração do Traçado do Piloto (X, Y)
        processed['driver_trace_xy'] = list(zip(df['pos_x'], df['pos_y']))

        # 3. Cálculo de Velocidade em Curvas (Exemplo simples: velocidade mínima em segmentos)
        #    Uma análise mais robusta exigiria detecção de curvas (mudança de heading/steer)
        #    Por enquanto, podemos calcular a velocidade média/mínima por setor
        processed['sector_speeds'] = self._calculate_sector_speeds(df, lap.sector_times_ms)

        # 4. Detecção de Voltas e Setores (Assumindo que já veio da camada de aquisição)
        #    Se não viesse, implementaríamos aqui baseado em distance_m e track_data.sector_markers_m
        processed['lap_time_ms'] = lap.lap_time_ms
        processed['sector_times_ms'] = lap.sector_times_ms

        # Adicionar outras análises conforme necessário

        return processed

    def _calculate_sector_speeds(self, df: pd.DataFrame, sector_times_ms: List[int]) -> List[Dict[str, float]]:
        """Calcula estatísticas de velocidade por setor."""
        sector_speeds_stats = []
        if 'sector' not in df.columns or not sector_times_ms:
            return sector_speeds_stats

        unique_sectors = sorted(df['sector'].unique())
        for i, sector_num in enumerate(unique_sectors):
            if sector_num <= 0: continue # Ignora setor 0 (geralmente pit/inválido)
            sector_df = df[df['sector'] == sector_num]
            if not sector_df.empty:
                stats = {
                    'sector': sector_num,
                    'avg_speed_kmh': sector_df['speed_kmh'].mean(),
                    'min_speed_kmh': sector_df['speed_kmh'].min(),
                    'max_speed_kmh': sector_df['speed_kmh'].max(),
                    'time_ms': sector_times_ms[i-1] if i > 0 and i <= len(sector_times_ms) else None # Associa tempo se disponível
                }
                sector_speeds_stats.append(stats)
        return sector_speeds_stats

    def _generate_track_map(self):
        """Gera um traçado aproximado da pista usando dados de múltiplas voltas."""
        all_coords = []
        if 'laps' not in self.processed_data:
            logger.warning("Nenhuma volta processada para gerar mapa da pista.")
            return

        for lap_num, lap_data in self.processed_data['laps'].items():
            if 'driver_trace_xy' in lap_data:
                all_coords.extend(lap_data['driver_trace_xy'])

        if not all_coords:
            logger.warning("Nenhuma coordenada XY encontrada nas voltas processadas.")
            return

        # Simplificação: Apenas armazena os pontos únicos (poderia usar algoritmos de clustering/média)
        # Converter para um set de tuplas para remover duplicatas, depois de volta para lista
        unique_coords_set = set(all_coords)
        # Ordenar pode ser complexo sem informação de distância/tempo, mas tentamos por X e Y
        # Uma abordagem melhor seria usar a volta mais rápida ou média como referência
        # Por enquanto, apenas armazenamos os pontos únicos
        self.processed_data['track_map_xy'] = sorted(list(unique_coords_set))
        logger.info(f"Mapa da pista gerado com {len(self.processed_data['track_map_xy'])} pontos únicos.")

    def get_processed_lap_data(self, lap_number: int) -> Optional[Dict[str, Any]]:
        """Retorna os dados processados para uma volta específica."""
        return self.processed_data.get('laps', {}).get(lap_number)

    def get_track_map(self) -> Optional[List[Tuple[float, float]]]:
        """Retorna as coordenadas do mapa da pista gerado."""
        return self.processed_data.get('track_map_xy')

# Exemplo de uso (requereria a criação de um objeto TelemetrySession)
# if __name__ == '__main__':
#     # Criar um mock TelemetrySession aqui para teste
#     mock_session = TelemetrySession(...)
#     processor = TelemetryProcessor(mock_session)
#     processor.process_all_laps()
#     processed_lap_1 = processor.get_processed_lap_data(1)
#     track_map = processor.get_track_map()
#     print(track_map)

