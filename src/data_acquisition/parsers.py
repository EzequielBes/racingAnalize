# -*- coding: utf-8 -*-
"""Módulo contendo parsers para diferentes formatos de arquivos de telemetria."""

import logging
import struct
import os
import datetime
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple
import numpy as np
import pandas as pd # Adicionado para facilitar a criação de DataPoints

# Importa a estrutura de dados padronizada
from src.core.standard_data import TelemetrySession, SessionInfo, TrackData, LapData, DataPoint

logger = logging.getLogger(__name__)

# --- Funções Auxiliares (podem ser movidas para um utils) ---
def decode_string(byte_string: bytes) -> str:
    """Decodifica bytes para string, removendo nulos e espaços extras."""
    try:
        return byte_string.decode("utf-8", errors="ignore").strip().rstrip("\0").strip()
    except Exception:
        try:
            # Tenta com outra codificação comum se utf-8 falhar
            return byte_string.decode("latin-1", errors="ignore").strip().rstrip("\0").strip()
        except Exception as e:
            logger.warning(f"Falha ao decodificar string: {byte_string}. Erro: {e}")
            return ""

# --- Classes Base ---
class BaseParser(ABC):
    """Classe base abstrata para parsers de telemetria."""

    @abstractmethod
    def parse(self, file_path: str) -> Optional[TelemetrySession]:
        """
        Analisa o arquivo de telemetria e retorna os dados em formato padronizado.

        Args:
            file_path: Caminho para o arquivo de telemetria.

        Returns:
            Um objeto TelemetrySession contendo os dados padronizados, ou None se o parsing falhar.
        """
        pass

# --- Parser MoTeC LD/LDX ---

# Estruturas de dados internas do ldparser (simplificadas e adaptadas)
# Baseado em https://github.com/gotzl/ldparser/blob/master/ldparser.py
class _ldChan:
    fmt = "<IIIIHHHhhhh32s8s12s40x" # Formato do cabeçalho do canal no .ld
    size = struct.calcsize(fmt)

    def __init__(self, f_path, meta_ptr):
        self.f_path = f_path
        self.meta_ptr = meta_ptr
        self._data = None
        self.prev_meta_ptr = 0
        self.next_meta_ptr = 0
        self.data_ptr = 0
        self.data_len = 0
        self.dtype_code_a = 0
        self.dtype_code_b = 0
        self.freq = 0
        self.shift = 0
        self.mul = 1
        self.scale = 1
        self.dec = 0
        self.name = ""
        self.short_name = ""
        self.unit = ""
        self.np_dtype = None
        self._read_header()

    def _read_header(self):
        try:
            with open(self.f_path, "rb") as f:
                f.seek(self.meta_ptr)
                (self.prev_meta_ptr, self.next_meta_ptr, self.data_ptr, self.data_len, _,
                 self.dtype_code_a, self.dtype_code_b, self.freq,
                 self.shift, self.mul, self.scale, self.dec,
                 name_b, short_name_b, unit_b) = struct.unpack(self.fmt, f.read(self.size))

            self.name = decode_string(name_b)
            self.short_name = decode_string(short_name_b)
            self.unit = decode_string(unit_b)

            # Determina o tipo numpy baseado nos códigos lidos
            dtype_map_float = {2: np.float16, 4: np.float32}
            dtype_map_int = {2: np.int16, 4: np.int32}

            if self.dtype_code_a in [0x07]: # Float
                self.np_dtype = dtype_map_float.get(self.dtype_code_b)
            elif self.dtype_code_a in [0, 0x03, 0x05]: # Integer
                self.np_dtype = dtype_map_int.get(self.dtype_code_b)
            else:
                logger.warning(f"Tipo de dado desconhecido (a={self.dtype_code_a}, b={self.dtype_code_b}) para canal {self.name}")
                self.np_dtype = None

            # Ajusta multiplicador e escala para evitar divisão por zero
            if self.mul == 0: self.mul = 1
            if self.scale == 0: self.scale = 1

        except Exception as e:
            logger.exception(f"Erro ao ler cabeçalho do canal {self.name} em {self.meta_ptr}: {e}")
            self.np_dtype = None # Marca como inválido

    def get_data(self, start_index: int = 0, count: Optional[int] = None) -> Optional[np.ndarray]:
        """Lê os dados brutos do canal, opcionalmente um segmento."""
        if self.np_dtype is None or self.data_len == 0:
            # logger.debug(f"Canal {self.name} sem tipo de dado ou tamanho zero.")
            return None
        if count is None:
            count = self.data_len - start_index
        if start_index < 0 or count <= 0 or start_index + count > self.data_len:
             logger.error(f"Índice/contagem inválido para ler dados do canal {self.name} (start={start_index}, count={count}, total={self.data_len})")
             return None

        try:
            with open(self.f_path, "rb") as f:
                # Calcula o offset em bytes
                byte_offset = self.data_ptr + start_index * np.dtype(self.np_dtype).itemsize
                f.seek(byte_offset)
                raw_data = np.fromfile(f, count=count, dtype=self.np_dtype)

            if len(raw_data) != count:
                 logger.warning(f"Não foi possível ler todos os dados solicitados para {self.name} (lido={len(raw_data)}, esperado={count}) em {byte_offset}")
                 if len(raw_data) == 0: return None

            # Aplica conversão: (valor_bruto / escala * 10^-dec + shift) * mul
            # Garante que a conversão seja feita em float para evitar problemas com inteiros
            converted_data = (raw_data.astype(np.float64) / self.scale * pow(10., -self.dec) + self.shift) * self.mul
            return converted_data

        except Exception as e:
            logger.exception(f"Erro ao ler dados do canal {self.name}: {e}")
            return None

class _ldHead:
    # Formato simplificado, focando no necessário para TelemetrySession
    fmt = "<I4xII20xI24xHHHI8sHH4xI4x16s16x16s16x64s64s64x64s64x1024xI66x64s126x"
    size = struct.calcsize(fmt)

    def __init__(self, f_path):
        self.f_path = f_path
        self.first_chan_meta_ptr = 0
        self.event_ptr = 0
        self.driver = "Desconhecido"
        self.vehicleid = "Desconhecido"
        self.venue = "Desconhecida"
        self.datetime = None
        self.short_comment = ""
        self.event_name = ""
        self.event_session = ""
        self._read_header()

    def _read_header(self):
        try:
            with open(self.f_path, "rb") as f:
                f.seek(0)
                (_, self.first_chan_meta_ptr, _, self.event_ptr,
                 _, _, _, _, _, _, _, _, _, # Ignora campos não usados por enquanto
                 date_b, time_b,
                 driver_b, vehicleid_b, venue_b,
                 _, short_comment_b) = struct.unpack(self.fmt, f.read(self.size))

            self.driver = decode_string(driver_b)
            self.vehicleid = decode_string(vehicleid_b)
            self.venue = decode_string(venue_b)
            self.short_comment = decode_string(short_comment_b)
            date_s = decode_string(date_b)
            time_s = decode_string(time_b)

            try:
                self.datetime = datetime.datetime.strptime(f"{date_s} {time_s}", "%d/%m/%Y %H:%M:%S")
            except ValueError:
                try:
                     self.datetime = datetime.datetime.strptime(f"{date_s} {time_s}", "%d/%m/%Y %H:%M") # Tenta sem segundos
                except ValueError:
                     logger.warning(f"Não foi possível decodificar data/hora: {date_s} {time_s}")
                     self.datetime = datetime.datetime.now() # Usa data/hora atual como fallback

            # Ler informações do evento (simplificado)
            if self.event_ptr > 0:
                 try:
                     with open(self.f_path, "rb") as f:
                          f.seek(self.event_ptr)
                          # Formato do ldEvent (simplificado)
                          event_fmt = "<64s64s1024sH"
                          name_b, session_b, _, _ = struct.unpack(event_fmt, f.read(struct.calcsize(event_fmt)))
                          self.event_name = decode_string(name_b)
                          self.event_session = decode_string(session_b)
                 except Exception as e:
                      logger.warning(f"Erro ao ler informações do evento em {self.event_ptr}: {e}")

        except FileNotFoundError:
             logger.error(f"Arquivo LD não encontrado ao ler cabeçalho: {self.f_path}")
             raise # Re-lança para o parser principal tratar
        except Exception as e:
            logger.exception(f"Erro ao ler cabeçalho do arquivo LD {self.f_path}: {e}")
            # Não lança exceção aqui, permite que o parser tente continuar se possível

# Estrutura para informações do LDX
class _ldxLapInfo:
    # Formato baseado em observações e suposições (precisa de validação)
    # Parece conter um cabeçalho e depois registros por volta.
    # Cada registro de volta parece ter 12 bytes: start_offset (I), end_offset (I), lap_time (f?)
    lap_record_fmt = "<IIf" # start_offset (uint), end_offset (uint), lap_time (float32)
    lap_record_size = struct.calcsize(lap_record_fmt)
    # O cabeçalho é desconhecido, vamos pular uma quantidade fixa por enquanto
    header_size_guess = 1024 # Chute inicial, precisa ser verificado

    def __init__(self, lap_num: int, start_offset: int, end_offset: int, lap_time_s: float):
        self.lap_num = lap_num
        self.start_offset = start_offset # Índice do primeiro ponto de dados da volta
        self.end_offset = end_offset     # Índice do último ponto de dados da volta (inclusivo)
        self.lap_time_s = lap_time_s     # Tempo da volta em segundos

def _parse_ldx(ldx_file_path: str) -> Optional[List[_ldxLapInfo]]:
    """
    Analisa um arquivo .ldx para extrair informações de voltas.
    ATENÇÃO: Implementação baseada em suposições sobre o formato.
    """
    lap_infos = []
    try:
        with open(ldx_file_path, "rb") as f:
            # Pula o cabeçalho desconhecido
            f.seek(_ldxLapInfo.header_size_guess)
            lap_num = 1 # MoTeC geralmente começa as voltas do 1
            while True:
                lap_record_bytes = f.read(_ldxLapInfo.lap_record_size)
                if not lap_record_bytes or len(lap_record_bytes) < _ldxLapInfo.lap_record_size:
                    break # Fim do arquivo ou registro incompleto

                start_offset, end_offset, lap_time_s = struct.unpack(_ldxLapInfo.lap_record_fmt, lap_record_bytes)

                # Verificação básica de sanidade
                if start_offset >= end_offset or lap_time_s <= 0:
                    logger.warning(f"Registro de volta inválido no LDX {ldx_file_path}: Lap {lap_num}, Start {start_offset}, End {end_offset}, Time {lap_time_s:.3f}. Pulando.")
                    # Não incrementa lap_num aqui, pois este registro é inválido
                    continue

                lap_infos.append(_ldxLapInfo(lap_num, start_offset, end_offset, lap_time_s))
                lap_num += 1

        if not lap_infos:
            logger.warning(f"Nenhuma informação de volta válida encontrada no arquivo LDX: {ldx_file_path}")
            return None

        logger.info(f"{len(lap_infos)} voltas lidas do arquivo LDX: {ldx_file_path}")
        return lap_infos

    except FileNotFoundError:
        logger.warning(f"Arquivo LDX não encontrado: {ldx_file_path}")
        return None # Retorna None se o LDX não existir
    except Exception as e:
        logger.exception(f"Erro ao analisar o arquivo LDX {ldx_file_path}: {e}")
        return None

class MotecParser(BaseParser):
    """Parser para arquivos MoTeC .ld (com suporte opcional a .ldx)."""

    # Mapeamento de nomes de canais MoTeC para nomes padronizados
    # Precisa ser expandido com base nos canais comuns do ACC/LMU/iRacing
    CHANNEL_MAP = {
        "Time": "timestamp_s", # Ou algum canal de tempo mais preciso?
        "Distance": "distance_m",
        "Ground Speed": "speed_kmh",
        "RPM": "rpm",
        "Gear": "gear",
        "Throttle Pos": "throttle",
        "Brake Pos": "brake", # Ou Brake Pres?
        "Steered Angle": "steer_angle",
        "Clutch Pos": "clutch",
        "GPS Latitude": "gps_lat",
        "GPS Longitude": "gps_lon",
        "Pos X": "pos_x", # Verificar se existe no MoTeC ou se precisa calcular do GPS
        "Pos Y": "pos_y",
        "Pos Z": "pos_z",
        # Adicionar outros canais relevantes: temps, pressures, forces, etc.
    }

    def parse(self, file_path: str) -> Optional[TelemetrySession]:
        logger.info(f"Iniciando parsing MoTeC para: {file_path}")
        if not file_path.lower().endswith(".ld"):
            logger.error("Arquivo fornecido não é um arquivo .ld")
            return None

        ld_file_path = file_path
        ldx_file_path = file_path[:-3] + ".ldx"

        try:
            # 1. Ler Cabeçalho do LD
            ld_head = _ldHead(ld_file_path)
            if ld_head.first_chan_meta_ptr == 0:
                 logger.error("Cabeçalho LD inválido ou não contém ponteiro para canais.")
                 return None

            # 2. Ler Metadados dos Canais do LD
            channels: Dict[str, _ldChan] = {}
            meta_ptr = ld_head.first_chan_meta_ptr
            while meta_ptr:
                chan = _ldChan(ld_file_path, meta_ptr)
                if chan.name and chan.np_dtype:
                    channels[chan.name] = chan
                else:
                     logger.warning(f"Canal inválido ou sem nome/tipo em {meta_ptr}. Pulando.")
                meta_ptr = chan.next_meta_ptr

            if not channels:
                logger.error("Nenhum canal válido encontrado no arquivo LD.")
                return None
            logger.info(f"{len(channels)} canais lidos do arquivo LD.")

            # 3. Tentar Ler Informações de Voltas do LDX
            ldx_laps = _parse_ldx(ldx_file_path)

            # 4. Criar Objeto SessionInfo
            session_info = SessionInfo(
                game="Assetto Corsa Competizione" if ".ldx" in ldx_file_path.lower() else "MoTeC Genérico", # Suposição
                track=ld_head.venue,
                vehicle=ld_head.vehicleid,
                driver=ld_head.driver,
                session_type=ld_head.event_session,
                date=ld_head.datetime
            )

            # 5. Criar Objeto TrackData (placeholder)
            # Idealmente, carregar de um arquivo ou calcular a partir dos dados
            track_data = TrackData(track_name=ld_head.venue, length_m=None, sector_markers_m=[])

            # 6. Processar Voltas (ou sessão inteira se não houver LDX)
            session_laps: List[LapData] = []

            if ldx_laps:
                logger.info("Processando dados por volta usando informações do LDX...")
                for ldx_lap in ldx_laps:
                    start_idx = ldx_lap.start_offset
                    # O índice final no LDX parece ser inclusivo, então o count é end - start + 1
                    count = ldx_lap.end_offset - start_idx + 1
                    if count <= 0:
                         logger.warning(f"Contagem de pontos inválida para volta {ldx_lap.lap_num} (Start: {start_idx}, End: {ldx_lap.end_offset}). Pulando volta.")
                         continue

                    logger.debug(f"Lendo dados para Volta {ldx_lap.lap_num}: Start Index={start_idx}, Count={count}")
                    lap_data_points: List[DataPoint] = []
                    lap_channels_data: Dict[str, np.ndarray] = {}

                    # Ler dados de cada canal para esta volta
                    valid_lap = True
                    for chan_name, chan_obj in channels.items():
                        channel_data = chan_obj.get_data(start_index=start_idx, count=count)
                        if channel_data is None:
                            # Tenta ler o canal inteiro se a leitura do segmento falhar (pode ser canal de baixa freq)
                            # Isso é uma heurística, pode não ser o ideal.
                            # Uma abordagem melhor seria verificar a frequência do canal.
                            # logger.warning(f"Falha ao ler segmento do canal {chan_name} para volta {ldx_lap.lap_num}. Tentando ler completo.")
                            # channel_data = chan_obj.get_data()
                            # if channel_data is None or len(channel_data) != chan_obj.data_len:
                            #      logger.error(f"Falha ao ler dados completos do canal {chan_name}. Pulando canal para esta volta.")
                            #      # Decide se a volta inteira é inválida ou só pula o canal
                            #      # valid_lap = False; break # Descomentar para invalidar a volta
                            #      continue # Pula este canal
                            # else:
                            #      # Se leu completo, precisa alinhar/interpolar? Complexo.
                            #      # Por enquanto, vamos pular o canal se o segmento falhar.
                            logger.warning(f"Falha ao ler segmento do canal {chan_name} (Freq: {chan_obj.freq}Hz) para volta {ldx_lap.lap_num}. Pulando canal para esta volta.")
                            continue
                        elif len(channel_data) != count:
                             logger.warning(f"Tamanho incorreto lido para canal {chan_name} na volta {ldx_lap.lap_num} (lido={len(channel_data)}, esperado={count}). Pulando canal.")
                             continue

                        lap_channels_data[chan_name] = channel_data

                    # if not valid_lap: continue # Pula para próxima volta se algum canal essencial falhou

                    # Encontrar o canal de maior frequência para usar como referência de tempo/pontos
                    # Ou usar um canal garantido como 'Time' ou 'Distance'?
                    ref_channel_name = None
                    max_len = 0
                    if "Time" in lap_channels_data and len(lap_channels_data["Time"]) == count:
                        ref_channel_name = "Time"
                        max_len = count
                    elif "Distance" in lap_channels_data and len(lap_channels_data["Distance"]) == count:
                         ref_channel_name = "Distance"
                         max_len = count
                    else: # Fallback: encontra o primeiro canal com o tamanho esperado
                        for name, data in lap_channels_data.items():
                            if len(data) == count:
                                ref_channel_name = name
                                max_len = count
                                break

                    if ref_channel_name is None:
                        logger.error(f"Nenhum canal de referência encontrado para a volta {ldx_lap.lap_num}. Pulando volta.")
                        continue

                    logger.debug(f"Canal de referência para volta {ldx_lap.lap_num}: {ref_channel_name} ({max_len} pontos)")

                    # Montar DataPoints
                    # Usar pandas para facilitar o alinhamento (interpolação se necessário)
                    df_lap = pd.DataFrame()
                    for std_name, motec_name in self.CHANNEL_MAP.items():
                        if motec_name in lap_channels_data:
                            # TODO: Lidar com diferentes frequências (interpolar para a maior freq?)
                            # Por enquanto, assume que todos os canais lidos têm o mesmo tamanho `count`
                            if len(lap_channels_data[motec_name]) == max_len:
                                 df_lap[std_name] = lap_channels_data[motec_name]
                            else:
                                 logger.warning(f"Canal {motec_name} ({len(lap_channels_data[motec_name])} pts) tem tamanho diferente do ref {ref_channel_name} ({max_len} pts) na volta {ldx_lap.lap_num}. Pulando.")
                        # else: logger.debug(f"Canal mapeado {motec_name} não encontrado nos dados da volta {ldx_lap.lap_num}.")

                    # Adiciona colunas que faltam com NaN ou valor padrão
                    for col in DataPoint.__annotations__.keys():
                        if col not in df_lap.columns:
                            df_lap[col] = np.nan # Ou 0 dependendo do campo
                    # Garante colunas essenciais
                    if "timestamp_ms" not in df_lap and "timestamp_s" in df_lap:
                         df_lap["timestamp_ms"] = df_lap["timestamp_s"] * 1000
                    elif "timestamp_ms" not in df_lap:
                         logger.warning(f"Canal de tempo não encontrado para volta {ldx_lap.lap_num}. Gerando timestamps.")
                         # Tenta estimar baseado na frequência do canal de referência
                         ref_freq = channels[ref_channel_name].freq
                         if ref_freq > 0:
                              timestamps = np.linspace(0, (max_len - 1) / ref_freq, max_len) * 1000
                              df_lap["timestamp_ms"] = timestamps
                         else:
                              df_lap["timestamp_ms"] = np.arange(max_len) # Fallback pobre

                    # Converte DataFrame para lista de DataPoints
                    try:
                        lap_data_points = [DataPoint(**row._asdict()) for row in df_lap.itertuples(index=False)]
                    except Exception as e:
                         logger.exception(f"Erro ao converter DataFrame para DataPoints na volta {ldx_lap.lap_num}: {e}")
                         continue # Pula esta volta

                    # Cria objeto LapData
                    # TODO: Calcular tempos de setor se possível
                    lap = LapData(
                        lap_number=ldx_lap.lap_num,
                        lap_time_ms=int(ldx_lap.lap_time_s * 1000),
                        sector_times_ms=[],
                        is_valid=True, # Assumir como válida por enquanto
                        data_points=lap_data_points
                    )
                    session_laps.append(lap)
                    logger.info(f"Volta {ldx_lap.lap_num} processada com {len(lap_data_points)} pontos.")

            else:
                # Sem LDX, processa o arquivo LD inteiro como uma única "volta"
                logger.warning("Arquivo LDX não encontrado ou inválido. Processando arquivo LD inteiro como volta 0.")
                all_channels_data: Dict[str, np.ndarray] = {}
                max_len = 0
                ref_channel_name = None

                for chan_name, chan_obj in channels.items():
                    channel_data = chan_obj.get_data()
                    if channel_data is not None:
                        all_channels_data[chan_name] = channel_data
                        if len(channel_data) > max_len:
                             max_len = len(channel_data)
                             ref_channel_name = chan_name # Usa o canal mais longo como referência
                    else:
                         logger.warning(f"Falha ao ler dados completos do canal {chan_name}. Pulando canal.")

                if ref_channel_name is None:
                    logger.error("Nenhum dado de canal pôde ser lido do arquivo LD.")
                    return None

                df_session = pd.DataFrame()
                for std_name, motec_name in self.CHANNEL_MAP.items():
                    if motec_name in all_channels_data:
                        # TODO: Interpolar canais de baixa frequência para o tamanho max_len
                        if len(all_channels_data[motec_name]) == max_len:
                            df_session[std_name] = all_channels_data[motec_name]
                        else:
                             logger.warning(f"Canal {motec_name} ({len(all_channels_data[motec_name])} pts) tem tamanho diferente do ref {ref_channel_name} ({max_len} pts). Pulando.")

                for col in DataPoint.__annotations__.keys():
                    if col not in df_session.columns:
                        df_session[col] = np.nan
                if "timestamp_ms" not in df_session and "timestamp_s" in df_session:
                    df_session["timestamp_ms"] = df_session["timestamp_s"] * 1000
                elif "timestamp_ms" not in df_session:
                     ref_freq = channels[ref_channel_name].freq
                     if ref_freq > 0:
                          timestamps = np.linspace(0, (max_len - 1) / ref_freq, max_len) * 1000
                          df_session["timestamp_ms"] = timestamps
                     else:
                          df_session["timestamp_ms"] = np.arange(max_len)

                try:
                    session_data_points = [DataPoint(**row._asdict()) for row in df_session.itertuples(index=False)]
                except Exception as e:
                    logger.exception(f"Erro ao converter DataFrame para DataPoints (sessão inteira): {e}")
                    return None

                lap = LapData(
                    lap_number=0, # Volta 0 representa a sessão inteira
                    lap_time_ms=int(session_data_points[-1].timestamp_ms - session_data_points[0].timestamp_ms) if session_data_points else 0,
                    sector_times_ms=[],
                    is_valid=True,
                    data_points=session_data_points
                )
                session_laps.append(lap)
                logger.info(f"Sessão inteira processada como Volta 0 com {len(session_data_points)} pontos.")

            # 7. Montar e retornar TelemetrySession
            if not session_laps:
                 logger.error("Nenhuma volta pôde ser processada.")
                 return None

            telemetry_session = TelemetrySession(
                session_info=session_info,
                track_data=track_data,
                laps=session_laps
            )
            logger.info("Parsing MoTeC concluído com sucesso.")
            return telemetry_session

        except FileNotFoundError:
            logger.error(f"Arquivo LD não encontrado: {ld_file_path}")
            return None
        except Exception as e:
            logger.exception(f"Erro inesperado durante o parsing MoTeC de {file_path}: {e}")
            return None

# --- Outros Parsers (Placeholders) ---

class IBTParser(BaseParser):
    """Parser para arquivos iRacing .ibt."""
    def parse(self, file_path: str) -> Optional[TelemetrySession]:
        logger.warning("Parser IBT ainda não implementado.")
        # TODO: Implementar leitura do formato binário .ibt
        # Bibliotecas como pyirsdk podem ser úteis aqui, mas podem exigir instalação
        # ou adaptação para ler arquivos em vez de dados em tempo real.
        raise NotImplementedError("Parser IBT não implementado.")

class CSVParser(BaseParser):
    """Parser genérico para arquivos CSV (formato a ser definido)."""
    def parse(self, file_path: str) -> Optional[TelemetrySession]:
        logger.warning("Parser CSV ainda não implementado.")
        # TODO: Implementar leitura de CSV, definindo colunas esperadas
        raise NotImplementedError("Parser CSV não implementado.")

class ReplayParser(BaseParser):
    """Parser para arquivos de replay (formato específico do jogo)."""
    def parse(self, file_path: str) -> Optional[TelemetrySession]:
        logger.warning("Parser de Replay ainda não implementado.")
        # TODO: Implementar leitura de formato de replay (altamente específico)
        raise NotImplementedError("Parser de Replay não implementado.")

# --- Fábrica de Parsers ---

def get_parser(file_path: str) -> Optional[BaseParser]:
    """Retorna o parser apropriado com base na extensão do arquivo."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".ld":
        return MotecParser()
    elif ext == ".ibt":
        return IBTParser()
    elif ext == ".csv":
        return CSVParser()
    # Adicionar outras extensões (replay, etc.)
    else:
        logger.error(f"Nenhum parser encontrado para a extensão: {ext}")
        return None

