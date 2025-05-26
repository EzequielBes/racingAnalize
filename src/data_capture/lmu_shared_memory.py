# -*- coding: utf-8 -*-
"""
Implementação da captura de telemetria para Le Mans Ultimate (LMU).
Utiliza a memória compartilhada do rFactor 2 (base do LMU) para obter dados em tempo real.
Baseado em pyRfactor2SharedMemory e na estrutura de acc_shared_memory.py.
"""

import os
import time
import logging
import ctypes
from ctypes import Structure, c_float, c_int, c_wchar, c_double, c_char, sizeof, byref, c_ubyte
import mmap
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import json
import threading
import copy
from enum import Enum

# Importa a estrutura de dados padronizada
from src.core.standard_data import TelemetrySession, SessionInfo, TrackData, LapData, DataPoint

# Configuração de logging
logger = logging.getLogger(__name__) # Usa o nome do módulo
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# --- Constantes e Enums do rFactor 2 / LMU ---
# (Baseado em rF2data.py de pyRfactor2SharedMemory)
class rFactor2Constants:
    MM_TELEMETRY_FILE_NAME = "$rFactor2SMMP_Telemetry$"
    MM_SCORING_FILE_NAME = "$rFactor2SMMP_Scoring$"
    # Outros arquivos podem ser úteis (Rules, Graphics, etc.), mas começamos com estes
    MAX_MAPPED_VEHICLES = 128
    MAX_MAPPED_IDS = 512

class rF2GamePhase(Enum):
    Garage = 0
    WarmUp = 1
    GridWalk = 2
    Formation = 3
    Countdown = 4
    GreenFlag = 5
    FullCourseYellow = 6
    SessionStopped = 7
    SessionOver = 8
    PausedOrHeartbeat = 9

# --- Estruturas de Dados rFactor 2 / LMU (Adaptadas de rF2data.py) ---
# (Simplificadas para focar no essencial inicialmente)
class rF2Vec3(Structure):
    _pack_ = 4
    _fields_ = [("x", c_double), ("y", c_double), ("z", c_double)]

class rF2Wheel(Structure):
    _pack_ = 4
    _fields_ = [
        ("mSuspensionDeflection", c_double), ("mRideHeight", c_double),
        ("mSuspForce", c_double), ("mBrakeTemp", c_double),
        ("mBrakePressure", c_double), ("mRotation", c_double),
        ("mLateralPatchVel", c_double), ("mLongitudinalPatchVel", c_double),
        ("mLateralGroundVel", c_double), ("mLongitudinalGroundVel", c_double),
        ("mCamber", c_double), ("mLateralForce", c_double),
        ("mLongitudinalForce", c_double), ("mTireLoad", c_double),
        ("mGripFract", c_double), ("mPressure", c_double),
        ("mTemperature", c_double * 3), ("mWear", c_double),
        ("mTerrainName", c_ubyte * 16), ("mSurfaceType", c_ubyte),
        ("mFlat", c_ubyte), ("mDetached", c_ubyte),
        ("mStaticUndeflectedRadius", c_ubyte), # Atenção: tipo pode estar incorreto na ref
        ("mVerticalTireDeflection", c_double), ("mWheelYLocation", c_double),
        ("mToe", c_double), ("mTireCarcassTemperature", c_double),
        ("mTireInnerLayerTemperature", c_double * 3),
        ("mExpansion", c_ubyte * 24),
    ]

class rF2VehicleTelemetry(Structure):
    _pack_ = 4
    _fields_ = [
        ("mID", c_int), ("mDeltaTime", c_double), ("mElapsedTime", c_double),
        ("mLapNumber", c_int), ("mLapStartET", c_double),
        ("mVehicleName", c_ubyte * 64), ("mTrackName", c_ubyte * 64),
        ("mPos", rF2Vec3), ("mLocalVel", rF2Vec3), ("mLocalAccel", rF2Vec3),
        ("mOri", rF2Vec3 * 3), ("mLocalRot", rF2Vec3), ("mLocalRotAccel", rF2Vec3),
        ("mGear", c_int), ("mEngineRPM", c_double), ("mEngineWaterTemp", c_double),
        ("mEngineOilTemp", c_double), ("mClutchRPM", c_double),
        ("mUnfilteredThrottle", c_double), ("mUnfilteredBrake", c_double),
        ("mUnfilteredSteering", c_double), ("mUnfilteredClutch", c_double),
        ("mFilteredThrottle", c_double), ("mFilteredBrake", c_double),
        ("mFilteredSteering", c_double), ("mFilteredClutch", c_double),
        ("mSteeringShaftTorque", c_double), ("mFront3rdDeflection", c_double),
        ("mRear3rdDeflection", c_double), ("mFrontWingHeight", c_double),
        ("mFrontRideHeight", c_double), ("mRearRideHeight", c_double),
        ("mDrag", c_double), ("mFrontDownforce", c_double), ("mRearDownforce", c_double),
        ("mFuel", c_double), ("mEngineMaxRPM", c_double),
        ("mScheduledStops", c_ubyte), ("mOverheating", c_ubyte),
        ("mDetached", c_ubyte), ("mHeadlights", c_ubyte),
        ("mDentSeverity", c_ubyte * 8), ("mLastImpactET", c_double),
        ("mLastImpactMagnitude", c_double), ("mLastImpactPos", rF2Vec3),
        ("mEngineTorque", c_double), ("mCurrentSector", c_int),
        ("mSpeedLimiter", c_ubyte), ("mMaxGears", c_ubyte),
        ("mFrontTireCompoundIndex", c_ubyte), ("mRearTireCompoundIndex", c_ubyte),
        ("mFuelCapacity", c_double), ("mFrontFlapActivated", c_ubyte),
        ("mRearFlapActivated", c_ubyte), ("mRearFlapLegalStatus", c_ubyte),
        ("mIgnitionStarter", c_ubyte), ("mFrontTireCompoundName", c_ubyte * 18),
        ("mRearTireCompoundName", c_ubyte * 18), ("mSpeedLimiterAvailable", c_ubyte),
        ("mAntiStallActivated", c_ubyte), ("mUnused", c_ubyte * 2),
        ("mVisualSteeringWheelRange", c_float), ("mRearBrakeBias", c_double),
        ("mTurboBoostPressure", c_double), ("mPhysicsToGraphicsOffset", c_float * 3),
        ("mPhysicalSteeringWheelRange", c_float), ("mExpansion", c_ubyte * 152),
        ("mWheels", rF2Wheel * 4),
    ]

class rF2VehicleScoring(Structure):
    _pack_ = 4
    _fields_ = [
        ("mID", c_int), ("mDriverName", c_ubyte * 32), ("mVehicleName", c_ubyte * 64),
        ("mTotalLaps", c_short), ("mSector", c_byte), ("mFinishStatus", c_byte),
        ("mLapDist", c_double), ("mPathLateral", c_double), ("mRelevantTrackEdge", c_double),
        ("mBestSector1", c_double), ("mBestSector2", c_double), ("mBestLapTime", c_double),
        ("mLastSector1", c_double), ("mLastSector2", c_double), ("mLastLapTime", c_double),
        ("mCurSector1", c_double), ("mCurSector2", c_double),
        ("mNumPitstops", c_short), ("mNumPenalties", c_short),
        ("mIsPlayer", c_byte), ("mControl", c_byte), ("mInPits", c_byte),
        ("mPlace", c_ubyte), ("mVehicleClass", c_ubyte * 32),
        ("mTimeBehindNext", c_double), ("mLapsBehindNext", c_int),
        ("mTimeBehindLeader", c_double), ("mLapsBehindLeader", c_int),
        ("mLapStartET", c_double), ("mPosition", rF2Vec3),
        ("mHeadlights", c_ubyte), ("mPitState", c_ubyte), ("mServerScored", c_ubyte),
        ("mIndividualPhase", c_ubyte),
        ("mQualification", c_int),
        ("mTimeIntoLap", c_double), ("mEstimatedLapTime", c_double),
        ("mPitLapDist", c_double), ("mBestLapSector1", c_double),
        ("mBestLapSector2", c_double), ("mBestLapSector3", c_double),
        ("mPlayerName", c_ubyte * 32), # Adicionado para possível uso
        ("mExpansion", c_ubyte * 232), # Ajustado para tamanho correto?
    ]

class rF2ScoringInfo(Structure):
    _pack_ = 4
    _fields_ = [
        ("mTrackName", c_ubyte * 64), ("mSession", c_int), ("mCurrentET", c_double),
        ("mEndET", c_double), ("mMaxLaps", c_int), ("mLapDist", c_double),
        ("mResultsStream", c_ubyte * 8192), # Pode ser útil para resultados pós-sessão
        ("mNumVehicles", c_int),
        ("mVehicles", rF2VehicleScoring * rFactor2Constants.MAX_MAPPED_VEHICLES),
    ]

# --- Classe Principal de Captura LMU ---
class LMUTelemetryCapture:
    """Classe para captura de telemetria do Le Mans Ultimate (via rF2 Shared Memory)."""

    def __init__(self):
        self.telemetry_mmap = None
        self.scoring_mmap = None
        self.telemetry_data = rF2VehicleTelemetry() # Apenas para o jogador
        self.scoring_data = rF2ScoringInfo()

        self.is_connected = False
        self.is_capturing = False
        self.last_lap_number = -1
        self.capture_start_time = None
        self.player_vehicle_scoring: Optional[rF2VehicleScoring] = None
        self.player_id = -1 # ID do veículo do jogador

        # Dados compartilhados
        self.data_lock = threading.Lock()
        self.data_points_buffer: List[DataPoint] = []
        self.current_lap_data: Optional[LapData] = None
        self.telemetry_session: Optional[TelemetrySession] = None

        logger.info("Inicializando capturador de telemetria do LMU/rF2")

    def connect(self) -> bool:
        logger.info("Tentando conectar à memória compartilhada do LMU/rF2")
        if self.is_connected:
            logger.warning("Já está conectado.")
            return True
        try:
            # Tenta abrir os arquivos de memória compartilhada
            # O tamanho exato pode variar com a versão do plugin/jogo, mas usamos as structs como base
            self.telemetry_mmap = mmap.mmap(-1, sizeof(rF2VehicleTelemetry), rFactor2Constants.MM_TELEMETRY_FILE_NAME)
            self.scoring_mmap = mmap.mmap(-1, sizeof(rF2ScoringInfo), rFactor2Constants.MM_SCORING_FILE_NAME)

            # Lê dados iniciais para confirmar
            self._read_scoring_data()
            if not self.scoring_data or self.scoring_data.mNumVehicles == 0:
                logger.error("Dados de scoring inválidos ou LMU/rF2 não está em uma sessão ativa.")
                self._cleanup_memory()
                return False

            # Encontra o ID do jogador
            self._find_player_vehicle()
            if self.player_id == -1:
                 logger.error("Não foi possível encontrar o veículo do jogador nos dados de scoring.")
                 self._cleanup_memory()
                 return False

            self.is_connected = True
            track_name = decode_string(self.scoring_data.mTrackName)
            logger.info(f"Conectado à memória compartilhada do LMU/rF2 (Track: {track_name}, Player ID: {self.player_id})")
            self._initialize_telemetry_session() # Cria a estrutura da sessão
            return True

        except FileNotFoundError:
            logger.error("Memória compartilhada do LMU/rF2 não encontrada. O jogo está em execução e o plugin ativo?")
            self._cleanup_memory()
            return False
        except Exception as e:
            logger.exception(f"Erro ao conectar à memória compartilhada do LMU/rF2: {e}")
            self._cleanup_memory()
            return False

    def disconnect(self) -> bool:
        logger.info("Tentando desconectar da memória compartilhada do LMU/rF2")
        if self.is_capturing:
            self.stop_capture()
        self._cleanup_memory()
        self.is_connected = False
        self.telemetry_session = None
        logger.info("Desconectado da memória compartilhada do LMU/rF2")
        return True

    def start_capture(self) -> bool:
        logger.info("Tentando iniciar captura de telemetria do LMU/rF2")
        if not self.is_connected:
            logger.error("Não está conectado à memória compartilhada do LMU/rF2.")
            return False
        if self.is_capturing:
            logger.warning("Captura já está em andamento.")
            return True

        with self.data_lock:
            self.is_capturing = True
            self.capture_start_time = time.time()
            # Lê dados de scoring para pegar a volta atual ANTES de limpar
            self._read_scoring_data()
            self._find_player_vehicle() # Garante que temos o scoring do jogador
            self.last_lap_number = self.player_vehicle_scoring.mTotalLaps if self.player_vehicle_scoring else -1
            self.data_points_buffer = []
            self.current_lap_data = None
            # Reinicializa a sessão para limpar voltas antigas
            self._initialize_telemetry_session()

        logger.info("Captura de telemetria do LMU/rF2 iniciada.")
        return True

    def stop_capture(self) -> bool:
        logger.info("Tentando parar captura de telemetria do LMU/rF2")
        if not self.is_capturing:
            logger.warning("Captura não está em andamento.")
            return True

        telemetry_to_save = None
        with self.data_lock:
            self.is_capturing = False
            if self.current_lap_data and self.data_points_buffer:
                self._finalize_current_lap_nolock()
            self.capture_start_time = None
            if self.telemetry_session:
                telemetry_to_save = copy.deepcopy(self.telemetry_session)

        logger.info("Captura de telemetria do LMU/rF2 parada.")
        # Salvar dados (funcionalidade pendente)
        # if telemetry_to_save:
        #     self._save_telemetry_data(telemetry_to_save)
        return True

    def get_current_data(self) -> Optional[Dict[str, Any]]:
        """Retorna os dados mais recentes lidos (formato nativo)."""
        if not self.is_connected:
            return None
        self._read_telemetry_data()
        self._read_scoring_data()
        self._find_player_vehicle() # Atualiza ponteiro para scoring do jogador

        return {
            "telemetry": copy.deepcopy(self.telemetry_data) if self.telemetry_data else None,
            "scoring_info": copy.deepcopy(self.scoring_data) if self.scoring_data else None,
            "player_scoring": copy.deepcopy(self.player_vehicle_scoring) if self.player_vehicle_scoring else None
        }

    def get_telemetry_session(self) -> Optional[TelemetrySession]:
         """Retorna uma cópia segura da sessão de telemetria atual."""
         with self.data_lock:
             return copy.deepcopy(self.telemetry_session)

    def run_capture_loop(self):
        """Método principal do loop de captura (executado em uma thread separada)."""
        logger.info("Iniciando loop de captura LMU/rF2...")
        last_telemetry_update_time = 0.0
        while True:
            with self.data_lock:
                if not self.is_capturing:
                    break

            start_time = time.perf_counter()

            # Lê os dados mais recentes
            self._read_telemetry_data()
            self._read_scoring_data()
            self._find_player_vehicle() # Atualiza ponteiro para scoring do jogador

            # Processa os dados se houver dados válidos e novos
            if self.telemetry_data and self.player_vehicle_scoring:
                # rF2 não tem packetId, usamos mElapsedTime como indicador de atualização
                current_telemetry_time = self.telemetry_data.mElapsedTime
                if current_telemetry_time > last_telemetry_update_time:
                    last_telemetry_update_time = current_telemetry_time
                    self._process_telemetry_data()
                # else: logger.debug("Nenhum dado novo de telemetria (tempo igual).")
            # else: logger.debug("Dados de telemetria ou scoring do jogador não disponíveis.")

            # Controla a taxa de atualização
            elapsed = time.perf_counter() - start_time
            sleep_time = (1/60) - elapsed # Ajuste a frequência
            if sleep_time > 0:
                time.sleep(sleep_time)

        logger.info("Loop de captura LMU/rF2 finalizado.")

    # --- Métodos Privados ---
    def _read_telemetry_data(self):
        if not self.telemetry_mmap:
            return
        try:
            self.telemetry_mmap.seek(0)
            telemetry_buffer = self.telemetry_mmap.read(sizeof(rF2VehicleTelemetry))
            self.telemetry_data = rF2VehicleTelemetry.from_buffer_copy(telemetry_buffer)
        except Exception as e:
            # logger.warning(f"Erro ao ler dados de telemetria rF2: {e}")
            self.telemetry_data = None

    def _read_scoring_data(self):
        if not self.scoring_mmap:
            return
        try:
            self.scoring_mmap.seek(0)
            scoring_buffer = self.scoring_mmap.read(sizeof(rF2ScoringInfo))
            self.scoring_data = rF2ScoringInfo.from_buffer_copy(scoring_buffer)
        except Exception as e:
            # logger.warning(f"Erro ao ler dados de scoring rF2: {e}")
            self.scoring_data = None

    def _find_player_vehicle(self):
        """Encontra o registro de scoring do jogador."""
        self.player_vehicle_scoring = None
        self.player_id = -1
        if self.scoring_data and self.scoring_data.mNumVehicles > 0:
            for i in range(self.scoring_data.mNumVehicles):
                vehicle = self.scoring_data.mVehicles[i]
                if vehicle.mIsPlayer:
                    self.player_vehicle_scoring = vehicle
                    self.player_id = vehicle.mID
                    # logger.debug(f"Veículo do jogador encontrado: ID={self.player_id}, Nome={decode_string(vehicle.mDriverName)}")
                    break
            # if self.player_id == -1: logger.warning("Veículo do jogador não encontrado na lista.")
        # else: logger.debug("Dados de scoring não disponíveis ou sem veículos.")

    def _initialize_telemetry_session(self):
        """Cria ou reinicia a estrutura TelemetrySession."""
        if not self.scoring_data or not self.player_vehicle_scoring:
            logger.error("Não é possível inicializar a sessão sem dados de scoring ou do jogador.")
            return

        with self.data_lock:
            session_info = SessionInfo(
                game="Le Mans Ultimate", # Ou rFactor 2?
                track=decode_string(self.scoring_data.mTrackName),
                vehicle=decode_string(self.player_vehicle_scoring.mVehicleName),
                driver=decode_string(self.player_vehicle_scoring.mPlayerName), # Usar mPlayerName se disponível
                session_type=self._map_session_type(self.scoring_data.mSession),
                date=datetime.now()
            )
            track_data = TrackData(
                track_name=decode_string(self.scoring_data.mTrackName),
                length_m=self.scoring_data.mLapDist if self.scoring_data.mLapDist > 0 else None,
                sector_markers_m=[] # TODO: Obter marcadores de setor
            )
            self.telemetry_session = TelemetrySession(
                session_info=session_info,
                track_data=track_data,
                laps=[]
            )
            logger.info("Estrutura TelemetrySession (LMU/rF2) inicializada.")

    def _process_telemetry_data(self):
        """Processa os dados lidos e atualiza a estrutura de telemetria (com lock)."""
        if not self.telemetry_data or not self.player_vehicle_scoring:
            return

        with self.data_lock:
            if not self.is_capturing or not self.telemetry_session:
                return

            # --- Detecção de Nova Volta ---
            current_lap = self.player_vehicle_scoring.mTotalLaps
            # Usa mLastLapTime > 0 como indicador e verifica incremento da volta
            if self.player_vehicle_scoring.mLastLapTime > 0 and current_lap > self.last_lap_number:
                logger.info(f"Nova volta LMU/rF2 detectada: {current_lap} (Tempo: {self.player_vehicle_scoring.mLastLapTime:.3f}s)")
                if self.current_lap_data and self.data_points_buffer:
                    self._finalize_current_lap_nolock()

                self.last_lap_number = current_lap
                self.current_lap_data = LapData(
                    lap_number=current_lap, # Volta completada
                    lap_time_ms=int(self.player_vehicle_scoring.mLastLapTime * 1000),
                    sector_times_ms=[
                        int(self.player_vehicle_scoring.mLastSector1 * 1000) if self.player_vehicle_scoring.mLastSector1 > 0 else 0,
                        int(self.player_vehicle_scoring.mLastSector2 * 1000) if self.player_vehicle_scoring.mLastSector2 > 0 else 0,
                        # Calcula S3
                        int((self.player_vehicle_scoring.mLastLapTime - self.player_vehicle_scoring.mLastSector1 - self.player_vehicle_scoring.mLastSector2) * 1000)
                        if self.player_vehicle_scoring.mLastSector1 > 0 and self.player_vehicle_scoring.mLastSector2 > 0 else 0
                    ],
                    is_valid=True, # TODO: Verificar se há flag de validade em rF2
                    data_points=[]
                )
                self.data_points_buffer = []

            # --- Coleta de Ponto de Dados Atual ---
            try:
                # Mapeamento rF2 -> DataPoint
                # Atenção: unidades podem precisar de conversão (ex: velocidade m/s -> km/h)
                speed_mps = np.linalg.norm([self.telemetry_data.mLocalVel.x, self.telemetry_data.mLocalVel.y, self.telemetry_data.mLocalVel.z])
                data_point = DataPoint(
                    timestamp_ms=int(self.telemetry_data.mElapsedTime * 1000),
                    distance_m=self.player_vehicle_scoring.mLapDist,
                    speed_kmh=speed_mps * 3.6,
                    rpm=self.telemetry_data.mEngineRPM,
                    gear=self.telemetry_data.mGear,
                    throttle=self.telemetry_data.mFilteredThrottle,
                    brake=self.telemetry_data.mFilteredBrake,
                    steer_angle=self.telemetry_data.mFilteredSteering * (self.telemetry_data.mPhysicalSteeringWheelRange / 2.0), # Converter para graus?
                    clutch=self.telemetry_data.mFilteredClutch,
                    pos_x=self.telemetry_data.mPos.x,
                    pos_y=self.telemetry_data.mPos.y,
                    pos_z=self.telemetry_data.mPos.z,
                    lap_number=current_lap + 1,
                    sector=self.player_vehicle_scoring.mSector + 1, # rF2 é 0-based
                    # Mapear outros campos importantes
                    tyre_press_fl=self.telemetry_data.mWheels[0].mPressure,
                    tyre_press_fr=self.telemetry_data.mWheels[1].mPressure,
                    tyre_press_rl=self.telemetry_data.mWheels[2].mPressure,
                    tyre_press_rr=self.telemetry_data.mWheels[3].mPressure,
                    # Temperaturas precisam de conversão Kelvin -> Celsius
                    tyre_temp_fl=self.telemetry_data.mWheels[0].mTireCarcassTemperature - 273.15,
                    tyre_temp_fr=self.telemetry_data.mWheels[1].mTireCarcassTemperature - 273.15,
                    tyre_temp_rl=self.telemetry_data.mWheels[2].mTireCarcassTemperature - 273.15,
                    tyre_temp_rr=self.telemetry_data.mWheels[3].mTireCarcassTemperature - 273.15,
                    # ... etc
                )
                self.data_points_buffer.append(data_point)
            except Exception as e:
                 logger.exception(f"Erro ao criar DataPoint LMU/rF2: {e}")

    def _finalize_current_lap_nolock(self):
        """Finaliza a volta atual (sem lock)."""
        if self.current_lap_data and self.data_points_buffer and self.telemetry_session:
            logger.debug(f"Finalizando volta LMU/rF2 {self.current_lap_data.lap_number} com {len(self.data_points_buffer)} pontos.")
            self.current_lap_data.data_points = self.data_points_buffer
            self.telemetry_session.laps.append(self.current_lap_data)
            self.current_lap_data = None
            self.data_points_buffer = []

    def _map_session_type(self, session_code: int) -> str:
        """Mapeia o código da sessão rF2 para um nome legível."""
        # rF2: 0=testday 1-4=practice 5-8=qual 9=warmup 10-13=race
        if session_code == 0: return "Test Day"
        if 1 <= session_code <= 4: return f"Practice {session_code}"
        if 5 <= session_code <= 8: return f"Qualify {session_code - 4}"
        if session_code == 9: return "Warmup"
        if 10 <= session_code <= 13: return f"Race {session_code - 9}"
        return f"Unknown ({session_code})"

    def _cleanup_memory(self):
        """Fecha os handles de memória compartilhada."""
        try:
            if self.telemetry_mmap: self.telemetry_mmap.close()
            if self.scoring_mmap: self.scoring_mmap.close()
        except Exception as e:
            logger.error(f"Erro ao fechar handles de memória LMU/rF2: {e}")
        finally:
            self.telemetry_mmap = None
            self.scoring_mmap = None
            self.telemetry_data = rF2VehicleTelemetry()
            self.scoring_data = rF2ScoringInfo()
            self.player_vehicle_scoring = None
            self.player_id = -1

# Exemplo de uso (para teste direto do módulo)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    capture = LMUTelemetryCapture()
    if capture.connect():
        print("Conectado ao LMU/rF2. Iniciando captura por 15 segundos...")
        if capture.start_capture():
            capture_thread = threading.Thread(target=capture.run_capture_loop, daemon=True)
            capture_thread.start()
            time.sleep(15)
            print("Parando captura...")
            capture.stop_capture()
            capture_thread.join(timeout=2)

            final_data = capture.get_telemetry_session()
            if final_data:
                print("--- Informações da Sessão (LMU/rF2) ---")
                print(f"Pista: {final_data.session_info.track}")
                print(f"Carro: {final_data.session_info.vehicle}")
                print(f"Piloto: {final_data.session_info.driver}")
                print(f"Data: {final_data.session_info.date}")
                print(f"Número de Voltas Capturadas: {len(final_data.laps)}")
                for lap in final_data.laps:
                    print(f"  Volta {lap.lap_number}: Tempo={lap.lap_time_ms/1000:.3f}s, Pontos={len(lap.data_points)}, Válida={lap.is_valid}")
                    if lap.data_points:
                         dp0 = lap.data_points[0]
                         print(f"    DP[0]: Time={dp0.timestamp_ms}, Dist={dp0.distance_m:.1f}, Spd={dp0.speed_kmh:.1f}, RPM={dp0.rpm}, Gear={dp0.gear}")
            else:
                 print("Nenhum dado de sessão LMU/rF2 capturado.")

        capture.disconnect()
    else:
        print("Falha ao conectar ao LMU/rF2. Certifique-se de que o jogo está rodando e o plugin de memória compartilhada está ativo.")

