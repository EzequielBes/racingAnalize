"""
Gerenciador de captura de telemetria para o Race Telemetry Analyzer.
Coordena a captura de dados de diferentes simuladores.
"""

import os
import sys
import json
import time
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

# Configuração de logging
logger = logging.getLogger("race_telemetry_api")
logger.setLevel(logging.INFO)

# Handler para console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Tenta importar os módulos de captura específicos
try:
    from src.data_capture.acc_shared_memory import ACCTelemetryCapture
    acc_available = True
except ImportError:
    acc_available = False
    logger.warning("Módulo de captura ACC não encontrado.")

try:
    from src.data_capture.lmu_plugin import LMUTelemetryCapture
    lmu_available = True
except ImportError:
    lmu_available = False
    logger.warning("Módulo de captura LMU não encontrado.")

# Se nenhum módulo de captura estiver disponível, avisa
if not acc_available and not lmu_available:
    logger.warning("Módulos de captura e processamento não encontrados. Usando stubs.")


class CaptureManager:
    """Gerenciador de captura de telemetria."""
    
    def __init__(self):
        """Inicializa o gerenciador de captura."""
        self.simulator = None
        self.capture_module = None
        self.is_capturing = False
        self.start_time = None
        self.telemetry_data = {
            "session": {},
            "laps": []
        }
        
        logger.info("Gerenciador de captura inicializado.")
    
    def connect(self, simulator_name: str) -> bool:
        """
        Conecta ao simulador especificado.
        
        Args:
            simulator_name: Nome do simulador
            
        Returns:
            True se a conexão foi bem-sucedida, False caso contrário
        """
        logger.info(f"Tentando conectar ao simulador: {simulator_name}")
        
        # Verifica se já está conectado
        if self.simulator:
            logger.warning(f"Já conectado ao simulador: {self.simulator}")
            return False
        
        # Seleciona o módulo de captura apropriado
        if simulator_name == "Assetto Corsa Competizione":
            if acc_available:
                try:
                    self.capture_module = ACCTelemetryCapture()
                    success = self.capture_module.connect()
                    
                    if success:
                        self.simulator = simulator_name
                        logger.info(f"Conectado com sucesso ao {simulator_name}")
                        return True
                    else:
                        logger.error(f"Falha ao conectar ao {simulator_name}")
                        self.capture_module = None
                        return False
                except Exception as e:
                    logger.error(f"Erro ao conectar ao {simulator_name}: {str(e)}")
                    self.capture_module = None
                    return False
            else:
                logger.warning(f"Módulo de captura para {simulator_name} não disponível.")
                # Modo de demonstração
                self.simulator = simulator_name
                logger.info(f"Usando modo de demonstração para {simulator_name}")
                return True
        
        elif simulator_name == "Le Mans Ultimate":
            if lmu_available:
                try:
                    self.capture_module = LMUTelemetryCapture()
                    success = self.capture_module.connect()
                    
                    if success:
                        self.simulator = simulator_name
                        logger.info(f"Conectado com sucesso ao {simulator_name}")
                        return True
                    else:
                        logger.error(f"Falha ao conectar ao {simulator_name}")
                        self.capture_module = None
                        return False
                except Exception as e:
                    logger.error(f"Erro ao conectar ao {simulator_name}: {str(e)}")
                    self.capture_module = None
                    return False
            else:
                logger.warning(f"Módulo de captura para {simulator_name} não disponível.")
                # Modo de demonstração
                self.simulator = simulator_name
                logger.info(f"Usando modo de demonstração para {simulator_name}")
                return True
        
        else:
            logger.error(f"Simulador não suportado: {simulator_name}")
            return False
    
    def disconnect(self) -> bool:
        """
        Desconecta do simulador atual.
        
        Returns:
            True se a desconexão foi bem-sucedida, False caso contrário
        """
        logger.info("Tentando desconectar do simulador")
        
        # Verifica se está conectado
        if not self.simulator:
            logger.warning("Não está conectado a nenhum simulador")
            return False
        
        # Para a captura se estiver ativa
        if self.is_capturing:
            self.stop_capture()
        
        # Desconecta do simulador
        if self.capture_module:
            try:
                success = self.capture_module.disconnect()
                
                if success:
                    logger.info(f"Desconectado com sucesso do {self.simulator}")
                else:
                    logger.error(f"Falha ao desconectar do {self.simulator}")
                    return False
            except Exception as e:
                logger.error(f"Erro ao desconectar do {self.simulator}: {str(e)}")
                return False
            finally:
                self.capture_module = None
        
        # Limpa o estado
        self.simulator = None
        self.telemetry_data = {
            "session": {},
            "laps": []
        }
        
        return True
    
    def start_capture(self) -> bool:
        """
        Inicia a captura de telemetria.
        
        Returns:
            True se a captura foi iniciada com sucesso, False caso contrário
        """
        logger.info("Tentando iniciar captura de telemetria")
        
        # Verifica se está conectado
        if not self.simulator:
            logger.error("Não está conectado a nenhum simulador")
            return False
        
        # Verifica se já está capturando
        if self.is_capturing:
            logger.warning("Já está capturando telemetria")
            return False
        
        # Inicia a captura
        if self.capture_module:
            try:
                success = self.capture_module.start_capture()
                
                if success:
                    self.is_capturing = True
                    self.start_time = time.time()
                    logger.info("Captura de telemetria iniciada com sucesso")
                    return True
                else:
                    logger.error("Falha ao iniciar captura de telemetria")
                    return False
            except Exception as e:
                logger.error(f"Erro ao iniciar captura de telemetria: {str(e)}")
                return False
        else:
            # Modo de demonstração
            self.is_capturing = True
            self.start_time = time.time()
            logger.info("Captura de telemetria iniciada em modo de demonstração")
            return True
    
    def stop_capture(self) -> bool:
        """
        Para a captura de telemetria.
        
        Returns:
            True se a captura foi parada com sucesso, False caso contrário
        """
        logger.info("Tentando parar captura de telemetria")
        
        # Verifica se está capturando
        if not self.is_capturing:
            logger.warning("Não está capturando telemetria")
            return False
        
        # Para a captura
        if self.capture_module:
            try:
                success = self.capture_module.stop_capture()
                
                if success:
                    logger.info("Captura de telemetria parada com sucesso")
                else:
                    logger.error("Falha ao parar captura de telemetria")
                    return False
            except Exception as e:
                logger.error(f"Erro ao parar captura de telemetria: {str(e)}")
                return False
        
        # Atualiza o estado
        self.is_capturing = False
        self.start_time = None
        
        # Salva os dados capturados
        self._save_telemetry_data()
        
        return True
    
    def get_telemetry_data(self) -> Dict[str, Any]:
        """
        Obtém os dados de telemetria mais recentes.
        
        Returns:
            Dicionário com dados de telemetria
        """
        # Verifica se está capturando
        if not self.is_capturing:
            # Se não estiver capturando, mas houver dados carregados, retorna eles
            if self.telemetry_data and self.telemetry_data.get("laps"):
                return self.telemetry_data
            else:
                logger.warning("Não está capturando telemetria e não há dados carregados")
                return {"session": {}, "laps": []}
        
        # Obtém os dados do módulo de captura
        if self.capture_module:
            try:
                new_data = self.capture_module.get_telemetry_data()
                
                if new_data:
                    # Atualiza os dados
                    self._update_telemetry_data(new_data)
            except Exception as e:
                logger.error(f"Erro ao obter dados de telemetria: {str(e)}")
        else:
            # Modo de demonstração
            self._update_demo_telemetry_data()
        
        return self.telemetry_data
    
    def import_telemetry(self, file_path: str) -> bool:
        """
        Importa dados de telemetria de um arquivo JSON.
        
        Args:
            file_path: Caminho para o arquivo JSON
            
        Returns:
            True se a importação foi bem-sucedida, False caso contrário
        """
        logger.info(f"Tentando importar telemetria do arquivo: {file_path}")
        
        try:
            # Carrega o arquivo
            with open(file_path, "r") as f:
                imported_data = json.load(f)
            
            # Verifica se os dados são válidos
            if not isinstance(imported_data, dict) or "session" not in imported_data or "laps" not in imported_data:
                raise ValueError("Formato de arquivo de telemetria inválido")
            
            # Para a captura se estiver ativa
            if self.is_capturing:
                self.stop_capture()
            
            # Desconecta se estiver conectado
            if self.simulator:
                self.disconnect()
            
            # Atualiza os dados de telemetria
            self.telemetry_data = imported_data
            
            # Define um simulador genérico para indicar dados importados
            self.simulator = "Importado"
            
            logger.info(f"Telemetria importada com sucesso de {file_path}")
            return True
        
        except FileNotFoundError:
            logger.error(f"Arquivo de telemetria não encontrado: {file_path}")
            return False
        except json.JSONDecodeError:
            logger.error(f"Erro ao decodificar JSON do arquivo: {file_path}")
            return False
        except ValueError as e:
            logger.error(f"Erro ao importar telemetria: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao importar telemetria: {str(e)}")
            return False
    
    def _update_telemetry_data(self, new_data: Dict[str, Any]):
        """
        Atualiza os dados de telemetria com novos dados.
        
        Args:
            new_data: Novos dados de telemetria
        """
        # Atualiza informações da sessão
        if "session" in new_data:
            self.telemetry_data["session"] = new_data["session"]
        
        # Atualiza voltas
        if "laps" in new_data:
            # Verifica se há novas voltas
            for new_lap in new_data["laps"]:
                lap_number = new_lap.get("lap_number", 0)
                
                # Verifica se a volta já existe
                existing_lap = next(
                    (lap for lap in self.telemetry_data["laps"] if lap.get("lap_number") == lap_number),
                    None
                )
                
                if existing_lap:
                    # Atualiza a volta existente
                    existing_lap.update(new_lap)
                else:
                    # Adiciona a nova volta
                    self.telemetry_data["laps"].append(new_lap)
    
    def _update_demo_telemetry_data(self):
        """Atualiza os dados de telemetria no modo de demonstração."""
        import random
        import math
        
        # Se não houver dados de sessão, cria
        if not self.telemetry_data["session"]:
            self.telemetry_data["session"] = {
                "track": "Monza",
                "car": "Ford Mustang GT3",
                "conditions": "Ensolarado",
                "temperature": {
                    "air": 25,
                    "track": 30
                }
            }
        
        # Simula uma nova volta a cada 30 segundos
        if self.start_time is None:
            self.start_time = time.time()
            
        elapsed_time = time.time() - self.start_time
        if elapsed_time > 0 and elapsed_time % 30 < 1 and len(self.telemetry_data["laps"]) < 10:
            # Número da volta
            lap_num = len(self.telemetry_data["laps"]) + 1
            
            # Tempo base da volta (1:50.000)
            base_time = 110.0
            
            # Variação aleatória
            variation = random.uniform(-2.0, 2.0)
            lap_time = base_time + variation
            
            # Setores
            sector1 = lap_time / 3 + random.uniform(-0.5, 0.5)
            sector2 = lap_time / 3 + random.uniform(-0.5, 0.5)
            sector3 = lap_time - sector1 - sector2
            
            # Pontos de dados
            data_points = []
            
            # Gera pontos ao longo da volta
            num_points = 1000
            for i in range(num_points):
                # Progresso na volta (0 a 1)
                progress = i / num_points
                
                # Distância percorrida
                distance = progress * 5800  # Comprimento aproximado de Monza
                
                # Posição (simplificada para um círculo)
                angle = progress * 2 * math.pi
                x = 1000 * math.cos(angle)
                y = 500 * math.sin(angle)
                
                # Velocidade (varia ao longo da volta)
                speed_factor = 1.0 + 0.2 * math.sin(progress * 2 * math.pi * 4)
                speed = 200 * speed_factor  # Velocidade média de 200 km/h
                
                # RPM
                rpm = 5000 + 3000 * speed_factor
                
                # Marcha
                gear = min(6, max(1, int(speed / 50) + 1))
                
                # Pedais
                throttle = 0.8 + 0.2 * math.sin(progress * 2 * math.pi * 8)
                brake = max(0, 0.5 - throttle)
                
                # Ponto de dados
                data_point = {
                    "time": progress * lap_time,
                    "distance": distance,
                    "position": [x, y],
                    "speed": speed,
                    "rpm": rpm,
                    "gear": gear,
                    "throttle": throttle,
                    "brake": brake
                }
                
                data_points.append(data_point)
            
            # Volta
            lap = {
                "lap_number": lap_num,
                "lap_time": lap_time,
                "sectors": [
                    {"sector": 1, "time": sector1},
                    {"sector": 2, "time": sector2},
                    {"sector": 3, "time": sector3}
                ],
                "data_points": data_points
            }
            
            # Adiciona a volta
            self.telemetry_data["laps"].append(lap)
    
    def _save_telemetry_data(self):
        """Salva os dados de telemetria capturados."""
        if not self.telemetry_data["laps"]:
            logger.warning("Nenhum dado de telemetria para salvar")
            return
        
        try:
            # Diretório de dados do usuário
            user_data_dir = os.path.join(os.path.expanduser("~"), "RaceTelemetryAnalyzer")
            telemetry_dir = os.path.join(user_data_dir, "telemetry")
            
            # Cria o diretório se não existir
            os.makedirs(telemetry_dir, exist_ok=True)
            
            # Nome do arquivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            simulator = self.simulator.replace(" ", "_").lower() if self.simulator else "unknown"
            
            file_name = f"telemetry_{simulator}_{timestamp}.json"
            file_path = os.path.join(telemetry_dir, file_name)
            
            # Salva os dados
            with open(file_path, "w") as f:
                json.dump(self.telemetry_data, f, indent=2)
            
            logger.info(f"Dados de telemetria salvos em: {file_path}")
        except Exception as e:
            logger.error(f"Erro ao salvar dados de telemetria: {str(e)}")

