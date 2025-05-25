# Guia do Usuário - Race Telemetry Analyzer

## Introdução

O Race Telemetry Analyzer é uma ferramenta profissional para análise de telemetria em simuladores de corrida como Assetto Corsa Competizione e Le Mans Ultimate. Desenvolvido para pilotos virtuais que buscam melhorar seus tempos de volta, o aplicativo oferece recursos avançados de análise, comparação e visualização de dados de telemetria.

Este guia apresenta as principais funcionalidades do Race Telemetry Analyzer e como utilizá-las para extrair o máximo de desempenho em suas corridas virtuais.

## Instalação

### Requisitos do Sistema

- Sistema Operacional: Windows 10/11 (64 bits)
- Processador: Intel Core i3 ou AMD Ryzen 3 ou superior
- Memória RAM: 4GB (mínimo), 8GB (recomendado)
- Espaço em Disco: 500MB
- Placa de Vídeo: Compatível com DirectX 11
- Resolução de Tela: 1366x768 ou superior

### Processo de Instalação

1. Execute o arquivo `RaceTelemetryAnalyzer-Setup.exe`
2. Siga as instruções do assistente de instalação
3. Após a conclusão, o Race Telemetry Analyzer estará disponível no menu Iniciar e na área de trabalho

## Visão Geral da Interface

O Race Telemetry Analyzer possui uma interface minimalista e intuitiva, dividida em cinco seções principais:

1. **Dashboard**: Visão geral dos dados de telemetria e estatísticas
2. **Análise de Voltas**: Visualização detalhada de uma volta específica
3. **Comparação de Voltas**: Comparação entre duas voltas para identificar diferenças
4. **Setups de Carros**: Gerenciamento e visualização de setups otimizados
5. **Configurações**: Personalização do aplicativo e conexão com simuladores

A navegação entre as seções é feita através da barra lateral, que permanece visível em todas as telas.

## Captura de Telemetria

### Conexão com Simuladores

O Race Telemetry Analyzer suporta captura de telemetria em tempo real dos seguintes simuladores:

- **Assetto Corsa Competizione**: Captura via memória compartilhada
- **Le Mans Ultimate**: Captura via plugin dedicado

Para iniciar a captura:

1. Inicie o simulador desejado
2. Abra o Race Telemetry Analyzer
3. Na seção Dashboard, clique em "Conectar"
4. Selecione o simulador na lista
5. Clique em "Iniciar Captura"

O status da conexão será exibido na parte inferior da tela. Uma vez conectado, o aplicativo começará a capturar dados automaticamente durante suas voltas.

### Importação de Arquivos de Telemetria

Além da captura em tempo real, você pode importar arquivos de telemetria previamente salvos:

1. Na seção Dashboard, clique em "Importar"
2. Navegue até o arquivo de telemetria (.json, .csv ou formato nativo do simulador)
3. Selecione o arquivo e clique em "Abrir"

Os dados importados serão processados e disponibilizados para análise.

## Análise de Voltas

A seção de Análise de Voltas permite examinar detalhadamente os dados de uma volta específica.

### Seleção de Volta

1. No painel esquerdo, selecione a sessão desejada
2. Escolha a volta que deseja analisar na lista
3. Os dados da volta serão carregados automaticamente

### Visualização de Dados

A tela de análise apresenta:

- **Mapa da Pista**: Visualização do traçado com código de cores para velocidade
- **Gráfico de Velocidade**: Velocidade ao longo da volta
- **Gráfico de Pedais**: Uso do acelerador e freio
- **Gráfico de RPM**: Rotações do motor e pontos de troca de marcha
- **Setores**: Tempos por setor e comparação com sua melhor volta

### Ferramentas de Análise

- **Zoom**: Use a roda do mouse para ampliar áreas específicas dos gráficos
- **Seleção**: Clique e arraste para selecionar um trecho específico
- **Pontos-chave**: Clique em um ponto do traçado para ver os dados exatos naquela posição
- **Filtros**: Selecione quais dados deseja visualizar usando as caixas de seleção

## Comparação de Voltas

A funcionalidade de comparação é uma das mais poderosas do Race Telemetry Analyzer, permitindo identificar precisamente onde você pode melhorar.

### Seleção de Voltas para Comparação

1. Na seção Comparação de Voltas, selecione a "Volta de Referência" (geralmente sua melhor volta)
2. Selecione a "Volta de Comparação" (a volta que deseja analisar)
3. Clique em "Comparar Voltas"

### Análise Comparativa

A tela de comparação exibe:

- **Delta de Tempo**: Diferença de tempo acumulada ao longo da volta
- **Traçados Sobrepostos**: Visualização dos dois traçados no mapa da pista
- **Gráficos Comparativos**: Velocidade, acelerador, freio e marcha das duas voltas
- **Pontos de Melhoria**: Identificação automática de áreas onde você pode melhorar

### Identificação de Pontos de Melhoria

O Race Telemetry Analyzer identifica automaticamente pontos onde você pode melhorar:

- **Frenagem**: Pontos onde você freia muito cedo, muito tarde ou com intensidade inadequada
- **Aceleração**: Pontos onde você poderia acelerar mais cedo ou com mais intensidade
- **Traçado**: Diferenças significativas no traçado que afetam o tempo
- **Velocidade de Curva**: Pontos onde você perde velocidade desnecessariamente

Cada ponto de melhoria é destacado no mapa e nos gráficos, com uma descrição detalhada do problema e sugestões para correção.

## Gerenciamento de Setups

A seção de Setups permite gerenciar configurações otimizadas para diferentes carros e pistas.

### Setups Pré-configurados

O Race Telemetry Analyzer inclui setups profissionais pré-configurados:

- **Ford Mustang GT3 para Monza**: Setup otimizado para máxima velocidade nas retas longas de Monza
- **McLaren 720S GT3 para Monza**: Setup balanceado com foco em estabilidade nas chicanes

### Visualização de Setups

1. Na seção Setups, selecione o carro e a pista desejados
2. Clique em "Filtrar" para ver os setups disponíveis
3. Selecione um setup para ver seus detalhes

Os detalhes do setup incluem:

- **Suspensão**: Altura, molas, amortecedores, barras estabilizadoras
- **Aerodinâmica**: Configurações de asas e difusor
- **Transmissão**: Relações de marcha e diferencial
- **Pneus**: Pressões e compostos
- **Notas**: Dicas específicas para utilizar o setup

### Criação e Edição de Setups

Para criar um novo setup:

1. Clique em "Novo Setup"
2. Preencha os dados básicos (carro, pista, autor)
3. Configure os parâmetros técnicos
4. Adicione notas e dicas
5. Clique em "Salvar"

Para editar um setup existente:

1. Selecione o setup na lista
2. Clique em "Editar"
3. Faça as alterações necessárias
4. Clique em "Salvar"

## Dicas para Melhorar seus Tempos

### Análise Sistemática

1. **Compare com sua melhor volta**: Identifique onde você está perdendo tempo
2. **Foque em um problema por vez**: Trabalhe em uma área específica até dominá-la
3. **Analise setores separadamente**: Divida a pista em seções para análise detalhada

### Interpretação dos Dados

- **Delta negativo (verde)**: Você está ganhando tempo em relação à referência
- **Delta positivo (vermelho)**: Você está perdendo tempo em relação à referência
- **Traçado ideal**: Geralmente combina a maior velocidade possível com a menor distância

### Técnicas Avançadas

- **Sobreposição de pedais**: Analise onde os pilotos mais rápidos sobrepõem acelerador e freio
- **Pontos de frenagem**: Identifique referências visuais para pontos de frenagem consistentes
- **Progressão do acelerador**: Observe como os pilotos mais rápidos aplicam o acelerador na saída das curvas

## Solução de Problemas

### Problemas de Conexão

Se o aplicativo não conseguir se conectar ao simulador:

1. Verifique se o simulador está em execução
2. Reinicie o Race Telemetry Analyzer
3. Verifique se há atualizações disponíveis para o aplicativo ou simulador
4. Desative temporariamente o antivírus ou firewall

### Problemas de Desempenho

Se o aplicativo estiver lento ou instável:

1. Feche outros programas em execução
2. Reduza a taxa de amostragem nas configurações
3. Desative a captura em tempo real e trabalhe com dados importados

### Suporte Técnico

Para obter suporte adicional:

- Consulte a documentação online em [www.racetelemetryanalyzer.com/support](http://www.racetelemetryanalyzer.com/support)
- Entre em contato pelo e-mail support@racetelemetryanalyzer.com

## Conclusão

O Race Telemetry Analyzer é uma ferramenta poderosa para pilotos virtuais que desejam melhorar seu desempenho. Com análise detalhada de telemetria, comparação de voltas e identificação de pontos de melhoria, você terá todas as informações necessárias para reduzir seus tempos de volta e se tornar mais competitivo.

Dedique tempo para explorar todas as funcionalidades do aplicativo e integre a análise de dados à sua rotina de treinos. Com prática e análise sistemática, você verá melhorias significativas em seu desempenho nas pistas virtuais.

Boas corridas e tempos cada vez melhores!
