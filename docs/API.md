# API RAIZTRACE · contrato 1.0.0

HTTP JSON local em `http://127.0.0.1:8765`. `py -3 app.py --port 8765` inicia o servidor; não expor em rede pública. Python 3.10+; somente biblioteca padrão em execução.

## Convenções

POST requer `Content-Type: application/json`, corpo objeto de até65536 bytes. Volume em m³ (até3 casas), estoque em inteiros de milésimos de m³, massas em kg, moeda BRL decimal com duas casas. Datas ISO8601 UTC. GeoJSON usa longitude antes de latitude. Versão do esquema no passaporte; alterações incompatíveis exigem nova versão. Não há declaração de conformidade EPCIS/GDSP, GeoID oficial ou assinatura digital.

Erros: `{"error":{"code":"validation_error","message":"Explicação"}}`. 400 JSON inválido; 403 origem/Host não local; 404 recurso desconhecido; 409 conflito de saldo/idempotência/revisão; 413 tamanho inválido; 415 tipo inadequado; 422 campos inválidos. Não há autenticação/perfis nesta versão local.

| Método | Rota | Resultado |
|---|---|---|
| GET | `/api/health` | Nome, versão e escopo local |
| GET | `/api/state` | Lotes, reservas/passaportes, análises, eventos e verificação de cadeia |
| POST | `/api/shipments` | Reserva indivisível e passaporte201; requer `Idempotency-Key` |
| GET | `/api/passports/{id}` | Mesmo JSON armazenado, sem recalcular saldo histórico |
| GET | `/passport/{id}` | Visualização legível imprimível do mesmo registro |
| POST | `/api/weigh` | Massa líquida e comparação com faixa hipotética |
| POST | `/api/inventory` | Volume geométrico didático, sem crédito |
| POST | `/api/assessments` | Cálculo SIM-001, sem validade jurídica;201 |
| POST | `/api/review` | Revisão motivada definitiva, sem ato oficial |
| GET | `/api/audit` | Verifica cadeia SHA256 local |
| GET | `/api/territory` | Snapshots reais IBGE/DETER, cenário fictício separado e cruzamento |
| POST | `/api/sources/refresh` | Consulta URLs fixas, valida e atualiza fontes; indisponibilidade explícita |
| GET | `/api/ml/model` | Configuração/aviso/métricas do laboratório sintético |
| POST | `/api/ml` | Perfil artificial ou abstenção; não identifica espécie |

## Reserva e idempotência

```http
POST /api/shipments
Content-Type: application/json
Idempotency-Key: demo-carga-001

{"lot_id":"AM-DEMO-001","volume_m3":"10","recipient":"Cooperativa demonstrativa","vehicle":"VEICULO-DEMO","invoice":"NF-DEMO-001","gross_kg":20000,"tare_kg":12000}
```

Repetir mesma chave/conteúdo normalizado retorna o mesmo passaporte, sem novo débito. Nova chave é outra operação: com5m³ disponíveis, pedir10 retorna409 `insufficient_balance`. Mesma chave/outro conteúdo retorna409 `idempotency_conflict`. Não há cancelamento ou remoção de histórico nesta versão. O passaporte é um retrato, não documento oficial. O cliente deve guardar chave e conteúdo até resolver falha de rede ambígua.

Estrutura completa: [JSON Schema](passport.schema.json). O hash é SHA256 do JSON canônico UTF8 sem campo hash (`sort_keys=True`, `separators=(',', ':')`, `ensure_ascii=False`). Não equivale a assinatura nem garante a verdade da declaração.

## Cálculos

`POST /api/weigh`: `{"volume_m3":10,"gross_kg":25000,"tare_kg":12000}` → líquido13000kg, hipótese6500–9500kg, divergência3500kg. A faixa650–950kg/m³ não é certificada por espécie nem intervalo estatístico.

`POST /api/inventory`: `{"diameter_cm":60,"height_m":15,"form_factor":0.7}` → aproximadamente2,9688m³. Equação `π × (DAP/100)² × H × f / 4`. Mede exemplo de fuste, não total do terreno, carbono ou volume autorizado.

`POST /api/assessments`: `{"quantity_m3":5,"hypothesis":"Hipótese de demonstração","reviewer":"Revisor demo"}` → SIM-001v1.0; multa fictícia `5×300=1500.00`, taxa fictícia `50+5×2=60.00`; separadas, não cobradas. Não implementa art47 ou tabela estadual.

`POST /api/review`: `{"assessment_id":"ID_RETORNADO","decision":"disagree","reviewer":"Revisor demo","reason":"Solicitar evidência adicional antes de enquadrar."}`. `agree` e `disagree` são opiniões sobre a simulação, não poderes administrativos.

`POST /api/ml`: `{"features":[999,999,999]}` → inconclusivo. Features artificiais `sinal_1/2/3`, classesA/B/C. Nunca enviar foto esperando identificação botânica. Entradas devem ser três números finitos, magnitude≤10¹².

## Fontes e cobertura

Leia [fontes e proveniência](SOURCES.md). Fontes têm URL fixa, hash, data de obtenção, quantidade e status. `live` significa resposta consultada agora; `cached` é snapshot; `stale` conserva última resposta válida após falha; `unavailable` não possui dado válido. DETER limitado aos200 alertas mais recentes do município; recorte parcial não é contagem de todo o município. `view_date` é observação, diferente da consulta.

### Cruzamento territorial em `GET /api/territory`

- `spatial`: interseção entre a área demonstrativa e os polígonos DETER carregados. O status é `evaluated`, `evaluated_partial` (recorte de 200) ou `not_evaluated` (fonte indisponível).
- `proximity`: distância em km da borda da área até cada alerta (plano local equiretangular). Traz `nearest`, os 5 alertas mais próximos (`closest`), contagens nos raios de 5, 10 e 20 km (`within`), `alerts_evaluated`, `plot_inside_municipality` (teste contra o limite IBGE), `source_fetched_at`, `partial` e `total_available`. Quando a fonte de alertas está indisponível, vale `null`.

Exemplo com o snapshot distribuído (consulta em 05/11/2026): 0 sobreposições; alerta mais próximo a cerca de 3,4 km (CICATRIZ_DE_QUEIMADA, observado em 08/10/2026); 1 alerta em até 5 km. A proximidade serve para priorizar a conferência e não atribui autoria.

O cruzamento compara geometria fictícia com alertas reais, considerando furos e segmentos no plano local. Não identifica autoria, ocupante, legalidade, infração ou retirada individual de árvore. `not_evaluated` significa falta de fonte, nunca ausência de risco. DOF/Sinaflor/WHISP não são consultados nesta entrega.
