# Arquitetura Refinada - Race Telemetry Analyzer

## 1. Visão Geral

O Race Telemetry Analyzer será um aplicativo desktop multiplataforma (com foco inicial em Windows), desenvolvido em Python, para análise de telemetria de simuladores de corrida. A arquitetura será modular, orientada a interfaces e focada em extensibilidade para suportar múltiplos jogos, modos de operação (tempo real e importação) e futuras funcionalidades.

## 2. Princípios de Design

*   **Modularidade:** Componentes independentes com responsabilidades claras.
*   **Abstração:** Interfaces bem definidas para isolar implementações específicas de jogos/formatos.
*   **Unificação:** Um formato de dados interno padronizado para telemetria, independentemente da origem.
*   **Extensibilidade:** Facilidade para adicionar suporte a novos jogos, formatos de arquivo ou funcionalidades de análise.
*   **Desempenho:** Considerações sobre o manuseio eficiente de grandes volumes de dados de telemetria.

## 3. Componentes Principais

### 3.1. Camada de Aquisição de Dados (`data_acquisition`)

Responsável por obter dados brutos dos simuladores ou arquivos.

*   **Interface `TelemetryProvider`:** Define o contrato para todas as fontes de dados (tempo real e importadores).
    *   Métodos: `connect()`, `disconnect()`, `start_capture()`, `stop_capture()`, `get_status()`, `read_data()` (para tempo real), `import_session()` (para importação).
    *   Eventos/Callbacks: `on_data_received(data)`, `on_lap_completed(lap_data)`, `on_session_loaded(session_data)`.
*   **Implementações em Tempo Real:**
    *   `ACCTelemetryProvider`: Usa memória compartilhada do ACC.
    *   `LMUTelemetryProvider`: Monitora a pasta MoTeC (`.ld` files) em tempo real.
    *   `iRacingTelemetryProvider`: Usa o SDK do iRacing (via `pyirsdk`).
    *   `ACEvoTelemetryProvider`: (A ser pesquisado e implementado).
*   **Implementações de Importação:**
    *   `MotecImporter`: Parser para arquivos `.ldx` (ACC) e `.ld` (LMU).
    *   `IBTImporter`: Parser para arquivos `.ibt` (iRacing).
    *   `ReplayImporter`: (A ser pesquisado e implementado para formatos de replay relevantes).
*   **Normalizador/Padronizador:** Converte os dados brutos específicos de cada jogo/formato para o **Formato Interno Padronizado de Telemetria** (ver seção 4).

### 3.2. Camada de Processamento e Análise (`processing_analysis`)

Recebe dados no formato padronizado e realiza análises.

*   **Motor de Processamento:**
    *   Detecção de Voltas/Setores (se não fornecido pela aquisição).
    *   Cálculo de Trajetórias (X, Y, Z).
    *   Suavização de dados (opcional).
    *   Cálculo de métricas derivadas (velocidade em curva, taxas de variação, etc.).
*   **Motor de Análise:**
    *   Identificação de pontos de frenagem/aceleração/troca de marcha.
    *   Análise de consistência de voltas.
    *   Geração de dados para visualização (traçados, estatísticas).
*   **Motor de Comparação:**
    *   Recebe duas ou mais voltas processadas.
    *   Calcula delta de tempo (geral e por setor/segmento).
    *   Compara canais de telemetria (gráficos sobrepostos, diferenças).
    *   Compara trajetórias (visualização sobreposta).
*   **Gerenciador de Pistas:**
    *   Armazena e fornece dados de pistas (layout, setores, elevação).
    *   Pode obter dados da telemetria ou de fontes externas.

### 3.3. Camada de Persistência (`persistence`)

Responsável por salvar e carregar dados.

*   **Banco de Dados (SQLite):**
    *   Metadados de sessões (jogo, pista, carro, data, etc.).
    *   Informações de voltas (número, tempo total, tempos de setor).
    *   Sumários e estatísticas.
    *   Configurações do usuário.
    *   Dados de pistas.
    *   (Opcional) Setups de carro.
*   **Armazenamento de Arquivos:**
    *   Arquivos otimizados (e.g., Parquet, Feather, ou mesmo JSON/CSV compactado) para armazenar os dados de telemetria ponto a ponto (timestamps, canais), referenciados pelo banco de dados. Isso evita sobrecarregar o SQLite com milhões de linhas.
    *   Arquivos de configuração.

### 3.4. Interface Gráfica do Usuário (GUI - `ui`)

Interação com o usuário, baseada em PyQt6.

*   **Janela Principal:** Gerenciamento de conexões, importações, sessões salvas.
*   **Widgets de Visualização:**
    *   `TrackViewWidget`: Exibe o traçado da pista, a trajetória do piloto, pontos de interesse (frenagem, etc.). Interativo (zoom, pan, seleção de pontos).
    *   `TelemetryPlotWidget`: Gráficos de canais de telemetria (vs. tempo ou distância). Sincronizado com `TrackViewWidget`.
    *   `DashboardWidget`: Exibição de dados em tempo real (velocímetros, conta-giros, etc.).
    *   `ComparisonWidget`: Exibe duas ou mais voltas lado a lado (plots sobrepostos, track view sobreposto, gráfico de delta).
*   **Controladores/Modelos de UI:** Lógica para buscar dados das outras camadas e atualizar a interface.

### 3.5. Núcleo da Aplicação (`core`)

Orquestra a interação entre as camadas.

*   Gerencia o ciclo de vida da aplicação.
*   Coordena o fluxo de dados: Aquisição -> Normalização -> Processamento -> Persistência / UI.
*   Gerencia threads para operações assíncronas (captura em tempo real, processamento pesado, I/O de arquivos).

## 4. Formato Interno Padronizado de Telemetria

Estrutura de dados unificada para representar uma sessão de telemetria, independentemente da origem.

*   **Estrutura da Sessão (Exemplo):**
    ```json
    {
      "session_info": {
        "game": "ACC",
        "track": "Spa-Francorchamps",
        "car": "Ferrari 488 GT3 Evo",
        "date": "2025-05-26T20:30:00Z",
        "source": "realtime" // ou "import:file.ldx"
        // ... outros metadados
      },
      "track_data": {
        "name": "Spa-Francorchamps",
        "length_meters": 7004,
        "sectors": [0.0, 2100.0, 5500.0] // Distâncias de início dos setores
        // ... coordenadas do traçado (opcional)
      },
      "laps": [
        {
          "lap_number": 1,
          "lap_time_ms": 140500,
          "sector_times_ms": [45000, 50000, 45500],
          "is_valid": true,
          "data_points_ref": "session_xyz_lap_1.parquet" // Referência ao arquivo com dados detalhados
        },
        // ... mais voltas
      ]
    }
    ```
*   **Estrutura dos Pontos de Dados (Exemplo - conteúdo do arquivo referenciado):**
    *   Formato tabular (Pandas DataFrame, Parquet, etc.)
    *   Colunas: `timestamp_ms`, `distance_m`, `lap_time_ms`, `sector`, `pos_x`, `pos_y`, `pos_z`, `speed_kmh`, `rpm`, `gear`, `steer_angle`, `throttle`, `brake`, `clutch`, `tyre_temp_fl`, `tyre_press_fl`, ... (todos os canais relevantes e padronizados).

## 5. Fluxo de Dados

1.  **Tempo Real:** `Provider` (e.g., `ACCTelemetryProvider`) captura dados -> `Normalizador` converte para formato padronizado -> `Core` envia para `Processing` (detecção de volta/setor em tempo real) e `UI` (Dashboard) -> Ao completar volta, `Processing` finaliza dados da volta -> `Core` envia para `UI` (atualiza lista de voltas) e `Persistence` (salva volta).
2.  **Importação:** `Importer` (e.g., `MotecImporter`) lê arquivo -> `Normalizador` converte para formato padronizado -> `Core` recebe dados da sessão completa -> Envia para `Processing` (análise completa) -> Envia para `Persistence` (salva sessão) -> Envia para `UI` (exibe sessão carregada).
3.  **Visualização/Análise:** `UI` solicita dados de uma volta/sessão ao `Core` -> `Core` busca em `Persistence` -> `Core` (ou `UI`) envia para `Processing` se necessário reprocessamento/cálculos específicos -> `Processing` retorna dados analisados -> `UI` renderiza.

## 6. Tecnologias Chave

*   **Linguagem:** Python 3.10+
*   **GUI:** PyQt6
*   **Processamento Dados:** NumPy, Pandas
*   **Gráficos:** Matplotlib, PyQtGraph (mais performático para tempo real)
*   **Visualização Pista:** Matplotlib (inicial) / PyOpenGL (avançado)
*   **Persistência:** SQLite, Apache Parquet/Feather (via `pyarrow`)
*   **Tempo Real (Específico):** `ctypes`, `mmap` (ACC), `pyirsdk` (iRacing)
*   **Empacotamento:** PyInstaller / cx_Freeze

## 7. Próximos Passos (Implementação)

1.  Estruturar diretórios do projeto conforme arquitetura.
2.  Definir formalmente as classes/estruturas do Formato Interno Padronizado.
3.  Implementar a interface `TelemetryProvider` e os parsers/normalizadores básicos.
4.  Desenvolver o núcleo de processamento (detecção de voltas, cálculo de trajetória).
5.  Criar a estrutura básica da UI com PyQt6.

