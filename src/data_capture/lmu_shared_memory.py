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
# CORRIGIDO: Adicionado c_short e c_byte à importação
from ctypes import Structure, c_float, c_int, c_wchar, c_double, c_char, sizeof, byref, c_ubyte, c_short, c_byte
import mmap
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import json
import threading
import copy
from enum import Enum

# Adiciona o diretório pai ao path para permitir imports absolutos
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

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

# --- Função Auxiliar para Decodificar Strings ---
def decode_string(byte_array: bytes) -> str:
    """Decodifica um array de bytes (c_ubyte *) para string, parando no nulo."""
    try:
        null_pos = byte_array.find(b"\x00")
        if null_pos != -1:
            return byte_array[:null_pos].decode("utf-8", errors="ignore")
        else:
            return byte_array.decode("utf-8", errors="ignore")
    except Exception:
        return ""

# --- Função Auxiliar para Converter ctypes para Nativo ---
def convert_ctypes_to_native(obj):
    """Converte recursivamente um objeto ctypes (Structure, Array) para tipos nativos Python."""
    if isinstance(obj, Structure):
        result = {}
        for field_name, field_type in obj._fields_:
            value = getattr(obj, field_name)
            result[field_name] = convert_ctypes_to_native(value)
        return result
    elif isinstance(obj, ctypes.Array):
        return [convert_ctypes_to_native(item) for item in obj]
    elif isinstance(obj, bytes):
        return decode_string(obj) # Tenta decodificar bytes como string
    elif isinstance(obj, (int, float, bool, str)) or obj is None:
        return obj
    else:
        # Para outros tipos ctypes básicos (c_int, c_float, etc.)
        try:
            return obj.value
        except AttributeError:
            return obj # Retorna como está se não for um tipo básico conhecido

# --- Classe Principal de Captura LMU ---
class LMUSharedMemoryReader:
    """Classe para ler dados da memória compartilhada do Le Mans Ultimate (via rF2)."""

    def __init__(self):
        self.telemetry_mmap = None
        self.scoring_mmap = None
        self.telemetry_data = rF2VehicleTelemetry() # Apenas para o jogador
        self.scoring_data = rF2ScoringInfo()

        self.is_connected = False
        self.last_telemetry_time = -1.0
        self.last_scoring_time = -1.0
        self.player_id = -1 # ID do veículo do jogador

        logger.info("Inicializando leitor de memória compartilhada do LMU/rF2")

    def connect(self) -> bool:
        logger.info("Tentando conectar à memória compartilhada do LMU/rF2")
        if self.is_connected:
            logger.warning("Já está conectado.")
            return True
        try:
            # Tenta abrir os arquivos de memória compartilhada
            self.telemetry_mmap = mmap.mmap(-1, sizeof(rF2VehicleTelemetry), rFactor2Constants.MM_TELEMETRY_FILE_NAME)
            self.scoring_mmap = mmap.mmap(-1, sizeof(rF2ScoringInfo), rFactor2Constants.MM_SCORING_FILE_NAME)

            # Lê dados iniciais para confirmar
            self._read_scoring_data()
            if not self.scoring_data or self.scoring_data.mNumVehicles == 0:
                logger.error("Dados de scoring inválidos ou LMU/rF2 não está em uma sessão ativa.")
                self._cleanup_memory()
                return False

            # Encontra o ID do jogador (pode ser necessário ler telemetria também)
            self._read_telemetry_data()
            self.player_id = self.telemetry_data.mID if self.telemetry_data else -1

            if self.player_id == -1:
                 # Tenta encontrar pelo scoring se telemetria não deu ID
                 for i in range(self.scoring_data.mNumVehicles):
                     if self.scoring_data.mVehicles[i].mIsPlayer:
                         self.player_id = self.scoring_data.mVehicles[i].mID
                         break
                 if self.player_id == -1:
                    logger.error("Não foi possível encontrar o veículo do jogador nos dados.")
                    self._cleanup_memory()
                    return False

            self.is_connected = True
            track_name = decode_string(self.scoring_data.mTrackName)
            logger.info(f"Conectado à memória compartilhada do LMU/rF2 (Track: {track_name}, Player ID: {self.player_id})")
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
        self._cleanup_memory()
        self.is_connected = False
        logger.info("Desconectado da memória compartilhada do LMU/rF2")
        return True

    def _cleanup_memory(self):
        if self.telemetry_mmap:
            self.telemetry_mmap.close()
            self.telemetry_mmap = None
        if self.scoring_mmap:
            self.scoring_mmap.close()
            self.scoring_mmap = None

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

    def read_data(self) -> Optional[Dict[str, Any]]:
        """Lê os dados mais recentes e retorna um dicionário se houver dados novos."""
        if not self.is_connected:
            logger.warning("Tentativa de ler dados sem estar conectado.")
            return None

        self._read_telemetry_data()
        self._read_scoring_data()

        # Verifica se há dados novos (baseado no mElapsedTime da telemetria)
        current_telemetry_time = self.telemetry_data.mElapsedTime if self.telemetry_data else -1.0
        current_scoring_time = self.scoring_data.mCurrentET if self.scoring_data else -1.0

        if current_telemetry_time > self.last_telemetry_time or current_scoring_time > self.last_scoring_time:
            self.last_telemetry_time = current_telemetry_time
            self.last_scoring_time = current_scoring_time

            # Encontra o scoring do jogador atual
            player_scoring = None
            if self.scoring_data:
                for i in range(self.scoring_data.mNumVehicles):
                    if self.scoring_data.mVehicles[i].mID == self.player_id:
                        player_scoring = self.scoring_data.mVehicles[i]
                        break

            # Retorna uma cópia dos dados lidos em formato nativo Python
            return {
                "telemetry": convert_ctypes_to_native(self.telemetry_data) if self.telemetry_data else None,
                "scoring_info": convert_ctypes_to_native(self.scoring_data) if self.scoring_data else None,
                "player_scoring": convert_ctypes_to_native(player_scoring) if player_scoring else None
            }
        else:
            # logger.debug("Nenhum dado novo de telemetria ou scoring (tempo igual).")
            return None # Nenhum dado novo

    def normalize_to_datapoint(self, raw_data: Dict[str, Any]) -> Optional[DataPoint]:
        """Converte os dados brutos lidos em um objeto DataPoint padronizado."""
        if not raw_data or "telemetry" not in raw_data or "player_scoring" not in raw_data:
            return None

        telemetry = raw_data["telemetry"]
        player_scoring = raw_data["player_scoring"]

        if not telemetry or not player_scoring:
             return None

        try:
            # Mapeamento dos campos LMU/rF2 para DataPoint
            datapoint = DataPoint(
                timestamp_ms=int(telemetry.get("mElapsedTime", 0.0) * 1000),
                distance_m=player_scoring.get("mLapDist", 0.0),
                lap_time_ms=int(player_scoring.get("mTimeIntoLap", 0.0) * 1000),
                sector=player_scoring.get("mSector", 0),
                pos_x=telemetry["mPos"]["x"] if telemetry.get("mPos") else 0.0,
                pos_y=telemetry["mPos"]["y"] if telemetry.get("mPos") else 0.0,
                pos_z=telemetry["mPos"]["z"] if telemetry.get("mPos") else 0.0,
                # Velocidade: rF2 fornece mLocalVel (m/s), converter para km/h
                speed_kmh=( (telemetry["mLocalVel"]["x"]**2 + telemetry["mLocalVel"]["y"]**2 + telemetry["mLocalVel"]["z"]**2)**0.5 * 3.6 )
                           if telemetry.get("mLocalVel") else 0.0,
                rpm=int(telemetry.get("mEngineRPM", 0)),
                gear=telemetry.get("mGear", 0),
                steer_angle=telemetry.get("mFilteredSteering", 0.0), # Usar filtrado?
                throttle=telemetry.get("mFilteredThrottle", 0.0),
                brake=telemetry.get("mFilteredBrake", 0.0),
                clutch=telemetry.get("mFilteredClutch", 0.0),
                # Dados de pneus (exemplo - pegar FL)
                tyre_temp_fl=telemetry["mWheels"][0]["mTemperature"][1] # [0]=FL, [1]=Centro?
                               if telemetry.get("mWheels") and len(telemetry["mWheels"]) > 0 and len(telemetry["mWheels"][0].get("mTemperature", [])) > 1 else None,
                tyre_press_fl=telemetry["mWheels"][0]["mPressure"] * 1000 # kPa para Pa?
                                if telemetry.get("mWheels") and len(telemetry["mWheels"]) > 0 else None,
                # ... adicionar outros pneus e canais conforme necessário
            )
            return datapoint
        except KeyError as e:
            logger.warning(f"Chave ausente ao normalizar dados LMU/rF2: {e}")
            return None
        except Exception as e:
            logger.exception(f"Erro ao normalizar dados LMU/rF2 para DataPoint: {e}")
            return None

# --- Exemplo de Uso (para teste direto do módulo) ---
if __name__ == "__main__":
    print("Testando LMUSharedMemoryReader...")
    reader = LMUSharedMemoryReader()

    if reader.connect():
        print("Conectado com sucesso!")
        scoring_native = convert_ctypes_to_native(reader.scoring_data)
        track_name = scoring_native.get("mTrackName", "N/A")
        print(f"Track: {track_name}")
        print(f"Player ID: {reader.player_id}")
        print("Lendo dados por 10 segundos...")

        start_time = time.time()
        last_print_time = 0
        packets_read = 0

        while time.time() - start_time < 10:
            raw_data = reader.read_data() # Retorna dados nativos Python
            if raw_data:
                packets_read += 1
                # Imprime dados a cada segundo
                if time.time() - last_print_time >= 1.0:
                    print("-" * 20)
                    print(f"Timestamp: {datetime.now().isoformat()}")
                    telemetry = raw_data.get("telemetry")
                    player_scoring = raw_data.get("player_scoring")

                    if telemetry:
                        # CORRIGIDO: Acessar dados do dicionário nativo
                        speed_x = telemetry.get("mLocalVel", {}).get("x", 0.0)
                        rpm = telemetry.get("mEngineRPM", 0.0)
                        gear = telemetry.get("mGear", 0)
                        print(f"Speed X: {speed_x:.2f} m/s")
                        print(f"RPM: {rpm:.0f}")
                        print(f"Gear: {gear}")
                    if player_scoring:
                        lap = player_scoring.get("mTotalLaps", 0)
                        lap_time_s = player_scoring.get("mTimeIntoLap", 0.0)
                        print(f"Lap: {lap}")
                        print(f"Lap Time (s): {lap_time_s:.3f}")

                    # Normaliza e imprime o DataPoint
                    dp = reader.normalize_to_datapoint(raw_data)
                    if dp:
                        print(f"DataPoint Speed: {dp.speed_kmh:.1f} km/h")
                    else:
                        print("Falha ao normalizar DataPoint")
                    last_print_time = time.time()
            time.sleep(0.01)

        print(f"\nLeitura concluída. {packets_read} pacotes lidos em 10 segundos.")
        reader.disconnect()
    else:
        print("Falha ao conectar. Verifique se o LMU/rF2 está em execução e o plugin ativo.")

