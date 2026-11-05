# Fontes de Dados Cartográficos e Geoespaciais - RaizTrace

Este documento descreve detalhadamente as fontes públicas de dados geográficos integradas ao sistema **RaizTrace**, explicitando as URLs fixas homologadas, os parâmetros de consulta, os metadados de proveniência criptográfica (hash SHA-256 e carimbo de data/hora UTC), sistemas de referência de coordenadas (CRS), termos de licenciamento e atribuição, limitações metodológicas de aproximação geométrica e ressalvas jurídicas/regulatórias.

---

## 1. Visão Geral e Arquitetura de Ingestão Robusta

O módulo [`integrations.py`](file:///C:/Users/orugi/Documents/Projetos/Hackathon/RAIZTRACE/integrations.py) adota uma arquitetura estrita e autossuficiente em conformidade com as diretrizes do projeto:
- **Exclusividade da Biblioteca Padrão Python (Python 3.11 stdlib)**: Toda a comunicação HTTP (`urllib.request`), descompressão GZIP segura (`gzip`, `io`), serialização/parsing (`json`), operações numéricas/matemáticas (`math`), integridade criptográfica (`hashlib`, `uuid`) e cálculo geométrico vetorial 2D utilizam estritamente módulos padrão do Python.
- **Allowlist Estrita de URLs Fixas**: O serviço bloqueia qualquer URL não cadastrada previamente na constante `ALLOWED_URLS`, prevenindo vetores de Server-Side Request Forgery (SSRF).
- **Limites Físicos e Proteção contra Gzip Bombs**: Limite rígido de 8 MB (8.388.608 bytes) por resposta HTTP e timeout de 12 segundos. A descompressão gzip via `safe_decompress_gzip` opera em streaming com verificação de cotas antes da expansão em memória, impedindo ataques de negação de serviço por descompressão excessiva.
- **Envelope de Proveniência Fiel (`raw_text` + `raw` + `sha256`)**:
  - Para garantir a reproducibilidade exata do hash SHA-256 (que não era possível ao serializar novamente objetos parseados), o envelope em disco armazena `raw_text` (a string UTF-8 idêntica aos bytes recebidos na requisição), o objeto derivado `raw` (GeoJSON FeatureCollection) e o hash SHA-256 calculado diretamente sobre `raw_text.encode('utf-8')`.
  - O método `_load_cache` valida rigorosamente:
    1. Se a URL declarada coincide exatamente com a `ALLOWED_URLS` correspondente (rejeitando URLs adulteradas);
    2. Se o hash SHA-256 de `raw_text` confere com o `sha256` registrado (rejeitando caches adulterados);
    3. Se a estrutura do GeoJSON `raw` satisfaz a validação topológica e semântica de schema (rejeitando coordenadas inválidas, anéis abertos ou atributos ausentes).
  - Qualquer inconsistência rejeita o cache, sinalizando status `unavailable` e prevenindo o uso de dados corrompidos.
- **Escrita Atômica Concorrente e Resiliência contra Quedas**:
  - A persistência é realizada em arquivo temporário com identificador único baseado no PID do processo e UUID randômico (`.{source_id}_{pid}_{uuid}.tmp`), realizando `f.flush()`, `os.fsync()` e substituição atômica via `os.replace`. Isso elimina condições de corrida entre escritas paralelas ou concorrentes.
  - Em caso de falha de conexão durante o `refresh=True`, o cache anterior válido é preservado, porém o estado `stale` é persistido em disco com data da tentativa (`last_attempt_at`) e mensagem de erro (`error`), mantendo intacta a data original de coleta (`fetched_at`). Chamadas subsequentes a `get(refresh=False)` reportam com honestidade o status `stale` e o último erro registrado.

---

## 2. Relação das Fontes Integradas e Snapshots Reais

### 2.1. IBGE Malha Municipal - Itacoatiara (1301902)
- **Identificador**: `ibge_municipality`
- **Órgão Produtor**: Instituto Brasileiro de Geografia e Estatística (IBGE)
- **URL Homologada**: `https://servicodados.ibge.gov.br/api/v3/malhas/municipios/1301902?formato=application/vnd.geo+json&qualidade=minima`
- **URL de Metadados / Localidades**: `https://servicodados.ibge.gov.br/api/v1/localidades/municipios/1301902` (Município de Itacoatiara, Microrregião 13009, Mesorregião 1303 Centro Amazonense, UF 13 AM).
- **Sistema de Coordenadas (CRS)**: As malhas digitais do IBGE são oficialmente referenciadas no **SIRGAS 2000 (EPSG:4674)**. Quando disponibilizadas no formato GeoJSON pela API de Malhas (RFC 7946), as coordenadas geográficas (longitude, latitude) são compatíveis com o elipsoide WGS 84 (EPSG:4326), apresentando discrepâncias submétricas desprezíveis para fins de zoneamento territorial.
- **Licença / Termos de Uso e Atribuição**: Dados Abertos Governamentais (Lei de Acesso à Informação nº 12.527/2011 e Política de Disseminação de Informações do IBGE).
  - *Atribuição*: "Fonte: IBGE - Malha Municipal Digital 2023 / Coordenação de Estruturas Territoriais".
- **Snapshot Real em Disco (`data/sources/ibge_municipality.json`)**:
  - **Data de Obtenção (UTC)**: `2026-11-05T21:40:07Z`
  - **Hash SHA-256 do `raw_text`**: `32fe08dca65ab31e07f4692ab5d56202f86dc16e9c1c614e52646d3ebee36fa3`
  - **Feições Contidas**: 1 Polígono
  - **Validação Específica**: Presença obrigatória da propriedade `codarea` igual a `"1301902"`.

### 2.2. IBGE Malha Estadual - Amazonas (13)
- **Identificador**: `ibge_state`
- **Órgão Produtor**: Instituto Brasileiro de Geografia e Estatística (IBGE)
- **URL Homologada**: `https://servicodados.ibge.gov.br/api/v3/malhas/estados/13?formato=application/vnd.geo+json&qualidade=minima`
- **Sistema de Coordenadas (CRS)**: **SIRGAS 2000 (EPSG:4674)**, disponibilizado em GeoJSON compatível com WGS 84 (EPSG:4326).
- **Licença / Termos de Uso e Atribuição**: Dados Abertos Governamentais (IBGE).
  - *Atribuição*: "Fonte: IBGE - Malha Estadual Digital 2023".
- **Snapshot Real em Disco (`data/sources/ibge_state.json`)**:
  - **Data de Obtenção (UTC)**: `2026-11-05T21:40:07Z`
  - **Hash SHA-256 do `raw_text`**: `057d94f482bf2885301245a4f5eed7cb56432636f594228e0448eadab22afc03`
  - **Feições Contidas**: 1 Polígono
  - **Validação Específica**: Presença obrigatória da propriedade `codarea` igual a `"13"`.

### 2.3. INPE TerraBrasilis - DETER Amazônia (Alertas de Cobertura Florestal)
- **Identificador**: `deter_alerts`
- **Órgão Produtor**: Instituto Nacional de Pesquisas Espaciais (INPE) / Plataforma TerraBrasilis
- **Serviço**: OGC Web Feature Service (WFS 2.0.0)
- **URL Homologada**: `https://terrabrasilis.dpi.inpe.br/geoserver/deter-amz/ows?service=WFS&version=2.0.0&request=GetFeature&typeNames=deter-amz:deter_amz&outputFormat=application%2Fjson&count=200&sortBy=view_date%20D&CQL_FILTER=mun_geocod%3D%271301902%27&srsName=EPSG:4326`
- **Filtro Aplicado**: `CQL_FILTER=mun_geocod='1301902'` (Itacoatiara / AM)
- **Ordenação**: `sortBy=view_date D` (alertas mais recentes primeiro)
- **Sistema de Coordenadas (CRS)**: Solicitado explicitamente como `srsName=EPSG:4326` (WGS 84), e confirmado na resposta do serviço WFS sob o URN `urn:ogc:def:crs:EPSG::4326`.
- **Licença / Termos de Uso e Atribuição**: Dados Públicos Governamentais (Decreto Federal nº 8.777/2016 e Política de Dados Abertos do INPE).
  - *Atribuição*: "Fonte: INPE/TerraBrasilis - Sistema DETER Amazônia".
- **Snapshot Real em Disco (`data/sources/deter_alerts.json`)**:
  - **Data de Obtenção (UTC)**: `2026-11-05T21:40:09Z`
  - **Hash SHA-256 do `raw_text`**: `a5817e7305558050c456598eff651ce69ae4fce52a42669a2835c3857adfbddb`
  - **Feições Retornadas (`feature_count`)**: 200 MultiPolígonos
  - **Total Disponível na Base do INPE (`total_available`)**: 815 registros
  - **Indicador de Recorte Parcial (`partial`)**: `True` (amostragem intencional das 200 ocorrências mais recentes, evitando tráfego de massa de dados e mantendo a métrica do total disponível estritamente honesta).
  - **Intervalo Temporal dos Registros**: 08/10/2024 a 23/10/2026.
  - **Composição dos Alertas no Snapshot**:
    * `DESMATAMENTO_CR` (Corte Raso): 116 ocorrências
    * `CICATRIZ_DE_QUEIMADA`: 53 ocorrências
    * `CS_DESORDENADO` (Corte Seletivo Desordenado): 22 ocorrências
    * `DEGRADACAO`: 8 ocorrências
    * `DESMATAMENTO_VEG` (Supressão com Vegetação Secundária): 1 ocorrência
  - **Validação Específica**: Cada alerta deve conter obrigatoriamente `uf == 'AM'`, `mun_geocod == '1301902'`, data de visualização (`view_date`) e identificador (`gid` ou `id`).

---

## 3. Diretrizes Metodológicas e Ressalvas Regulatórias

> [!IMPORTANT]
> **Aproximação Geométrica no Plano Local vs. Medição Geodésica Legal**:
> O cálculo de interseção implementado em [`spatial_context`](file:///C:/Users/orugi/Documents/Projetos/Hackathon/RAIZTRACE/integrations.py) adota o método de aproximação bidimensional em projeção plana local (*local planar ray-casting and segment intersection*).
> Este método trata com precisão topológica anéis exteriores, anéis interiores (furos/orifícios), arestas coincidentes e geometrias multipoligonais. No entanto, por operar diretamente nas coordenadas angulares projetadas localmente sem computação de geodésicas elipsoidais geocêntricas (como fórmulas de Vincenty ou Karney), **não deve ser divulgado ou interpretado como determinação com precisão geodésica exata legal**, servindo como filtro computacional preliminar de triagem e sobreposição.

> [!WARNING]
> **DETER é alerta indicativo de satélite e não laudo pericial**:
> 1. O Sistema de Detecção de Desmatamento em Tempo Real (DETER) foi concebido pelo INPE exclusivamente para orientar ações táticas de fiscalização em campo executadas pelo IBAMA e órgãos ambientais estaduais (SEMA/AM).
> 2. Seus dados derivam de sensores orbitais de resolução temporal diária ou quase diária (WFI e AWFI nos satélites CBERS-4 e Amazonia-1), com limites de resolução espacial e tolerância posicional.
> 3. Os alertas **não constituem laudo pericial de infração ambiental**, não comprovam dano definitivo nem produzem presunção automática de infração ou culpa penal/administrativa.
> 4. O mapeamento oficial e conclusivo das taxas anuais de desmatamento para a Amazônia Legal é de atribuição do projeto **PRODES** (INPE), realizado após a estação seca com sensores de alta resolução.

> [!CAUTION]
> **Ausência de alertas NÃO comprova regularidade fundiária ou ambiental**:
> A inexistência de sobreposição entre uma determinada coordenada/polígono e os alertas DETER **não certifica e não atesta** que o imóvel, concessão florestal ou lote esteja regular do ponto de vista ambiental, fiscal ou florestal. Limitações físicas como cobertura persistente de nuvens, queima sob dossel contínuo ou intervenções menores que a área mínima de amostragem do sensor podem não ser detectadas pelo DETER. A conformidade regulatória plena (inclusive para fins de exportação internacional, e.g. EUDR) depende obrigatoriamente de consulta ao Cadastro Ambiental Rural (CAR), certidões dos órgãos ambientais e auditoria da cadeia de custódia.

> [!NOTE]
> **Polígonos de Origem têm Natureza Técnica Demonstrativa**:
> Qualquer polígono de origem empregado nos testes ou no demonstrador possui caráter demonstrativo e não representa propriedade rural certificada pelo INCRA. Nenhuma sobreposição computacional gerada pelo sistema é capaz de produzir acusação de infração ou atestado regulatório sem verificação documental e pericial pelos órgãos competentes.
