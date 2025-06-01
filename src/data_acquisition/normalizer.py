# -*- coding: utf-8 -*-
"""Módulo para normalizar dados brutos de telemetria para o formato padrão."""

import logging
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
from datetime import datetime
import os

from src.core.standard_data import TelemetrySession, SessionInfo, TrackData, LapData, DataPoint

logger = logging.getLogger(__name__)

class TelemetryNormalizer:
    """Normaliza dados brutos de diferentes fontes para o formato TelemetrySession."""

    def normalize(self, raw_data: Dict[str, Any], source_format: str, file_path: Optional[str] = None) -> Optional[TelemetrySession]:
        """Normaliza os dados brutos com base no formato de origem."""
        logger.info(f"Normalizando dados do formato: {source_format}")
        
        if source_format == "motec":
            return self._normalize_motec(raw_data, file_path)
        elif source_format == "ibt":
            return self._normalize_ibt(raw_data, file_path)
        elif source_format == "csv":
            return self._normalize_csv(raw_data, file_path)
        else:
            logger.error(f"Normalizador não implementado para o formato: {source_format}")
            return None

    def _normalize_motec(self, raw_data: Any, file_path: Optional[str]) -> Optional[TelemetrySession]:
        """Normaliza dados brutos do parser MoTeC (LD/LDX)."""
        
        # Se raw_data já é um TelemetrySession, retorna diretamente
        if isinstance(raw_data, TelemetrySession):
            logger.info("Dados MoTeC já estão no formato TelemetrySession")
            return raw_data

        # Se é um dicionário, processa os dados
        if not isinstance(raw_data, dict):
            logger.error("Dados MoTeC em formato inesperado. Se o arquivo não for suportado, exporte para CSV pelo MoTeC i2 Pro e use o importador CSV.")
            return None

        try:
            header = raw_data.get("header", {})
            channels = raw_data.get("channels", {})
            samples = raw_data.get("samples", {})

            if not samples:
                logger.error("Dados de samples MoTeC ausentes ou vazios.")
                return None

            # Mapeamento de canais MoTeC
            channel_mapping = {
                # Canais básicos
                "Lap": "lap_number",
                "Lap Count": "lap_number", 
                "Laps": "lap_number",
                "Time": "timestamp_s",
                "Timestamp": "timestamp_s",
                "Distance": "distance_m",
                "Lap Distance": "distance_m",
                "Track Distance": "distance_m",
                "Sector": "sector",
                "Sector Index": "sector",
                
                # Velocidade e motor
                "Speed": "speed_kmh",
                "Ground Speed": "speed_kmh",
                "GPS Speed": "speed_kmh",
                "RPM": "rpm",
                "Engine RPM": "rpm",
                "Gear": "gear",
                
                # Controles do piloto
                "Throttle": "throttle",
                "Throttle Pos": "throttle",
                "Brake": "brake",
                "Brake Pos": "brake",
                "Brake Pressure": "brake",
                "Steering": "steer_angle",
                "Steer Angle": "steer_angle",
                "Clutch": "clutch",
                
                # Posição GPS/3D
                "Pos X": "pos_x",
                "Pos Y": "pos_y", 
                "Pos Z": "pos_z",
                "GPS Pos X": "pos_x",
                "GPS Pos Y": "pos_y",
                "GPS Pos Z": "pos_z",
                "X Pos": "pos_x",
                "Y Pos": "pos_y",
                "Z Pos": "pos_z",
                
                # Forças G
                "Lat Accel": "lat_g",
                "Long Accel": "long_g", 
                "Vert Accel": "vert_g",
                "G Force Lat": "lat_g",
                "G Force Long": "long_g",
                "G Force Vert": "vert_g",
                
                # Suspensão
                "Susp Pos FL": "susp_pos_fl",
                "Susp Pos FR": "susp_pos_fr",
                "Susp Pos RL": "susp_pos_rl", 
                "Susp Pos RR": "susp_pos_rr",
                
                # Temperatura dos pneus
                "Tyre Temp FL": "tyre_temp_fl",
                "Tyre Temp FR": "tyre_temp_fr",
                "Tyre Temp RL": "tyre_temp_rl",
                "Tyre Temp RR": "tyre_temp_rr",
                
                # Pressão dos pneus
                "Tyre Press FL": "tyre_press_fl",
                "Tyre Press FR": "tyre_press_fr", 
                "Tyre Press RL": "tyre_press_rl",
                "Tyre Press RR": "tyre_press_rr",
            }

            # Encontra canais mapeados
            mapped_channels = {}
            for original_name, data in samples.items():
                std_name = self._find_channel_mapping(original_name, channel_mapping)
                if std_name:
                    mapped_channels[std_name] = np.array(data)

            # Verifica canais essenciais
            required_channels = ["lap_number", "timestamp_s", "distance_m"]
            missing_channels = [ch for ch in required_channels if ch not in mapped_channels]
            
            if missing_channels:
                logger.error(f"Canais essenciais ausentes: {missing_channels}")
                return None

            # Extrai metadados da sessão
            session_info = SessionInfo(
                game=header.get("game", "MoTeC Data"),
                track=header.get("venue", "Pista Desconhecida"),
                car=header.get("vehicle", "Carro Desconhecido"),
                date=header.get("datetime", datetime.now().isoformat()),
                source=f"import:{os.path.basename(file_path)}" if file_path else "import:motec",
                driver_name=header.get("driver", "Piloto Desconhecido"),
                session_type=header.get("session", "Sessão")
            )

            # Cria dados da pista
            track_data = TrackData(
                name=session_info.track,
                length_meters=None,
                sector_markers_m=[]
            )

            # Processa voltas
            laps_data = self._process_laps_from_samples(mapped_channels, track_data)
            
            if not laps_data:
                logger.error("Nenhuma volta válida processada")
                return None

            # Atualiza comprimento da pista
            if laps_data and laps_data[-1].data_points:
                last_point = laps_data[-1].data_points[-1]
                if hasattr(last_point, 'distance_m') and last_point.distance_m > 0:
                    track_data.length_meters = last_point.distance_m

            session = TelemetrySession(
                session_info=session_info,
                track_data=track_data,
                laps=laps_data
            )
            
            logger.info(f"Normalização MoTeC concluída: {len(laps_data)} voltas processadas")
            return session

        except Exception as e:
            logger.exception(f"Erro durante a normalização MoTeC: {e}")
            return None

    def _process_laps_from_samples(self, channels: Dict[str, np.ndarray], track_data: TrackData) -> List[LapData]:
        """Processa dados de amostras em voltas."""
        laps_data = []
        
        try:
            lap_numbers = channels["lap_number"]
            timestamps = channels["timestamp_s"] 
            distances = channels["distance_m"]
            num_samples = len(timestamps)

            # Encontra mudanças de volta
            lap_changes = np.where(np.diff(lap_numbers) > 0)[0] + 1
            start_indices = np.insert(lap_changes, 0, 0)
            end_indices = np.append(lap_changes, num_samples)

            logger.info(f"Processando {len(start_indices)} voltas")

            for i in range(len(start_indices)):
                start_idx = start_indices[i]
                end_idx = end_indices[i]
                
                if start_idx >= end_idx:
                    continue

                current_lap = int(lap_numbers[start_idx])
                if current_lap <= 0:
                    continue

                # Calcula tempo da volta
                lap_start_time = timestamps[start_idx]
                lap_end_time = timestamps[end_idx - 1] 
                lap_time_ms = int((lap_end_time - lap_start_time) * 1000)

                # Processa setores (se disponível)
                sector_times_ms = []
                if "sector" in channels:
                    sector_times_ms = self._calculate_sector_times(
                        channels["sector"][start_idx:end_idx],
                        timestamps[start_idx:end_idx],
                        distances[start_idx:end_idx],
                        track_data
                    )

                # Cria pontos de dados da volta
                data_points = []
                for j in range(start_idx, end_idx):
                    point_data = self._create_data_point(channels, j, lap_start_time)
                    if point_data:
                        data_points.append(point_data)

                if data_points:
                    lap_data = LapData(
                        lap_number=current_lap,
                        lap_time_ms=lap_time_ms,
                        sector_times_ms=sector_times_ms,
                        is_valid=True,
                        data_points=data_points
                    )
                    laps_data.append(lap_data)

        except Exception as e:
            logger.error(f"Erro ao processar voltas: {e}")

        return laps_data

    def _create_data_point(self, channels: Dict[str, np.ndarray], index: int, lap_start_time: float) -> Optional[DataPoint]:
        """Cria um ponto de dados a partir dos canais."""
        try:
            # Campos obrigatórios com valores padrão
            point_data = {
                'timestamp_ms': int(channels.get('timestamp_s', [0])[index] * 1000) if 'timestamp_s' in channels else 0,
                'distance_m': float(channels.get('distance_m', [0.0])[index]) if 'distance_m' in channels else 0.0,
                'lap_time_ms': int((channels.get('timestamp_s', [lap_start_time])[index] - lap_start_time) * 1000) if 'timestamp_s' in channels else 0,
                'sector': int(channels.get('sector', [0])[index]) if 'sector' in channels else 0,
                'pos_x': float(channels.get('pos_x', [0.0])[index]) if 'pos_x' in channels else 0.0,
                'pos_y': float(channels.get('pos_y', [0.0])[index]) if 'pos_y' in channels else 0.0,
                'pos_z': float(channels.get('pos_z', [0.0])[index]) if 'pos_z' in channels else 0.0,
                'speed_kmh': float(channels.get('speed_kmh', [0.0])[index]) if 'speed_kmh' in channels else 0.0,
                'rpm': int(channels.get('rpm', [0])[index]) if 'rpm' in channels else 0,
                'gear': int(channels.get('gear', [0])[index]) if 'gear' in channels else 0,
                'throttle': float(channels.get('throttle', [0.0])[index]) if 'throttle' in channels else 0.0,
                'brake': float(channels.get('brake', [0.0])[index]) if 'brake' in channels else 0.0,
                'steer_angle': float(channels.get('steer_angle', [0.0])[index]) if 'steer_angle' in channels else 0.0,
                'clutch': float(channels.get('clutch', [0.0])[index]) if 'clutch' in channels else 0.0,
            }

            # Adiciona campos extras se disponíveis  
            extra_fields = {
                'lat_g': 'lat_g',
                'long_g': 'long_g', 
                'vert_g': 'vert_g',
                'susp_pos_fl': 'susp_pos_fl',
                'susp_pos_fr': 'susp_pos_fr',
                'susp_pos_rl': 'susp_pos_rl',
                'susp_pos_rr': 'susp_pos_rr',
                'tyre_temp_fl': 'tyre_temp_fl',
                'tyre_temp_fr': 'tyre_temp_fr',
                'tyre_temp_rl': 'tyre_temp_rl',
                'tyre_temp_rr': 'tyre_temp_rr',
                'tyre_press_fl': 'tyre_press_fl',
                'tyre_press_fr': 'tyre_press_fr',
                'tyre_press_rl': 'tyre_press_rl',
                'tyre_press_rr': 'tyre_press_rr',
            }

            for field, channel_name in extra_fields.items():
                if channel_name in channels and index < len(channels[channel_name]):
                    point_data[field] = float(channels[channel_name][index])

            # Filtra apenas campos válidos do DataPoint
            allowed_keys = DataPoint.__annotations__.keys()
            filtered_data = {k: v for k, v in point_data.items() if k in allowed_keys}

            return DataPoint(**filtered_data)

        except Exception as e:
            logger.error(f"Erro ao criar DataPoint no índice {index}: {e}")
            return None

    def _calculate_sector_times(self, sectors: np.ndarray, timestamps: np.ndarray, 
                              distances: np.ndarray, track_data: TrackData) -> List[int]:
        """Calcula tempos de setor."""
        sector_times_ms = []
        
        try:
            sector_changes = np.where(np.diff(sectors) != 0)[0] + 1
            sector_starts = np.insert(sector_changes, 0, 0)
            sector_ends = np.append(sector_changes, len(sectors))

            for i in range(len(sector_starts)):
                start_idx = sector_starts[i]
                end_idx = sector_ends[i]
                
                if start_idx >= end_idx:
                    continue
                    
                sector_num = int(sectors[start_idx])
                if sector_num > 0:
                    sector_time = timestamps[end_idx - 1] - timestamps[start_idx]
                    sector_times_ms.append(int(sector_time * 1000))
                    
                    # Atualiza marcadores da pista
                    if len(track_data.sector_markers_m) < sector_num:
                        track_data.sector_markers_m.append(float(distances[start_idx]))

        except Exception as e:
            logger.error(f"Erro ao calcular tempos de setor: {e}")

        return sector_times_ms

    def _find_channel_mapping(self, channel_name: str, mapping: Dict[str, str]) -> Optional[str]:
        """Encontra o mapeamento de um canal (case-insensitive)."""
        # Busca exata primeiro
        if channel_name in mapping:
            return mapping[channel_name]
            
        # Busca case-insensitive
        channel_lower = channel_name.lower()
        for orig_name, std_name in mapping.items():
            if orig_name.lower() == channel_lower:
                return std_name
                
        return None

    def _find_channel(self, available_channels: List[str], possible_names: List[str]) -> Optional[str]:
        """Encontra o nome real de um canal (case-insensitive)."""
        for actual_name in available_channels:
            for possible_name in possible_names:
                if possible_name.lower() == actual_name.lower():
                    return actual_name
        return None

    def _normalize_ibt(self, raw_data: Dict[str, Any], file_path: Optional[str]) -> Optional[TelemetrySession]:
        """Normaliza dados brutos do parser IBT (iRacing)."""
        logger.warning("Normalizador IBT ainda não implementado.")
        # TODO: Implementar normalização para dados IBT
        return None

    def _normalize_csv(self, raw_data: Any, file_path: Optional[str]) -> Optional[TelemetrySession]:
        """Normaliza dados brutos do parser CSV."""
        # Se já é TelemetrySession, retorna
        if isinstance(raw_data, TelemetrySession):
            return raw_data
        # Se é um dicionário, tenta criar TelemetrySession
        if isinstance(raw_data, dict) and "laps" in raw_data:
            # Suporte a formato já padronizado
            return TelemetrySession(**raw_data)
        # Se é uma lista de DataPoints, cria uma volta única
        if isinstance(raw_data, list) and all(isinstance(dp, DataPoint) for dp in raw_data):
            lap = LapData(
                lap_number=1,
                lap_time_ms=0,
                is_valid=True,
                data_points=raw_data
            )
            session_info = SessionInfo(
                game="CSV Import",
                track="Desconhecida",
                car="Desconhecido",
                date="N/A",
                source=f"import:{os.path.basename(file_path)}" if file_path else "import:csv",
                driver_name="Desconhecido",
                session_type="Importado"
            )
            track_data = TrackData(
                name="Desconhecida",
                length_meters=None,
                sector_markers_m=[]
            )
            return TelemetrySession(
                session_info=session_info,
                track_data=track_data,
                laps=[lap]
            )
        logger.error("Formato CSV não reconhecido. Exporte do MoTeC i2 Pro ou use a conversão LD->CSV.")
        return None