# -*- coding: utf-8 -*-
"""Módulo contendo parsers para diferentes formatos de arquivos de telemetria."""

import logging
import struct
import os
import datetime
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple
import numpy as np
import pandas as pd

# Importa a estrutura de dados padronizada
from src.core.standard_data import TelemetrySession, SessionInfo, TrackData, LapData, DataPoint

logger = logging.getLogger(__name__)

# --- Funções Auxiliares ---
def decode_string(byte_string: bytes) -> str:
    """Decodifica bytes para string, removendo nulos e espaços extras."""
    try:
        return byte_string.decode("utf-8", errors="ignore").strip().rstrip("\0").strip()
    except Exception:
        try:
            return byte_string.decode("latin-1", errors="ignore").strip().rstrip("\0").strip()
        except Exception as e:
            logger.warning(f"Falha ao decodificar string: {byte_string}. Erro: {e}")
            return ""

# --- Classes Base ---
class BaseParser(ABC):
    """Classe base abstrata para parsers de telemetria."""

    @abstractmethod
    def parse(self, file_path: str) -> Optional[TelemetrySession]:
        pass

# --- Parser MoTeC LD/LDX ---
# ATENÇÃO: Não existe biblioteca oficial Python para ler arquivos MoTeC LD/LDX.
# Este parser é baseado em engenharia reversa e no projeto ldparser:
# https://github.com/gotzl/ldparser
# Para máxima compatibilidade, recomenda-se exportar os dados para CSV usando o MoTeC i2 Pro
# e importar o CSV, ou converter para formatos abertos.

class MotecParser(BaseParser):
    """Parser para arquivos MoTeC .ld (com suporte opcional a .ldx).
    Baseado em engenharia reversa do formato. Pode não funcionar para todos os arquivos MoTeC.
    Se encontrar problemas, exporte para CSV pelo MoTeC i2 Pro e use o importador CSV.
    """

    CHANNEL_MAP = {
        "Time": "timestamp_s",
        "Distance": "distance_m",
        "Ground Speed": "speed_kmh",
        "RPM": "rpm",
        "Gear": "gear",
        "Throttle Pos": "throttle",
        "Brake Pos": "brake",
        "Steered Angle": "steer_angle",
        "Clutch Pos": "clutch",
        "GPS Latitude": "gps_lat",
        "GPS Longitude": "gps_lon",
        "Pos X": "pos_x",
        "Pos Y": "pos_y",
        "Pos Z": "pos_z",
        "LAP_BEACON": "lap_beacon",
        "ROTY": "rot_y",
        "STEERANGLE": "steer_angle",
        "SPEED": "speed_kmh",
        "THROTTLE": "throttle",
        "BRAKE": "brake",
        "GEAR": "gear",
        "CLUTCH": "clutch",
        "RPMS": "rpm",
        "BRAKE_TEMP_LF": "brake_temp_lf",
        "BRAKE_TEMP_RF": "brake_temp_rf",
        "BRAKE_TEMP_LR": "brake_temp_lr",
        "BRAKE_TEMP_RR": "brake_temp_rr",
        "WHEEL_SPEED_LF": "wheel_speed_lf",
        "WHEEL_SPEED_RF": "wheel_speed_rf",
        "WHEEL_SPEED_LR": "wheel_speed_lr",
        "WHEEL_SPEED_RR": "wheel_speed_rr",
        "BUMPSTOP_FORCE_LF": "bumpstop_force_lf",
        "BUMPSTOP_FORCE_RF": "bumpstop_force_rf",
        "BUMPSTOP_FORCE_LR": "bumpstop_force_lr",
        "BUMPSTOP_FORCE_RR": "bumpstop_force_rr",
    }

    FIRST_CHANNEL_OFFSET_GUESS = 0x2c68

    def parse(self, file_path: str) -> Optional[TelemetrySession]:
        logger.info(f"Iniciando parsing MoTeC para: {file_path}")

        # Verifica arquivos LD/LDX
        if not os.path.exists(file_path):
            logger.error(f"Arquivo não encontrado: {file_path}")
            return None
            
        if file_path.lower().endswith(".ldx"):
            ld_file_path = file_path[:-1]
            ldx_file_path = file_path
            if not os.path.exists(ld_file_path):
                logger.error(f"Arquivo .ld correspondente não encontrado: {ld_file_path}")
                return None
        elif file_path.lower().endswith(".ld"):
            ld_file_path = file_path
            ldx_file_path = file_path + "x"
            if not os.path.exists(ldx_file_path):
                logger.warning(f"Arquivo .ldx correspondente não encontrado: {ldx_file_path}")
                ldx_file_path = None
        else:
            logger.error("Formato de arquivo inválido (deve ser .ld ou .ldx)")
            return None

        try:
            # 1. Ler Cabeçalho do LD
            ld_head = _ldHead(ld_file_path)
            
            # 2. Ler Metadados dos Canais do LD
            channels: Dict[str, _ldChan] = {}
            meta_ptr = self.FIRST_CHANNEL_OFFSET_GUESS
            processed_offsets = set()
            channel_count = 0

            # Tenta ler o primeiro canal
            try:
                first_chan = _ldChan(ld_file_path, meta_ptr)
                if first_chan.name and first_chan.np_dtype:
                    logger.info(f"Primeiro canal encontrado: {first_chan.name} (Tipo: {first_chan.np_dtype})")
                    channels[first_chan.name] = first_chan
                    processed_offsets.add(meta_ptr)
                    channel_count += 1
                    meta_ptr = first_chan.next_meta_ptr
                else:
                    logger.error(f"Não foi possível ler um canal válido no offset 0x{meta_ptr:08x}")
                    return None
            except Exception as e:
                logger.error(f"Erro ao tentar ler o primeiro canal: {e}")
                return None

            # Segue a lista encadeada
            while meta_ptr != 0 and meta_ptr not in processed_offsets:
                processed_offsets.add(meta_ptr)
                try:
                    chan = _ldChan(ld_file_path, meta_ptr)
                    if chan.name and chan.np_dtype:
                        channels[chan.name] = chan
                        channel_count += 1
                        meta_ptr = chan.next_meta_ptr
                    else:
                        logger.warning(f"Canal inválido em 0x{meta_ptr:08x}. Interrompendo lista.")
                        break
                except Exception as e:
                    logger.error(f"Erro ao ler canal em 0x{meta_ptr:08x}: {e}")
                    break
                if len(processed_offsets) > 1000:
                    logger.error("Limite de canais processados atingido (1000)")
                    break

            if not channels:
                logger.error("Nenhum canal válido encontrado")
                return None
            logger.info(f"{channel_count} canais lidos do arquivo LD")

            # 3. Tentar Ler Informações de Voltas do LDX
            ldx_laps = None
            if ldx_file_path and os.path.exists(ldx_file_path):
                ldx_laps = _parse_ldx(ldx_file_path)

            # 4. Criar Objeto SessionInfo
            session_info = SessionInfo(
                game="Assetto Corsa Competizione",
                track=ld_head.venue,
                car=ld_head.vehicleid,
                date=ld_head.datetime.isoformat() if ld_head.datetime else "N/A",
                source=f"import:{os.path.basename(file_path)}",
                driver_name=ld_head.driver,
                session_type=ld_head.event_session
            )

            # 5. Criar Objeto TrackData
            track_data = TrackData(
                name=ld_head.venue,
                length_meters=None,
                sector_markers_m=[]
            )

            # 6. Processar Voltas (ou sessão inteira se não houver LDX)
            session_laps: List[LapData] = []

            # Encontra canal de referência para tamanho dos dados
            ref_chan = None
            for ref_name in ["LAP_BEACON", "Distance", "Time"]:
                if ref_name in channels:
                    ref_chan = channels[ref_name]
                    break
            total_points = ref_chan.data_len if ref_chan else None

            if ldx_laps:
                laps_validos = []
                for ldx_lap in ldx_laps:
                    start_idx = ldx_lap.start_offset
                    end_idx = ldx_lap.end_offset
                    
                    if total_points is None or start_idx < 0 or end_idx > total_points or start_idx >= end_idx:
                        logger.error(f"Lap offsets inválidos: lap={ldx_lap.lap_num}, start={start_idx}, end={end_idx}")
                        continue
                    laps_validos.append(ldx_lap)

                if laps_validos:
                    logger.info("Processando dados por volta usando LDX")
                    for ldx_lap in laps_validos:
                        start_idx = ldx_lap.start_offset
                        count = ldx_lap.end_offset - start_idx + 1
                        lap_data_dict = {}
                        
                        for chan_name, chan in channels.items():
                            chan_data = chan.get_data(start_idx, count)
                            if chan_data is not None and len(chan_data) > 0:
                                std_name = self.CHANNEL_MAP.get(chan_name, chan_name)
                                lap_data_dict[std_name] = chan_data
                        
                        if not lap_data_dict:
                            logger.warning(f"Nenhum dado válido para a volta {ldx_lap.lap_num}")
                            continue
                            
                        min_samples = min(len(data) for data in lap_data_dict.values())
                        data_points = []
                        
                        for i in range(min_samples):
                            point_data = {}
                            for key, values in lap_data_dict.items():
                                point_data[key] = values[i] if i < len(values) else 0.0
                            
                            # Preenche campos obrigatórios
                            point_data.setdefault('timestamp_ms', 0)
                            point_data.setdefault('distance_m', 0.0)
                            point_data.setdefault('speed_kmh', 0.0)
                            point_data.setdefault('rpm', 0)
                            point_data.setdefault('gear', 0)
                            point_data.setdefault('throttle', 0.0)
                            point_data.setdefault('brake', 0.0)
                            point_data.setdefault('steer_angle', 0.0)
                            point_data.setdefault('pos_x', 0.0)
                            point_data.setdefault('pos_y', 0.0)
                            point_data.setdefault('pos_z', 0.0)
                            point_data.setdefault('clutch', 0.0)
                            
                            # Converte timestamp se necessário
                            if 'timestamp_s' in point_data:
                                point_data['timestamp_ms'] = int(point_data['timestamp_s'] * 1000)
                                del point_data['timestamp_s']
                            
                            data_points.append(DataPoint(**point_data))
                        
                        lap_data = LapData(
                            lap_number=ldx_lap.lap_num,
                            lap_time_ms=int(ldx_lap.lap_time_s * 1000),
                            is_valid=True,
                            data_points=data_points
                        )
                        session_laps.append(lap_data)

            # Processar sessão inteira como uma volta se não houver LDX válido
            if not session_laps:
                logger.info("Processando sessão inteira como uma única volta")
                lap_data_dict = {}
                
                for chan_name, chan in channels.items():
                    chan_data = chan.get_data()
                    if chan_data is not None and len(chan_data) > 0:
                        std_name = self.CHANNEL_MAP.get(chan_name, chan_name)
                        lap_data_dict[std_name] = chan_data
                
                if not lap_data_dict:
                    logger.error("Nenhum dado válido encontrado na sessão")
                    return None
                    
                min_samples = min(len(data) for data in lap_data_dict.values())
                data_points = []
                
                for i in range(min_samples):
                    point_data = {}
                    for key, values in lap_data_dict.items():
                        point_data[key] = values[i] if i < len(values) else 0.0
                    
                    # Preenche campos obrigatórios
                    point_data.setdefault('timestamp_ms', 0)
                    point_data.setdefault('distance_m', 0.0)
                    point_data.setdefault('speed_kmh', 0.0)
                    point_data.setdefault('rpm', 0)
                    point_data.setdefault('gear', 0)
                    point_data.setdefault('throttle', 0.0)
                    point_data.setdefault('brake', 0.0)
                    point_data.setdefault('steer_angle', 0.0)
                    point_data.setdefault('pos_x', 0.0)
                    point_data.setdefault('pos_y', 0.0)
                    point_data.setdefault('pos_z', 0.0)
                    point_data.setdefault('clutch', 0.0)
                    
                    # Converte timestamp se necessário
                    if 'timestamp_s' in point_data:
                        point_data['timestamp_ms'] = int(point_data['timestamp_s'] * 1000)
                        del point_data['timestamp_s']
                    
                    data_points.append(DataPoint(**point_data))
                
                lap_data = LapData(
                    lap_number=1,
                    lap_time_ms=0,
                    is_valid=True,
                    data_points=data_points
                )
                session_laps.append(lap_data)

            # 7. Criar e retornar o objeto TelemetrySession
            if not session_laps:
                logger.error("Nenhuma volta processada")
                return None

            telemetry_session = TelemetrySession(
                session_info=session_info,
                track_data=track_data,
                laps=session_laps
            )

            logger.info(f"Parsing MoTeC concluído: {len(session_laps)} voltas processadas")
            return telemetry_session

        except Exception as e:
            logger.exception(f"Erro fatal ao processar arquivo MoTeC: {e}")
            return None

    def convert_ld_to_csv(self, ld_file_path: str, csv_file_path: str) -> bool:
        """
        Converte um arquivo .ld para .csv usando o próprio parser.
        O CSV gerado pode ser lido pelo CSVParser.
        """
        session = self.parse(ld_file_path)
        if not session:
            logger.error("Falha ao converter LD para CSV: parsing falhou.")
            return False
        try:
            import csv
            # Assume que todos os laps têm os mesmos campos
            with open(csv_file_path, "w", newline="") as csvfile:
                writer = None
                for lap in session.laps:
                    for dp in lap.data_points:
                        row = dp.__dict__ if hasattr(dp, "__dict__") else dict(dp)
                        if writer is None:
                            writer = csv.DictWriter(csvfile, fieldnames=row.keys())
                            writer.writeheader()
                        writer.writerow(row)
            logger.info(f"Arquivo CSV salvo em: {csv_file_path}")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar CSV: {e}")
            return False

# --- Parser iRacing IBT ---
class IBTParser(BaseParser):
    """Parser para arquivos iRacing .ibt."""

    def parse(self, file_path: str) -> Optional[TelemetrySession]:
        logger.error("Parser IBT não implementado")
        return None

# --- Parser CSV Genérico ---
class CSVParser(BaseParser):
    """Parser para arquivos CSV exportados do MoTeC i2 Pro ou convertidos."""
    def parse(self, file_path: str) -> Optional[TelemetrySession]:
        import csv
        logger.info(f"Lendo arquivo CSV: {file_path}")
        try:
            with open(file_path, "r", newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                data_points = []
                # Obtenha os campos válidos do DataPoint
                valid_fields = set(DataPoint.__annotations__.keys())
                for row in reader:
                    dp_data = {}
                    for k, v in row.items():
                        key = str(k)
                        try:
                            if v is None or v == "":
                                dp_data[key] = 0.0
                            elif "." in v or "e" in v.lower():
                                dp_data[key] = float(v)
                            else:
                                dp_data[key] = int(v)
                        except Exception:
                            dp_data[key] = v
                    # Filtra apenas os campos válidos do DataPoint
                    filtered_dp_data = {k: v for k, v in dp_data.items() if k in valid_fields}
                    try:
                        data_points.append(DataPoint(**filtered_dp_data))
                    except Exception as e:
                        logger.warning(f"Erro ao criar DataPoint do CSV: {e}")
                        continue
            # Cria uma volta única com todos os pontos
            lap = LapData(
                lap_number=1,
                lap_time_ms=0,
                is_valid=True,
                data_points=data_points
            )
            session_info = SessionInfo(
                game="CSV Import",
                track="Desconhecida",
                car="Desconhecido",
                date="N/A",
                source=f"import:{os.path.basename(file_path)}",
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
        except Exception as e:
            logger.error(f"Erro ao ler arquivo CSV: {e}")
            return None

# --- Factory para criar o parser apropriado ---
def create_parser(file_path: str) -> Optional[BaseParser]:
    file_ext = os.path.splitext(file_path)[1].lower()

    if file_ext == ".ld" or file_ext == ".ldx":
        return MotecParser()
    elif file_ext == ".ibt":
        return IBTParser()
    elif file_ext == ".csv":
        return CSVParser()
    else:
        logger.error(f"Formato não suportado: {file_ext}")
        return None