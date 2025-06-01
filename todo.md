# Lista de Tarefas - Analisador de Telemetria de Corrida

Este arquivo acompanha o progresso do desenvolvimento do Race Telemetry Analyzer.

- [X] 001: Analisar o repositório GitHub base (`racingAnalize`) para entender a estrutura e código existentes.
- [X] 002: Levantar requisitos específicos para cada jogo suportado (ACC, LMU, iRacing, AC Evo), focando em formatos de telemetria (tempo real e arquivos) e APIs disponíveis.
- [X] 003: Projetar a arquitetura refinada do sistema, considerando módulos para captura de dados (tempo real e importação), normalização, processamento, análise, comparação e interface gráfica.
- [X] 004: Implementar funcionalidades centrais de análise de telemetria (processamento de dados brutos, cálculo de métricas básicas, estrutura para traçados).
- [X] 005: Finalizar e integrar o parser para arquivos MoTeC `.ld` (formato do ACC), permitindo a importação correta de voltas e dados.
- [X] 006: Implementar a estrutura de captura de dados em tempo real para ACC (via Shared Memory) e LMU (via Shared Memory rF2), incluindo detecção de voltas e armazenamento padronizado.
- [X] 007: Desenvolver o widget de visualização 2D do traçado e análise detalhada (`AnalysisWidget`), incluindo mapa interativo, gráficos de velocidade/inputs e cursor sincronizado.
- [X] 008: Integrar e validar o fluxo completo de importação e visualização detalhada, garantindo que os dados carregados sejam exibidos corretamente nas abas de Análise e Comparação.
- [X] 009: Reportar resultados e entregar versão funcional ao usuário.

