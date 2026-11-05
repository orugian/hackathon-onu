# FRONTEND-01 rodada 3 (última delegada) — integração app.js ↔ index.html

Escopo exclusivo: static/app.js, static/index.html, static/styles.css, static/map.js, tests/ui.integration.spec.js, .orchestration/frontend-report.md. NÃO altere Python, playwright.config.js, documents.py, passport.*. Sem subagentes. Sem exclusão de arquivos.

## Diagnóstico do orquestrador (verificado)
A rodada 2 alterou index.html/map.js/styles.css mas NÃO atualizou static/app.js (data 18:33, rodada 1). Resultado no navegador real: /api/state, /api/territory e /api/ml/model respondem 200, porém o badge continua "Integridade: 100% íntegro (1 eventos)" e #btn-submit-shipment fica disabled para sempre. Comando de prova: `node .orchestration/diag.cjs` (servidor em http://127.0.0.1:8765 já rodando).

`npx playwright test tests/ui.integration.spec.js --reporter=line` (servidor próprio 8766, banco novo, sem mocks) hoje: 4 passam, 6 falham:
1. badge deve conter "Cadeia verificada · N eventos" (dados reais de /api/state integrity.valid/count); se integrity.valid=false mostrar "Cadeia com divergência" ; antes de carregar "Verificando cadeia…"; erro de rede "Estado indisponível — tentar novamente" com botão.
3. #deter-counter-badge deve refletir filtro: ex "53 de 200 alertas · CICATRIZ_DE_QUEIMADA (recorte de 815 na fonte)". Use total_available da fonte deter_alerts.
4. Reserva: habilitar #btn-submit-shipment quando estado válido; desabilitar só durante envio. Sucesso: feedback "Passaporte emitido com sucesso", saldo atualizado em [data-testid="available-volume"] via novo /api/state.
5. Segunda reserva 409 insufficient_balance: mostrar message do backend (contém "insuficiente"), saldo permanece.
6. Tabela de passaportes: link a.passport-download-btn href=/api/passports/{id} download="passaporte-{id}.json"; a.passport-print-btn href=/passport/{id} target=_blank rel=noopener.
10. Abas: roving tabindex (selecionada tabindex=0, demais -1), ArrowDown/ArrowRight próxima, ArrowUp/ArrowLeft anterior, Home/End, foco move E seleciona. Nós de custódia devem ser <button class="custody-node"> (≥4).
Marque o describe como test.describe.serial (testes 4→5→6 dependem da ordem). Ajuste teste 7 para o cenário do documento: volume 10, bruto 25000, tara 12000 → "Divergente" e diferença "3.500".

## Cruzamento territorial (NOVO no backend, já disponível em GET /api/territory)
Chave `proximity`: {method, nearest:{gid,distance_km,classname,view_date}, closest:[até5 iguais], within:[{radius_km:5,count},{radius_km:10,count},{radius_km:20,count}], alerts_evaluated, plot_inside_municipality, source_fetched_at, partial, total_available, notice} ou null se fonte indisponível. Chave `spatial`: {status:'evaluated'|'evaluated_partial'|'not_evaluated', count, intersections, method, notice, source_fetched_at}.
Valores atuais reais: 0 sobreposições; alerta mais próximo ≈3,4 km (CICATRIZ_DE_QUEIMADA 2026-10-08); 1 alerta ≤5 km; 19 ≤15 km.
Renderize no painel "Sobreposição territorial" do território: linha "Sobreposição com a área: 0 alertas (recorte de 200 de 815)", "Alerta mais próximo: 3,4 km · classe · data", contagens por raio 5/10/20 km, lista dos 5 mais próximos como <button> que focam a geometria do alerta no mapa (fitBounds) e abrem o detalhe; "Área dentro do município IBGE: sim". Se null/not_evaluated: "Não avaliado — fonte indisponível. Ausência de dados não confirma regularidade." Exibir notice curto. Nunca linguagem de culpa ou aprovação. Teste no ui.integration.spec.js que o painel mostra "km" e um botão de alerta próximo foca o mapa (data-zoom aumenta).

## Correções visuais confirmadas por captura (.impeccable/review/*.png)
- Mobile 390px: marca "RAIZTRACE" colide com o badge no cabeçalho — badge abaixo ou abreviado; legenda "Convenções" cobre o mapa: recolher em <details> no mobile; barra de status do mapa sobreposta ao texto.
- Dossiê: linhas rótulo/valor alinhadas (dl em grid), valores tabulares; "15,000 m³" deve usar formato pt-BR "15,000"→ manter 3 casas mas com vírgula decimal: "15,000 m³" já é pt-BR (15 vírgula 000) OK.
- Datas de filtro: Consulta mostra "12:00 UTC" fixo inventado; usar fetched_at real da fonte.
- Botão "Reservar Carga Deste Lote" cinza desabilitado sem explicação: habilitado quando estado ok.
Preserve identidade verde, mapa protagonista e composição aprovada. Sem emojis, gradientes, kicker acima de título, cards aninhados, texto <12px.

## Rigor
TDD: ajuste/adicione o teste, rode RED, implemente, rode GREEN. Execute a suíte integrada completa ao final e cole o resumo real no relatório (sem inventar). Não use mocks/page.route para /api. Libere a porta 8766 se ocupada: só processos cujo CommandLine contenha "app.py --port 8766".
