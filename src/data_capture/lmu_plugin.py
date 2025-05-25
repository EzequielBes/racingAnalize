"""
Adaptador para captura de telemetria do Le Mans Ultimate.
Utiliza o plugin MoTeC DAM para acessar dados do simulador.
"""

import os
import sys
import time
import logging
import json
import glob
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import shutil
import struct
import numpy as np
import threading
import copy # Para cópias seguras

# Configuração de logging
logger = logging.getLogger("race_telemetry_api.lmu")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
if not logger.hasHandlers():
    logger.addHandler(handler)


class LDParser:
    """Parser para arquivos binários LD do MoTeC."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data = {}
        self.channels = {}
        self.samples = {}
        self.header = {}
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        if not file_path.lower().endswith(".ld"):
            raise ValueError(f"Arquivo não é um arquivo LD: {file_path}")
    
    def parse(self) -> Dict[str, Any]:
        """Analisa o arquivo LD e retorna dados processados."""
        try:
            with open(self.file_path, "rb") as f:
                self._parse_header(f)
                self._parse_channels(f)
                self._parse_data(f)
                self._process_data()
                # Retorna apenas os dados processados relevantes (laps, etc.)
                return self.data 
        except Exception as e:
            logger.error(f"Erro ao analisar arquivo LD {self.file_path}: {str(e)}")
            raise
    
    def _parse_header(self, f):
        f.seek(0)
        signature = f.read(8)
        if signature != b"LDFILE\x00\x00":
            raise ValueError(f"Assinatura inválida: {signature}")
        self.header["version"] = struct.unpack("<I", f.read(4))[0]
        self.header["num_channels"] = struct.unpack("<I", f.read(4))[0]
        self.header["sample_rate"] = struct.unpack("<f", f.read(4))[0]
        self.header["num_samples"] = struct.unpack("<I", f.read(4))[0]
        logger.info(f"Cabeçalho LD: v={self.header['version']}, ch={self.header['num_channels']}, rate={self.header['sample_rate']}Hz, samples={self.header['num_samples']}")

    def _parse_channels(self, f):
        f.seek(24)
        for i in range(self.header["num_channels"]):
            name_len = struct.unpack("<I", f.read(4))[0]
            name = f.read(name_len).decode("utf-8", errors="ignore")
            unit_len = struct.unpack("<I", f.read(4))[0]
            unit = f.read(unit_len).decode("utf-8", errors="ignore")
            data_type = struct.unpack("<I", f.read(4))[0]
            scale = struct.unpack("<f", f.read(4))[0]
            offset = struct.unpack("<f", f.read(4))[0]
            self.channels[i] = {"name": name, "unit": unit, "data_type": data_type, "scale": scale, "offset": offset}
            # logger.debug(f"Canal {i}: {name} ({unit})")

    def _parse_data(self, f):
        # Calcula o tamanho esperado dos dados
        bytes_per_sample = 4 # Assumindo float32
        expected_data_size = self.header["num_samples"] * self.header["num_channels"] * bytes_per_sample
        
        # Calcula a posição inicial dos dados
        # Tamanho do cabeçalho + tamanho total das definições de canal
        f.seek(24) # Posição após cabeçalho
        channel_def_size = 0
        for i in range(self.header["num_channels"]):
             # name_len(4) + name + unit_len(4) + unit + type(4) + scale(4) + offset(4)
             name_len = len(self.channels[i]["name"].encode("utf-8"))
             unit_len = len(self.channels[i]["unit"].encode("utf-8"))
             channel_def_size += 4 + name_len + 4 + unit_len + 4 + 4 + 4
             
        data_start_pos = 24 + channel_def_size
        f.seek(data_start_pos)
        
        # Lê os dados brutos
        raw_data = f.read(expected_data_size)
        if len(raw_data) != expected_data_size:
             logger.warning(f"Tamanho dos dados lidos ({len(raw_data)}) diferente do esperado ({expected_data_size}) para {self.file_path}")
             # Tenta ajustar o número de amostras se possível
             actual_samples = len(raw_data) // (self.header["num_channels"] * bytes_per_sample)
             if actual_samples > 0:
                  logger.info(f"Ajustando número de amostras para {actual_samples}")
                  self.header["num_samples"] = actual_samples
                  expected_data_size = actual_samples * self.header["num_channels"] * bytes_per_sample
                  raw_data = raw_data[:expected_data_size] # Trunca se necessário
             else:
                  raise ValueError("Não foi possível ler dados suficientes do arquivo LD.")

        # Converte para array numpy
        data_array = np.frombuffer(raw_data, dtype=np.float32)
        data_array = data_array.reshape((self.header["num_samples"], self.header["num_channels"]))
        
        # Armazena e processa dados por canal
        for i in range(self.header["num_channels"]):
            channel_data = data_array[:, i]
            scale = self.channels[i]["scale"]
            offset = self.channels[i]["offset"]
            # Aplica escala e offset apenas se não forem triviais
            if scale != 1.0 or offset != 0.0:
                 channel_data = channel_data * scale + offset
            self.samples[self.channels[i]["name"]] = channel_data

    def _process_data(self):
        """Processa os dados extraídos para o formato desejado."""
        self.data = {
            "laps": [],
            # Adiciona informações básicas se disponíveis
            "session": {
                 "sample_rate": self.header.get("sample_rate", 0)
            }
        }
        self._process_lap_data()

    def _process_lap_data(self):
        """Processa os dados de volta a partir dos samples."""
        # Nomes comuns dos canais MoTeC (case-insensitive matching)
        lap_ch = self._find_channel(["Lap", "Lap Count", "Laps"]) 
        lap_time_ch = self._find_channel(["Lap Time", "Time"]) 
        lap_dist_ch = self._find_channel(["Lap Distance", "Distance"]) 
        sector_ch = self._find_channel(["Sector", "Sector Index"]) 
        speed_ch = self._find_channel(["Speed", "Ground Speed"]) 
        rpm_ch = self._find_channel(["RPM", "Engine RPM"]) 
        gear_ch = self._find_channel(["Gear"]) 
        throttle_ch = self._find_channel(["Throttle", "Throttle Pos"]) 
        brake_ch = self._find_channel(["Brake", "Brake Pos", "Brake Pressure"]) 
        steer_ch = self._find_channel(["Steering", "Steer Angle"]) 
        pos_x_ch = self._find_channel(["Pos X", "GPS Pos X", "X Pos"]) 
        pos_y_ch = self._find_channel(["Pos Y", "GPS Pos Y", "Y Pos"]) 
        pos_z_ch = self._find_channel(["Pos Z", "GPS Pos Z", "Z Pos"]) 

        if not lap_ch or not lap_time_ch:
            logger.warning(f"Canais essenciais 'Lap' ou 'Lap Time' não encontrados em {self.file_path}")
            return

        lap_numbers = self.samples[lap_ch]
        lap_times = self.samples[lap_time_ch]
        num_samples = self.header["num_samples"]

        # Identifica mudanças de volta
        lap_change_indices = np.where(np.diff(lap_numbers) > 0)[0] + 1
        start_indices = np.insert(lap_change_indices, 0, 0)
        end_indices = np.append(lap_change_indices, num_samples)

        laps_data = []
        for i in range(len(start_indices)):
            start_idx = start_indices[i]
            end_idx = end_indices[i]
            current_lap_number = int(lap_numbers[start_idx])

            # Ignora voltas inválidas (e.g., volta 0 ou outlap)
            if current_lap_number <= 0:
                continue

            # Extrai dados para a volta atual
            lap_slice_indices = np.arange(start_idx, end_idx)
            if len(lap_slice_indices) == 0:
                 continue
                 
            final_lap_time = lap_times[end_idx - 1] - lap_times[start_idx]

            # Extrai setores (se disponível)
            sectors = []
            if sector_ch:
                sector_numbers = self.samples[sector_ch][lap_slice_indices]
                sector_change_indices = np.where(np.diff(sector_numbers) != 0)[0] + 1
                sector_start_indices = np.insert(sector_change_indices, 0, 0)
                sector_end_indices = np.append(sector_change_indices, len(lap_slice_indices))
                
                for j in range(len(sector_start_indices)):
                     sec_start = sector_start_indices[j]
                     sec_end = sector_end_indices[j]
                     sector_num = int(sector_numbers[sec_start])
                     if sector_num > 0:
                          sector_time = lap_times[lap_slice_indices[sec_end - 1]] - lap_times[lap_slice_indices[sec_start]]
                          sectors.append({"sector": sector_num, "time": sector_time})

            # Extrai pontos de dados
            data_points = []
            for k in lap_slice_indices:
                point = {
                    "time": lap_times[k] - lap_times[start_idx], # Tempo relativo ao início da volta
                    "distance": float(self.samples[lap_dist_ch][k]) if lap_dist_ch else 0.0,
                    "position": [
                        float(self.samples[pos_x_ch][k]) if pos_x_ch else 0.0,
                        float(self.samples[pos_y_ch][k]) if pos_y_ch else 0.0,
                        float(self.samples[pos_z_ch][k]) if pos_z_ch else 0.0
                    ],
                    "speed": float(self.samples[speed_ch][k]) if speed_ch else 0.0,
                    "rpm": int(self.samples[rpm_ch][k]) if rpm_ch else 0,
                    "gear": int(self.samples[gear_ch][k]) if gear_ch else 0,
                    "throttle": float(self.samples[throttle_ch][k]) if throttle_ch else 0.0,
                    "brake": float(self.samples[brake_ch][k]) if brake_ch else 0.0,
                    "steer": float(self.samples[steer_ch][k]) if steer_ch else 0.0,
                    "sector": int(self.samples[sector_ch][k]) if sector_ch else 0
                }
                data_points.append(point)

            lap_data = {
                "lap_number": current_lap_number,
                "lap_time": final_lap_time,
                "sectors": sectors,
                "data_points": data_points
            }
            laps_data.append(lap_data)

        self.data["laps"] = laps_data
        logger.info(f"Processadas {len(laps_data)} voltas do arquivo {self.file_path}")

    def _find_channel(self, possible_names: List[str]) -> Optional[str]:
        """Encontra o nome real de um canal MoTeC (case-insensitive)."""
        for actual_name in self.samples.keys():
            for possible_name in possible_names:
                if possible_name.lower() == actual_name.lower():
                    return actual_name
        return None


class LMUTelemetryCapture:
    """Classe para captura de telemetria do Le Mans Ultimate."""
    
    def __init__(self):
        self.motec_folder = None
        self.is_connected = False
        self.is_capturing = False
        self.capture_start_time = None
        self.last_check_time = 0
        self.processed_files = set()
        self.watch_thread = None
        self.stop_event = threading.Event()
        self.data_lock = threading.Lock() # Lock para proteger acesso a telemetry_data
        self.telemetry_data = {"session": {}, "laps": []}
        logger.info("Inicializando capturador de telemetria do Le Mans Ultimate")
        self._find_motec_folder()
    
    def _find_motec_folder(self):
        # (Código para encontrar pasta MoTeC - sem alterações)
        possible_paths = [
            os.path.join(os.path.expanduser("~"), "Documents", "Le Mans Ultimate", "MoTeC"),
            os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Le Mans Ultimate", "MoTeC"),
            os.path.join(os.path.expanduser("~"), "OneDrive", "Documents", "Le Mans Ultimate", "MoTeC"),
            os.path.join("C:\\", "Users", os.getenv("USERNAME", ""), "Documents", "Le Mans Ultimate", "MoTeC"),
            os.path.join("C:\\", "Users", os.getenv("USERNAME", ""), "Documents", "My Games", "Le Mans Ultimate", "MoTeC"),
            os.path.join("C:\\", "Users", os.getenv("USERNAME", ""), "OneDrive", "Documents", "Le Mans Ultimate", "MoTeC")
        ]
        for path in possible_paths:
            if os.path.exists(path) and os.path.isdir(path):
                self.motec_folder = path
                logger.info(f"Pasta MoTeC encontrada automaticamente: {path}")
                return
        logger.warning("Pasta MoTeC não encontrada automaticamente")

    def connect(self) -> bool:
        logger.info("Tentando conectar ao Le Mans Ultimate")
        if not self.motec_folder or not os.path.exists(self.motec_folder):
            logger.error(f"Pasta do MoTeC não encontrada ou inacessível: {self.motec_folder}")
            return False
        self._update_session_info() # Tenta ler info de arquivos existentes
        self.is_connected = True
        logger.info(f"Conectado ao Le Mans Ultimate via pasta MoTeC: {self.motec_folder}")
        return True
    
    def disconnect(self) -> bool:
        logger.info("Tentando desconectar do Le Mans Ultimate")
        if self.is_capturing:
            self.stop_capture()
        self.is_connected = False
        logger.info("Desconectado do Le Mans Ultimate")
        return True
    
    def start_capture(self) -> bool:
        logger.info("Tentando iniciar captura de telemetria do Le Mans Ultimate")
        if not self.is_connected:
            logger.error("Não está conectado ao Le Mans Ultimate")
            return False
        if self.is_capturing:
            logger.warning("Já está capturando telemetria do Le Mans Ultimate")
            return False
        
        with self.data_lock:
            self.is_capturing = True
            self.capture_start_time = time.time()
            self.last_check_time = time.time()
            self.processed_files = set(self._get_telemetry_files())
            # Limpa voltas anteriores, mantém info da sessão
            self.telemetry_data["laps"] = [] 
        
        self.stop_event.clear()
        self.watch_thread = threading.Thread(target=self._watch_folder, daemon=True)
        self.watch_thread.start()
        logger.info("Captura de telemetria do Le Mans Ultimate iniciada com sucesso")
        return True
    
    def stop_capture(self) -> bool:
        logger.info("Tentando parar captura de telemetria do Le Mans Ultimate")
        if not self.is_capturing:
            logger.warning("Não está capturando telemetria do Le Mans Ultimate")
            return False
        
        self.stop_event.set()
        if self.watch_thread and self.watch_thread.is_alive():
            self.watch_thread.join(timeout=2.0)
        
        with self.data_lock:
             self.is_capturing = False
             telemetry_to_save = copy.deepcopy(self.telemetry_data)

        logger.info("Captura de telemetria do Le Mans Ultimate parada com sucesso")
        # Salva os dados acumulados (se houver)
        self._save_telemetry_data(telemetry_to_save)
        return True

    def get_telemetry_data(self) -> Dict[str, Any]:
        """Retorna uma cópia segura dos dados de telemetria atuais."""
        with self.data_lock:
            return copy.deepcopy(self.telemetry_data)

    def _watch_folder(self):
        """Monitora a pasta MoTeC por novos arquivos (executado em thread)."""
        logger.info(f"Monitorando pasta: {self.motec_folder}")
        while not self.stop_event.is_set():
            try:
                current_files = set(self._get_telemetry_files())
                new_files = current_files - self.processed_files
                
                if new_files:
                    logger.info(f"Novos arquivos detectados: {len(new_files)}")
                    # Prioriza processar LDX para info de sessão, depois LD
                    new_ldx = sorted([f for f in new_files if f.lower().endswith(".ldx")])
                    new_ld = sorted([f for f in new_files if f.lower().endswith(".ld")])
                    
                    for file_path in new_ldx:
                        self._process_ldx_file(file_path)
                        self.processed_files.add(file_path)
                        
                    for file_path in new_ld:
                        self._process_ld_file(file_path)
                        self.processed_files.add(file_path)
                        
                self.last_check_time = time.time()
            except Exception as e:
                logger.error(f"Erro no loop de monitoramento: {e}")
            
            # Espera antes da próxima verificação
            self.stop_event.wait(5.0) # Verifica a cada 5 segundos
        logger.info("Monitoramento da pasta MoTeC finalizado.")

    def _get_telemetry_files(self) -> List[str]:
        """Retorna lista de arquivos LD e LDX na pasta MoTeC."""
        if not self.motec_folder:
            return []
        try:
            ldx_files = glob.glob(os.path.join(self.motec_folder, "*.ldx"))
            ld_files = glob.glob(os.path.join(self.motec_folder, "*.ld"))
            return ldx_files + ld_files
        except Exception as e:
            logger.error(f"Erro ao listar arquivos de telemetria: {e}")
            return []

    def _process_ldx_file(self, file_path: str):
        """Processa um arquivo LDX para obter informações da sessão."""
        logger.info(f"Processando arquivo LDX: {file_path}")
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            session_info = {}
            session_node = root.find("Session")
            if session_node is not None:
                vehicle = session_node.find("Vehicle")
                venue = session_node.find("Venue")
                driver = session_node.find("Driver")
                session_info["car"] = vehicle.get("name") if vehicle is not None else "Desconhecido"
                session_info["track"] = venue.get("name") if venue is not None else "Desconhecida"
                session_info["player"] = driver.get("name") if driver is not None else "Piloto"
                # Adiciona outras informações se disponíveis no LDX
                session_info["conditions"] = "Seco" # Exemplo, LDX pode não ter
                session_info["temperature"] = {"air": 20, "track": 25} # Exemplo
            
            # Atualiza a sessão principal com lock
            with self.data_lock:
                 # Mescla, mantendo dados existentes se não encontrados no LDX
                 current_session = self.telemetry_data.get("session", {})
                 current_session.update(session_info)
                 self.telemetry_data["session"] = current_session
                 
            logger.info(f"Informações da sessão atualizadas pelo LDX: {session_info}")
            
        except ET.ParseError:
            logger.error(f"Erro ao analisar XML do arquivo LDX: {file_path}")
        except Exception as e:
            logger.error(f"Erro ao processar arquivo LDX {file_path}: {e}")

    def _process_ld_file(self, file_path: str):
        """Processa um arquivo LD para obter dados de voltas."""
        logger.info(f"Processando arquivo LD: {file_path}")
        try:
            parser = LDParser(file_path)
            parsed_data = parser.parse()
            
            # Extrai as voltas processadas
            new_laps = parsed_data.get("laps", [])
            
            if new_laps:
                # Adiciona as novas voltas aos dados principais com lock
                with self.data_lock:
                    # Evita duplicatas (baseado no número da volta, pode precisar de lógica melhor)
                    existing_lap_numbers = {lap.get("lap_number") for lap in self.telemetry_data.get("laps", [])}
                    laps_to_add = [lap for lap in new_laps if lap.get("lap_number") not in existing_lap_numbers]
                    self.telemetry_data["laps"].extend(laps_to_add)
                    # Ordena as voltas pelo número
                    self.telemetry_data["laps"].sort(key=lambda x: x.get("lap_number", 0))
                    logger.info(f"{len(laps_to_add)} novas voltas adicionadas do arquivo {file_path}")
            else:
                 logger.warning(f"Nenhuma volta processada do arquivo LD: {file_path}")

        except FileNotFoundError:
             logger.error(f"Arquivo LD não encontrado durante processamento: {file_path}")
        except ValueError as ve:
             logger.error(f"Erro de valor ao processar LD {file_path}: {ve}")
        except Exception as e:
            logger.error(f"Erro inesperado ao processar arquivo LD {file_path}: {e}")

    def _update_session_info(self):
        """Tenta atualizar info da sessão a partir do LDX mais recente."""
        ldx_files = sorted(glob.glob(os.path.join(self.motec_folder, "*.ldx")), key=os.path.getmtime, reverse=True)
        if ldx_files:
            self._process_ldx_file(ldx_files[0])
        else:
             logger.info("Nenhum arquivo LDX encontrado para atualizar informações da sessão.")

    def _save_telemetry_data(self, telemetry_data_to_save: Dict):
        """Salva os dados de telemetria acumulados."""
        if not telemetry_data_to_save or not telemetry_data_to_save.get("laps"):
            # logger.warning("Nenhum dado de telemetria LMU para salvar")
            return None
        
        try:
            user_data_dir = os.path.join(os.path.expanduser("~"), "RaceTelemetryAnalyzer")
            telemetry_dir = os.path.join(user_data_dir, "telemetry")
            os.makedirs(telemetry_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session = telemetry_data_to_save.get("session", {})
            track = session.get("track", "unknown").replace(" ", "_").lower()
            car = session.get("car", "unknown").replace(" ", "_").lower()
            file_name = f"lmu_{track}_{car}_{timestamp}.json"
            file_path = os.path.join(telemetry_dir, file_name)
            
            with open(file_path, "w") as f:
                json.dump(telemetry_data_to_save, f, indent=2)
            
            logger.info(f"Dados de telemetria LMU salvos em: {file_path}")
            return file_path
        
        except Exception as e:
            logger.error(f"Erro ao salvar dados de telemetria LMU: {str(e)}")
            return None

# --- Função de teste --- 
def test_lmu_capture():
    capture = LMUTelemetryCapture()
    
    print("Tentando conectar ao LMU (via pasta MoTeC)...")
    if capture.connect():
        print(f"Conectado! Pasta MoTeC: {capture.motec_folder}")
        print(f"Sessão inicial: {capture.telemetry_data['session']}")
        
        print("Iniciando captura (monitoramento da pasta)...")
        if capture.start_capture():
            print("Captura iniciada. Gere novos arquivos LD/LDX no jogo. Pressione Ctrl+C para parar.")
            
            try:
                last_lap_count = 0
                while True:
                    # Obtém cópia segura dos dados
                    data = capture.get_telemetry_data()
                    current_lap_count = len(data.get("laps", []))
                    if current_lap_count > last_lap_count:
                         print(f"\nNovas voltas detectadas! Total: {current_lap_count}")
                         last_lap_count = current_lap_count
                    
                    print(f"\rMonitorando... Voltas processadas: {current_lap_count}   ", end="")
                    time.sleep(1)
            
            except KeyboardInterrupt:
                print("\nParando captura...")
                capture.stop_capture()
                print("Captura finalizada.")
        
        print("Desconectando...")
        capture.disconnect()
        print("Desconectado.")
    else:
        print("Falha ao conectar. Verifique a pasta MoTeC.")

if __name__ == "__main__":
    # Para testar o parser diretamente:
    # test_ld_file = "caminho/para/seu/arquivo.ld" 
    # if os.path.exists(test_ld_file):
    #     parser = LDParser(test_ld_file)
    #     parsed = parser.parse()
    #     print(json.dumps(parsed, indent=2))
    # else:
    #     print(f"Arquivo de teste LD não encontrado: {test_ld_file}")
    
    # Para testar a captura:
    test_lmu_capture()

