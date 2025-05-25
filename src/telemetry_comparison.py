"""
Módulo de comparação de telemetria para o Race Telemetry Analyzer.
Responsável por comparar dados de telemetria entre diferentes voltas e identificar pontos de melhoria.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
from scipy.interpolate import interp1d
from scipy.spatial.distance import cdist


class TelemetryComparison:
    """Classe principal para comparação de dados de telemetria."""
    
    def __init__(self):
        """Inicializa o comparador de telemetria."""
        self.comparison_methods = {
            'distance': self._compare_by_distance,
            'time': self._compare_by_time,
            'position': self._compare_by_position
        }
    
    def compare_laps(self, reference_lap: Dict[str, Any], comparison_lap: Dict[str, Any], 
                     method: str = 'distance') -> Dict[str, Any]:
        """
        Compara duas voltas e identifica diferenças e pontos de melhoria.
        
        Args:
            reference_lap: Dicionário com dados da volta de referência
            comparison_lap: Dicionário com dados da volta a ser comparada
            method: Método de comparação ('distance', 'time', 'position')
            
        Returns:
            Dicionário com os resultados da comparação
        """
        if method not in self.comparison_methods:
            raise ValueError(f"Método de comparação não suportado: {method}")
        
        compare_func = self.comparison_methods[method]
        return compare_func(reference_lap, comparison_lap)
    
    def _compare_by_distance(self, reference_lap: Dict[str, Any], comparison_lap: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compara voltas usando a distância percorrida como referência.
        
        Args:
            reference_lap: Dicionário com dados da volta de referência
            comparison_lap: Dicionário com dados da volta a ser comparada
            
        Returns:
            Dicionário com os resultados da comparação
        """
        # Extrai os pontos de dados
        ref_points = reference_lap['data_points']
        comp_points = comparison_lap['data_points']
        
        # Verifica se há pontos suficientes para comparação
        if len(ref_points) < 10 or len(comp_points) < 10:
            raise ValueError("Dados insuficientes para comparação")
        
        # Extrai distâncias e tempos
        ref_distances = [p['distance'] for p in ref_points]
        ref_times = [p['time'] for p in ref_points]
        comp_distances = [p['distance'] for p in comp_points]
        comp_times = [p['time'] for p in comp_points]
        
        # Normaliza as distâncias para 0-1
        max_ref_dist = max(ref_distances)
        max_comp_dist = max(comp_distances)
        norm_ref_dist = [d / max_ref_dist for d in ref_distances]
        norm_comp_dist = [d / max_comp_dist for d in comp_distances]
        
        # Cria interpoladores para os tempos
        ref_time_interp = interp1d(norm_ref_dist, ref_times, kind='linear', bounds_error=False, fill_value='extrapolate')
        comp_time_interp = interp1d(norm_comp_dist, comp_times, kind='linear', bounds_error=False, fill_value='extrapolate')
        
        # Cria pontos de amostragem uniformes
        sample_points = np.linspace(0, 1, 1000)
        
        # Interpola os tempos nos pontos de amostragem
        ref_times_sampled = ref_time_interp(sample_points)
        comp_times_sampled = comp_time_interp(sample_points)
        
        # Calcula o delta de tempo (positivo significa que a volta de comparação é mais lenta)
        delta_times = comp_times_sampled - ref_times_sampled
        
        # Calcula o delta cumulativo
        delta_cumulative = np.zeros_like(delta_times)
        for i in range(1, len(delta_times)):
            delta_cumulative[i] = delta_cumulative[i-1] + (delta_times[i] - delta_times[i-1])
        
        # Identifica pontos de ganho e perda significativos
        threshold = 0.05  # 50ms como limiar para considerar ganho/perda significativo
        gain_points = []
        loss_points = []
        
        for i in range(1, len(delta_times) - 1):
            # Verifica se há uma mudança significativa na derivada do delta
            delta_derivative = delta_times[i+1] - delta_times[i-1]
            
            if delta_derivative < -threshold:  # Ganho de tempo
                # Encontra o ponto de dados mais próximo
                dist_val = sample_points[i] * max_ref_dist
                closest_idx = self._find_closest_point_by_distance(ref_points, dist_val)
                
                if closest_idx is not None:
                    gain_points.append({
                        'position': ref_points[closest_idx]['position'],
                        'distance': dist_val,
                        'delta': delta_times[i],
                        'delta_derivative': delta_derivative,
                        'speed_ref': ref_points[closest_idx]['speed'],
                        'speed_comp': self._interpolate_value_at_distance(comp_points, 'speed', dist_val / max_comp_dist * max_ref_dist),
                        'type': 'gain'
                    })
            
            elif delta_derivative > threshold:  # Perda de tempo
                # Encontra o ponto de dados mais próximo
                dist_val = sample_points[i] * max_ref_dist
                closest_idx = self._find_closest_point_by_distance(ref_points, dist_val)
                
                if closest_idx is not None:
                    loss_points.append({
                        'position': ref_points[closest_idx]['position'],
                        'distance': dist_val,
                        'delta': delta_times[i],
                        'delta_derivative': delta_derivative,
                        'speed_ref': ref_points[closest_idx]['speed'],
                        'speed_comp': self._interpolate_value_at_distance(comp_points, 'speed', dist_val / max_comp_dist * max_ref_dist),
                        'type': 'loss'
                    })
        
        # Analisa os setores
        sector_analysis = self._analyze_sectors(reference_lap, comparison_lap)
        
        # Identifica pontos-chave (frenagem, ápice, aceleração)
        key_points = self._identify_key_points(reference_lap, comparison_lap)
        
        # Prepara o resultado da comparação
        comparison_result = {
            'reference_lap': reference_lap['lap_number'],
            'comparison_lap': comparison_lap['lap_number'],
            'time_delta': comparison_lap['lap_time'] - reference_lap['lap_time'],
            'sectors': sector_analysis,
            'delta_samples': {
                'distance': [d * max_ref_dist for d in sample_points],
                'delta': delta_times.tolist(),
                'cumulative_delta': delta_cumulative.tolist()
            },
            'key_differences': {
                'gain_points': gain_points,
                'loss_points': loss_points,
                'key_points': key_points
            },
            'improvement_suggestions': self._generate_improvement_suggestions(gain_points, loss_points, key_points)
        }
        
        return comparison_result
    
    def _compare_by_time(self, reference_lap: Dict[str, Any], comparison_lap: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compara voltas usando o tempo como referência.
        
        Args:
            reference_lap: Dicionário com dados da volta de referência
            comparison_lap: Dicionário com dados da volta a ser comparada
            
        Returns:
            Dicionário com os resultados da comparação
        """
        # Extrai os pontos de dados
        ref_points = reference_lap['data_points']
        comp_points = comparison_lap['data_points']
        
        # Verifica se há pontos suficientes para comparação
        if len(ref_points) < 10 or len(comp_points) < 10:
            raise ValueError("Dados insuficientes para comparação")
        
        # Extrai tempos
        ref_times = [p['time'] for p in ref_points]
        comp_times = [p['time'] for p in comp_points]
        
        # Normaliza os tempos para 0-1
        max_ref_time = max(ref_times)
        max_comp_time = max(comp_times)
        norm_ref_time = [t / max_ref_time for t in ref_times]
        norm_comp_time = [t / max_comp_time for t in comp_times]
        
        # Cria interpoladores para as posições e outras métricas
        ref_pos_x = [p['position'][0] for p in ref_points]
        ref_pos_y = [p['position'][1] for p in ref_points]
        comp_pos_x = [p['position'][0] for p in comp_points]
        comp_pos_y = [p['position'][1] for p in comp_points]
        
        ref_pos_x_interp = interp1d(norm_ref_time, ref_pos_x, kind='linear', bounds_error=False, fill_value='extrapolate')
        ref_pos_y_interp = interp1d(norm_ref_time, ref_pos_y, kind='linear', bounds_error=False, fill_value='extrapolate')
        comp_pos_x_interp = interp1d(norm_comp_time, comp_pos_x, kind='linear', bounds_error=False, fill_value='extrapolate')
        comp_pos_y_interp = interp1d(norm_comp_time, comp_pos_y, kind='linear', bounds_error=False, fill_value='extrapolate')
        
        # Cria pontos de amostragem uniformes
        sample_points = np.linspace(0, 1, 1000)
        
        # Interpola as posições nos pontos de amostragem
        ref_pos_x_sampled = ref_pos_x_interp(sample_points)
        ref_pos_y_sampled = ref_pos_y_interp(sample_points)
        comp_pos_x_sampled = comp_pos_x_interp(sample_points)
        comp_pos_y_sampled = comp_pos_y_interp(sample_points)
        
        # Calcula as diferenças de trajetória
        trajectory_diff = np.sqrt((ref_pos_x_sampled - comp_pos_x_sampled)**2 + 
                                 (ref_pos_y_sampled - comp_pos_y_sampled)**2)
        
        # Identifica pontos com diferenças significativas de trajetória
        threshold = np.percentile(trajectory_diff, 90)  # 10% mais significativos
        significant_diff_indices = np.where(trajectory_diff > threshold)[0]
        
        trajectory_differences = []
        for idx in significant_diff_indices:
            time_val = sample_points[idx] * max_ref_time
            trajectory_differences.append({
                'time': time_val,
                'position_ref': [ref_pos_x_sampled[idx], ref_pos_y_sampled[idx]],
                'position_comp': [comp_pos_x_sampled[idx], comp_pos_y_sampled[idx]],
                'difference': trajectory_diff[idx]
            })
        
        # Analisa os setores
        sector_analysis = self._analyze_sectors(reference_lap, comparison_lap)
        
        # Identifica pontos-chave (frenagem, ápice, aceleração)
        key_points = self._identify_key_points(reference_lap, comparison_lap)
        
        # Prepara o resultado da comparação
        comparison_result = {
            'reference_lap': reference_lap['lap_number'],
            'comparison_lap': comparison_lap['lap_number'],
            'time_delta': comparison_lap['lap_time'] - reference_lap['lap_time'],
            'sectors': sector_analysis,
            'trajectory_samples': {
                'time': [t * max_ref_time for t in sample_points],
                'ref_x': ref_pos_x_sampled.tolist(),
                'ref_y': ref_pos_y_sampled.tolist(),
                'comp_x': comp_pos_x_sampled.tolist(),
                'comp_y': comp_pos_y_sampled.tolist(),
                'difference': trajectory_diff.tolist()
            },
            'key_differences': {
                'trajectory_differences': trajectory_differences,
                'key_points': key_points
            },
            'improvement_suggestions': self._generate_improvement_suggestions_by_trajectory(
                trajectory_differences, key_points)
        }
        
        return comparison_result
    
    def _compare_by_position(self, reference_lap: Dict[str, Any], comparison_lap: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compara voltas usando a posição na pista como referência.
        
        Args:
            reference_lap: Dicionário com dados da volta de referência
            comparison_lap: Dicionário com dados da volta a ser comparada
            
        Returns:
            Dicionário com os resultados da comparação
        """
        # Extrai os pontos de dados
        ref_points = reference_lap['data_points']
        comp_points = comparison_lap['data_points']
        
        # Verifica se há pontos suficientes para comparação
        if len(ref_points) < 10 or len(comp_points) < 10:
            raise ValueError("Dados insuficientes para comparação")
        
        # Extrai posições
        ref_positions = np.array([[p['position'][0], p['position'][1]] for p in ref_points])
        comp_positions = np.array([[p['position'][0], p['position'][1]] for p in comp_points])
        
        # Para cada ponto na volta de referência, encontra o ponto mais próximo na volta de comparação
        distances = cdist(ref_positions, comp_positions)
        closest_comp_indices = np.argmin(distances, axis=1)
        
        # Compara métricas nos pontos correspondentes
        speed_diffs = []
        brake_diffs = []
        throttle_diffs = []
        line_diffs = []
        
        for i, comp_idx in enumerate(closest_comp_indices):
            ref_point = ref_points[i]
            comp_point = comp_points[comp_idx]
            
            # Diferença de velocidade
            speed_diff = comp_point['speed'] - ref_point['speed']
            speed_diffs.append({
                'position': ref_point['position'],
                'ref_speed': ref_point['speed'],
                'comp_speed': comp_point['speed'],
                'difference': speed_diff
            })
            
            # Diferença de frenagem
            if 'brake' in ref_point and 'brake' in comp_point:
                brake_diff = comp_point['brake'] - ref_point['brake']
                brake_diffs.append({
                    'position': ref_point['position'],
                    'ref_brake': ref_point['brake'],
                    'comp_brake': comp_point['brake'],
                    'difference': brake_diff
                })
            
            # Diferença de aceleração
            if 'throttle' in ref_point and 'throttle' in comp_point:
                throttle_diff = comp_point['throttle'] - ref_point['throttle']
                throttle_diffs.append({
                    'position': ref_point['position'],
                    'ref_throttle': ref_point['throttle'],
                    'comp_throttle': comp_point['throttle'],
                    'difference': throttle_diff
                })
            
            # Diferença de trajetória (distância entre os pontos)
            line_diff = distances[i, comp_idx]
            line_diffs.append({
                'position': ref_point['position'],
                'ref_position': ref_point['position'],
                'comp_position': comp_point['position'],
                'difference': float(line_diff)
            })
        
        # Identifica pontos com diferenças significativas
        speed_threshold = np.percentile([abs(d['difference']) for d in speed_diffs], 90)
        significant_speed_diffs = [d for d in speed_diffs if abs(d['difference']) > speed_threshold]
        
        line_threshold = np.percentile([d['difference'] for d in line_diffs], 90)
        significant_line_diffs = [d for d in line_diffs if d['difference'] > line_threshold]
        
        # Analisa os setores
        sector_analysis = self._analyze_sectors(reference_lap, comparison_lap)
        
        # Prepara o resultado da comparação
        comparison_result = {
            'reference_lap': reference_lap['lap_number'],
            'comparison_lap': comparison_lap['lap_number'],
            'time_delta': comparison_lap['lap_time'] - reference_lap['lap_time'],
            'sectors': sector_analysis,
            'key_differences': {
                'speed_differences': significant_speed_diffs,
                'line_differences': significant_line_diffs
            },
            'improvement_suggestions': self._generate_improvement_suggestions_by_metrics(
                significant_speed_diffs, significant_line_diffs, brake_diffs, throttle_diffs)
        }
        
        return comparison_result
    
    def _analyze_sectors(self, reference_lap: Dict[str, Any], comparison_lap: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analisa as diferenças por setor entre duas voltas.
        
        Args:
            reference_lap: Dicionário com dados da volta de referência
            comparison_lap: Dicionário com dados da volta a ser comparada
            
        Returns:
            Lista de dicionários com análise por setor
        """
        # Verifica se há dados de setores
        if 'sectors' not in reference_lap or 'sectors' not in comparison_lap:
            return []
        
        ref_sectors = reference_lap['sectors']
        comp_sectors = comparison_lap['sectors']
        
        # Verifica se o número de setores é compatível
        if len(ref_sectors) != len(comp_sectors):
            return []
        
        sector_analysis = []
        
        for i in range(len(ref_sectors)):
            ref_sector = ref_sectors[i]
            comp_sector = comp_sectors[i]
            
            delta = comp_sector['time'] - ref_sector['time']
            
            sector_analysis.append({
                'sector': ref_sector['sector'],
                'ref_time': ref_sector['time'],
                'comp_time': comp_sector['time'],
                'delta': delta,
                'percentage': (delta / ref_sector['time']) * 100 if ref_sector['time'] > 0 else 0
            })
        
        return sector_analysis
    
    def _identify_key_points(self, reference_lap: Dict[str, Any], comparison_lap: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Identifica e compara pontos-chave entre duas voltas (frenagem, ápice, aceleração).
        
        Args:
            reference_lap: Dicionário com dados da volta de referência
            comparison_lap: Dicionário com dados da volta a ser comparada
            
        Returns:
            Dicionário com listas de pontos-chave e suas diferenças
        """
        # Extrai os pontos de dados
        ref_points = reference_lap['data_points']
        comp_points = comparison_lap['data_points']
        
        # Identifica pontos de frenagem na volta de referência
        ref_braking_points = self._find_braking_points(ref_points)
        comp_braking_points = self._find_braking_points(comp_points)
        
        # Identifica pontos de ápice na volta de referência
        ref_apex_points = self._find_apex_points(ref_points)
        comp_apex_points = self._find_apex_points(comp_points)
        
        # Identifica pontos de aceleração na volta de referência
        ref_acceleration_points = self._find_acceleration_points(ref_points)
        comp_acceleration_points = self._find_acceleration_points(comp_points)
        
        # Compara os pontos de frenagem
        braking_comparison = self._compare_key_points(ref_braking_points, comp_braking_points, 'braking')
        
        # Compara os pontos de ápice
        apex_comparison = self._compare_key_points(ref_apex_points, comp_apex_points, 'apex')
        
        # Compara os pontos de aceleração
        acceleration_comparison = self._compare_key_points(ref_acceleration_points, comp_acceleration_points, 'acceleration')
        
        return {
            'braking': braking_comparison,
            'apex': apex_comparison,
            'acceleration': acceleration_comparison
        }
    
    def _find_braking_points(self, points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identifica pontos de frenagem significativos.
        
        Args:
            points: Lista de pontos de dados
            
        Returns:
            Lista de pontos de frenagem
        """
        braking_points = []
        
        # Verifica se há dados de frenagem
        if len(points) < 3 or 'brake' not in points[0]:
            return braking_points
        
        # Encontra pontos onde a frenagem começa a aumentar significativamente
        for i in range(1, len(points) - 1):
            prev_brake = points[i-1].get('brake', 0)
            curr_brake = points[i].get('brake', 0)
            next_brake = points[i+1].get('brake', 0)
            
            # Detecta início de frenagem forte
            if curr_brake > 0.5 and curr_brake > prev_brake and curr_brake >= next_brake:
                braking_points.append({
                    'index': i,
                    'position': points[i]['position'],
                    'time': points[i]['time'],
                    'distance': points[i].get('distance', 0),
                    'speed': points[i]['speed'],
                    'brake': curr_brake,
                    'throttle': points[i].get('throttle', 0)
                })
        
        # Filtra pontos muito próximos
        filtered_points = []
        min_distance = 50  # Distância mínima entre pontos de frenagem
        
        for i, point in enumerate(braking_points):
            if i == 0 or self._calculate_distance(point['position'], filtered_points[-1]['position']) > min_distance:
                filtered_points.append(point)
        
        return filtered_points
    
    def _find_apex_points(self, points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identifica pontos de ápice (menor velocidade em curvas).
        
        Args:
            points: Lista de pontos de dados
            
        Returns:
            Lista de pontos de ápice
        """
        apex_points = []
        
        if len(points) < 3:
            return apex_points
        
        # Encontra pontos de velocidade mínima local
        for i in range(1, len(points) - 1):
            prev_speed = points[i-1]['speed']
            curr_speed = points[i]['speed']
            next_speed = points[i+1]['speed']
            
            # Detecta mínimo local de velocidade
            if curr_speed < prev_speed and curr_speed <= next_speed:
                # Verifica se é uma redução significativa de velocidade
                if prev_speed - curr_speed > 10:  # Pelo menos 10 unidades de velocidade
                    apex_points.append({
                        'index': i,
                        'position': points[i]['position'],
                        'time': points[i]['time'],
                        'distance': points[i].get('distance', 0),
                        'speed': curr_speed,
                        'brake': points[i].get('brake', 0),
                        'throttle': points[i].get('throttle', 0)
                    })
        
        # Filtra pontos muito próximos
        filtered_points = []
        min_distance = 30  # Distância mínima entre pontos de ápice
        
        for i, point in enumerate(apex_points):
            if i == 0 or self._calculate_distance(point['position'], filtered_points[-1]['position']) > min_distance:
                filtered_points.append(point)
        
        return filtered_points
    
    def _find_acceleration_points(self, points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identifica pontos de aceleração significativos.
        
        Args:
            points: Lista de pontos de dados
            
        Returns:
            Lista de pontos de aceleração
        """
        acceleration_points = []
        
        # Verifica se há dados de aceleração
        if len(points) < 3 or 'throttle' not in points[0]:
            return acceleration_points
        
        # Encontra pontos onde a aceleração começa a aumentar significativamente
        for i in range(1, len(points) - 1):
            prev_throttle = points[i-1].get('throttle', 0)
            curr_throttle = points[i].get('throttle', 0)
            next_throttle = points[i+1].get('throttle', 0)
            
            # Detecta início de aceleração forte após uma curva
            if curr_throttle > 0.7 and curr_throttle > prev_throttle and curr_throttle <= next_throttle:
                # Verifica se havia frenagem antes
                if points[i-1].get('brake', 0) > 0.1:
                    acceleration_points.append({
                        'index': i,
                        'position': points[i]['position'],
                        'time': points[i]['time'],
                        'distance': points[i].get('distance', 0),
                        'speed': points[i]['speed'],
                        'brake': points[i].get('brake', 0),
                        'throttle': curr_throttle
                    })
        
        # Filtra pontos muito próximos
        filtered_points = []
        min_distance = 50  # Distância mínima entre pontos de aceleração
        
        for i, point in enumerate(acceleration_points):
            if i == 0 or self._calculate_distance(point['position'], filtered_points[-1]['position']) > min_distance:
                filtered_points.append(point)
        
        return filtered_points
    
    def _compare_key_points(self, ref_points: List[Dict[str, Any]], comp_points: List[Dict[str, Any]], 
                           point_type: str) -> List[Dict[str, Any]]:
        """
        Compara pontos-chave entre duas voltas.
        
        Args:
            ref_points: Lista de pontos-chave da volta de referência
            comp_points: Lista de pontos-chave da volta de comparação
            point_type: Tipo de ponto ('braking', 'apex', 'acceleration')
            
        Returns:
            Lista de comparações entre pontos-chave
        """
        comparisons = []
        
        # Para cada ponto na volta de referência, encontra o ponto mais próximo na volta de comparação
        for ref_point in ref_points:
            closest_comp_point = None
            min_distance = float('inf')
            
            for comp_point in comp_points:
                dist = self._calculate_distance(ref_point['position'], comp_point['position'])
                if dist < min_distance:
                    min_distance = dist
                    closest_comp_point = comp_point
            
            # Se encontrou um ponto próximo o suficiente
            if closest_comp_point is not None and min_distance < 100:  # Limiar de distância
                comparison = {
                    'type': point_type,
                    'position': ref_point['position'],
                    'ref_time': ref_point['time'],
                    'comp_time': closest_comp_point['time'],
                    'time_delta': closest_comp_point['time'] - ref_point['time'],
                    'ref_speed': ref_point['speed'],
                    'comp_speed': closest_comp_point['speed'],
                    'speed_delta': closest_comp_point['speed'] - ref_point['speed'],
                    'distance': min_distance
                }
                
                # Adiciona dados específicos por tipo de ponto
                if point_type == 'braking':
                    comparison.update({
                        'ref_brake': ref_point['brake'],
                        'comp_brake': closest_comp_point['brake'],
                        'brake_delta': closest_comp_point['brake'] - ref_point['brake']
                    })
                elif point_type == 'acceleration':
                    comparison.update({
                        'ref_throttle': ref_point['throttle'],
                        'comp_throttle': closest_comp_point['throttle'],
                        'throttle_delta': closest_comp_point['throttle'] - ref_point['throttle']
                    })
                
                comparisons.append(comparison)
        
        return comparisons
    
    def _generate_improvement_suggestions(self, gain_points: List[Dict[str, Any]], 
                                         loss_points: List[Dict[str, Any]],
                                         key_points: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Gera sugestões de melhoria com base nos pontos de ganho/perda e pontos-chave.
        
        Args:
            gain_points: Lista de pontos onde houve ganho de tempo
            loss_points: Lista de pontos onde houve perda de tempo
            key_points: Dicionário com pontos-chave comparados
            
        Returns:
            Lista de sugestões de melhoria
        """
        suggestions = []
        
        # Analisa pontos de perda significativos
        for point in sorted(loss_points, key=lambda x: x['delta_derivative'], reverse=True)[:5]:
            suggestion = {
                'position': point['position'],
                'type': 'loss',
                'severity': 'high' if point['delta_derivative'] > 0.1 else 'medium',
                'description': f"Perda de tempo significativa ({point['delta']:.3f}s)",
                'suggestion': "Analise sua trajetória e ponto de frenagem nesta área"
            }
            suggestions.append(suggestion)
        
        # Analisa pontos-chave de frenagem
        for point in key_points.get('braking', []):
            if point['time_delta'] > 0.05:  # Perdeu tempo na frenagem
                suggestion = {
                    'position': point['position'],
                    'type': 'braking',
                    'severity': 'high' if point['time_delta'] > 0.1 else 'medium',
                    'description': f"Frenagem tardia ou excessiva ({point['time_delta']:.3f}s)",
                    'suggestion': "Tente frear mais cedo e progressivamente"
                }
                suggestions.append(suggestion)
            elif point['time_delta'] < -0.05:  # Ganhou tempo na frenagem
                suggestion = {
                    'position': point['position'],
                    'type': 'braking_good',
                    'severity': 'low',
                    'description': f"Boa frenagem (ganho de {-point['time_delta']:.3f}s)",
                    'suggestion': "Continue com esta técnica de frenagem"
                }
                suggestions.append(suggestion)
        
        # Analisa pontos-chave de ápice
        for point in key_points.get('apex', []):
            if point['speed_delta'] < -5:  # Velocidade menor no ápice
                suggestion = {
                    'position': point['position'],
                    'type': 'apex',
                    'severity': 'medium',
                    'description': f"Velocidade de ápice menor ({point['speed_delta']:.1f} unidades)",
                    'suggestion': "Ajuste sua trajetória para manter mais velocidade no ápice da curva"
                }
                suggestions.append(suggestion)
            elif point['speed_delta'] > 5:  # Velocidade maior no ápice
                suggestion = {
                    'position': point['position'],
                    'type': 'apex_good',
                    'severity': 'low',
                    'description': f"Boa velocidade de ápice (ganho de {point['speed_delta']:.1f} unidades)",
                    'suggestion': "Continue com esta trajetória de curva"
                }
                suggestions.append(suggestion)
        
        # Analisa pontos-chave de aceleração
        for point in key_points.get('acceleration', []):
            if point['time_delta'] > 0.05:  # Perdeu tempo na aceleração
                suggestion = {
                    'position': point['position'],
                    'type': 'acceleration',
                    'severity': 'medium',
                    'description': f"Aceleração tardia ou insuficiente ({point['time_delta']:.3f}s)",
                    'suggestion': "Antecipe a aceleração na saída da curva"
                }
                suggestions.append(suggestion)
        
        return suggestions
    
    def _generate_improvement_suggestions_by_trajectory(self, trajectory_differences: List[Dict[str, Any]],
                                                      key_points: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Gera sugestões de melhoria com base nas diferenças de trajetória.
        
        Args:
            trajectory_differences: Lista de pontos com diferenças significativas de trajetória
            key_points: Dicionário com pontos-chave comparados
            
        Returns:
            Lista de sugestões de melhoria
        """
        suggestions = []
        
        # Analisa diferenças de trajetória significativas
        for point in sorted(trajectory_differences, key=lambda x: x['difference'], reverse=True)[:5]:
            suggestion = {
                'position': point['position_ref'],
                'type': 'trajectory',
                'severity': 'medium',
                'description': f"Diferença significativa de trajetória ({point['difference']:.1f} unidades)",
                'suggestion': "Analise a diferença de linha neste ponto"
            }
            suggestions.append(suggestion)
        
        # Adiciona sugestões dos pontos-chave
        for point in key_points.get('braking', []):
            if point['time_delta'] > 0.05:  # Perdeu tempo na frenagem
                suggestion = {
                    'position': point['position'],
                    'type': 'braking',
                    'severity': 'high' if point['time_delta'] > 0.1 else 'medium',
                    'description': f"Frenagem tardia ou excessiva ({point['time_delta']:.3f}s)",
                    'suggestion': "Tente frear mais cedo e progressivamente"
                }
                suggestions.append(suggestion)
        
        for point in key_points.get('apex', []):
            if point['speed_delta'] < -5:  # Velocidade menor no ápice
                suggestion = {
                    'position': point['position'],
                    'type': 'apex',
                    'severity': 'medium',
                    'description': f"Velocidade de ápice menor ({point['speed_delta']:.1f} unidades)",
                    'suggestion': "Ajuste sua trajetória para manter mais velocidade no ápice da curva"
                }
                suggestions.append(suggestion)
        
        return suggestions
    
    def _generate_improvement_suggestions_by_metrics(self, speed_diffs: List[Dict[str, Any]],
                                                   line_diffs: List[Dict[str, Any]],
                                                   brake_diffs: List[Dict[str, Any]],
                                                   throttle_diffs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Gera sugestões de melhoria com base nas diferenças de métricas.
        
        Args:
            speed_diffs: Lista de pontos com diferenças significativas de velocidade
            line_diffs: Lista de pontos com diferenças significativas de trajetória
            brake_diffs: Lista de pontos com diferenças de frenagem
            throttle_diffs: Lista de pontos com diferenças de aceleração
            
        Returns:
            Lista de sugestões de melhoria
        """
        suggestions = []
        
        # Analisa diferenças de velocidade significativas
        for point in sorted(speed_diffs, key=lambda x: x['difference'])[:5]:  # Velocidades menores
            suggestion = {
                'position': point['position'],
                'type': 'speed',
                'severity': 'high' if point['difference'] < -10 else 'medium',
                'description': f"Velocidade significativamente menor ({point['difference']:.1f} unidades)",
                'suggestion': "Analise sua trajetória e técnica para manter mais velocidade neste ponto"
            }
            suggestions.append(suggestion)
        
        # Analisa diferenças de trajetória significativas
        for point in sorted(line_diffs, key=lambda x: x['difference'], reverse=True)[:3]:
            suggestion = {
                'position': point['position'],
                'type': 'line',
                'severity': 'medium',
                'description': f"Diferença significativa de trajetória ({point['difference']:.1f} unidades)",
                'suggestion': "Compare as linhas neste ponto para identificar a trajetória ideal"
            }
            suggestions.append(suggestion)
        
        # Analisa diferenças de frenagem
        if brake_diffs:
            # Encontra pontos onde a frenagem é significativamente diferente
            brake_threshold = 0.2
            for i in range(len(brake_diffs)):
                if abs(brake_diffs[i]['difference']) > brake_threshold:
                    suggestion = {
                        'position': brake_diffs[i]['position'],
                        'type': 'braking',
                        'severity': 'medium',
                        'description': f"Técnica de frenagem diferente ({brake_diffs[i]['difference']:.2f})",
                        'suggestion': "Ajuste a intensidade e timing da frenagem neste ponto"
                    }
                    suggestions.append(suggestion)
        
        # Analisa diferenças de aceleração
        if throttle_diffs:
            # Encontra pontos onde a aceleração é significativamente diferente
            throttle_threshold = 0.2
            for i in range(len(throttle_diffs)):
                if throttle_diffs[i]['difference'] < -throttle_threshold:  # Menos aceleração
                    suggestion = {
                        'position': throttle_diffs[i]['position'],
                        'type': 'acceleration',
                        'severity': 'medium',
                        'description': f"Aceleração mais conservadora ({throttle_diffs[i]['difference']:.2f})",
                        'suggestion': "Seja mais agressivo na aceleração neste ponto"
                    }
                    suggestions.append(suggestion)
        
        return suggestions
    
    def _find_closest_point_by_distance(self, points: List[Dict[str, Any]], target_distance: float) -> Optional[int]:
        """
        Encontra o índice do ponto mais próximo a uma distância específica.
        
        Args:
            points: Lista de pontos de dados
            target_distance: Distância alvo
            
        Returns:
            Índice do ponto mais próximo ou None se não encontrado
        """
        if not points or 'distance' not in points[0]:
            return None
        
        closest_idx = None
        min_diff = float('inf')
        
        for i, point in enumerate(points):
            diff = abs(point['distance'] - target_distance)
            if diff < min_diff:
                min_diff = diff
                closest_idx = i
        
        return closest_idx
    
    def _interpolate_value_at_distance(self, points: List[Dict[str, Any]], value_key: str, 
                                      target_distance: float) -> float:
        """
        Interpola um valor em uma distância específica.
        
        Args:
            points: Lista de pontos de dados
            value_key: Chave do valor a ser interpolado
            target_distance: Distância alvo
            
        Returns:
            Valor interpolado
        """
        if not points or 'distance' not in points[0] or value_key not in points[0]:
            return 0.0
        
        # Encontra os pontos antes e depois da distância alvo
        prev_point = None
        next_point = None
        
        for i, point in enumerate(points):
            if point['distance'] <= target_distance:
                prev_point = point
            else:
                next_point = point
                break
        
        # Se não encontrou pontos adequados, retorna 0
        if prev_point is None or next_point is None:
            return 0.0
        
        # Interpola linearmente
        dist_range = next_point['distance'] - prev_point['distance']
        if dist_range == 0:
            return prev_point[value_key]
        
        t = (target_distance - prev_point['distance']) / dist_range
        return prev_point[value_key] + t * (next_point[value_key] - prev_point[value_key])
    
    def _calculate_distance(self, pos1: List[float], pos2: List[float]) -> float:
        """
        Calcula a distância euclidiana entre dois pontos.
        
        Args:
            pos1: Posição do primeiro ponto [x, y]
            pos2: Posição do segundo ponto [x, y]
            
        Returns:
            Distância entre os pontos
        """
        return np.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
