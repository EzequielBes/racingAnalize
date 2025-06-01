# -*- coding: utf-8 -*-
"""Define as estruturas de dados padronizadas para telemetria."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

@dataclass
class DataPoint:
    """Representa um único ponto de dados de telemetria em um instante."""
    timestamp_ms: int = 0
    distance_m: float = 0.0
    lap_time_ms: int = 0
    sector: int = 0
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0
    speed_kmh: float = 0.0
    rpm: int = 0
    gear: int = 0
    steer_angle: float = 0.0
    throttle: float = 0.0
    brake: float = 0.0
    clutch: float = 0.0
    # Adicionar outros canais conforme necessário (pneus, etc.)
    tyre_temp_fl: Optional[float] = None
    tyre_temp_fr: Optional[float] = None
    tyre_temp_rl: Optional[float] = None
    tyre_temp_rr: Optional[float] = None
    tyre_press_fl: Optional[float] = None
    tyre_press_fr: Optional[float] = None
    tyre_press_rl: Optional[float] = None
    tyre_press_rr: Optional[float] = None
    # ... outros canais padronizados

@dataclass
class LapData:
    """Representa os dados de uma única volta."""
    lap_number: int
    lap_time_ms: int
    sector_times_ms: List[int] = field(default_factory=list)
    is_valid: bool = True
    # Os pontos de dados podem ser carregados sob demanda
    data_points: List[DataPoint] = field(default_factory=list)
    # Ou referenciar um arquivo externo para dados grandes
    data_points_ref: Optional[str] = None 

@dataclass
class TrackData:
    """Representa informações sobre a pista."""
    name: str
    length_meters: Optional[float] = None
    # Distâncias de início dos setores em metros
    sector_markers_m: List[float] = field(default_factory=list)
    # Coordenadas do traçado da pista (opcional, pode ser gerado)
    track_map_coords: Optional[List[Tuple[float, float]]] = None 

@dataclass
class SessionInfo:
    """Representa metadados de uma sessão de telemetria."""
    game: str
    track: str
    car: str
    date: str # ISO 8601 format
    source: str # e.g., "realtime", "import:file.ldx"
    driver_name: Optional[str] = None
    session_type: Optional[str] = None # e.g., "Practice", "Qualifying", "Race"
    # Outros metadados relevantes
    weather: Optional[Dict[str, Any]] = None

@dataclass
class TelemetrySession:
    """Estrutura completa para uma sessão de telemetria padronizada."""
    session_info: SessionInfo
    track_data: TrackData
    laps: List[LapData] = field(default_factory=list)


