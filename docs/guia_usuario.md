# Guia do Usuário - Race Telemetry Analyzer

## 1. Introdução

Bem-vindo ao Race Telemetry Analyzer! Esta ferramenta foi desenvolvida para ajudar pilotos de simuladores de corrida a analisar sua performance através da telemetria, oferecendo insights para melhoria contínua.

Este guia descreve a arquitetura do sistema, as funcionalidades implementadas e como utilizar a ferramenta.

## 2. Visão Geral da Arquitetura

O sistema foi construído com uma arquitetura modular em Python, projetada para ser extensível e suportar múltiplos simuladores e modos de operação (tempo real e importação de arquivos).

Os principais componentes são:

*   **Aquisição de Dados (`data_acquisition`):** Responsável por conectar-se aos simuladores (via memória compartilhada, SDKs, ou monitoramento de arquivos) e importar dados de arquivos de telemetria (MoTeC .ld/.ldx, iRacing .ibt - *parser pendente*, CSV, JSON). Contém implementações parciais para ACC e LMU baseadas no código original e pesquisa, além de parsers específicos.
*   **Núcleo (`core`):** Orquestra o fluxo de dados e define as estruturas de dados padronizadas (`standard_data.py`) usadas internamente.
*   **Processamento e Análise (`processing_analysis`):** Contém a lógica para processar os dados padronizados (`telemetry_processor.py`), calcular métricas, gerar traçados e comparar voltas (`lap_comparator.py`).
*   **Interface Gráfica (`ui`):** Responsável pela interação com o usuário (baseada em PyQt6). Inclui widgets para visualização de traçados, gráficos de telemetria e comparação de voltas (`comparison_widget.py` - estrutura implementada).
*   **Persistência (`persistence`):** (Não implementado nesta fase) Gerenciaria o armazenamento de sessões e configurações.

Consulte `docs/arquitetura_refinada.md` para detalhes completos da arquitetura projetada.

## 3. Funcionalidades Implementadas

*   **Estrutura de Projeto Modular:** O código está organizado em diretórios seguindo a arquitetura definida.
*   **Estrutura de Dados Padronizada:** Definição clara das estruturas para Sessão, Volta, Ponto de Dados e Pista em `src/core/standard_data.py`.
*   **Processamento de Telemetria:** Implementação do `TelemetryProcessor` em `src/processing_analysis/telemetry_processor.py` capaz de:
    *   Ler dados padronizados de uma volta.
    *   Extrair canais essenciais (velocidade, RPM, pedais, volante, etc.).
    *   Gerar o traçado do piloto (coordenadas X, Y).
    *   Calcular estatísticas básicas de velocidade por setor.
    *   Gerar um mapa agregado da pista a partir dos traçados das voltas.
*   **Importação de Arquivos:**
    *   Módulo `telemetry_import.py` com lógica para detectar e chamar parsers específicos.
    *   Parser para MoTeC (`.ld`, `.ldx`) implementado em `src/data_acquisition/parsers.py` (com base na estrutura LD, requer testes e ajustes para LDX).
    *   Estrutura para parser IBT (`.ibt`) criada, mas a implementação do parsing binário está pendente.
    *   Importadores básicos para CSV e JSON (assumindo formatos específicos).
*   **Comparação de Voltas:**
    *   Implementação do `LapComparator` em `src/processing_analysis/lap_comparator.py` capaz de:
        *   Alinhar dados de duas voltas por distância usando interpolação.
        *   Comparar canais de telemetria selecionados.
        *   Calcular o gráfico de delta time entre as voltas.
        *   Fornecer os traçados das duas voltas para visualização sobreposta.
*   **Interface de Comparação (Estrutura):** O arquivo `src/ui/comparison_widget.py` contém a estrutura (placeholder) de um widget PyQt6 para seleção de voltas e exibição dos resultados da comparação (plots de traçado, canais e delta time), incluindo a lógica básica de interação.

## 4. Como Utilizar (Conceitual)

1.  **Execução:** Inicie a aplicação (requer ambiente Python com dependências como PyQt6, NumPy, Pandas, PyQtGraph instaladas). O ponto de entrada principal seria `run.py` ou `main.py` (a ser finalizado).
2.  **Conexão/Importação:**
    *   **Tempo Real:** Selecione o simulador (ACC, LMU, iRacing) e conecte-se. A aplicação começará a capturar dados em segundo plano.
    *   **Importação:** Use a opção "Importar Arquivo", selecione o arquivo de telemetria (.ld, .ldx, .ibt, .csv, .json). A aplicação processará o arquivo.
3.  **Análise de Sessão:** Após a captura ou importação, a sessão será exibida. Você poderá ver informações gerais e a lista de voltas.
4.  **Visualização de Volta Única:** Selecione uma volta para ver seus detalhes:
    *   Traçado na pista.
    *   Gráficos de telemetria (velocidade, RPM, pedais, etc.) vs. distância ou tempo.
5.  **Comparação de Voltas:**
    *   Navegue até a tela/widget de comparação.
    *   Selecione duas voltas válidas da sessão carregada nos menus dropdown.
    *   Clique em "Comparar".
    *   Os gráficos serão atualizados mostrando:
        *   Traçados das duas voltas sobrepostos no mapa.
        *   Gráficos dos canais selecionados (ex: velocidade) das duas voltas sobrepostos.
        *   Gráfico do delta time (diferença de tempo acumulada) entre as voltas.
    *   Utilize o cursor interativo (passando o mouse sobre os gráficos de canais ou delta) para ver os valores correspondentes em todos os gráficos e no mapa da pista.

## 5. Próximos Passos e Limitações

*   **Teste com Dados Reais:** A validação completa requer testes extensivos com dados reais de todos os simuladores suportados (ACC, LMU, iRacing) em um ambiente com os jogos instalados.
*   **Interface Gráfica:** A UI precisa ser completamente implementada e integrada com a lógica de backend (processamento, importação, comparação).
*   **Captura em Tempo Real:** As implementações de captura em tempo real (`ACCTelemetryProvider`, `LMUTelemetryProvider`, `iRacingTelemetryProvider`) precisam ser finalizadas e testadas.
*   **Parsers:** O parser MoTeC LDX precisa de refinamento e testes. O parser IBT precisa ser implementado.
*   **Assetto Corsa Evo:** Requer pesquisa para determinar APIs/formatos de telemetria e implementação subsequente.
*   **Replays:** A importação de replays não foi implementada e geralmente é complexa.
*   **Análise Avançada:** Funcionalidades como detecção automática de erros, sugestões de melhoria, análise de setup, etc., não foram incluídas nesta fase.
*   **Persistência:** O salvamento/carregamento de sessões analisadas não foi implementado.
*   **Empacotamento:** A criação de um executável standalone (via PyInstaller) requer configuração adicional.

## 6. Estrutura do Código Fonte

O código fonte está organizado da seguinte forma:

```
/racingAnalize
|-- docs/                 # Documentação (arquitetura, guia)
|-- src/
|   |-- core/             # Núcleo, dados padronizados
|   |-- data_acquisition/ # Captura em tempo real e parsers de importação
|   |-- processing_analysis/ # Processamento, análise, comparação
|   |-- ui/               # Componentes da interface gráfica
|   |-- __init__.py
|   |-- main.py           # Ponto de entrada principal (a ser finalizado)
|   |-- telemetry_analysis.py # (Refatorado para processing_analysis)
|   |-- telemetry_comparison.py # (Refatorado para processing_analysis)
|   |-- telemetry_import.py   # Lógica de importação
|-- tests/                # Testes unitários/integração (a serem criados)
|-- tools/                # Ferramentas auxiliares (empacotamento)
|-- executar.bat          # Script de execução (Windows)
|-- run.py                # Script de execução (Cross-platform)
|-- todo.md               # Lista de tarefas do desenvolvimento
```

