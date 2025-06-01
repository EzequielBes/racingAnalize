# -*- coding: utf-8 -*-
"""
Implementação real da captura de telemetria para Assetto Corsa.
Utiliza a memória compartilhada oficial do Assetto Corsa para obter dados em tempo real.
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

# Adiciona o diretório pai ao path para permitir imports absolutos
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

# Importa a estrutura de dados padronizada
from src.core.standard_data import TelemetrySession, SessionInfo, TrackData, LapData, DataPoint

# Configuração de logging
logger = logging.getLogger(__name__) # Usa o nome do módulo
# Configuração básica se não houver handlers (evita duplicação)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

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

class ACCSharedMemoryReader:
    """Classe para ler dados da memória compartilhada do Assetto Corsa."""

    def __init__(self):
        """Inicializa o leitor de memória compartilhada do ACC."""
        self.physics_mmap = None
        self.graphics_mmap = None
        self.static_mmap = None

        self.physics_data = SPageFilePhysics()
        self.graphics_data = SPageFileGraphic()
        self.static_data = SPageFileStatic()

        self.is_connected = False
        self.last_physics_packet_id = -1
        self.last_graphics_packet_id = -1

        logger.info("Inicializando leitor de memória compartilhada do ACC")

    def connect(self) -> bool:
        logger.info("Tentando conectar à memória compartilhada do ACC")
        if self.is_connected:
            logger.warning("Já está conectado.")
            return True
        try:
            self.physics_mmap = mmap.mmap(-1, sizeof(SPageFilePhysics), "Local\\acpmf_physics")
            self.graphics_mmap = mmap.mmap(-1, sizeof(SPageFileGraphic), "Local\\acpmf_graphics")
            self.static_mmap = mmap.mmap(-1, sizeof(SPageFileStatic), "Local\\acpmf_static")

            # Lê dados estáticos para confirmar conexão
            self._read_static_data()
            if not self.static_data or not self.static_data.track or not self.static_data.carModel:
                logger.error("Dados estáticos inválidos ou ACC não está em uma sessão ativa.")
                self._cleanup_memory()
                return False

            self.is_connected = True
            logger.info(f"Conectado à memória compartilhada do ACC (Track: {self.static_data.track}, Car: {self.static_data.carModel})")
            return True

        except FileNotFoundError:
            logger.error("Memória compartilhada do ACC não encontrada. O jogo está em execução?")
            self._cleanup_memory()
            return False
        except Exception as e:
            logger.exception(f"Erro ao conectar à memória compartilhada do ACC: {e}")
            self._cleanup_memory()
            return False

    def disconnect(self) -> bool:
        logger.info("Tentando desconectar da memória compartilhada do ACC")
        self._cleanup_memory()
        self.is_connected = False
        logger.info("Desconectado da memória compartilhada do ACC")
        return True

    def _cleanup_memory(self):
        """Fecha os mapeamentos de memória."""
        if self.physics_mmap:
            self.physics_mmap.close()
            self.physics_mmap = None
        if self.graphics_mmap:
            self.graphics_mmap.close()
            self.graphics_mmap = None
        if self.static_mmap:
            self.static_mmap.close()
            self.static_mmap = None

    def _read_physics_data(self):
        """Lê os dados de física da memória compartilhada."""
        if not self.physics_mmap:
            return
        try:
            self.physics_mmap.seek(0)
            ctypes.memmove(byref(self.physics_data), self.physics_mmap.read(sizeof(SPageFilePhysics)), sizeof(SPageFilePhysics))
        except Exception as e:
            logger.error(f"Erro ao ler dados de física: {e}")
            # Considerar desconectar ou tentar reconectar se erros persistirem

    def _read_graphics_data(self):
        """Lê os dados gráficos da memória compartilhada."""
        if not self.graphics_mmap:
            return
        try:
            self.graphics_mmap.seek(0)
            ctypes.memmove(byref(self.graphics_data), self.graphics_mmap.read(sizeof(SPageFileGraphic)), sizeof(SPageFileGraphic))
        except Exception as e:
            logger.error(f"Erro ao ler dados gráficos: {e}")

    def _read_static_data(self):
        """Lê os dados estáticos da memória compartilhada."""
        if not self.static_mmap:
            return
        try:
            self.static_mmap.seek(0)
            ctypes.memmove(byref(self.static_data), self.static_mmap.read(sizeof(SPageFileStatic)), sizeof(SPageFileStatic))
        except Exception as e:
            logger.error(f"Erro ao ler dados estáticos: {e}")

    def read_data(self) -> Optional[Dict[str, Any]]:
        """Lê os dados mais recentes e retorna um dicionário se houver dados novos."""
        if not self.is_connected:
            logger.warning("Tentativa de ler dados sem estar conectado.")
            return None

        self._read_physics_data()
        self._read_graphics_data()

        # Verifica se há dados novos (baseado no packetId da física, que atualiza mais rápido)
        current_physics_id = self.physics_data.packetId
        current_graphics_id = self.graphics_data.packetId

        if current_physics_id != self.last_physics_packet_id or current_graphics_id != self.last_graphics_packet_id:
            self.last_physics_packet_id = current_physics_id
            self.last_graphics_packet_id = current_graphics_id

            # Retorna uma cópia dos dados lidos em formato nativo Python
            return {
                "physics": convert_ctypes_to_native(self.physics_data),
                "graphics": convert_ctypes_to_native(self.graphics_data),
                "static": convert_ctypes_to_native(self.static_data) # Dados estáticos não mudam, mas incluímos por consistência
            }
        else:
            # logger.debug("Nenhum pacote novo de física ou gráficos.")
            return None # Nenhum dado novo

    def normalize_to_datapoint(self, raw_data: Dict[str, Any]) -> Optional[DataPoint]:
        """Converte os dados brutos lidos em um objeto DataPoint padronizado."""
        if not raw_data or "physics" not in raw_data or "graphics" not in raw_data:
            return None

        physics = raw_data["physics"]
        graphics = raw_data["graphics"]

        if not physics or not graphics:
             return None

        try:
            # Mapeamento dos campos ACC para DataPoint
            # Atenção: Alguns campos podem precisar de conversão ou cálculo
            datapoint = DataPoint(
                timestamp_ms=int(time.time() * 1000), # Usa timestamp do sistema
                distance_m=graphics.get("distanceTraveled", 0.0),
                lap_time_ms=graphics.get("iCurrentTime", 0),
                sector=graphics.get("currentSectorIndex", 0),
                # Posição: ACC fornece coordenadas normalizadas e globais. Usar globais?
                # Precisa verificar se carCoordinates[playerCarID] está correto
                # pos_x=graphics["carCoordinates"][graphics["playerCarID"]][0] if graphics["playerCarID"] < len(graphics["carCoordinates"]) else 0.0,
                # pos_y=graphics["carCoordinates"][graphics["playerCarID"]][1] if graphics["playerCarID"] < len(graphics["carCoordinates"]) else 0.0,
                # pos_z=graphics["carCoordinates"][graphics["playerCarID"]][2] if graphics["playerCarID"] < len(graphics["carCoordinates"]) else 0.0,
                pos_x=0.0, # Placeholder - Coordenadas precisam de tratamento cuidadoso
                pos_y=0.0, # Placeholder
                pos_z=0.0, # Placeholder
                speed_kmh=physics.get("speedKmh", 0.0),
                rpm=physics.get("rpms", 0),
                gear=physics.get("gear", 0),
                steer_angle=physics.get("steerAngle", 0.0),
                throttle=physics.get("gas", 0.0),
                brake=physics.get("brake", 0.0),
                clutch=physics.get("clutch", 0.0),
                # Dados de pneus (exemplo - pegar FL)
                tyre_temp_fl=physics["tyreCoreTemperature"][0] if len(physics.get("tyreCoreTemperature", [])) > 0 else None,
                tyre_press_fl=physics["wheelsPressure"][0] if len(physics.get("wheelsPressure", [])) > 0 else None,
                # ... adicionar outros pneus e canais conforme necessário
            )
            return datapoint
        except KeyError as e:
            logger.warning(f"Chave ausente ao normalizar dados ACC: {e}")
            return None
        except Exception as e:
            logger.exception(f"Erro ao normalizar dados ACC para DataPoint: {e}")
            return None

class ACCTelemetryCapture:
    """Captura de telemetria em tempo real do Assetto Corsa via memória compartilhada."""

    def __init__(self):
        self.reader = ACCSharedMemoryReader()
        self.is_connected = False
        self.is_capturing = False
        self.capture_thread = None
        self.stop_event = threading.Event()
        self.data_lock = threading.Lock()
        self.telemetry_data = {"session": {}, "laps": []}
        self.current_lap_points = []
        self.last_lap = 0

    def connect(self) -> bool:
        self.is_connected = self.reader.connect()
        if self.is_connected:
            static = self.reader.static_data
            self.telemetry_data["session"] = {
                "track": getattr(static, "track", ""),
                "car": getattr(static, "carModel", ""),
                "player": getattr(static, "playerName", ""),
            }
        return self.is_connected

    def disconnect(self) -> bool:
        self.stop_capture()
        self.reader.disconnect()
        self.is_connected = False
        return True

    def start_capture(self) -> bool:
        if not self.is_connected or self.is_capturing:
            return False
        self.stop_event.clear()
        self.is_capturing = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        return True

    def stop_capture(self) -> bool:
        if not self.is_capturing:
            return False
        self.stop_event.set()
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
        self.is_capturing = False
        return True

    def get_telemetry_data(self):
        with self.data_lock:
            return copy.deepcopy(self.telemetry_data)

    def _capture_loop(self):
        while not self.stop_event.is_set():
            raw = self.reader.read_data()
            if raw:
                dp = self.reader.normalize_to_datapoint(raw)
                if dp:
                    with self.data_lock:
                        lap = raw["graphics"].get("completedLaps", 0)
                        if lap != self.last_lap and self.current_lap_points:
                            self.telemetry_data["laps"].append({
                                "lap_number": self.last_lap,
                                "lap_time": raw["graphics"].get("iLastTime", 0) / 1000.0,
                                "sectors": [],
                                "data_points": [p.__dict__ for p in self.current_lap_points]
                            })
                            self.current_lap_points = []
                        self.current_lap_points.append(dp)
                        self.last_lap = lap
            time.sleep(0.05)

# --- Exemplo de Uso (para teste direto do módulo) ---
if __name__ == "__main__":
    print("Testando ACCSharedMemoryReader...")
    reader = ACCSharedMemoryReader()

    if reader.connect():
        print("Conectado com sucesso!")
        print(f"Track: {reader.static_data.track}")
        print(f"Car: {reader.static_data.carModel}")
        print("Lendo dados por 10 segundos...")

        start_time = time.time()
        last_print_time = 0
        packets_read = 0

        while time.time() - start_time < 10:
            raw_data = reader.read_data()
            if raw_data:
                packets_read += 1
                # Imprime dados a cada segundo para não poluir o console
                if time.time() - last_print_time >= 1.0:
                    print("-" * 20)
                    print(f"Timestamp: {datetime.now().isoformat()}")
                    print(f"Speed: {raw_data[	'physics	'][	'speedKmh	']:.1f} km/h")
                    print(f"RPM: {raw_data[	'physics	'][	'rpms	']}")
                    print(f"Gear: {raw_data[	'physics	'][	'gear	']}")
                    print(f"Lap: {raw_data[	'graphics	'][	'completedLaps	']}")
                    print(f"Lap Time (ms): {raw_data[	'graphics	'][	'iCurrentTime	']}")
                    # Normaliza e imprime o DataPoint
                    dp = reader.normalize_to_datapoint(raw_data)
                    if dp:
                        print(f"DataPoint: {dp}")
                    else:
                        print("Falha ao normalizar DataPoint")
                    last_print_time = time.time()
            time.sleep(0.01) # Pequena pausa para não sobrecarregar CPU

        print(f"\nLeitura concluída. {packets_read} pacotes lidos em 10 segundos.")
        reader.disconnect()
    else:
        print("Falha ao conectar. Verifique se o ACC está em execução e em uma sessão.")

