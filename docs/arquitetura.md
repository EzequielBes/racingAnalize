# Arquitetura do Race Telemetry Analyzer

## Visão Geral

O Race Telemetry Analyzer será um aplicativo desktop nativo para Windows, focado em análise profissional de telemetria para simuladores de corrida. A arquitetura será modular, permitindo fácil extensão e manutenção.

## Componentes Principais

### 1. Interface Gráfica (GUI)
- Framework: PyQt6 (escolhido por sua capacidade de criar interfaces modernas e responsivas)
- Design: Minimalista, clean e profissional com tema escuro/claro
- Componentes: Gráficos interativos, visualização de pista, painéis de telemetria

### 2. Motor de Captura de Dados
- Captura em tempo real dos simuladores (ACC, Le Mans Ultimate)
- Leitura de arquivos de telemetria e replays
- Suporte a múltiplos formatos de dados

### 3. Processamento de Telemetria
- Detecção automática de voltas
- Análise de trajetórias
- Cálculo de tempos por setor
- Identificação de pontos de frenagem/aceleração

### 4. Motor de Comparação
- Comparação detalhada entre voltas
- Análise de diferenças de trajetória
- Identificação precisa de ganhos/perdas de tempo
- Sugestões de melhoria baseadas em dados

### 5. Gerenciador de Setups
- Armazenamento de setups por carro/pista
- Comparação entre setups
- Setups profissionais pré-configurados

### 6. Sistema de Persistência
- Armazenamento local de dados de telemetria
- Exportação/importação de dados
- Backup automático

## Fluxo de Dados

1. **Entrada de Dados**:
   - Captura em tempo real via memória compartilhada/API dos simuladores
   - Importação de arquivos de telemetria/replay
   - Entrada manual de setups

2. **Processamento**:
   - Normalização de dados
   - Detecção de eventos (voltas, setores, frenagens)
   - Análise comparativa
   - Geração de insights

3. **Visualização**:
   - Renderização de traçados na pista
   - Gráficos de telemetria (velocidade, RPM, pedais)
   - Comparação visual de trajetórias
   - Indicadores de performance

4. **Armazenamento**:
   - Salvamento de sessões analisadas
   - Exportação de relatórios
   - Backup de setups

## Tecnologias

- **Linguagem**: Python 3.10+
- **GUI**: PyQt6
- **Gráficos**: Matplotlib (integrado com PyQt)
- **Processamento de Dados**: NumPy, Pandas
- **Visualização de Pista**: OpenGL via PyOpenGL
- **Persistência**: SQLite para dados estruturados, arquivos JSON para configurações
- **Empacotamento**: PyInstaller para geração de executável standalone

## Requisitos de Sistema

- Windows 10/11 (64-bit)
- 4GB RAM mínimo (8GB recomendado)
- Processador dual-core 2.0GHz ou superior
- 500MB de espaço em disco
- Placa de vídeo com suporte a OpenGL 3.3+
