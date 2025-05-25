"""
Módulo de análise avançada de telemetria para o Race Telemetry Analyzer.
Responsável por analisar pedais, setores e identificar erros de pilotagem.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
from scipy.signal import find_peaks


class TelemetryAnalyzer:
    """Classe principal para análise avançada de telemetria."""
    
    def __init__(self):
        """Inicializa o analisador de telemetria."""
        pass
    
    def analyze_lap(self, lap_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Realiza uma análise completa de uma única volta.
        
        Args:
            lap_data: Dicionário com os dados da volta
            
        Returns:
            Dicionário com os resultados da análise
        """
        analysis_results = {
            'pedal_analysis': self.analyze_pedal_inputs(lap_data),
            'sector_analysis': self.analyze_sector_performance(lap_data),
            'error_detection': self.detect_driving_errors(lap_data),
            'key_points': self._find_key_points(lap_data["data_points"])
        }
        
        return analysis_results
    
    def analyze_pedal_inputs(self, lap_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analisa o uso dos pedais (acelerador e freio) durante a volta.
        
        Args:
            lap_data: Dicionário com os dados da volta
            
        Returns:
            Dicionário com a análise dos pedais
        """
        points = lap_data["data_points"]
        
        if not points or ("throttle" not in points[0] and "brake" not in points[0]):
            return {
                "throttle_usage": 0,
                "brake_usage": 0,
                "overlap_time": 0,
                "throttle_smoothness": 0,
                "brake_smoothness": 0,
                "issues": []
            }
        
        # Extrai dados dos pedais e tempo
        times = np.array([p["time"] for p in points])
        throttles = np.array([p.get("throttle", 0) for p in points])
        brakes = np.array([p.get("brake", 0) for p in points])
        
        # Calcula tempo total da volta
        total_time = times[-1] - times[0]
        if total_time <= 0:
            return {
                "throttle_usage": 0,
                "brake_usage": 0,
                "overlap_time": 0,
                "throttle_smoothness": 0,
                "brake_smoothness": 0,
                "issues": []
            }
        
        # Calcula tempo de uso de cada pedal
        throttle_threshold = 0.1
        brake_threshold = 0.1
        
        throttle_active_time = 0
        brake_active_time = 0
        overlap_time = 0
        
        for i in range(len(times) - 1):
            dt = times[i+1] - times[i]
            
            throttle_active = throttles[i] > throttle_threshold
            brake_active = brakes[i] > brake_threshold
            
            if throttle_active:
                throttle_active_time += dt
            if brake_active:
                brake_active_time += dt
            if throttle_active and brake_active:
                overlap_time += dt
        
        # Calcula suavidade (inverso da variação média)
        throttle_diff = np.diff(throttles)
        brake_diff = np.diff(brakes)
        
        throttle_smoothness = 1 / (np.mean(np.abs(throttle_diff)) + 1e-6)
        brake_smoothness = 1 / (np.mean(np.abs(brake_diff)) + 1e-6)
        
        # Identifica problemas comuns
        issues = []
        if overlap_time / total_time > 0.02: # Mais de 2% de overlap
            issues.append({
                "type": "pedal_overlap",
                "severity": "medium",
                "description": f"Tempo excessivo de sobreposição de acelerador e freio ({overlap_time:.2f}s)"
            })
        
        # Verifica se há "bombeamento" excessivo do freio
        brake_peaks, _ = find_peaks(brakes, height=0.5, distance=5) # Picos de frenagem forte
        if len(brake_peaks) > 20: # Número arbitrário, ajustar conforme necessário
            issues.append({
                "type": "brake_pumping",
                "severity": "low",
                "description": "Possível bombeamento excessivo do freio"
            })
            
        # Verifica aceleração instável
        throttle_std_dev = np.std(throttle_diff)
        if throttle_std_dev > 0.1: # Variação padrão alta
             issues.append({
                "type": "throttle_instability",
                "severity": "low",
                "description": "Aceleração instável detectada"
            })

        return {
            "throttle_usage_time": throttle_active_time,
            "brake_usage_time": brake_active_time,
            "throttle_usage_percent": (throttle_active_time / total_time) * 100,
            "brake_usage_percent": (brake_active_time / total_time) * 100,
            "overlap_time": overlap_time,
            "overlap_percent": (overlap_time / total_time) * 100,
            "throttle_smoothness": throttle_smoothness,
            "brake_smoothness": brake_smoothness,
            "issues": issues
        }

    def analyze_sector_performance(self, lap_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analisa o desempenho em cada setor da volta.
        
        Args:
            lap_data: Dicionário com os dados da volta
            
        Returns:
            Dicionário com a análise dos setores
        """
        if "sectors" not in lap_data or not lap_data["sectors"]:
            return {"sector_times": [], "consistency": 0, "best_sector": None, "worst_sector": None}
        
        sectors = lap_data["sectors"]
        sector_times = [s["time"] for s in sectors]
        
        if not sector_times:
             return {"sector_times": [], "consistency": 0, "best_sector": None, "worst_sector": None}

        # Calcula consistência (desvio padrão relativo)
        mean_time = np.mean(sector_times)
        std_dev = np.std(sector_times)
        consistency = (std_dev / mean_time) * 100 if mean_time > 0 else 0
        
        # Identifica melhor e pior setor
        best_sector_idx = np.argmin(sector_times)
        worst_sector_idx = np.argmax(sector_times)
        
        best_sector = sectors[best_sector_idx]["sector"]
        worst_sector = sectors[worst_sector_idx]["sector"]
        
        return {
            "sector_times": sector_times,
            "consistency_percentage": consistency,
            "best_sector": best_sector,
            "worst_sector": worst_sector
        }

    def detect_driving_errors(self, lap_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detecta erros comuns de pilotagem com base nos dados de telemetria.
        
        Args:
            lap_data: Dicionário com os dados da volta
            
        Returns:
            Lista de dicionários descrevendo os erros detectados
        """
        points = lap_data["data_points"]
        errors = []
        
        if len(points) < 10:
            return errors
        
        # Extrai dados relevantes
        times = np.array([p["time"] for p in points])
        speeds = np.array([p["speed"] for p in points])
        throttles = np.array([p.get("throttle", 0) for p in points])
        brakes = np.array([p.get("brake", 0) for p in points])
        distances = np.array([p.get("distance", 0) for p in points])
        positions = np.array([p["position"] for p in points])
        
        # 1. Frenagem Tardia / Excessiva
        braking_points = self._find_braking_points(points)
        apex_points = self._find_apex_points(points)
        
        for bp in braking_points:
            # Encontra o próximo ápice
            next_apex = None
            for ap in apex_points:
                if ap["index"] > bp["index"]:
                    next_apex = ap
                    break
            
            if next_apex:
                # Verifica se a velocidade no ápice é muito baixa após a frenagem
                speed_at_apex = next_apex["speed"]
                speed_at_braking = bp["speed"]
                
                # Heurística: Se a velocidade no ápice for < 50% da velocidade na frenagem
                if speed_at_apex < speed_at_braking * 0.5 and speed_at_braking > 100:
                    errors.append({
                        "type": "late_braking",
                        "severity": "medium",
                        "time": bp["time"],
                        "position": bp["position"],
                        "description": "Possível frenagem tardia ou excessiva, resultando em baixa velocidade no ápice"
                    })
        
        # 2. Aceleração Prematura / Tardia
        acceleration_points = self._find_acceleration_points(points)
        
        for ap in acceleration_points:
            # Verifica se a aceleração começou muito antes do ápice
            prev_apex = None
            for apex in reversed(apex_points):
                if apex["index"] < ap["index"]:
                    prev_apex = apex
                    break
            
            if prev_apex:
                time_diff = ap["time"] - prev_apex["time"]
                # Heurística: Se acelerou muito rápido após o ápice
                if time_diff < 0.5 and prev_apex["speed"] < 100: # Menos de 0.5s após ápice lento
                     errors.append({
                        "type": "early_acceleration",
                        "severity": "low",
                        "time": ap["time"],
                        "position": ap["position"],
                        "description": "Possível aceleração prematura antes de completar a curva"
                    })
        
        # 3. Perda de Tração (detecção simplificada por variação de velocidade)
        speed_diff = np.diff(speeds)
        acceleration = speed_diff / np.diff(times)
        
        # Procura por quedas bruscas de aceleração enquanto o acelerador está alto
        for i in range(1, len(acceleration)):
            if throttles[i] > 0.8 and acceleration[i] < -20: # Queda de aceleração > 20 m/s^2
                errors.append({
                    "type": "traction_loss",
                    "severity": "medium",
                    "time": times[i+1],
                    "position": points[i+1]["position"],
                    "description": "Possível perda de tração detectada durante aceleração"
                })
                break # Reporta apenas a primeira ocorrência para evitar spam
        
        # 4. Trajetória Inconsistente (detecção simplificada por variação lateral)
        # Calcula a curvatura da trajetória (aproximada)
        dx = np.gradient([p[0] for p in positions])
        dy = np.gradient([p[1] for p in positions])
        ddx = np.gradient(dx)
        ddy = np.gradient(dy)
        curvature = np.abs(dx * ddy - dy * ddx) / (dx**2 + dy**2)**1.5
        
        # Procura por picos altos e repentinos na curvatura
        curvature_peaks, _ = find_peaks(curvature, height=np.percentile(curvature, 98), distance=10)
        if len(curvature_peaks) > 10:
             errors.append({
                "type": "inconsistent_line",
                "severity": "low",
                "time": times[curvature_peaks[0]], # Reporta o primeiro pico
                "position": points[curvature_peaks[0]]["position"],
                "description": "Trajetória inconsistente detectada (muitas correções)"
            })

        # Adiciona problemas detectados na análise de pedais
        pedal_analysis = self.analyze_pedal_inputs(lap_data)
        errors.extend(pedal_analysis["issues"])

        return errors

    # Funções auxiliares para encontrar pontos-chave (reutilizadas da classe de comparação)
    def _find_key_points(self, points: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Identifica pontos-chave (frenagem, ápice, aceleração)."""
        return {
            'braking': self._find_braking_points(points),
            'apex': self._find_apex_points(points),
            'acceleration': self._find_acceleration_points(points)
        }

    def _find_braking_points(self, points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identifica pontos de frenagem significativos."""
        braking_points = []
        if len(points) < 3 or 'brake' not in points[0]: return braking_points
        for i in range(1, len(points) - 1):
            if points[i].get('brake', 0) > 0.5 and points[i]['brake'] > points[i-1].get('brake', 0) and points[i]['brake'] >= points[i+1].get('brake', 0):
                braking_points.append({'index': i, 'position': points[i]['position'], 'time': points[i]['time'], 'distance': points[i].get('distance', 0), 'speed': points[i]['speed'], 'brake': points[i]['brake'], 'throttle': points[i].get('throttle', 0)})
        filtered_points = []
        min_distance = 50
        for i, point in enumerate(braking_points):
            if i == 0 or self._calculate_distance(point['position'], filtered_points[-1]['position']) > min_distance:
                filtered_points.append(point)
        return filtered_points

    def _find_apex_points(self, points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identifica pontos de ápice (menor velocidade em curvas)."""
        apex_points = []
        if len(points) < 3: return apex_points
        for i in range(1, len(points) - 1):
            if points[i]['speed'] < points[i-1]['speed'] and points[i]['speed'] <= points[i+1]['speed']:
                if points[i-1]['speed'] - points[i]['speed'] > 10:
                    apex_points.append({'index': i, 'position': points[i]['position'], 'time': points[i]['time'], 'distance': points[i].get('distance', 0), 'speed': points[i]['speed'], 'brake': points[i].get('brake', 0), 'throttle': points[i].get('throttle', 0)})
        filtered_points = []
        min_distance = 30
        for i, point in enumerate(apex_points):
            if i == 0 or self._calculate_distance(point['position'], filtered_points[-1]['position']) > min_distance:
                filtered_points.append(point)
        return filtered_points

    def _find_acceleration_points(self, points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identifica pontos de aceleração significativos."""
        acceleration_points = []
        if len(points) < 3 or 'throttle' not in points[0]: return acceleration_points
        for i in range(1, len(points) - 1):
            if points[i].get('throttle', 0) > 0.7 and points[i]['throttle'] > points[i-1].get('throttle', 0) and points[i]['throttle'] <= points[i+1].get('throttle', 0):
                if points[i-1].get('brake', 0) > 0.1:
                    acceleration_points.append({'index': i, 'position': points[i]['position'], 'time': points[i]['time'], 'distance': points[i].get('distance', 0), 'speed': points[i]['speed'], 'brake': points[i].get('brake', 0), 'throttle': points[i]['throttle']})
        filtered_points = []
        min_distance = 50
        for i, point in enumerate(acceleration_points):
            if i == 0 or self._calculate_distance(point['position'], filtered_points[-1]['position']) > min_distance:
                filtered_points.append(point)
        return filtered_points

    def _calculate_distance(self, pos1: List[float], pos2: List[float]) -> float:
        """Calcula a distância euclidiana entre dois pontos."""
        return np.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
