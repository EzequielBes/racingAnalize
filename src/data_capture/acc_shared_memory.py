"""
Implementação real da captura de telemetria para Assetto Corsa Competizione.
Utiliza a memória compartilhada oficial do ACC para obter dados em tempo real.
"""

import os
import sys
import time
import logging
import ctypes
from ctypes import Structure, c_float, c_int, c_wchar, c_double, c_char, sizeof, byref
import mmap
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import json
import threading # Adicionado para locking
import copy      # Adicionado para deepcopy

# Configuração de logging
logger = logging.getLogger("race_telemetry_api.acc")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
# Evita adicionar handlers duplicados se o módulo for recarregado
if not logger.hasHandlers():
    logger.addHandler(handler)


# --- Estruturas de Dados ACC (sem alterações) ---
class SPageFilePhysics(Structure):
    _fields_ = [
        ("packetId", c_int), ("gas", c_float), ("brake", c_float), ("fuel", c_float),
        ("gear", c_int), ("rpms", c_int), ("steerAngle", c_float), ("speedKmh", c_float),
        ("velocity", c_float * 3), ("accG", c_float * 3), ("wheelSlip", c_float * 4),
        ("wheelLoad", c_float * 4), ("wheelsPressure", c_float * 4), ("wheelAngularSpeed", c_float * 4),
        ("tyreWear", c_float * 4), ("tyreDirtyLevel", c_float * 4), ("tyreCoreTemperature", c_float * 4),
        ("camberRAD", c_float * 4), ("suspensionTravel", c_float * 4), ("drs", c_float),
        ("tc", c_float), ("heading", c_float), ("pitch", c_float), ("roll", c_float),
        ("cgHeight", c_float), ("carDamage", c_float * 5), ("numberOfTyresOut", c_int),
        ("pitLimiterOn", c_int), ("abs", c_float), ("kersCharge", c_float), ("kersInput", c_float),
        ("autoShifterOn", c_int), ("rideHeight", c_float * 2), ("turboBoost", c_float),
        ("ballast", c_float), ("airDensity", c_float), ("airTemp", c_float), ("roadTemp", c_float),
        ("localAngularVel", c_float * 3), ("finalFF", c_float), ("performanceMeter", c_float),
        ("engineBrake", c_int), ("ersRecoveryLevel", c_int), ("ersPowerLevel", c_int),
        ("ersHeatCharging", c_int), ("ersIsCharging", c_int), ("kersCurrentKJ", c_float),
        ("drsAvailable", c_int), ("drsEnabled", c_int), ("brakeTemp", c_float * 4),
        ("clutch", c_float), ("tyreTempI", c_float * 4), ("tyreTempM", c_float * 4),
        ("tyreTempO", c_float * 4), ("isAIControlled", c_int), ("tyreContactPoint", c_float * 4 * 3),
        ("tyreContactNormal", c_float * 4 * 3), ("tyreContactHeading", c_float * 4 * 3),
        ("brakeBias", c_float), ("localVelocity", c_float * 3), ("P2PActivations", c_int),
        ("P2PStatus", c_int), ("currentMaxRpm", c_int), ("mz", c_float * 4), ("fx", c_float * 4),
        ("fy", c_float * 4), ("slipRatio", c_float * 4), ("slipAngle", c_float * 4),
        ("tcinAction", c_int), ("absInAction", c_int), ("suspensionDamage", c_float * 4),
        ("tyreTemp", c_float * 4), ("waterTemp", c_float), ("brakePressure", c_float * 4),
        ("frontBrakeCompound", c_int), ("rearBrakeCompound", c_int), ("padLife", c_float * 4),
        ("discLife", c_float * 4), ("ignitionOn", c_int), ("starterEngineOn", c_int),
        ("isEngineRunning", c_int), ("kerbVibration", c_float), ("slipVibrations", c_float),
        ("gVibrations", c_float), ("absVibrations", c_float)
    ]

class SPageFileGraphic(Structure):
    _fields_ = [
        ("packetId", c_int), ("status", c_int), ("session", c_int), ("currentTime", c_wchar * 15),
        ("lastTime", c_wchar * 15), ("bestTime", c_wchar * 15), ("split", c_wchar * 15),
        ("completedLaps", c_int), ("position", c_int), ("iCurrentTime", c_int), ("iLastTime", c_int),
        ("iBestTime", c_int), ("sessionTimeLeft", c_float), ("distanceTraveled", c_float),
        ("isInPit", c_int), ("currentSectorIndex", c_int), ("lastSectorTime", c_int),
        ("numberOfLaps", c_int), ("tyreCompound", c_wchar * 33), ("replayTimeMultiplier", c_float),
        ("normalizedCarPosition", c_float), ("activeCars", c_int), ("carCoordinates", c_float * 60 * 3),
        ("carID", c_int * 60), ("playerCarID", c_int), ("penaltyTime", c_float), ("flag", c_int),
        ("penalty", c_int), ("idealLineOn", c_int), ("isInPitLane", c_int), ("surfaceGrip", c_float),
        ("mandatoryPitDone", c_int), ("windSpeed", c_float), ("windDirection", c_float),
        ("isSetupMenuVisible", c_int), ("mainDisplayIndex", c_int), ("secondaryDisplayIndex", c_int),
        ("TC", c_int), ("TCCut", c_int), ("EngineMap", c_int), ("ABS", c_int), ("fuelXLap", c_float),
        ("rainLights", c_int), ("flashingLights", c_int), ("lightsStage", c_int),
        ("exhaustTemperature", c_float), ("wiperLV", c_int), ("DriverStintTotalTimeLeft", c_int),
        ("DriverStintTimeLeft", c_int), ("rainTyres", c_int), ("sessionIndex", c_int),
        ("usedFuel", c_float), ("deltaLapTime", c_wchar * 15), ("iDeltaLapTime", c_int),
        ("estimatedLapTime", c_wchar * 15), ("iEstimatedLapTime", c_int), ("isDeltaPositive", c_int),
        ("iSplit", c_int), ("isValidLap", c_int), ("fuelEstimatedLaps", c_float),
        ("trackStatus", c_wchar * 33), ("missingMandatoryPits", c_int), ("clock", c_float),
        ("directionLightsLeft", c_int), ("directionLightsRight", c_int), ("globalYellow", c_int),
        ("globalYellow1", c_int), ("globalYellow2", c_int), ("globalYellow3", c_int),
        ("globalWhite", c_int), ("globalGreen", c_int), ("globalChequered", c_int),
        ("globalRed", c_int), ("mfdTyreSet", c_int), ("mfdFuelToAdd", c_float),
        ("mfdTyrePressureLF", c_float), ("mfdTyrePressureRF", c_float), ("mfdTyrePressureLR", c_float),
        ("mfdTyrePressureRR", c_float), ("trackGripStatus", c_int), ("rainIntensity", c_int),
        ("rainIntensityIn10min", c_int), ("rainIntensityIn30min", c_int), ("currentTyreSet", c_int),
        ("strategyTyreSet", c_int), ("gapAhead", c_int), ("gapBehind", c_int)
    ]

class SPageFileStatic(Structure):
    _fields_ = [
        ("smVersion", c_wchar * 15), ("acVersion", c_wchar * 15), ("numberOfSessions", c_int),
        ("numCars", c_int), ("carModel", c_wchar * 33), ("track", c_wchar * 33),
        ("playerName", c_wchar * 33), ("playerSurname", c_wchar * 33), ("playerNick", c_wchar * 33),
        ("sectorCount", c_int), ("maxTorque", c_float), ("maxPower", c_float), ("maxRpm", c_int),
        ("maxFuel", c_float), ("suspensionMaxTravel", c_float * 4), ("tyreRadius", c_float * 4),
        ("maxTurboBoost", c_float), ("deprecated_1", c_float), ("deprecated_2", c_float),
        ("penaltiesEnabled", c_int), ("aidFuelRate", c_float), ("aidTireRate", c_float),
        ("aidMechanicalDamage", c_float), ("aidAllowTyreBlankets", c_int), ("aidStability", c_float),
        ("aidAutoClutch", c_int), ("aidAutoBlip", c_int), ("hasDRS", c_int), ("hasERS", c_int),
        ("hasKERS", c_int), ("kersMaxJ", c_float), ("engineBrakeSettingsCount", c_int),
        ("ersPowerControllerCount", c_int), ("trackSplineLength", c_float),
        ("trackConfiguration", c_wchar * 33), ("ersMaxJ", c_float), ("isTimedRace", c_int),
        ("hasExtraLap", c_int), ("carSkin", c_wchar * 33), ("reversedGridPositions", c_int),
        ("PitWindowStart", c_int), ("PitWindowEnd", c_int), ("isOnline", c_int),
        ("dryTyresName", c_wchar * 33), ("wetTyresName", c_wchar * 33)
    ]

# --- Helper para conversão de ctypes para JSON (sem alterações) ---
def convert_ctypes_to_native(data):
    if isinstance(data, (int, float, str, bool)) or data is None:
        return data
    elif isinstance(data, bytes):
        try:
            return data.decode("utf-8").strip("\x00")
        except UnicodeDecodeError:
            return repr(data)
    elif isinstance(data, ctypes.Array):
        return [convert_ctypes_to_native(item) for item in data]
    elif isinstance(data, Structure):
        result = {}
        for field_name, field_type in data._fields_:
            result[field_name] = convert_ctypes_to_native(getattr(data, field_name))
        return result
    elif isinstance(data, dict):
        return {k: convert_ctypes_to_native(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_ctypes_to_native(item) for item in data]
    elif hasattr(data, "value"):
         return data.value
    else:
        return repr(data)

class ACCTelemetryCapture:
    """Classe para captura de telemetria do Assetto Corsa Competizione."""
    
    def __init__(self):
        """Inicializa o capturador de telemetria do ACC."""
        self.physics_mmap = None
        self.graphics_mmap = None
        self.static_mmap = None
        
        self.physics_data = None
        self.graphics_data = None
        self.static_data = None
        
        self.is_connected = False
        self.is_capturing = False
        self.last_lap_number = -1
        self.capture_start_time = None
        
        # Dados compartilhados entre threads (protegidos por lock)
        self.data_lock = threading.Lock()
        self.data_points_buffer = []
        self.current_lap_data = None
        self.telemetry_data = {
            "session": {},
            "laps": []
        }
        
        logger.info("Inicializando capturador de telemetria do ACC")
    
    def connect(self) -> bool:
        logger.info("Tentando conectar à memória compartilhada do ACC")
        try:
            self.physics_mmap = mmap.mmap(-1, sizeof(SPageFilePhysics), "Local\\acpmf_physics")
            self.graphics_mmap = mmap.mmap(-1, sizeof(SPageFileGraphic), "Local\\acpmf_graphics")
            self.static_mmap = mmap.mmap(-1, sizeof(SPageFileStatic), "Local\\acpmf_static")
            
            self.physics_data = SPageFilePhysics()
            self.graphics_data = SPageFileGraphic()
            self.static_data = SPageFileStatic()
            
            self._read_shared_memory() # Lê dados iniciais
            
            if self.static_data and self.static_data.track and self.static_data.carModel:
                self.is_connected = True
                logger.info(f"Conectado à memória compartilhada do ACC")
                self._update_session_info() # Atualiza info da sessão com lock
                return True
            else:
                logger.error("Dados de memória compartilhada inválidos ou ACC não está em execução")
                self._cleanup_memory()
                return False
        except Exception as e:
            logger.error(f"Erro ao conectar à memória compartilhada do ACC: {str(e)}")
            self._cleanup_memory()
            return False
    
    def disconnect(self) -> bool:
        logger.info("Tentando desconectar da memória compartilhada do ACC")
        try:
            if self.is_capturing:
                self.stop_capture()
            self._cleanup_memory()
            self.is_connected = False
            logger.info("Desconectado da memória compartilhada do ACC")
            return True
        except Exception as e:
            logger.error(f"Erro ao desconectar da memória compartilhada do ACC: {str(e)}")
            return False
    
    def start_capture(self) -> bool:
        logger.info("Tentando iniciar captura de telemetria do ACC")
        if not self.is_connected:
            logger.error("Não está conectado à memória compartilhada do ACC")
            return False
        if self.is_capturing:
            logger.warning("Já está capturando telemetria do ACC")
            return False
        
        with self.data_lock:
            self.is_capturing = True
            self.capture_start_time = time.time()
            # Lê a última volta ANTES de limpar para evitar condição de corrida
            if self.graphics_data:
                 self.last_lap_number = self.graphics_data.completedLaps
            else:
                 self.last_lap_number = -1 # Garante que a primeira volta seja detectada
            self.data_points_buffer = []
            self.current_lap_data = None
            # Limpa apenas as voltas, mantém a info da sessão
            self.telemetry_data["laps"] = [] 
            
        logger.info("Captura de telemetria do ACC iniciada com sucesso")
        return True
    
    def stop_capture(self) -> bool:
        logger.info("Tentando parar captura de telemetria do ACC")
        if not self.is_capturing:
            logger.warning("Não está capturando telemetria do ACC")
            return False
        
        file_path = None
        with self.data_lock:
            self.is_capturing = False # Sinaliza para parar a coleta
            # Finaliza a volta atual se houver dados (dentro do lock)
            if self.current_lap_data and self.data_points_buffer:
                self._finalize_current_lap_nolock()
            self.capture_start_time = None
            # Faz cópia para salvar fora do lock
            telemetry_to_save = copy.deepcopy(self.telemetry_data)
            
        logger.info("Captura de telemetria do ACC parada com sucesso")
        
        # Salva os dados fora do lock principal
        file_path = self._save_telemetry_data(telemetry_to_save)
        
        return True
    
    def get_telemetry_data(self) -> Dict[str, Any]:
        """Retorna uma cópia segura dos dados de telemetria atuais."""
        with self.data_lock:
            # Retorna uma cópia profunda para segurança da thread da UI
            return copy.deepcopy(self.telemetry_data)
    
    def run_capture_loop(self): 
        """Método principal do loop de captura (executado em uma thread separada)."""
        while self.is_capturing: # Verifica a flag dentro do loop
            start_time = time.perf_counter()
            
            # Lê os dados mais recentes da memória compartilhada
            self._read_shared_memory()
            
            # Processa os dados (detecta voltas, coleta pontos)
            # A modificação dos dados compartilhados acontece dentro de _process_telemetry_data com lock
            if self.physics_data and self.graphics_data:
                 self._process_telemetry_data()
            
            # Controla a taxa de atualização (ex: 60Hz)
            elapsed = time.perf_counter() - start_time
            sleep_time = (1/60) - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            # Verifica novamente se a captura deve continuar
            with self.data_lock:
                 if not self.is_capturing:
                      break # Sai do loop se stop_capture foi chamado

    def _read_shared_memory(self):
        if not self.physics_mmap or not self.graphics_mmap or not self.static_mmap:
            return
        try:
            self.physics_mmap.seek(0)
            self.graphics_mmap.seek(0)
            self.static_mmap.seek(0)
            physics_buffer = self.physics_mmap.read(sizeof(SPageFilePhysics))
            graphics_buffer = self.graphics_mmap.read(sizeof(SPageFileGraphic))
            static_buffer = self.static_mmap.read(sizeof(SPageFileStatic))
            self.physics_data = SPageFilePhysics.from_buffer_copy(physics_buffer)
            self.graphics_data = SPageFileGraphic.from_buffer_copy(graphics_buffer)
            # Static data muda raramente, poderia otimizar leitura
            self.static_data = SPageFileStatic.from_buffer_copy(static_buffer)
        except Exception as e:
            # logger.error(f"Erro ao ler memória compartilhada: {str(e)}") # Pode poluir logs
            self.physics_data = None
            self.graphics_data = None
            self.static_data = None
    
    def _cleanup_memory(self):
        try:
            if self.physics_mmap: self.physics_mmap.close()
            if self.graphics_mmap: self.graphics_mmap.close()
            if self.static_mmap: self.static_mmap.close()
        except Exception as e:
            logger.error(f"Erro ao limpar recursos de memória: {str(e)}")
        finally:
             self.physics_mmap = self.graphics_mmap = self.static_mmap = None
             self.physics_data = self.graphics_data = self.static_data = None
    
    def _update_session_info(self):
        """Atualiza as informações da sessão com tipos nativos (com lock)."""
        if not self.static_data or not self.physics_data or not self.graphics_data:
            return
        
        # Converte estruturas ctypes para dicionários nativos
        # Faz a conversão fora do lock para minimizar tempo bloqueado
        try:
            static_native = convert_ctypes_to_native(self.static_data)
            physics_native = convert_ctypes_to_native(self.physics_data)
            graphics_native = convert_ctypes_to_native(self.graphics_data)
        except Exception as e:
            logger.error(f"Erro ao converter dados ctypes para nativos: {e}")
            return

        with self.data_lock: # Bloqueia apenas para atualizar o dict compartilhado
            track_name = static_native.get("track", "Desconhecido").strip()
            car_model = static_native.get("carModel", "Desconhecido").strip()
            track_temp = physics_native.get("roadTemp", 25)
            air_temp = physics_native.get("airTemp", 20)
            conditions = "Desconhecido"
            rain_intensity = graphics_native.get("rainIntensity", 0)
            if rain_intensity == 0: conditions = "Ensolarado"
            elif rain_intensity == 1: conditions = "Nublado"
            elif rain_intensity >= 2: conditions = "Chuvoso"
            
            self.telemetry_data["session"] = {
                "track": track_name,
                "car": car_model,
                "conditions": conditions,
                "temperature": {"air": air_temp, "track": track_temp},
                "player": static_native.get("playerName", "Piloto").strip()
            }
    
    def _process_telemetry_data(self):
        """Processa os dados de telemetria (chamado pelo loop de captura)."""
        # Lê dados necessários fora do lock
        current_lap = self.graphics_data.completedLaps
        last_lap_read = self.last_lap_number # Lê o valor atual antes do lock
        
        # Bloqueia para modificar dados compartilhados
        with self.data_lock:
            # Verifica se a captura ainda está ativa
            if not self.is_capturing:
                 return
                 
            # Verifica nova volta
            if current_lap > last_lap_read and last_lap_read >= 0:
                if self.current_lap_data and self.data_points_buffer:
                    self._finalize_current_lap_nolock()
                self._start_new_lap_nolock(current_lap)
            
            # Atualiza o número da última volta *dentro* do lock
            self.last_lap_number = current_lap
            
            # Coleta ponto de dados (modifica buffer e current_lap_data)
            self._collect_data_point_nolock()

    # --- Métodos _nolock para modificar estado compartilhado --- 
    
    def _start_new_lap_nolock(self, lap_number: int):
        """Inicia nova volta (assume lock externo)."""
        self.current_lap_data = {
            "lap_number": lap_number,
            "lap_time": 0,
            "sectors": [],
            "data_points": []
        }
        self.data_points_buffer = []
        # logger.info(f"Iniciando volta {lap_number}") # Log pode ser movido para fora se necessário
    
    def _collect_data_point_nolock(self):
        """Coleta ponto de dados (assume lock externo)."""
        if not self.current_lap_data:
            # logger.warning("Tentando coletar ponto sem volta atual iniciada.")
            # Tenta iniciar a volta 0 se for o caso inicial
            if self.last_lap_number <= 0:
                 self._start_new_lap_nolock(0)
            else: # Evita coletar se a volta não foi devidamente iniciada
                 return

        # Usa os dados ctypes lidos fora do lock
        if not self.physics_data or not self.graphics_data:
            # logger.warning("Dados de física ou gráficos ausentes ao coletar ponto.")
            return

        position = [0.0, 0.0, 0.0]
        try:
            player_id = self.graphics_data.playerCarID
            if player_id >= 0 and player_id < 60:
                coords = self.graphics_data.carCoordinates[player_id * 3 : player_id * 3 + 3]
                position = [float(c) for c in coords]
        except Exception as e:
             logger.error(f"Erro ao extrair coordenadas do carro: {e}")

        capture_time = self.capture_start_time if self.capture_start_time else time.time()
        data_point = {
            "time": time.time() - capture_time,
            "distance": float(self.graphics_data.distanceTraveled),
            "position": position,
            "speed": float(self.physics_data.speedKmh),
            "rpm": int(self.physics_data.rpms),
            "gear": int(self.physics_data.gear),
            "throttle": float(self.physics_data.gas),
            "brake": float(self.physics_data.brake),
            "clutch": float(self.physics_data.clutch),
            "steer": float(self.physics_data.steerAngle),
            "sector": int(self.graphics_data.currentSectorIndex)
        }
        self.data_points_buffer.append(data_point)
    
    def _finalize_current_lap_nolock(self):
        """Finaliza volta atual (assume lock externo)."""
        if not self.current_lap_data or not self.data_points_buffer:
            return
        
        lap_time = float(self.graphics_data.iLastTime) / 1000.0
        self.current_lap_data["lap_time"] = lap_time
        self.current_lap_data["data_points"] = self.data_points_buffer
        
        sectors = []
        sector_count = int(self.static_data.sectorCount)
        if sector_count > 0 and lap_time > 0:
            # Simplificado
            for i in range(sector_count):
                sectors.append({"sector": i + 1, "time": lap_time / sector_count})
        self.current_lap_data["sectors"] = sectors
        
        # Adiciona a volta finalizada à lista principal
        self.telemetry_data["laps"].append(self.current_lap_data)
        
        logger.info(f"Volta {self.current_lap_data["lap_number"]} finalizada: {lap_time:.3f}s")
        
        # Limpa para a próxima volta
        self.current_lap_data = None
        self.data_points_buffer = []
    
    def _save_telemetry_data(self, telemetry_data_to_save: Dict):
        """Salva os dados de telemetria fornecidos."""
        if not telemetry_data_to_save or not telemetry_data_to_save.get("laps"):
            logger.warning("Nenhum dado de telemetria para salvar")
            return None
        
        try:
            user_data_dir = os.path.join(os.path.expanduser("~"), "RaceTelemetryAnalyzer")
            telemetry_dir = os.path.join(user_data_dir, "telemetry")
            os.makedirs(telemetry_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session = telemetry_data_to_save.get("session", {})
            track = session.get("track", "unknown").replace(" ", "_").lower()
            car = session.get("car", "unknown").replace(" ", "_").lower()
            file_name = f"acc_{track}_{car}_{timestamp}.json"
            file_path = os.path.join(telemetry_dir, file_name)
            
            with open(file_path, "w") as f:
                json.dump(telemetry_data_to_save, f, indent=2)
            
            logger.info(f"Dados de telemetria salvos em: {file_path}")
            return file_path
        
        except TypeError as e:
             logger.error(f"Erro de tipo ao salvar JSON: {e}. Verifique a conversão de dados.")
             return None
        except Exception as e:
            logger.error(f"Erro inesperado ao salvar dados de telemetria: {str(e)}")
            return None

# --- Função de teste (sem alterações significativas) ---
def test_acc_capture():
    capture = ACCTelemetryCapture()
    capture_thread = None
    
    print("Tentando conectar ao ACC...")
    if capture.connect():
        print("Conectado com sucesso!")
        print("Iniciando captura...")
        if capture.start_capture():
            # Inicia o loop de captura em uma thread separada
            capture_thread = threading.Thread(target=capture.run_capture_loop, daemon=True)
            capture_thread.start()
            print("Captura iniciada em background. Pressione Ctrl+C para parar.")
            
            try:
                while True:
                    # Obtém cópia segura dos dados
                    data = capture.get_telemetry_data()
                    laps = len(data.get("laps", []))
                    
                    # Acessa dados ctypes lidos pela thread de captura (pode ser None)
                    physics = capture.physics_data
                    speed = physics.speedKmh if physics else 0
                    rpms = physics.rpms if physics else 0
                    print(f"\rVoltas: {laps} | Velocidade: {speed:.1f} km/h | RPM: {rpms}   ", end="")
                    
                    time.sleep(0.5) # Atualiza a UI mais devagar
            
            except KeyboardInterrupt:
                print("\nParando captura...")
                capture.stop_capture() # Sinaliza para a thread parar
                if capture_thread:
                     capture_thread.join(timeout=2) # Espera a thread terminar
                print("Captura finalizada.")
        
        print("Desconectando...")
        capture.disconnect()
        print("Desconectado.")
    else:
        print("Falha ao conectar. Verifique se o ACC está em execução.")

if __name__ == "__main__":
    test_acc_capture()

