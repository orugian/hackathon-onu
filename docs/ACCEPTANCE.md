# Critérios de aceite e evidências exigidas

O documento principal prevalece sobre a apresentação V1. Nada nesta lista é considerado concluído antes da verificação.

| Requisito | Evidência exigida |
|---|---|
| Execução Python stdlib offline | Inicialização sem pip/npm; testes e navegação com rede externa bloqueada |
| Dados reais visíveis | Snapshots IBGE e DETER obtidos na fonte, hashes/datas/URLs; camadas e seleção no navegador |
| Cenário fictício separado | Rótulos em área, lote, cargas, passaportes e ML; fontes oficiais não verificam autorização |
| Saldo 15/10/10 | Uma reserva aceita e outra409, sequencial e simultaneamente; saldo5 |
| Idempotência | Mesmo pedido/chave devolve passaporte anterior; conteúdo divergente409, sem débito |
| Precisão/unidades | Milésimos inteiros; 3×0,1 deixa14,7; inválidos/NaN/inf rejeitados |
| Pesagem | 20000−12000=8000kg; faixa6500–9500; 13000 diverge3500; sem tolerância inventada |
| Inventário | 60cm/15m/0,7 ≈2,9688m³; nunca vira crédito |
| Passaporte | ID, versão, UTC, origem/autorização fictícias, destinatário, veículo, fiscal, peso, saldo e SHA256; JSON e impressão do mesmo registro |
| SIM-001 | 5m³→multa1500/taxa60 separados, hipótese e revisor; revisão única motivada |
| Auditoria | Eventos persistidos/consultáveis, cadeia verificada; adulteração detectada no banco temporário |
| ML didático | 90 treino/30 teste sintéticos separados; métricas reproduzíveis; abstenção; cartão limitações |
| Contratos abertos | JSON Schema, GeoJSON, API versionada documentada, exemplos, MIT |
| Segurança local | Bind127.0.0.1, limites body, origem, validação, arquivos internos não expostos; sem alegar produção |
| UX operacional | Mapa interativo ligado ao dossiê, navegação, filtros, erros e loading; teclado e mobile |
| Entrega banca | README, roteiro5min, contribuição, plano piloto/ODS, ZIP sem DB operacional/credenciais/node_modules |
| Desempenho | Medir respostas reservas localmente; meta<1s é medida, não promessa |

## Exclusões do documento preservadas
Não emite DOF, não homologa regras reais, não cobra valores, não identifica espécies em imagens, não autentica cadastro oficial, não rastreia cada árvore via satélite, não sincroniza dispositivos, não oferece autenticação corporativa.
