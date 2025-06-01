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
    # Formato ajustado com base na análise hexdump do arquivo ACC
    # Ordem: strings, padding, ponteiros, metadados, padding final
    fmt = "<32s8s12s40xIIIIHHHHhhh94x"
    size = struct.calcsize(fmt) # Deve ser 216 bytes

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
        self.mul = 1 # Inicializa com valor padrão
        self.scale = 1 # Inicializa com valor padrão
        self.dec = 0 # Inicializa com valor padrão
        self.name = ""
        self.short_name = ""
        self.unit = ""
        self.np_dtype = None
        self._read_header()

    def _read_header(self):
        try:
            with open(self.f_path, "rb") as f:
                f.seek(self.meta_ptr)
                header_bytes = f.read(self.size)
                if len(header_bytes) < self.size:
                    raise ValueError(f"Não foi possível ler cabeçalho completo do canal ({len(header_bytes)} < {self.size} bytes) em {self.meta_ptr:#0x}")

                # Desempacota com o formato derivado do hexdump
                (name_b, short_name_b, unit_b,
                 self.prev_meta_ptr, self.next_meta_ptr, self.data_ptr, self.data_len,
                 self.dtype_code_a, self.dtype_code_b, self.freq,
                 self.shift, self.mul, self.scale, self.dec) = struct.unpack(self.fmt, header_bytes)

            self.name = decode_string(name_b)
            self.short_name = decode_string(short_name_b)
            self.unit = decode_string(unit_b)

            # Determina o tipo numpy baseado nos códigos lidos
            dtype_map_float = {2: np.float16, 4: np.float32}
            dtype_map_int = {2: np.int16, 4: np.int32}

            # Tentativa de mapeamento específico para ACC (hipótese)
            if self.dtype_code_b == 7: # Código observado no hexdump para LAP_BEACON
                self.np_dtype = np.float32 # Suposição: float32
                logger.debug(f"Assumindo float32 para canal {self.name} baseado em dtype_code_b=7")
            elif self.dtype_code_a in [0x07]: # Float padrão
                self.np_dtype = dtype_map_float.get(self.dtype_code_b)
            elif self.dtype_code_a in [0, 0x03, 0x05]: # Integer padrão
                self.np_dtype = dtype_map_int.get(self.dtype_code_b)
            else:
                logger.warning(f"Tipo de dado desconhecido (a={self.dtype_code_a}, b={self.dtype_code_b}) para canal {self.name}")
                self.np_dtype = None

            # Ajusta multiplicador e escala para evitar divisão por zero
            if self.scale == 0:
                logger.warning(f"Escala zero encontrada para o canal {self.name}. Definindo para 1.")
                self.scale = 1
            if self.mul == 0:
                # O hexdump mostrou mul=0 para LAP_BEACON, mas isso não faz sentido para conversão.
                # Mantendo como 1 para evitar problemas, mas pode precisar de revisão.
                logger.warning(f"Multiplicador zero encontrado para o canal {self.name}. Definindo para 1.")
                self.mul = 1

            # Log para depuração
            # logger.debug(f"Canal Lido: {self.name} ({self.short_name}) | Unit: {self.unit} | Freq: {self.freq}Hz | Type: {self.np_dtype} | Len: {self.data_len} | Ptrs: Prev={self.prev_meta_ptr:#0x}, Next={self.next_meta_ptr:#0x}, Data={self.data_ptr:#0x}")

        except ValueError as ve:
            logger.error(f"Erro ao desempacotar cabeçalho do canal {self.name} em {self.meta_ptr:#0x} (tamanho {self.size}, fmt=\"{self.fmt}\"): {ve}", exc_info=True)
            self.np_dtype = None # Marca como inválido
        except Exception as e:
            logger.exception(f"Erro inesperado ao ler cabeçalho do canal {self.name} em {self.meta_ptr:#0x}: {e}")
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
                 logger.warning(f"Não foi possível ler todos os dados solicitados para {self.name} (lido={len(raw_data)}, esperado={count}) em {byte_offset:#0x}")
                 if len(raw_data) == 0: return None

            # Aplica conversão: (valor_bruto / escala * 10^-dec + shift) * mul
            # Garante que a conversão seja feita em float para evitar problemas com inteiros
            converted_data = (raw_data.astype(np.float64) / self.scale * pow(10., -self.dec) + self.shift) * self.mul
            return converted_data

        except Exception as e:
            logger.exception(f"Erro ao ler dados do canal {self.name}: {e}")
            return None

class _ldHead:
    # Formato atualizado baseado na análise do arquivo real
    fmt = "<II4xII76x16s16x16s16x64s64s64s64s"
    size = struct.calcsize(fmt)

    def __init__(self, f_path):
        self.f_path = f_path
        self.magic = 0
        self.version = 0
        self.first_chan_meta_ptr = 0 # Este ponteiro parece inválido nos arquivos ACC
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
                header_bytes = f.read(self.size)
                if len(header_bytes) < self.size:
                    raise ValueError(f"Não foi possível ler o cabeçalho completo ({len(header_bytes)} < {self.size} bytes)")

                # Desempacota os campos definidos no fmt atualizado
                (self.magic, self.version, self.first_chan_meta_ptr, self.event_ptr,
                 date_b, time_b,
                 driver_b, vehicleid_b, venue_b, short_comment_b) = struct.unpack(self.fmt, header_bytes)

            # Decodifica strings
            self.driver = decode_string(driver_b)
            self.vehicleid = decode_string(vehicleid_b)
            self.venue = decode_string(venue_b)
            self.short_comment = decode_string(short_comment_b)
            date_s = decode_string(date_b)
            time_s = decode_string(time_b)

            # Leitura direta de strings em offsets específicos se os campos acima estiverem vazios
            if not self.venue and not date_s and not time_s:
                with open(self.f_path, "rb") as f:
                    # Lê data em offset 0x5E
                    f.seek(0x5E)
                    date_b = f.read(16)
                    date_s = decode_string(date_b)

                    # Lê hora em offset 0x7E
                    f.seek(0x7E)
                    time_b = f.read(16)
                    time_s = decode_string(time_b)

                    # Lê pista em offset 0x15E
                    f.seek(0x15E)
                    venue_b = f.read(16)
                    self.venue = decode_string(venue_b)

            # Processa data e hora
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
                        event_size = struct.calcsize(event_fmt)
                        event_bytes = f.read(event_size)
                        if len(event_bytes) == event_size:
                            name_b, session_b, _, _ = struct.unpack(event_fmt, event_bytes)
                            self.event_name = decode_string(name_b)
                            self.event_session = decode_string(session_b)
                        else:
                            logger.warning(f"Não foi possível ler dados completos do evento em {self.event_ptr:#0x}")
                except Exception as e:
                    logger.warning(f"Erro ao ler informações do evento em {self.event_ptr:#0x}: {e}")

        except FileNotFoundError:
            logger.error(f"Arquivo LD não encontrado ao ler cabeçalho: {self.f_path}")
            raise # Re-lança para o parser principal tratar
        except ValueError as ve: # Captura erro de unpack especificamente
            logger.error(f"Erro ao desempacotar cabeçalho LD (tamanho {self.size}, fmt=\"{self.fmt}\"): {ve}", exc_info=True)
            raise # Re-lança para o parser principal tratar
        except Exception as e:
            logger.exception(f"Erro inesperado ao ler cabeçalho do arquivo LD {self.f_path}: {e}")
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
        # Mapeamentos adicionados baseados na análise profunda
        "LAP_BEACON": "lap_beacon",
        "ROTY": "rot_y",
        "STEERANGLE": "steer_angle", # Já mapeado, mas confirma nome
        "SPEED": "speed_kmh", # Já mapeado
        "THROTTLE": "throttle", # Já mapeado
        "BRAKE": "brake", # Já mapeado
        "GEAR": "gear", # Já mapeado
        "CLUTCH": "clutch", # Já mapeado
        "RPMS": "rpm", # Já mapeado
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

    # Offset inicial onde os canais parecem começar (baseado na análise profunda)
    FIRST_CHANNEL_OFFSET_GUESS = 0x2c68 # Offset de 'LAP_BEACON'

    def parse(self, file_path: str) -> Optional[TelemetrySession]:
        logger.info(f"Iniciando parsing MoTeC para: {file_path}")

        # Verifica se é um arquivo .ld ou .ldx
        if file_path.lower().endswith(".ldx"):
            # Se for .ldx, encontra o .ld correspondente
            ld_file_path = file_path[:-1]  # Remove o 'x' do final
            ldx_file_path = file_path
            if not os.path.exists(ld_file_path):
                logger.error(f"Arquivo .ld correspondente não encontrado para {ldx_file_path}")
                return None
        elif file_path.lower().endswith(".ld"):
            # Se for .ld, verifica se existe um .ldx correspondente
            ld_file_path = file_path
            ldx_file_path = file_path + "x"  # Adiciona 'x' ao final
            if not os.path.exists(ldx_file_path):
                logger.warning(f"Arquivo .ldx correspondente não encontrado para {ld_file_path}. Processando apenas o .ld.")
                ldx_file_path = None
        else:
            logger.error("Arquivo fornecido não é um arquivo .ld ou .ldx")
            return None

        try:
            # 1. Ler Cabeçalho do LD
            ld_head = _ldHead(ld_file_path)
            # O ponteiro ld_head.first_chan_meta_ptr é ignorado, pois parece inválido

            # 2. Ler Metadados dos Canais do LD
            channels: Dict[str, _ldChan] = {}
            # Começa a busca pelo primeiro canal a partir do offset estimado
            meta_ptr = self.FIRST_CHANNEL_OFFSET_GUESS
            processed_offsets = set()
            channel_count = 0

            # Tenta ler o primeiro canal no offset estimado
            try:
                first_chan = _ldChan(ld_file_path, meta_ptr)
                if first_chan.name and first_chan.np_dtype:
                    logger.info(f"Primeiro canal encontrado em 0x{meta_ptr:08x}: {first_chan.name} (Tipo: {first_chan.np_dtype})")
                    channels[first_chan.name] = first_chan
                    processed_offsets.add(meta_ptr)
                    channel_count += 1
                    # Segue a lista encadeada a partir do primeiro canal
                    meta_ptr = first_chan.next_meta_ptr
                else:
                    logger.error(f"Não foi possível ler um canal válido no offset estimado 0x{meta_ptr:08x}. Verifique o formato e tipo do canal.")
                    return None # Aborta se o primeiro canal falhar
            except Exception as e:
                logger.error(f"Erro ao tentar ler o primeiro canal em 0x{meta_ptr:08x}: {e}. Abortando.")
                return None

            # Segue a lista encadeada
            while meta_ptr != 0 and meta_ptr not in processed_offsets:
                processed_offsets.add(meta_ptr)
                try:
                    chan = _ldChan(ld_file_path, meta_ptr)
                    if chan.name and chan.np_dtype:
                        # logger.debug(f"Canal lido em 0x{meta_ptr:08x}: {chan.name} (Tipo: {chan.np_dtype})")
                        channels[chan.name] = chan
                        channel_count += 1
                        meta_ptr = chan.next_meta_ptr
                    else:
                        logger.warning(f"Canal inválido ou sem nome/tipo em 0x{meta_ptr:08x}. Interrompendo lista encadeada.")
                        break
                except Exception as e:
                    logger.error(f"Erro ao ler canal em 0x{meta_ptr:08x}: {e}. Interrompendo lista encadeada.")
                    break
                # Limite para evitar loops infinitos
                if len(processed_offsets) > 1000: # Aumentado o limite
                    logger.error("Limite de canais processados atingido (1000). Possível loop na lista encadeada.")
                    break

            if not channels:
                logger.error("Nenhum canal válido encontrado no arquivo LD.")
                return None
            logger.info(f"{channel_count} canais lidos do arquivo LD.")

            # 3. Tentar Ler Informações de Voltas do LDX
            ldx_laps = None
            if ldx_file_path and os.path.exists(ldx_file_path):
                ldx_laps = _parse_ldx(ldx_file_path)

            # 4. Criar Objeto SessionInfo (CORRIGIDO)
            session_info = SessionInfo(
                game="Assetto Corsa Competizione" if ldx_file_path and ldx_file_path.lower().endswith(".ldx") else "MoTeC Genérico",
                track=ld_head.venue,
                car=ld_head.vehicleid, # Corrigido de 'vehicle'
                date=ld_head.datetime.isoformat() if ld_head.datetime else "N/A", # Formato ISO
                source=f"import:{os.path.basename(file_path)}", # Adicionado source
                driver_name=ld_head.driver, # Corrigido de 'driver'
                session_type=ld_head.event_session
            )

            # 5. Criar Objeto TrackData (CORRIGIDO)
            track_data = TrackData(
                name=ld_head.venue, # Corrigido de 'track_name'
                length_meters=None, # Corrigido de 'length_m'
                sector_markers_m=[]
            )

            # 6. Processar Voltas (ou sessão inteira se não houver LDX)
            session_laps: List[LapData] = []

            if ldx_laps:
                logger.info("Processando dados por volta usando informações do LDX...")
                for ldx_lap in ldx_laps:
                    start_idx = ldx_lap.start_offset
                    # O índice final no LDX parece ser inclusivo, então o count é end - start + 1
                    count = ldx_lap.end_offset - start_idx + 1

                    # Cria um dicionário para armazenar os dados de cada canal para esta volta
                    lap_data_dict = {}
                    min_samples_in_lap = float('inf')

                    # Lê os dados de cada canal para esta volta
                    for chan_name, chan in channels.items():
                        chan_data = chan.get_data(start_idx, count)
                        if chan_data is not None and len(chan_data) > 0:
                            # Mapeia o nome do canal para o nome padronizado, se disponível
                            std_name = self.CHANNEL_MAP.get(chan_name, chan_name)
                            lap_data_dict[std_name] = chan_data
                            min_samples_in_lap = min(min_samples_in_lap, len(chan_data))
                        # else:
                            # logger.debug(f"Sem dados para canal {chan_name} na volta {ldx_lap.lap_num}")

                    # Verifica se temos dados suficientes para criar uma volta válida
                    if not lap_data_dict or min_samples_in_lap == float('inf'):
                        logger.warning(f"Nenhum dado válido encontrado para a volta {ldx_lap.lap_num}. Pulando.")
                        continue

                    # Cria DataPoints para esta volta, truncando para o menor número de amostras
                    data_points = []
                    num_samples = min_samples_in_lap

                    # Tenta encontrar um canal de timestamp
                    timestamp_key = None
                    if 'timestamp_s' in lap_data_dict:
                        timestamp_key = 'timestamp_s'
                    elif 'Time' in lap_data_dict:
                        timestamp_key = 'Time'

                    for i in range(num_samples):
                        point_data = {key: values[i] for key, values in lap_data_dict.items() if len(values) >= num_samples}
                        # Converte timestamp para ms se existir
                        if timestamp_key and timestamp_key in point_data:
                            point_data['timestamp_ms'] = int(point_data[timestamp_key] * 1000)
                            # Remove a chave original se for diferente de 'timestamp_ms'
                            if timestamp_key != 'timestamp_ms':
                                del point_data[timestamp_key]
                        else:
                            # Se não houver timestamp, tenta estimar ou deixa 0
                            # Poderia usar a frequência do canal, mas é complexo
                            point_data['timestamp_ms'] = 0 # Ou alguma outra lógica

                        # Adiciona outros campos obrigatórios do DataPoint se não existirem
                        point_data.setdefault('distance_m', 0.0)
                        point_data.setdefault('lap_time_ms', 0)
                        point_data.setdefault('sector', 0)
                        point_data.setdefault('pos_x', 0.0)
                        point_data.setdefault('pos_y', 0.0)
                        point_data.setdefault('pos_z', 0.0)
                        point_data.setdefault('speed_kmh', 0.0)
                        point_data.setdefault('rpm', 0)
                        point_data.setdefault('gear', 0)
                        point_data.setdefault('steer_angle', 0.0)
                        point_data.setdefault('throttle', 0.0)
                        point_data.setdefault('brake', 0.0)
                        point_data.setdefault('clutch', 0.0)

                        # Remove chaves que não pertencem ao DataPoint
                        allowed_keys = DataPoint.__annotations__.keys()
                        point_data_filtered = {k: v for k, v in point_data.items() if k in allowed_keys}

                        try:
                            data_points.append(DataPoint(**point_data_filtered))
                        except TypeError as te:
                            logger.error(f"Erro ao criar DataPoint na volta {ldx_lap.lap_num}, amostra {i}: {te}. Dados: {point_data_filtered}")
                            # Decide se quer pular a amostra ou a volta inteira
                            continue # Pula esta amostra

                    # Cria o objeto LapData
                    lap_data = LapData(
                        lap_number=ldx_lap.lap_num,
                        lap_time_ms=int(ldx_lap.lap_time_s * 1000), # Converte para ms
                        is_valid=True,  # Assumimos que todas as voltas no LDX são válidas
                        data_points=data_points
                    )

                    session_laps.append(lap_data)
            else:
                logger.info("Nenhuma informação de volta encontrada. Processando sessão inteira como uma única volta...")

                # Processa todos os dados como uma única "volta"
                lap_data_dict = {}
                min_samples_in_session = float('inf')

                # Lê os dados de cada canal
                for chan_name, chan in channels.items():
                    chan_data = chan.get_data()
                    if chan_data is not None and len(chan_data) > 0:
                        # Mapeia o nome do canal para o nome padronizado, se disponível
                        std_name = self.CHANNEL_MAP.get(chan_name, chan_name)
                        lap_data_dict[std_name] = chan_data
                        min_samples_in_session = min(min_samples_in_session, len(chan_data))
                    # else:
                        # logger.debug(f"Sem dados para canal {chan_name} na sessão inteira")

                # Verifica se temos dados suficientes
                if not lap_data_dict or min_samples_in_session == float('inf'):
                    logger.error("Nenhum dado válido encontrado na sessão.")
                    return None

                # Cria DataPoints, truncando para o menor número de amostras
                data_points = []
                num_samples = min_samples_in_session

                # Tenta encontrar um canal de timestamp
                timestamp_key = None
                if 'timestamp_s' in lap_data_dict:
                    timestamp_key = 'timestamp_s'
                elif 'Time' in lap_data_dict:
                    timestamp_key = 'Time'

                for i in range(num_samples):
                    point_data = {key: values[i] for key, values in lap_data_dict.items() if len(values) >= num_samples}
                    # Converte timestamp para ms se existir
                    if timestamp_key and timestamp_key in point_data:
                        point_data['timestamp_ms'] = int(point_data[timestamp_key] * 1000)
                        if timestamp_key != 'timestamp_ms':
                            del point_data[timestamp_key]
                    else:
                        point_data['timestamp_ms'] = 0

                    # Adiciona outros campos obrigatórios do DataPoint se não existirem
                    point_data.setdefault('distance_m', 0.0)
                    point_data.setdefault('lap_time_ms', 0)
                    point_data.setdefault('sector', 0)
                    point_data.setdefault('pos_x', 0.0)
                    point_data.setdefault('pos_y', 0.0)
                    point_data.setdefault('pos_z', 0.0)
                    point_data.setdefault('speed_kmh', 0.0)
                    point_data.setdefault('rpm', 0)
                    point_data.setdefault('gear', 0)
                    point_data.setdefault('steer_angle', 0.0)
                    point_data.setdefault('throttle', 0.0)
                    point_data.setdefault('brake', 0.0)
                    point_data.setdefault('clutch', 0.0)

                    # Remove chaves que não pertencem ao DataPoint
                    allowed_keys = DataPoint.__annotations__.keys()
                    point_data_filtered = {k: v for k, v in point_data.items() if k in allowed_keys}

                    try:
                        data_points.append(DataPoint(**point_data_filtered))
                    except TypeError as te:
                        logger.error(f"Erro ao criar DataPoint na sessão inteira, amostra {i}: {te}. Dados: {point_data_filtered}")
                        continue # Pula esta amostra

                # Cria o objeto LapData (uma única "volta" contendo todos os dados)
                lap_data = LapData(
                    lap_number=1,
                    lap_time_ms=0,  # Não temos informação de tempo de volta
                    is_valid=True,
                    data_points=data_points
                )

                session_laps.append(lap_data)

            # 7. Criar e retornar o objeto TelemetrySession
            if not session_laps:
                logger.error("Nenhuma volta válida processada.")
                return None

            telemetry_session = TelemetrySession(
                session_info=session_info,
                track_data=track_data,
                laps=session_laps
            )

            logger.info(f"Parsing MoTeC concluído com sucesso: {len(session_laps)} voltas processadas.")
            return telemetry_session

        except Exception as e:
            logger.exception(f"Erro ao processar arquivo MoTeC {file_path}: {e}")
            return None

# --- Parser iRacing IBT ---
class IBTParser(BaseParser):
    """Parser para arquivos iRacing .ibt."""

    def parse(self, file_path: str) -> Optional[TelemetrySession]:
        logger.error("Parser IBT não implementado completamente.")
        return None

# --- Parser CSV Genérico ---
class CSVParser(BaseParser):
    """Parser para arquivos CSV genéricos."""

    def parse(self, file_path: str) -> Optional[TelemetrySession]:
        logger.error("Parser CSV não implementado completamente.")
        return None

# --- Factory para criar o parser apropriado ---
def create_parser(file_path: str) -> Optional[BaseParser]:
    """
    Cria o parser apropriado com base na extensão do arquivo.

    Args:
        file_path: Caminho para o arquivo de telemetria.

    Returns:
        Um objeto parser apropriado, ou None se o formato não for suportado.
    """
    file_ext = os.path.splitext(file_path)[1].lower()

    if file_ext == ".ld" or file_ext == ".ldx":
        return MotecParser()
    elif file_ext == ".ibt":
        return IBTParser()
    elif file_ext == ".csv":
        return CSVParser()
    else:
        logger.error(f"Formato de arquivo não suportado: {file_ext}")
        return None
