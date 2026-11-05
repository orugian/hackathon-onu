# Relatório de Execução e Robustez - GEO-01 (Rodada 2)

**Data de Conclusão**: 2026-11-05  
**Escopo**: `integrations.py`, `tests/test_integrations.py`, `docs/SOURCES.md`, `data/sources/*`, `.orchestration/geo-report.md`  
**Tecnologia**: Python 3.11 Standard Library exclusivamente. Sem dependências externas. Sem subagentes.

---

## 1. Métricas de Testes e TDD Vertical

- **Total de Testes Unitários e de Integração**: 33 testes implementados e passando com 100% de sucesso.
- **Comando de Verificação**: `python -m unittest tests/test_integrations.py -v`
- **Tempo de Execução**: ~0.3s a 0.5s
- **Distribuição dos Testes**:
  * `TestIntegrationsAllowlistAndLimits`: 2 testes (Allowlist estrita e teto de 8 MB).
  * `TestIntegrationsCacheOffline`: 5 testes (Ausência de cache, cache offline, rejeição de cache adulterado, rejeição de URL não confiável e validação de schema ao carregar cache).
  * `TestIntegrationsLiveRefreshAndResilience`: 6 testes (Refresh atômico com sucesso, preservação de stale em falha de refresh, persistência do estado stale para `get(False)` subsequente, preservação de `fetched_at` e registro datado de `last_attempt_at`, falha sem cache, não captura de `KeyboardInterrupt` e proteção contra descompressão desmedida gzip).
  * `TestIntegrationsValidation`: 12 testes (Rejeição de booleanos em coordenadas, rejeição de Inf/NaN, rejeição de anel aberto, rejeição de anel com < 4 posições, rejeição de posições com contagem != 2, rejeição de GeoJSON não FeatureCollection, propriedades obrigatórias ausentes em IBGE e DETER, rejeição de UF diferente de AM e código municipal incorreto).
  * `TestIntegrationsSpatialContext`: 7 testes (Disjunto, interseção, furo em alerta donut, furo na geometria de origem com alerta interno, falso positivo de bounding box, MultiPolígono em origem e alerta, declaração explícita de aproximação planar local).
  * `TestIntegrationsRealSnapshots`: 1 teste (Validação ponta a ponta dos snapshots reais em disco: integridade criptográfica SHA-256 do `raw_text`, carimbos UTC e análise espacial).

---

## 2. Robustez Implementada Conforme Revisão do Orquestrador

1. **Envelope de Proveniência Fiel e Validação de Integridade Criptográfica**:
   - `_load_cache` não confia mais cegamente nos arquivos em disco.
   - O envelope armazena `raw_text` (conteúdo UTF-8 exato recebido da rede), `raw` (objeto FeatureCollection derivado) e `sha256` calculado sobre os bytes do `raw_text`.
   - Ao carregar:
     * Compara o hash do `raw_text` com o `sha256` registrado.
     * Valida a URL gravada contra `ALLOWED_URLS[source_id]`.
     * Valida o schema e as coordenadas com `validate_fc_structure`.
     * Qualquer discrepância resulta na rejeição do cache (`status: unavailable`), impedindo adulteração de dados.
2. **Persistência do Estado `stale` e Isolamento de Tentativas**:
   - Quando ocorre falha durante `refresh=True`, o último dado válido é preservado.
   - O estado `stale` é gravado no envelope com a data da tentativa (`last_attempt_at`) e a mensagem de falha (`error`).
   - O carimbo original `fetched_at` é rigorosamente preservado (não é sobrescrito).
   - Chamadas subsequentes a `get(refresh=False)` mantêm e reportam o status `stale` de forma honesta e transparente.
3. **Escrita Concorrente Segura**:
   - `_atomic_save_cache` utiliza arquivos temporários exclusivos (`.{source_id}_{pid}_{uuid}.tmp`), realizando `f.flush()`, `os.fsync()` e substituição atômica via `os.replace`.
   - Elimina colisões e condições de corrida entre processos paralelos.
4. **Validação Estrita de Geometria e Propriedades**:
   - Rejeição de tipos booleanos nas coordenadas (tratando a subclasse `bool` de `int` em Python).
   - Exigência de anéis fechados com pelo menos 4 posições (`ring[0] == ring[-1]` e `len >= 4`).
   - Posições limitadas a pares finitos numéricos `[lon, lat]` dentro dos limites válidos `[-180, 180]` e `[-90, 90]`.
   - Validação mandatória de propriedades: `codarea` obrigatório no IBGE (`1301902` e `13`); `uf == 'AM'`, `mun_geocod == '1301902'`, `view_date` e identificador (`gid`/`id`) obrigatórios no DETER.
5. **Proteção contra Gzip Bomb e Não Captura de `KeyboardInterrupt`**:
   - Método `safe_decompress_gzip` lê em blocos limitados (64 KB) até o teto de 8 MB (`MAX_PAYLOAD_BYTES`), abortando com `ValueError` antes de expansão descontrolada na memória.
   - `KeyboardInterrupt` é re-lançado imediatamente, preservando a capacidade de interrupção pelo operador (`Ctrl+C`).
6. **Aproximação Planar Local em `spatial_context`**:
   - O método declara formalmente `method: "local_planar_approximation_ray_casting"` e ressalva em `notice` que a análise opera em projeção de plano local, sem alegações de precisão geodésica exata legal.
   - Suporte verificado a polígonos de origem com furos interiores, MultiPolígonos e casos de borda.

---

## 3. Auditoria dos Snapshots Reais Coletados

Todos os dados presentes em `data/sources/` foram obtidos diretamente dos endpoints governamentais autorizados através do pipeline de refresh do `SourceService`:

| Identificador | Órgão / Fonte | Recorte / Filtro | Feições | Total Base | Parcial | Data Coleta (UTC) | Hash SHA-256 (`raw_text`) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `ibge_municipality` | IBGE Malhas | Itacoatiara (`1301902`) | 1 | 1 | `False` | 2026-11-05T21:40:07Z | `32fe08dca65ab31e07f4692ab5d56202f86dc16e9c1c614e52646d3ebee36fa3` |
| `ibge_state` | IBGE Malhas | Amazonas (`13`) | 1 | 1 | `False` | 2026-11-05T21:40:07Z | `057d94f482bf2885301245a4f5eed7cb56432636f594228e0448eadab22afc03` |
| `deter_alerts` | INPE TerraBrasilis | Itacoatiara (`1301902`) | 200 | 815 | `True` | 2026-11-05T21:40:09Z | `a5817e7305558050c456598eff651ce69ae4fce52a42669a2835c3857adfbddb` |

### Detalhamento dos Alertas DETER Reais
- **Janela Temporal dos Registros Coletados**: 08/10/2024 até 23/10/2026.
- **Classes Identificadas**:
  * `DESMATAMENTO_CR` (Corte Raso): 116 alertas
  * `CICATRIZ_DE_QUEIMADA`: 53 alertas
  * `CS_DESORDENADO` (Corte Seletivo Desordenado): 22 alertas
  * `DEGRADACAO`: 8 alertas
  * `DESMATAMENTO_VEG` (Supressão com Vegetação Secundária): 1 alerta
- **Sistemas de Coordenadas (CRS)**:
  * IBGE: SIRGAS 2000 (EPSG:4674), servido em GeoJSON compatível com WGS 84 (EPSG:4326).
  * DETER: WFS solicitado explicitamente em EPSG:4326 (WGS 84), confirmado no cabeçalho do serviço.

---

## 4. Conformidade Regulatória e Metodológica
- A documentação completa das fontes, políticas de acesso, termos de licença e ressalvas foi integralmente atualizada em [`docs/SOURCES.md`](file:///C:/Users/orugi/Documents/Projetos/Hackathon/RAIZTRACE/docs/SOURCES.md).
- Destaca-se que alertas DETER são ferramentas táticas de fiscalização em campo e não constituem laudo pericial definitivo de infração; de forma análoga, a ausência de alertas não atesta regularidade fundiária ou ambiental do imóvel.
