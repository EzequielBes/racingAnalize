"""
Script de execução simplificado para o Race Telemetry Analyzer.
Este arquivo facilita a execução direta do aplicativo sem problemas de importação.
"""

import os
import sys

# Adiciona o diretório atual ao path do Python
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Importa e executa o módulo principal
try:
    from src.main import main
    
    if __name__ == "__main__":
        main()
except ImportError as e:
    print(f"Erro de importação: {e}")
    print("\nVerifique se todas as dependências estão instaladas:")
    print("pip install PyQt6 numpy matplotlib scipy pandas")
    
    input("\nPressione Enter para sair...")
    sys.exit(1)
except Exception as e:
    print(f"Erro ao iniciar o aplicativo: {e}")
    
    input("\nPressione Enter para sair...")
    sys.exit(1)
