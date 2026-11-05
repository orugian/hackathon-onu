# Relatório de validação — RAIZTRACE 1.0.0

Data: 05/11/2026. Ambiente: Windows, Python 3.14 (stdlib) e Chromium (Playwright 1.58). Os critérios vêm de [ACCEPTANCE.md](ACCEPTANCE.md) e do documento do desafio.

## Evidências

| Requisito | Evidência | Situação |
|---|---|---|
| Execução com Python stdlib, offline | Clone limpo em pasta temporária: `py -3 app.py` servindo `/`, `/api/state` e `/api/territory` a partir do snapshot, sem npm e sem rede | Atendido |
| Saldo 15/10/10 | `test_reserve_15_10_10_sequential`, `test_reservation_flow_preserves_balance_and_passport` e teste de navegador 4→5 | Atendido |
| Reservas simultâneas | `test_concurrency_http` (HTTP real, 2 threads, repetido 5×) e teste de domínio com várias threads | Atendido |
| Idempotência | Mesma chave e conteúdo: mesmo passaporte. Mesma chave e outro conteúdo: 409. Teste concorrente com a mesma chave | Atendido |
| Milésimos inteiros (3 × 0,1 → 14,7) | `test_reserve_three_times_point_one_exact_milli` | Atendido |
| Entradas inválidas (negativo, NaN, inf, enorme) | Testes de domínio, `test_numeric_limits` e `test_hostile_numbers...` (422/400 em vez de conexão derrubada) | Atendido |
| Pesagem 8.000 kg / divergência 3.500 kg | `test_calculations` e `test_weighing_http`; teste de navegador 7 | Atendido |
| Inventário 2,9688 m³ sem crédito | `test_inventory_returns_explained_volume_and_no_credit` | Atendido |
| Passaporte JSON + impressão do mesmo registro | Teste de recuperação e de `/passport/{id}` com hash e aviso; teste de escape XSS; teste de navegador 6 | Atendido |
| SIM-001 (R$ 1.500 / R$ 60) e revisão motivada única | `test_review_simulation_is_motivated_definitive_and_auditable`; teste de navegador 8 | Atendido |
| Trilha encadeada e adulteração detectada | Teste de domínio de adulteração e `/api/audit` | Atendido |
| ML 90/30 com abstenção | 17 testes `test_ml`; teste de navegador 9 | Atendido |
| Dados reais visíveis (IBGE + INPE) | Consulta ao vivo em 05/11/2026: IBGE 1+1 feições, DETER 200 de 815. Snapshots com SHA-256 de `raw_text` | Atendido |
| Fonte indisponível ≠ aprovação | `test_refresh_network_failure_is_explicit_not_validation` (`not_evaluated`, proximidade `null`) | Atendido |
| Cache adulterado | `test_cache_hardening` (campos derivados reconstruídos a partir do texto com hash; NaN deixa a fonte indisponível) | Atendido |
| Cruzamento territorial | `test_proximity` e `test_territory_with_real_snapshots_reports_proximity`; teste de navegador 11 (botão foca o alerta) | Atendido |
| Segurança local | Testes de Host, Origin, tipo de conteúdo, tamanho, travessia de caminho e cabeçalhos. Revisão de segurança independente aplicada (ver abaixo) | Atendido para uso local |
| UX: mapa e dossiê, teclado, celular | Testes de navegador 2, 3, 10 e 11; capturas em 1440 e 390 px sem rolagem horizontal; detector Impeccable | Atendido |
| Desempenho < 1 s | Reservas simultâneas medidas abaixo de 1 s | Medido localmente |
| MIT, API, esquema, model card, contribuição | [LICENSE](../LICENSE), [API](API.md), [esquema](passport.schema.json), [model card](MODEL_CARD.md), [contribuição](CONTRIBUTING.md) | Atendido |

Totais: **96 testes Python** e **20 testes de navegador** (9 de componentes com mocks e 11 integrados sem mocks), todos aprovados.

## Revisão de segurança (SEC-01) e correções

| Achado | Correção | Teste |
|---|---|---|
| `raw` do cache não era coberto pelo hash | GeoJSON e metadados reconstruídos a partir de `raw_text`, validado por SHA-256 | `test_cache_hardening` |
| Inteiros enormes e JSON profundo derrubavam a conexão | Limite de 10¹⁵, captura de `RecursionError` e resposta 500 em JSON como último recurso | `test_hostile_numbers...` |
| NaN e `totalFeatures` inválido vindos da fonte | `parse_constant` estrito e tipo inteiro obrigatório | `test_cache_hardening` |
| Redirecionamento podia contornar a allowlist | Redirecionamentos recusados; anuncia apenas `gzip` | Refresh real verificado |
| JSON sem `nosniff`/`no-store` | Cabeçalhos adicionados | `test_json_responses_carry_protective_headers` |
| Cliente lento prende thread | Não corrigido: risco baixo e apenas local, documentado | — |

## Dados simulados (declaração explícita)
São fictícios: a área AREA-DEMO-001 e sua geometria, árvore, pátio, ligação logística, destino, lote AM-DEMO-001 com 15 m³, autorização AUT-DEMO-001, destinatários, veículos, notas fiscais, pesagens digitadas, a regra SIM-001 e seus valores, e os perfis A/B/C do laboratório (`data/ml_synthetic.json`).

São reais: as malhas IBGE de Itacoatiara (1301902) e do Amazonas (13) e os 200 alertas DETER mais recentes de Itacoatiara (de 815 disponíveis), com URL, data de consulta e hash.

## Limitações conhecidas
- DOF+, Sinaflor, IPAAM, CAR, WHISP, balanças e sistemas fiscais não estão integrados; isso exige acesso autorizado e, em alguns casos, credenciais.
- O recorte DETER é parcial (200 de 815). Distâncias usam aproximação plana local, adequada à triagem mas não geodésica.
- Sem autenticação nem perfis: o servidor é para uso apenas em 127.0.0.1. A cadeia SHA-256 detecta alterações casuais, mas quem controla o banco pode reconstruí-la.
- A acurácia de 100% do laboratório reflete agrupamentos artificiais separados por construção; não indica desempenho em campo.
- A base OSM depende de internet. Sem rede, o mapa mostra apenas os vetores.
