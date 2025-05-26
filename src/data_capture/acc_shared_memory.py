# -*- coding: utf-8 -*-
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

# Importa a estrutura de dados padronizada
from src.core.standard_data import TelemetrySession, SessionInfo, TrackData, LapData, DataPoint

# Configuração de logging
logger = logging.getLogger(__name__) # Usa o nome do módulo
# Configuração básica se não houver handlers (evita duplicação)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# --- Estruturas de Dados ACC (sem alterações) ---
# (Estruturas SPageFilePhysics, SPageFileGraphic, SPageFileStatic permanecem as mesmas)
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
# (Função convert_ctypes_to_native permanece a mesma)
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

        self.physics_data = SPageFilePhysics()
        self.graphics_data = SPageFileGraphic()
        self.static_data = SPageFileStatic()

        self.is_connected = False
        self.is_capturing = False
        self.last_lap_number = -1
        self.capture_start_time = None
        self.last_packet_id = -1

        # Dados compartilhados entre threads (protegidos por lock)
        self.data_lock = threading.Lock()
        self.data_points_buffer: List[DataPoint] = []
        self.current_lap_data: Optional[LapData] = None
        self.telemetry_session: Optional[TelemetrySession] = None

        logger.info("Inicializando capturador de telemetria do ACC")

    def connect(self) -> bool:
        logger.info("Tentando conectar à memória compartilhada do ACC")
        if self.is_connected:
            logger.warning("Já está conectado.")
            return True
        try:
            self.physics_mmap = mmap.mmap(-1, sizeof(SPageFilePhysics), "Local\\acpmf_physics")
            self.graphics_mmap = mmap.mmap(-1, sizeof(SPageFileGraphic), "Local\\acpmf_graphics")
            self.static_mmap = mmap.mmap(-1, sizeof(SPageFileStatic), "Local\\acpmf_static")

            # Lê dados estáticos para confirmar conexão e obter info da sessão
            self._read_static_data()
            if not self.static_data or not self.static_data.track or not self.static_data.carModel:
                logger.error("Dados estáticos inválidos ou ACC não está em uma sessão ativa.")
                self._cleanup_memory()
                return False

            self.is_connected = True
            logger.info(f"Conectado à memória compartilhada do ACC (Track: {self.static_data.track}, Car: {self.static_data.carModel})")
            self._initialize_telemetry_session() # Cria a estrutura da sessão
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
        if self.is_capturing:
            self.stop_capture()
        self._cleanup_memory()
        self.is_connected = False
        self.telemetry_session = None # Limpa a sessão ao desconectar
        logger.info("Desconectado da memória compartilhada do ACC")
        return True

    def start_capture(self) -> bool:
        logger.info("Tentando iniciar captura de telemetria do ACC")
        if not self.is_connected:
            logger.error("Não está conectado à memória compartilhada do ACC.")
            return False
        if self.is_capturing:
            logger.warning("Captura já está em andamento.")
            return True

        with self.data_lock:
            self.is_capturing = True
            self.capture_start_time = time.time()
            self.last_packet_id = -1 # Reseta para garantir leitura inicial
            # Lê dados gráficos para pegar a volta atual ANTES de limpar
            self._read_graphics_data()
            self.last_lap_number = self.graphics_data.completedLaps if self.graphics_data else -1
            self.data_points_buffer = []
            self.current_lap_data = None
            # Reinicializa a sessão para limpar voltas antigas
            self._initialize_telemetry_session()

        logger.info("Captura de telemetria do ACC iniciada.")
        return True

    def stop_capture(self) -> bool:
        logger.info("Tentando parar captura de telemetria do ACC")
        if not self.is_capturing:
            logger.warning("Captura não está em andamento.")
            return True # Já está parado

        telemetry_to_save = None
        with self.data_lock:
            self.is_capturing = False # Sinaliza para parar a coleta
            # Finaliza a volta atual se houver dados (dentro do lock)
            if self.current_lap_data and self.data_points_buffer:
                self._finalize_current_lap_nolock()
            self.capture_start_time = None
            # Faz cópia para salvar fora do lock
            if self.telemetry_session:
                telemetry_to_save = copy.deepcopy(self.telemetry_session)

        logger.info("Captura de telemetria do ACC parada.")

        # Salva os dados fora do lock principal (se houver)
        # if telemetry_to_save:
        #     self._save_telemetry_data(telemetry_to_save)

        return True

    def get_current_data(self) -> Optional[Dict[str, Any]]:
        """Retorna os dados mais recentes lidos da memória compartilhada (formato nativo)."""
        if not self.is_connected:
            return None
        # Lê os dados mais recentes fora do lock principal para minimizar bloqueio
        self._read_physics_data()
        self._read_graphics_data()
        # Static data é lido na conexão

        # Retorna cópias para evitar modificação externa
        return {
            "physics": copy.deepcopy(self.physics_data) if self.physics_data else None,
            "graphics": copy.deepcopy(self.graphics_data) if self.graphics_data else None,
            "static": copy.deepcopy(self.static_data) if self.static_data else None
        }

    def get_telemetry_session(self) -> Optional[TelemetrySession]:
         """Retorna uma cópia segura da sessão de telemetria atual."""
         with self.data_lock:
             return copy.deepcopy(self.telemetry_session)

    def run_capture_loop(self):
        """Método principal do loop de captura (executado em uma thread separada)."""
        logger.info("Iniciando loop de captura ACC...")
        while True:
            with self.data_lock:
                if not self.is_capturing:
                    break # Sai do loop se stop_capture foi chamado

            start_time = time.perf_counter()

            # Lê os dados mais recentes da memória compartilhada
            self._read_physics_data()
            self._read_graphics_data()

            # Processa os dados (detecta voltas, coleta pontos)
            if self.physics_data and self.graphics_data:
                # Verifica se há um novo pacote de dados
                current_packet_id = self.physics_data.packetId
                if current_packet_id != self.last_packet_id:
                    self.last_packet_id = current_packet_id
                    # Processa apenas se houver dados novos
                    self._process_telemetry_data()
                # else: logger.debug("Nenhum pacote novo de física.")
            # else: logger.debug("Dados de física ou gráficos não disponíveis.")

            # Controla a taxa de atualização (ex: 60Hz)
            elapsed = time.perf_counter() - start_time
            sleep_time = (1/60) - elapsed # Ajuste a frequência conforme necessário
            if sleep_time > 0:
                time.sleep(sleep_time)

        logger.info("Loop de captura ACC finalizado.")

    # --- Métodos Privados ---
    def _read_static_data(self):
        if not self.static_mmap:
            return
        try:
            self.static_mmap.seek(0)
            static_buffer = self.static_mmap.read(sizeof(SPageFileStatic))
            self.static_data = SPageFileStatic.from_buffer_copy(static_buffer)
        except Exception as e:
            logger.error(f"Erro ao ler dados estáticos: {e}")
            self.static_data = None

    def _read_physics_data(self):
        if not self.physics_mmap:
            return
        try:
            self.physics_mmap.seek(0)
            physics_buffer = self.physics_mmap.read(sizeof(SPageFilePhysics))
            self.physics_data = SPageFilePhysics.from_buffer_copy(physics_buffer)
        except Exception as e:
            # logger.warning(f"Erro ao ler dados de física: {e}") # Pode ser comum se o jogo fechar
            self.physics_data = None

    def _read_graphics_data(self):
        if not self.graphics_mmap:
            return
        try:
            self.graphics_mmap.seek(0)
            graphics_buffer = self.graphics_mmap.read(sizeof(SPageFileGraphic))
            self.graphics_data = SPageFileGraphic.from_buffer_copy(graphics_buffer)
        except Exception as e:
            # logger.warning(f"Erro ao ler dados gráficos: {e}")
            self.graphics_data = None

    def _initialize_telemetry_session(self):
        """Cria ou reinicia a estrutura TelemetrySession com base nos dados estáticos."""
        if not self.static_data:
            logger.error("Não é possível inicializar a sessão sem dados estáticos.")
            return

        with self.data_lock:
            session_info = SessionInfo(
                game="Assetto Corsa Competizione",
                track=self.static_data.track,
                vehicle=self.static_data.carModel,
                driver=f"{self.static_data.playerName} {self.static_data.playerSurname}".strip(),
                session_type=self._map_session_type(self.graphics_data.session if self.graphics_data else -1),
                date=datetime.now() # Usar data/hora atual do início da captura
            )
            track_data = TrackData(
                track_name=self.static_data.track,
                length_m=self.static_data.trackSplineLength,
                sector_markers_m=[] # TODO: Obter marcadores de setor se possível
            )
            self.telemetry_session = TelemetrySession(
                session_info=session_info,
                track_data=track_data,
                laps=[]
            )
            logger.info("Estrutura TelemetrySession inicializada.")

    def _process_telemetry_data(self):
        """Processa os dados lidos e atualiza a estrutura de telemetria (com lock)."""
        if not self.physics_data or not self.graphics_data or not self.static_data:
            # logger.debug("Dados incompletos para processamento.")
            return

        with self.data_lock:
            if not self.is_capturing or not self.telemetry_session:
                return # Não processa se não estiver capturando ou sem sessão

            # --- Detecção de Nova Volta ---
            current_lap = self.graphics_data.completedLaps
            # Usa iLastTime > 0 como indicador de que uma volta foi completada
            # E verifica se o número da volta realmente incrementou
            if self.graphics_data.iLastTime > 0 and current_lap > self.last_lap_number:
                logger.info(f"Nova volta detectada: {current_lap} (Tempo: {self.graphics_data.iLastTime / 1000:.3f}s)")
                # Finaliza a volta anterior (se existir)
                if self.current_lap_data and self.data_points_buffer:
                    self._finalize_current_lap_nolock()

                # Inicia a nova volta
                self.last_lap_number = current_lap
                self.current_lap_data = LapData(
                    lap_number=current_lap, # Usa a volta completada como número da volta anterior
                    lap_time_ms=self.graphics_data.iLastTime,
                    sector_times_ms=[], # TODO: Capturar tempos de setor
                    is_valid=bool(self.graphics_data.isValidLap),
                    data_points=[] # O buffer será movido para cá ao finalizar
                )
                self.data_points_buffer = [] # Limpa buffer para a nova volta

            # --- Coleta de Ponto de Dados Atual ---
            # Mapeia os dados crus para a estrutura DataPoint
            # Certifique-se de que os nomes dos campos correspondem aos da classe DataPoint
            try:
                data_point = DataPoint(
                    timestamp_ms=int(time.time() * 1000), # Usar timestamp do sistema
                    # Ou usar self.graphics_data.clock ? Precisa verificar o que representa
                    distance_m=self.graphics_data.distanceTraveled,
                    speed_kmh=self.physics_data.speedKmh,
                    rpm=self.physics_data.rpms,
                    gear=self.physics_data.gear,
                    throttle=self.physics_data.gas,
                    brake=self.physics_data.brake,
                    steer_angle=self.physics_data.steerAngle,
                    clutch=self.physics_data.clutch,
                    # Adicionar mais campos conforme necessário e disponíveis
                    pos_x=self.graphics_data.carCoordinates[0], # Posição do jogador
                    pos_y=self.graphics_data.carCoordinates[1],
                    pos_z=self.graphics_data.carCoordinates[2],
                    # Outros campos podem precisar de cálculo ou vir de outros locais
                    lap_number=current_lap + 1, # Número da volta atual
                    sector=self.graphics_data.currentSectorIndex + 1, # Setor atual (base 1)
                    # ... outros campos como None ou 0 por padrão
                    tyre_press_fl=self.physics_data.wheelsPressure[0],
                    tyre_press_fr=self.physics_data.wheelsPressure[1],
                    tyre_press_rl=self.physics_data.wheelsPressure[2],
                    tyre_press_rr=self.physics_data.wheelsPressure[3],
                    tyre_temp_fl=self.physics_data.tyreCoreTemperature[0],
                    tyre_temp_fr=self.physics_data.tyreCoreTemperature[1],
                    tyre_temp_rl=self.physics_data.tyreCoreTemperature[2],
                    tyre_temp_rr=self.physics_data.tyreCoreTemperature[3],
                    # etc.
                )
                self.data_points_buffer.append(data_point)
            except Exception as e:
                 logger.exception(f"Erro ao criar DataPoint: {e}")

    def _finalize_current_lap_nolock(self):
        """Finaliza a volta atual, movendo o buffer para a lista de voltas (sem lock)."""
        if self.current_lap_data and self.data_points_buffer and self.telemetry_session:
            logger.debug(f"Finalizando volta {self.current_lap_data.lap_number} com {len(self.data_points_buffer)} pontos.")
            self.current_lap_data.data_points = self.data_points_buffer
            # Recalcula o tempo da volta com base nos timestamps dos pontos, se necessário?
            # Ou confia no iLastTime?
            # Por enquanto, confia no iLastTime.
            self.telemetry_session.laps.append(self.current_lap_data)
            self.current_lap_data = None
            self.data_points_buffer = []
        # else: logger.debug("Nenhuma volta atual ou buffer vazio para finalizar.")

    def _map_session_type(self, session_code: int) -> str:
        """Mapeia o código da sessão ACC para um nome legível."""
        mapping = {
            0: "Practice", 1: "Qualify", 2: "Race",
            3: "Hotlap", 4: "Time Attack", 5: "Drift",
            6: "Drag", 7: "Hotstint", 8: "Hotlap Superpole"
        }
        return mapping.get(session_code, f"Unknown ({session_code})")

    def _cleanup_memory(self):
        """Fecha os handles de memória compartilhada."""
        try:
            if self.physics_mmap: self.physics_mmap.close()
            if self.graphics_mmap: self.graphics_mmap.close()
            if self.static_mmap: self.static_mmap.close()
        except Exception as e:
            logger.error(f"Erro ao fechar handles de memória: {e}")
        finally:
            self.physics_mmap = None
            self.graphics_mmap = None
            self.static_mmap = None
            self.physics_data = SPageFilePhysics() # Reseta structs
            self.graphics_data = SPageFileGraphic()
            self.static_data = SPageFileStatic()

    # def _save_telemetry_data(self, data_to_save: TelemetrySession):
    #     """Salva os dados de telemetria capturados em um arquivo (ex: JSON)."""
    #     if not data_to_save or not data_to_save.session_info:
    #         logger.warning("Nenhum dado de telemetria para salvar.")
    #         return None
    #     try:
    #         # Cria um nome de arquivo baseado na sessão
    #         timestamp = data_to_save.session_info.date.strftime("%Y%m%d_%H%M%S")
    #         filename = f"ACC_{data_to_save.session_info.track}_{timestamp}.json"
    #         save_path = os.path.join(os.getcwd(), "telemetry_logs", filename) # Salva em subpasta
    #         os.makedirs(os.path.dirname(save_path), exist_ok=True)

    #         # Converte para dicionário antes de salvar como JSON
    #         # (Precisa de uma função para converter TelemetrySession e seus conteúdos)
    #         # data_dict = convert_telemetry_session_to_dict(data_to_save)

    #         # Simplificação: Usando convert_ctypes_to_native (não ideal para TelemetrySession)
    #         # Uma função to_dict() nas classes de dados seria melhor.
    #         # Por enquanto, vamos pular a serialização complexa.
    #         logger.info(f"Salvar dados em {save_path} (funcionalidade pendente)")
    #         # with open(save_path, "w", encoding="utf-8") as f:
    #         #     json.dump(data_dict, f, indent=4)

    #         logger.info(f"Dados de telemetria salvos (simulado) em: {save_path}")
    #         return save_path
    #     except Exception as e:
    #         logger.exception(f"Erro ao salvar dados de telemetria: {e}")
    #         return None

# Exemplo de uso (para teste direto do módulo)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG) # Habilita DEBUG para teste
    capture = ACCTelemetryCapture()
    if capture.connect():
        print("Conectado ao ACC. Iniciando captura por 15 segundos...")
        if capture.start_capture():
            # Simula a execução em uma thread
            capture_thread = threading.Thread(target=capture.run_capture_loop, daemon=True)
            capture_thread.start()

            time.sleep(15) # Captura por 15 segundos

            print("Parando captura...")
            capture.stop_capture()
            capture_thread.join(timeout=2) # Espera a thread terminar

            # Obtém e imprime os dados finais
            final_data = capture.get_telemetry_session()
            if final_data:
                print("--- Informações da Sessão ---")
                print(f"Pista: {final_data.session_info.track}")
                print(f"Carro: {final_data.session_info.vehicle}")
                print(f"Piloto: {final_data.session_info.driver}")
                print(f"Data: {final_data.session_info.date}")
                print(f"Número de Voltas Capturadas: {len(final_data.laps)}")
                for lap in final_data.laps:
                    print(f"  Volta {lap.lap_number}: Tempo={lap.lap_time_ms/1000:.3f}s, Pontos={len(lap.data_points)}, Válida={lap.is_valid}")
                    if lap.data_points:
                         # Imprime alguns dados do primeiro ponto da volta
                         dp0 = lap.data_points[0]
                         print(f"    DP[0]: Time={dp0.timestamp_ms}, Dist={dp0.distance_m:.1f}, Spd={dp0.speed_kmh:.1f}, RPM={dp0.rpm}, Gear={dp0.gear}")
            else:
                 print("Nenhum dado de sessão capturado.")

        capture.disconnect()
    else:
        print("Falha ao conectar ao ACC. Certifique-se de que o jogo está rodando em uma sessão.")

