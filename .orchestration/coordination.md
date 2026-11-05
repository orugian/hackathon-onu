# Controle de orquestração

Chamadas nativas: 1 de 5 (SEC-01 revisão de segurança somente leitura). Agentes preferenciais agy gemini-3.8-flash-high.

## Rodadas
- ARCH-01 rodada 1: parecer recebido; parcialmente rejeitado. REAL no estoque, Smalian em substituição à fórmula do escopo, tolerância 15%, regra SIM-001 como bloqueio geral e mocks como integração não aprovados.
- UX-01 rodada 1: parecer recebido; composição mapa/painel aproveitada. Rejeitados localStorage como ledger, confiabilidade inventada, balança em m³, alegação de imutabilidade e precisão cartográfica fictícia.
- BACKEND-01 rodada 1: contrato em backend-task.md. Responsabilidade exclusiva domain.py, calculations.py e seus testes.

- BACKEND-01 rodada 1: timeout parcial (reserva ok; passport/assess/review ausentes). Rodada 2: concluída; 87 testes verificados pelo orquestrador.
- GEO-01 rodada 1: timeout parcial. Rodada 2: cache com hash de raw_text, stale persistente, snapshots reais (IBGE 2, DETER 200/815). Aceita após verificação.
- ML-01 rodada 1: aceita; orquestrador corrigiu overflow (teste test_numeric_limits).
- FRONTEND-01 rodada 1: timeout parcial; mapa enquadrava o AM inteiro, testes UI todos com mocks. Rodada 2 em andamento.
- Orquestrador direto: app.py (rotas, Host/Origin, estáticos, impressão), documents.py, proximidade espacial (tests/test_proximity.py), docs API/README/PILOT.

## Regra de revisão
Testes e inspeção independentes obrigatórios. Após três rodadas insatisfatórias de uma tarefa, orquestrador assume; teto de cinco tentativas. Não confiar em relato de teste sem executar. Sem exclusões destrutivas. Materiais originais preservados.

## Decisões confirmadas
Python + web local. Usuário exige dados reais visualizáveis e avaliar necessidade SQLite: mantém-se apenas para transações atômicas de estoque; fontes geográficas usam JSON/GeoJSON. Mapa principal/painel conectado e identidade do pitch aprovados. Operações sintéticas explicitamente diferenciadas da cartografia pública.
