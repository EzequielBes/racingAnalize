#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para testar o parser de arquivos MoTeC .ld/.ldx
"""

import os
import sys
import logging
import json
from datetime import datetime

# Configurar logging (CORRIGIDO)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' # Corrigido aspas
)
logger = logging.getLogger("test_parser")

# Adicionar diretório pai ao path para importar módulos do projeto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar o parser e a estrutura de dados
from src.data_acquisition.parsers import MotecParser
from src.core.standard_data import TelemetrySession, DataPoint # Importar DataPoint

def test_motec_parser(file_path):
    """
    Testa o parser MoTeC com um arquivo específico.

    Args:
        file_path: Caminho para o arquivo .ld ou .ldx
    """
    logger.info(f"Testando parser MoTeC com arquivo: {file_path}")

    # Criar instância do parser
    parser = MotecParser()

    # Tentar fazer o parsing do arquivo
    try:
        session = parser.parse(file_path)

        if session is None:
            logger.error("Parser retornou None. Falha no parsing.")
            return False

        # Exibir informações básicas da sessão (usando atributos corretos)
        logger.info(f"Parsing bem-sucedido!")
        logger.info(f"Jogo: {session.session_info.game}")
        logger.info(f"Pista: {session.session_info.track}")
        logger.info(f"Carro: {session.session_info.car}") # Corrigido de vehicle
        logger.info(f"Piloto: {session.session_info.driver_name}") # Corrigido de driver
        logger.info(f"Data: {session.session_info.date}")
        logger.info(f"Tipo de sessão: {session.session_info.session_type}")
        logger.info(f"Fonte: {session.session_info.source}")

        # Exibir informações das voltas (usando atributos corretos)
        logger.info(f"Número de voltas: {len(session.laps)}")
        for i, lap in enumerate(session.laps):
            lap_time_sec = lap.lap_time_ms / 1000.0 if lap.lap_time_ms is not None else "N/A"
            logger.info(f"Volta {lap.lap_number}: {lap_time_sec}s, {len(lap.data_points)} pontos")

            # Exibir alguns canais da primeira volta para verificação
            if i == 0:
                if lap.data_points and len(lap.data_points) > 0:
                    # Pegar o primeiro ponto de dados
                    first_point = lap.data_points[0]
                    logger.info("Canais disponíveis no primeiro ponto:")

                    # Converter para dict e exibir as chaves (nomes dos canais)
                    point_dict = first_point.__dict__
                    for key in point_dict.keys():
                        logger.info(f"  - {key}")

                    # Exibir alguns valores de exemplo (primeiros 5 pontos)
                    sample_size = min(5, len(lap.data_points))
                    logger.info(f"Amostra dos primeiros {sample_size} pontos:")

                    # Tentar encontrar canais comuns para exibir (usando nomes de DataPoint)
                    common_channels = [f.name for f in DataPoint.__dataclass_fields__.values()]

                    for channel in common_channels:
                        if hasattr(first_point, channel) and getattr(first_point, channel) is not None:
                            logger.info(f"Canal: {channel}")
                            for j in range(sample_size):
                                value = getattr(lap.data_points[j], channel)
                                logger.info(f"  Ponto {j}: {value}")

        return True

    except Exception as e:
        logger.exception(f"Erro durante o teste do parser: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Uso: python test_parser.py <caminho_para_arquivo.ld>")
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        logger.error(f"Arquivo não encontrado: {file_path}")
        sys.exit(1)

    success = test_motec_parser(file_path)
    sys.exit(0 if success else 1)

