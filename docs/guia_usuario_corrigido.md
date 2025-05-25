# Guia do Usuário - Race Telemetry Analyzer (Versão Corrigida)

## Introdução

O Race Telemetry Analyzer é uma ferramenta para análise de telemetria em simuladores de corrida como Assetto Corsa Competizione (ACC) e Le Mans Ultimate (LMU). Desenvolvido para pilotos virtuais que buscam melhorar seus tempos de volta, o aplicativo oferece recursos de análise, comparação e visualização de dados de telemetria.

Este guia apresenta as principais funcionalidades do Race Telemetry Analyzer e como utilizá-las.

## Instalação

### Requisitos do Sistema

- Sistema Operacional: Windows 10/11 (64 bits)
- Python 3.9+ (recomendado 3.11)
- Dependências Python (PyQt6, numpy, matplotlib)

### Executando o Aplicativo

1.  **Descompacte** o arquivo `race_telemetry_desktop_final_v2.zip` em uma pasta de sua escolha.
2.  **Abra um terminal** (Prompt de Comando ou PowerShell) nessa pasta.
3.  **Instale as dependências** (se ainda não o fez):
    ```bash
    pip install PyQt6 numpy matplotlib
    ```
4.  **Execute o aplicativo**:
    ```bash
    python src/main.py
    ```
    *Alternativamente, você pode usar o arquivo `executar.bat` (se disponível e configurado corretamente).* 

## Visão Geral da Interface

O Race Telemetry Analyzer possui uma interface dividida em seções principais acessadas por abas:

1.  **Dashboard**: Visão geral, controle de captura e importação.
2.  **Análise de Telemetria**: Visualização detalhada de uma volta específica (gráficos).
3.  **Comparação de Voltas**: Comparação lado a lado de duas voltas.
4.  **Setups**: Gerenciamento de configurações de carros.
5.  **Configurações**: (Futura implementação)

## Captura de Telemetria

### Conexão com Simuladores

O Race Telemetry Analyzer suporta captura de telemetria dos seguintes simuladores:

-   **Assetto Corsa Competizione (ACC)**: Captura via memória compartilhada em tempo real.
-   **Le Mans Ultimate (LMU)**: Captura via monitoramento da pasta MoTeC (arquivos `.ld` e `.ldx`).

**Para iniciar a captura:**

1.  Inicie o simulador desejado.
2.  Abra o Race Telemetry Analyzer.
3.  Na aba **Dashboard**, no painel "Controle de Captura":
    *   Selecione o simulador na lista (ACC ou LMU).
    *   Clique em **Conectar**.
    *   Se a conexão for bem-sucedida, o status será atualizado.
    *   Clique em **Iniciar Captura**.

**Observações:**

*   **ACC**: A captura é em tempo real. Os dados são coletados enquanto você dirige.
*   **LMU**: O aplicativo monitora a pasta MoTeC configurada no LMU (geralmente em `Documentos\Le Mans Ultimate\MoTeC`). Novos arquivos `.ld` e `.ldx` gerados pelo jogo serão processados automaticamente enquanto a captura estiver ativa. Certifique-se de que o LMU está configurado para gerar logs MoTeC.
*   O status da conexão e captura é exibido no painel "Status da Captura".

### Importação de Arquivos de Telemetria

Você pode importar sessões de telemetria previamente salvas pelo Race Telemetry Analyzer (formato `.json`):

1.  Na aba **Dashboard**, clique em **Importar Telemetria**.
2.  Navegue até o arquivo `.json` da sessão desejada.
3.  Selecione o arquivo e clique em "Abrir".

**Importação de Arquivos `.ld` (MoTeC):**

*   Atualmente, a importação direta de arquivos `.ld` individuais pela interface **não está implementada**. 
*   Para analisar dados do LMU, utilize a função de **captura para LMU**, que monitorará a pasta MoTeC e processará os arquivos `.ld` automaticamente.

## Análise de Voltas

A aba **Análise de Telemetria** permite examinar detalhadamente os dados de uma volta específica.

*(Esta seção ainda utiliza gráficos básicos. A visualização completa, incluindo mapa, está na aba Dashboard e Comparação)*

1.  Selecione a volta desejada (após captura ou importação).
2.  Os gráficos (Velocidade, Pedais, RPM, etc.) serão atualizados.
3.  Use as ferramentas de zoom e seleção para analisar trechos específicos.

## Comparação de Voltas

A aba **Comparação de Voltas** é essencial para identificar onde ganhar tempo.

### Seleção de Voltas para Comparação

1.  No painel "Volta de Referência", selecione a sessão e a volta base (ex: sua melhor volta).
2.  No painel "Volta de Comparação", selecione a sessão e a volta que deseja analisar.
3.  Clique em **Comparar Voltas**.

### Análise Comparativa

A tela de comparação exibe:

-   **Resultados da Comparação**: Diferença total de tempo e por setor.
-   **Pontos de Melhoria**: Sugestões automáticas baseadas na análise comparativa (frenagem, aceleração, trajetória).
-   **Visualização da Pista**: Mapa com os traçados das duas voltas sobrepostos. Cores indicam onde uma volta foi mais rápida que a outra.
-   **Gráficos Comparativos**: Delta de tempo, Velocidade, Pedais (Acelerador/Freio).

Use a visualização do traçado e o gráfico de delta para identificar rapidamente onde as maiores diferenças ocorrem.

## Gerenciamento de Setups

A aba **Setups** permite gerenciar configurações de carros.

### Visualização e Gerenciamento

-   A lista à esquerda exibe os setups salvos (arquivos `.json` na pasta `RaceTelemetryAnalyzer\setups` em seu diretório de usuário).
-   Clique em um setup para ver seus detalhes no painel direito.
-   Use os botões **Novo Setup**, **Importar Setup** e **Editar/Exportar** (nos cards ou painel de detalhes) para gerenciar seus setups.

### Salvamento e Exportação

-   Ao criar ou editar um setup, ele será salvo automaticamente como um arquivo `.json` na pasta `RaceTelemetryAnalyzer\setups`.
-   O botão **Exportar** permite salvar uma cópia do setup em qualquer local desejado.
-   A função de aplicar setup diretamente ao simulador **não está implementada**.

## Dicas e Solução de Problemas

### Estabilidade

-   Foram implementadas melhorias significativas na estabilidade e tratamento de erros.
-   Se o aplicativo fechar inesperadamente, verifique os arquivos de log na pasta `RaceTelemetryAnalyzer\logs` no seu diretório de usuário para obter detalhes sobre o erro.

### Problemas Comuns

-   **LMU não detectado/sem dados**: Verifique se o LMU está configurado para gerar logs MoTeC e se a pasta MoTeC correta foi detectada pelo Analyzer (indicado nos logs ao iniciar a captura LMU).
-   **Erro ao salvar setup**: Verifique as permissões de escrita na pasta `RaceTelemetryAnalyzer\setups`.
-   **Mapa/Traçado não aparece**: Certifique-se de que a captura de dados (ACC ou LMU) está funcionando e coletando dados de posição (PosX, PosY, PosZ).
-   **Erro `c_float_Array_60 not JSON serializable` (ACC)**: Este erro foi corrigido. Se ocorrer, verifique se está usando a versão mais recente.
-   **Erro `TypeError: '<' not supported` (Mapa)**: Este erro foi corrigido. Se ocorrer, verifique os dados de posição sendo enviados para o mapa.

### Suporte

Se encontrar problemas persistentes, por favor, reporte detalhando o problema e, se possível, anexe o arquivo de log relevante.

## Conclusão

Esta versão corrigida do Race Telemetry Analyzer visa resolver os problemas reportados e fornecer uma ferramenta mais estável e funcional para análise de telemetria. Explore as funcionalidades de captura, análise e comparação para aprimorar seu desempenho nas pistas virtuais.

