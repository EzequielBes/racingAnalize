# -*- coding: utf-8 -*-
"""Módulo responsável pela comparação de dados entre voltas."""

import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

# Importa as estruturas de dados padronizadas (se necessário diretamente)
# from ..core.standard_data import LapData, DataPoint

logger = logging.getLogger(__name__)

class LapComparator:
    """Compara dados de telemetria entre duas voltas processadas."""

    def __init__(self, lap_data_1: Dict[str, Any], lap_data_2: Dict[str, Any]):
        """Inicializa o comparador com os dados processados de duas voltas.

        Args:
            lap_data_1: Dicionário com dados processados da primeira volta (output do TelemetryProcessor).
            lap_data_2: Dicionário com dados processados da segunda volta.
        """
        if not isinstance(lap_data_1, dict) or not isinstance(lap_data_2, dict):
            raise TypeError("Input lap data must be dictionaries.")
        if 'distance_m' not in lap_data_1 or 'distance_m' not in lap_data_2:
             raise ValueError("Lap data must contain 'distance_m' for comparison.")
        if 'timestamps_ms' not in lap_data_1 or 'timestamps_ms' not in lap_data_2:
             raise ValueError("Lap data must contain 'timestamps_ms' for delta calculation.")

        self.lap1 = lap_data_1
        self.lap2 = lap_data_2
        self.comparison_results = {}
        logger.info("LapComparator inicializado.")

    def compare_laps(self):
        """Executa todas as comparações entre as duas voltas."""
        logger.info("Iniciando comparação entre as voltas.")

        # 1. Alinhar dados por distância (ou tempo)
        # Usaremos a distância como eixo comum e interpolaremos os dados da volta 2
        # na escala de distância da volta 1 (ou vice-versa, ou uma escala comum).
        # Usar a volta 1 como referência:
        common_distance = np.array(self.lap1['distance_m'])
        aligned_lap2_data = self._align_data_by_distance(common_distance, self.lap2)

        if not aligned_lap2_data:
             logger.error("Falha ao alinhar dados da volta 2. Abortando comparação.")
             return None

        self.comparison_results['common_distance'] = common_distance.tolist()

        # 2. Comparar canais principais
        channels_to_compare = ['speed_kmh', 'rpm', 'gear', 'throttle', 'brake', 'steer_angle']
        self.comparison_results['channels'] = {}
        for channel in channels_to_compare:
            if channel in self.lap1 and channel in aligned_lap2_data:
                self.comparison_results['channels'][channel] = {
                    'lap1': self.lap1[channel],
                    'lap2': aligned_lap2_data[channel]
                }
            else:
                 logger.warning(f"Canal '{channel}' não encontrado em ambas as voltas para comparação.")

        # 3. Calcular Delta Time
        # Precisamos dos tempos alinhados por distância
        if 'timestamps_ms' in aligned_lap2_data:
            time1_ms = np.array(self.lap1['timestamps_ms'])
            time2_ms_aligned = np.array(aligned_lap2_data['timestamps_ms'])
            # Delta = Tempo Volta 2 - Tempo Volta 1 (positivo = volta 2 mais lenta)
            delta_time_ms = time2_ms_aligned - time1_ms
            self.comparison_results['delta_time_ms'] = delta_time_ms.tolist()
        else:
            logger.warning("Não foi possível calcular o delta time (timestamps não alinhados).")
            self.comparison_results['delta_time_ms'] = None

        # 4. Comparar Traçados (já estão disponíveis em lap1 e lap2)
        self.comparison_results['traces'] = {
            'lap1_xy': self.lap1.get('driver_trace_xy'),
            'lap2_xy': self.lap2.get('driver_trace_xy')
        }

        logger.info("Comparação entre voltas concluída.")
        return self.comparison_results

    def _align_data_by_distance(self, target_distance: np.ndarray, source_lap_data: Dict[str, Any]) -> Optional[Dict[str, list]]:
        """Alinha os dados da volta fonte com a escala de distância alvo usando interpolação."""
        source_distance = np.array(source_lap_data['distance_m'])
        aligned_data = {}

        # Garante que a distância seja estritamente crescente para interpolação
        unique_indices_source = np.unique(source_distance, return_index=True)[1]
        source_distance_unique = source_distance[unique_indices_source]

        # Verifica se temos pontos suficientes e se os limites coincidem razoavelmente
        if len(source_distance_unique) < 2:
            logger.error("Distância da volta fonte tem menos de 2 pontos únicos para interpolação.")
            return None
        if target_distance.min() < source_distance_unique.min() or target_distance.max() > source_distance_unique.max():
             logger.warning(f"Intervalo de distância alvo [{target_distance.min():.1f}, {target_distance.max():.1f}] excede o intervalo fonte [{source_distance_unique.min():.1f}, {source_distance_unique.max():.1f}]. A extrapolação pode ocorrer.")
             # Considerar ajuste dos limites ou tratamento de extrapolação (fill_value='extrapolate')

        for channel, source_values in source_lap_data.items():
            # Só interpola canais numéricos que tenham o mesmo tamanho da distância
            if isinstance(source_values, list) and len(source_values) == len(source_distance) and np.issubdtype(type(source_values[0]), np.number):
                try:
                    source_values_array = np.array(source_values)
                    source_values_unique = source_values_array[unique_indices_source]

                    # Cria a função de interpolação linear
                    interp_func = interp1d(
                        source_distance_unique, 
                        source_values_unique, 
                        kind='linear', 
                        bounds_error=False, # Não gera erro se fora dos limites
                        fill_value=(source_values_unique[0], source_values_unique[-1]) # Preenche com primeiro/último valor fora
                        # fill_value="extrapolate" # Alternativa: permitir extrapolação
                    )
                    
                    # Interpola os valores na distância alvo
                    aligned_data[channel] = interp_func(target_distance).tolist()
                except ValueError as e:
                    logger.error(f"Erro de interpolação para o canal '{channel}': {e}")
                    # Pula este canal se a interpolação falhar
                    aligned_data[channel] = [np.nan] * len(target_distance) # Preenche com NaN
                except Exception as e:
                     logger.error(f"Erro inesperado durante interpolação do canal '{channel}': {e}")
                     aligned_data[channel] = [np.nan] * len(target_distance)

        return aligned_data if aligned_data else None

    def get_comparison_results(self) -> Dict[str, Any]:
        """Retorna os resultados da comparação."""
        return self.comparison_results

# Exemplo de uso (requereria dados processados de duas voltas)
# if __name__ == '__main__':
#     # Mock lap_data_1 and lap_data_2 from TelemetryProcessor output
#     mock_lap1 = {
#         'distance_m': [0, 10, 20, 30, 40],
#         'timestamps_ms': [0, 100, 200, 300, 400],
#         'speed_kmh': [50, 60, 70, 65, 60],
#         'driver_trace_xy': [(0,0), (10,1), (20,0), (30,-1), (40,0)]
#         # ... other channels
#     }
#     mock_lap2 = {
#         'distance_m': [0, 12, 25, 35, 40],
#         'timestamps_ms': [0, 110, 230, 340, 410],
#         'speed_kmh': [52, 65, 75, 68, 62],
#         'driver_trace_xy': [(0,0), (12,1.1), (25,0.2), (35,-0.8), (40,0.1)]
#         # ... other channels
#     }
#
#     comparator = LapComparator(mock_lap1, mock_lap2)
#     results = comparator.compare_laps()
#     if results:
#         print(f"Distância Comum: {results['common_distance']}")
#         print(f"Delta Time (ms): {results['delta_time_ms']}")
#         print(f"Velocidade Lap 1: {results['channels']['speed_kmh']['lap1']}")
#         print(f"Velocidade Lap 2 (Alinhada): {results['channels']['speed_kmh']['lap2']}")

