# -*- coding: utf-8 -*-
"""Módulo para normalizar dados brutos de telemetria para o formato padrão."""

import logging
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
from datetime import datetime

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
        # Adicionar outros formatos aqui (CSV, JSON, ACC_binário, etc.)
        else:
            logger.error(f"Normalizador não implementado para o formato: {source_format}")
            return None

    def _normalize_motec(self, raw_data: Dict[str, Any], file_path: Optional[str]) -> Optional[TelemetrySession]:
        """Normaliza dados brutos do parser MoTeC (LD/LDX)."""
        try:
            header = raw_data.get("header", {})
            channels = raw_data.get("channels", {})
            samples = raw_data.get("samples", {})

            if not samples:
                logger.error("Dados de samples MoTeC ausentes ou vazios.")
                return None

            # --- Mapeamento de Canais (Exemplo - precisa ser robusto) ---
            # Tenta encontrar os nomes dos canais MoTeC comuns (case-insensitive)
            map_ch = lambda names: self._find_channel(samples.keys(), names)

            lap_ch = map_ch(["Lap", "Lap Count", "Laps"])
            time_ch = map_ch(["Time", "Timestamp"])
            dist_ch = map_ch(["Distance", "Lap Distance", "Track Distance"])
            sector_ch = map_ch(["Sector", "Sector Index"])
            speed_ch = map_ch(["Speed", "Ground Speed"])
            rpm_ch = map_ch(["RPM", "Engine RPM"])
            gear_ch = map_ch(["Gear"])
            throttle_ch = map_ch(["Throttle", "Throttle Pos"])
            brake_ch = map_ch(["Brake", "Brake Pos", "Brake Pressure"])
            steer_ch = map_ch(["Steering", "Steer Angle"])
            clutch_ch = map_ch(["Clutch"])
            pos_x_ch = map_ch(["Pos X", "GPS Pos X", "X Pos"])
            pos_y_ch = map_ch(["Pos Y", "GPS Pos Y", "Y Pos"])
            pos_z_ch = map_ch(["Pos Z", "GPS Pos Z", "Z Pos"])
            # Adicionar mapeamento para pneus, etc.

            if not lap_ch or not time_ch or not dist_ch:
                logger.error("Canais MoTeC essenciais (Lap, Time, Distance) não encontrados.")
                return None

            # --- Extrair Metadados da Sessão (Pode precisar de mais info do cabeçalho LDX) ---
            session_info = SessionInfo(
                game="Unknown (MoTeC)", # Tentar extrair do log/meta se disponível
                track="Unknown", # Tentar extrair do log/meta
                car="Unknown", # Tentar extrair do log/meta
                date=datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat() if file_path else datetime.now().isoformat(),
                source=f"import:{os.path.basename(file_path)}" if file_path else "import:motec",
                driver_name=None # Tentar extrair
            )

            # --- Extrair Dados da Pista (Pode ser derivado ou de metadados) ---
            track_data = TrackData(
                name=session_info.track,
                # Comprimento e setores podem ser calculados ou vir de metadados
                length_meters=None,
                sector_markers_m=[]
            )

            # --- Processar Voltas e Pontos de Dados ---
            lap_numbers = samples[lap_ch]
            timestamps_sec = samples[time_ch]
            distances_m = samples[dist_ch]
            num_samples = header.get("num_samples", len(timestamps_sec))

            laps_data: List[LapData] = []
            lap_change_indices = np.where(np.diff(lap_numbers) > 0)[0] + 1
            start_indices = np.insert(lap_change_indices, 0, 0)
            end_indices = np.append(lap_change_indices, num_samples)

            logger.info(f"Encontradas {len(start_indices)} mudanças de volta (incluindo início/fim).")

            for i in range(len(start_indices)):
                start_idx = start_indices[i]
                end_idx = end_indices[i]
                if start_idx >= end_idx: continue # Ignora se não houver pontos

                current_lap_number = int(lap_numbers[start_idx])
                if current_lap_number <= 0: continue # Ignora volta 0 ou inválida

                lap_slice = np.arange(start_idx, end_idx)
                if len(lap_slice) == 0: continue

                lap_start_time_sec = timestamps_sec[start_idx]
                lap_end_time_sec = timestamps_sec[end_idx - 1]
                final_lap_time_ms = int((lap_end_time_sec - lap_start_time_sec) * 1000)

                # Processar Setores
                sector_times_ms: List[int] = []
                sector_start_time = lap_start_time_sec
                if sector_ch:
                    sector_numbers = samples[sector_ch][lap_slice]
                    sector_change_indices_rel = np.where(np.diff(sector_numbers) != 0)[0] + 1
                    sector_starts_rel = np.insert(sector_change_indices_rel, 0, 0)
                    sector_ends_rel = np.append(sector_change_indices_rel, len(lap_slice))

                    for j in range(len(sector_starts_rel)):
                        sec_start_rel = sector_starts_rel[j]
                        sec_end_rel = sector_ends_rel[j]
                        if sec_start_rel >= sec_end_rel: continue
                        sector_num = int(sector_numbers[sec_start_rel])
                        if sector_num > 0:
                            sec_start_abs_idx = lap_slice[sec_start_rel]
                            sec_end_abs_idx = lap_slice[sec_end_rel - 1]
                            sector_time_sec = timestamps_sec[sec_end_abs_idx] - timestamps_sec[sec_start_abs_idx]
                            sector_times_ms.append(int(sector_time_sec * 1000))
                            # Atualiza marcadores da pista se ainda não definidos
                            if len(track_data.sector_markers_m) < sector_num:
                                 track_data.sector_markers_m.append(distances_m[sec_start_abs_idx])

                # Processar Pontos de Dados
                data_points: List[DataPoint] = []
                for k in lap_slice:
                    point = DataPoint(
                        timestamp_ms=int(timestamps_sec[k] * 1000),
                        distance_m=float(distances_m[k]),
                        lap_time_ms=int((timestamps_sec[k] - lap_start_time_sec) * 1000),
                        sector=int(samples[sector_ch][k]) if sector_ch else 0,
                        pos_x=float(samples[pos_x_ch][k]) if pos_x_ch else 0.0,
                        pos_y=float(samples[pos_y_ch][k]) if pos_y_ch else 0.0,
                        pos_z=float(samples[pos_z_ch][k]) if pos_z_ch else 0.0,
                        speed_kmh=float(samples[speed_ch][k]) if speed_ch else 0.0,
                        rpm=int(samples[rpm_ch][k]) if rpm_ch else 0,
                        gear=int(samples[gear_ch][k]) if gear_ch else 0,
                        throttle=float(samples[throttle_ch][k]) if throttle_ch else 0.0,
                        brake=float(samples[brake_ch][k]) if brake_ch else 0.0,
                        steer_angle=float(samples[steer_ch][k]) if steer_ch else 0.0,
                        clutch=float(samples[clutch_ch][k]) if clutch_ch else 0.0,
                        # Adicionar outros canais mapeados aqui
                    )
                    data_points.append(point)

                lap_data = LapData(
                    lap_number=current_lap_number,
                    lap_time_ms=final_lap_time_ms,
                    sector_times_ms=sector_times_ms,
                    is_valid=True, # TODO: Adicionar lógica de validação se disponível
                    data_points=data_points
                )
                laps_data.append(lap_data)

            # Atualiza comprimento da pista se possível
            if not track_data.length_meters and laps_data:
                 last_lap_points = laps_data[-1].data_points
                 if last_lap_points:
                      track_data.length_meters = last_lap_points[-1].distance_m

            session = TelemetrySession(
                session_info=session_info,
                track_data=track_data,
                laps=laps_data
            )
            logger.info(f"Normalização MoTeC concluída. {len(laps_data)} voltas processadas.")
            return session

        except Exception as e:
            logger.exception(f"Erro durante a normalização MoTeC: {e}")
            return None

    def _normalize_ibt(self, raw_data: Dict[str, Any], file_path: Optional[str]) -> Optional[TelemetrySession]:
        """Normaliza dados brutos do parser IBT (iRacing)."""
        # TODO: Implementar normalização para dados IBT quando o parser estiver pronto
        logger.warning("Normalizador IBT ainda não implementado.")
        # Exemplo de estrutura:
        # session_info = SessionInfo(game="iRacing", ...)
        # track_data = TrackData(...)
        # laps_data = []
        # ... processar raw_data do IBTParser ...
        # return TelemetrySession(session_info, track_data, laps_data)
        return None

    def _find_channel(self, available_channels: List[str], possible_names: List[str]) -> Optional[str]:
        """Encontra o nome real de um canal (case-insensitive)."""
        for actual_name in available_channels:
            for possible_name in possible_names:
                if possible_name.lower() == actual_name.lower():
                    return actual_name
        return None

