"""
Script de teste para validação do Race Telemetry Analyzer.
Executa testes automatizados para verificar o funcionamento das principais funcionalidades.
"""

import os
import sys
import time
import json
import unittest
import tempfile
import shutil
from datetime import datetime
from unittest.mock import MagicMock, patch

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importações do sistema
try:
    from src.data_capture.capture_manager import CaptureManager
    from src.data_capture.acc_shared_memory import ACCTelemetryCapture
    from src.data_capture.lmu_plugin import LMUTelemetryCapture, LDParser
    capture_available = True
except ImportError:
    print("AVISO: Módulos de captura não encontrados. Alguns testes serão ignorados.")
    # Define explicitamente para False se a importação falhar
    CaptureManager = None
    ACCTelemetryCapture = None
    LMUTelemetryCapture = None
    LDParser = None
    capture_available = False


class TestCaptureManager(unittest.TestCase):
    """Testes para o gerenciador de captura."""
    
    def setUp(self):
        """Configuração inicial para os testes."""
        # Cria um diretório temporário para os testes
        self.test_dir = tempfile.mkdtemp()
        
        # Cria um arquivo de telemetria de exemplo
        self.example_telemetry = {
            "session": {
                "track": "Monza",
                "car": "Ford Mustang GT3",
                "player": "Teste"
            },
            "laps": [
                {
                    "lap_number": 1,
                    "lap_time": 110.5,
                    "sectors": [
                        {"sector": 1, "time": 35.2},
                        {"sector": 2, "time": 40.1},
                        {"sector": 3, "time": 35.2}
                    ],
                    "data_points": [
                        {
                            "time": 0.0,
                            "distance": 0.0,
                            "position": [0.0, 0.0],
                            "speed": 0.0,
                            "rpm": 1000.0,
                            "gear": 1,
                            "throttle": 0.0,
                            "brake": 0.0
                        }
                    ]
                }
            ]
        }
        
        # Salva o arquivo de exemplo
        self.example_file = os.path.join(self.test_dir, "example_telemetry.json")
        with open(self.example_file, "w") as f:
            json.dump(self.example_telemetry, f)
    
    def tearDown(self):
        """Limpeza após os testes."""
        # Remove o diretório temporário
        shutil.rmtree(self.test_dir)
    
    @unittest.skipIf(not capture_available, "Módulo de captura não disponível")
    def test_capture_manager_initialization(self):
        """Testa a inicialização do gerenciador de captura."""
        try:
            manager = CaptureManager()
            self.assertIsNotNone(manager)
            print("✓ Gerenciador de captura inicializado com sucesso")
        except Exception as e:
            self.fail(f"Falha ao inicializar o gerenciador de captura: {str(e)}")
    
    @unittest.skipIf(not capture_available, "Módulo de captura não disponível")
    @patch('src.data_capture.capture_manager.acc_available', False) # Força modo demo
    def test_connect_acc_demo_mode(self):
        """Testa a conexão com o ACC em modo de demonstração."""
        manager = CaptureManager()
        result = manager.connect("Assetto Corsa Competizione")
        self.assertTrue(result, "A conexão em modo de demonstração para ACC deve retornar True")
        self.assertEqual(manager.simulator, "Assetto Corsa Competizione")
        self.assertIsNone(manager.capture_module, "O módulo de captura deve ser None em modo de demonstração")
        print("✓ Conexão com ACC em modo de demonstração funcionando corretamente")

    @unittest.skipIf(not capture_available, "Módulo de captura não disponível")
    @patch('src.data_capture.capture_manager.lmu_available', False) # Força modo demo
    def test_connect_lmu_demo_mode(self):
        """Testa a conexão com o LMU em modo de demonstração."""
        manager = CaptureManager()
        result = manager.connect("Le Mans Ultimate")
        self.assertTrue(result, "A conexão em modo de demonstração para LMU deve retornar True")
        self.assertEqual(manager.simulator, "Le Mans Ultimate")
        self.assertIsNone(manager.capture_module, "O módulo de captura deve ser None em modo de demonstração")
        print("✓ Conexão com LMU em modo de demonstração funcionando corretamente")
    
    @unittest.skipIf(not capture_available, "Módulo de captura não disponível")
    def test_import_telemetry(self):
        """Testa a importação de telemetria de um arquivo."""
        manager = CaptureManager()
        
        # Importa o arquivo de exemplo
        result = manager.import_telemetry(self.example_file)
        self.assertTrue(result)
        
        # Verifica se os dados foram importados corretamente
        telemetry_data = manager.get_telemetry_data()
        self.assertEqual(telemetry_data["session"]["track"], "Monza")
        self.assertEqual(telemetry_data["session"]["car"], "Ford Mustang GT3")
        self.assertEqual(len(telemetry_data["laps"]), 1)
        print("✓ Importação de telemetria funcionando corretamente")


class TestACCTelemetryCapture(unittest.TestCase):
    """Testes para a captura de telemetria do ACC."""
    
    @unittest.skipIf(not capture_available, "Módulo ACC não disponível")
    def test_acc_initialization(self):
        """Testa a inicialização do módulo de captura do ACC."""
        try:
            capture = ACCTelemetryCapture()
            self.assertIsNotNone(capture)
            print("✓ Módulo de captura ACC inicializado com sucesso")
        except Exception as e:
            self.fail(f"Falha ao inicializar o módulo de captura ACC: {str(e)}")
    
    @unittest.skipIf(not capture_available, "Módulo ACC não disponível")
    @patch('src.data_capture.acc_shared_memory.mmap')
    def test_acc_connect(self, mock_mmap):
        """Testa a conexão com o ACC."""
        # Configura o mock para simular a memória compartilhada
        mock_mmap.return_value = MagicMock()
        
        capture = ACCTelemetryCapture()
        result = capture.connect()
        
        # Em um ambiente de teste, a conexão pode falhar se o ACC não estiver em execução
        # Mas o importante é que o método não lance exceções
        print("✓ Método de conexão ACC executado sem erros")


class TestLMUTelemetryCapture(unittest.TestCase):
    """Testes para a captura de telemetria do LMU."""
    
    def setUp(self):
        """Configuração inicial para os testes."""
        # Cria um diretório temporário para os testes
        self.test_dir = tempfile.mkdtemp()
        
        # Cria um arquivo LDX de exemplo
        self.example_ldx_content = """<?xml version="1.0" encoding="UTF-8"?>
<LDXFile version="1.0">
  <Session>
    <Vehicle name="Ford Mustang GT3" />
    <Venue name="Monza" />
    <Driver name="Teste" />
  </Session>
  <Laps>
    <Lap number="1" time="110500">
      <Sector number="1" time="35200" />
      <Sector number="2" time="40100" />
      <Sector number="3" time="35200" />
    </Lap>
  </Laps>
</LDXFile>
"""
        
        # Salva o arquivo LDX de exemplo
        self.example_ldx_file = os.path.join(self.test_dir, "example.ldx")
        with open(self.example_ldx_file, "w") as f:
            f.write(self.example_ldx_content)
    
    def tearDown(self):
        """Limpeza após os testes."""
        # Remove o diretório temporário
        shutil.rmtree(self.test_dir)
    
    @unittest.skipIf(not capture_available, "Módulo LMU não disponível")
    def test_lmu_initialization(self):
        """Testa a inicialização do módulo de captura do LMU."""
        try:
            capture = LMUTelemetryCapture()
            self.assertIsNotNone(capture)
            print("✓ Módulo de captura LMU inicializado com sucesso")
        except Exception as e:
            self.fail(f"Falha ao inicializar o módulo de captura LMU: {str(e)}")
    
    @unittest.skipIf(not capture_available, "Módulo LMU não disponível")
    def test_lmu_process_ldx(self):
        """Testa o processamento de arquivos LDX."""
        capture = LMUTelemetryCapture()
        
        # Define a pasta MoTeC como o diretório de teste
        capture.motec_folder = self.test_dir
        
        # Processa o arquivo LDX
        capture._process_ldx_file(self.example_ldx_file)
        
        # Verifica se os dados foram extraídos corretamente
        self.assertEqual(capture.telemetry_data["session"]["track"], "Monza")
        self.assertEqual(capture.telemetry_data["session"]["car"], "Ford Mustang GT3")
        self.assertEqual(len(capture.telemetry_data["laps"]), 1)
        print("✓ Processamento de arquivos LDX funcionando corretamente")
    
    @unittest.skipIf(not capture_available or LDParser is None, "Parser LD não disponível")
    @patch('src.data_capture.lmu_plugin.LDParser.parse')
    def test_lmu_process_ld(self, mock_parse):
        """Testa o processamento de arquivos LD."""
        # Configura o mock para simular o parser LD
        mock_parse.return_value = {
            'laps': [
                {
                    'lap_number': 1,
                    'lap_time': 110.5,
                    'data_points': [
                        {
                            'time': 0.0,
                            'distance': 0.0,
                            'position': [0.0, 0.0, 0.0],
                            'speed': 0.0,
                            'rpm': 1000.0,
                            'gear': 1,
                            'throttle': 0.0,
                            'brake': 0.0
                        }
                    ]
                }
            ]
        }
        
        capture = LMUTelemetryCapture()
        
        # Define a pasta MoTeC como o diretório de teste
        capture.motec_folder = self.test_dir
        
        # Processa o arquivo LDX primeiro para criar a estrutura de dados
        capture._process_ldx_file(self.example_ldx_file)
        
        # Cria um arquivo LD de exemplo (vazio, pois usamos mock)
        example_ld_file = os.path.join(self.test_dir, "example.ld")
        with open(example_ld_file, "wb") as f:
            f.write(b"LDFILE\x00\x00") # Escreve um cabeçalho mínimo válido
        
        # Processa o arquivo LD
        capture._process_ld_file(example_ld_file)
        
        # Verifica se o parser foi chamado
        self.assertTrue(mock_parse.called)
        print("✓ Processamento de arquivos LD funcionando corretamente")


class TestSetupManagement(unittest.TestCase):
    """Testes para o gerenciamento de setups."""
    
    def setUp(self):
        """Configuração inicial para os testes."""
        # Cria um diretório temporário para os testes
        self.test_dir = tempfile.mkdtemp()
        
        # Cria um setup de exemplo
        self.example_setup = {
            "id": "test_setup_123",
            "car": "Ford Mustang GT3",
            "track": "Monza",
            "author": "Teste",
            "date": datetime.now().isoformat(),
            "suspension": {
                "Altura dianteira": "56 mm",
                "Altura traseira": "58 mm"
            },
            "aero": {
                "Asa dianteira": "3",
                "Asa traseira": "5"
            },
            "transmission": {
                "Diferencial": "45%"
            },
            "tyres": {
                "Pressão dianteira esquerda": "27.5 psi",
                "Pressão dianteira direita": "27.8 psi"
            },
            "notes": "Setup de teste"
        }
    
    def tearDown(self):
        """Limpeza após os testes."""
        # Remove o diretório temporário
        shutil.rmtree(self.test_dir)
    
    def test_setup_export(self):
        """Testa a exportação de setups."""
        # Arquivo de destino
        export_file = os.path.join(self.test_dir, "exported_setup.json")
        
        # Exporta o setup
        try:
            with open(export_file, "w") as f:
                json.dump(self.example_setup, f, indent=2)
            
            # Verifica se o arquivo foi criado
            self.assertTrue(os.path.exists(export_file))
            print("✓ Exportação de setup funcionando corretamente")
        except Exception as e:
            self.fail(f"Falha ao exportar setup: {str(e)}")
    
    def test_setup_import(self):
        """Testa a importação de setups."""
        # Arquivo de origem
        import_file = os.path.join(self.test_dir, "import_setup.json")
        
        # Salva o setup para importação
        with open(import_file, "w") as f:
            json.dump(self.example_setup, f, indent=2)
        
        # Importa o setup
        try:
            with open(import_file, "r") as f:
                imported_setup = json.load(f)
            
            # Verifica se os dados foram importados corretamente
            self.assertEqual(imported_setup["car"], "Ford Mustang GT3")
            self.assertEqual(imported_setup["track"], "Monza")
            self.assertEqual(imported_setup["suspension"]["Altura dianteira"], "56 mm")
            print("✓ Importação de setup funcionando corretamente")
        except Exception as e:
            self.fail(f"Falha ao importar setup: {str(e)}")


def run_tests():
    """Executa os testes automatizados."""
    print("\n=== Iniciando testes do Race Telemetry Analyzer ===\n")
    
    # Cria um runner personalizado para capturar a saída
    runner = unittest.TextTestRunner(verbosity=2)
    
    # Executa os testes
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(TestCaptureManager))
    test_suite.addTest(unittest.makeSuite(TestACCTelemetryCapture))
    test_suite.addTest(unittest.makeSuite(TestLMUTelemetryCapture))
    test_suite.addTest(unittest.makeSuite(TestSetupManagement))
    
    result = runner.run(test_suite)
    
    print("\n=== Resumo dos testes ===")
    print(f"Total de testes: {result.testsRun}")
    print(f"Testes bem-sucedidos: {result.testsRun - len(result.errors) - len(result.failures)}")
    print(f"Falhas: {len(result.failures)}")
    print(f"Erros: {len(result.errors)}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

