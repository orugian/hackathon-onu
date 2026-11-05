# RAIZTRACE

Conciliação de evidências florestais para o Amazonas. Um mapa real de Itacoatiara conecta fontes públicas à demonstração de controle de saldo, pesagem, passaporte e revisão humana.

**Protótipo local, não sistema de autorização.** Lotes, parcelas operacionais, árvores, pátio, rota, cargas, referências fiscais, autorizações e perfis de ML são fictícios. Malhas IBGE e alertas DETER são dados reais consultados de fontes públicas, com proveniência. Não confundir uma camada territorial real com a validação de uma operação florestal.

## Executar

Requer Python3.10 ou mais recente. Não precisa instalar pacotes Python, Node, SQLite separado ou serviço pago.

```powershell
py -3 app.py
```

Abra **http://127.0.0.1:8765**. Em Linux/macOS, use `python3 app.py`.

O banco operacional é criado na primeira execução. Para uma nova demonstração, escolha **outro arquivo**, preservando o histórico anterior:

```powershell
py -3 app.py --port 8765 --db .runtime/banca-01.sqlite
```

Se a porta estiver ocupada, encerre a instância anterior comCtrl+C ou escolha `--port 8767`. Não apague o banco para reiniciar um ensaio.

## Roteiro de cinco minutos

1. **0:00–0:40 — Território:** mostre Itacoatiara, limite IBGE e alertas DETER. Selecione um alerta e leia data, classe e fonte. Explique que a área operacional é fictícia e o recorte de alertas é limitado.
2. **0:40–1:50 — Saldo:** com15m³ disponíveis, reserve10. O saldo passa a5. Solicite mais10 e mostre o bloqueio. Uma tentativa bloqueada não prova transporte nem crime.
3. **1:50–2:40 — Carga:** confira20000−12000=8000kg e hipótese6500–9500kg. Troque bruto para25000 e obtenha divergência3500kg. Exporte JSON e abra impressão do passaporte, com avisoSEM VALIDADE OFICIAL.
4. **2:40–3:25 — Laboratório:** inventário60cm/15m/0,7→2,9688m³ sem criar crédito. Teste perfis artificiais e exemplo distante com abstenção. Não há identificação botânica por foto.
5. **3:25–4:15 — Revisão:** simule5m³ naSIM-001: multa fictíciaR$1500 e taxa fictíciaR$60. Registre discordância motivada. Nada é cobrado ou autuado.
6. **4:15–5:00 — Evidências:** mostre eventos, verificação de hash, fontes/datas, testes e próximos passos do piloto.

## Offline e integrações

O núcleo funciona sem rede. Leaflet está distribuído localmente; os snapshots territoriais também. Os mosaicos de fundo OpenStreetMap precisam de internet e podem ser desligados, mantendo os vetores. Não há download em massa de tiles.

“Atualizar fontes” consulta IBGE e INPE. Erro de rede conserva o último dado válido e informa indisponibilidade; não confirma regularidade. Observe a diferença entre data da consulta e data da imagem/alerta. Ausência de alerta não garante ausência de exploração.

Não há integração operacional com DOF+, Sinaflor, IPAAM, WHISP, balança industrial, sistemas fiscais ou pagamentos. Essas integrações dependem de acesso autorizado, documentação e, quando aplicável, credenciais. Para usar operações reais, veja [plano de piloto](docs/PILOT.md).

## Por que SQLite?

Somente estoque, reservas, passaportes, simulações e eventos precisam de persistência transacional. SQLite já integra Python e garante reserva indivisível, idempotência e exclusão de concorrência. Um arquivoJSON ou localStorage exigiria implementar manualmente bloqueio e recuperação. Dados públicos continuam emJSON/GeoJSON, sem banco adicional.

## Testes e ferramentas opcionais

```powershell
py -3 -m unittest discover -s tests -v
py -3 ml.py
```

Testes usam bancos temporários, não o banco da apresentação. O laboratório reproduz os dados artificiais e suas métricas; desempenho perfeito nesse conjunto simples não é evidência de acurácia em campo.

Para desenvolvimento e testes reais de navegador (não necessários para usar o produto):

```powershell
npm ci
npx playwright install chromium
npm run test:ui
```

Os testes de navegador criam um banco novo a cada execução. [ui.spec.js](tests/ui.spec.js) testa componentes com respostas simuladas. Já [ui.integration.spec.js](tests/ui.integration.spec.js) não intercepta a API e exercita o fluxo completo contra o servidor real; somente os tiles OSM são bloqueados, para validar o modo offline.

Resultado verificado em 05/11/2026: **96 testes Python** e **20 testes de navegador** aprovados (11 integrados, sem mocks). A reserva concorrente via HTTP (duas de 10 m³ simultâneas contra 15 m³) foi repetida cinco vezes: em cada rodada, uma foi aceita, outra foi bloqueada e as respostas ficaram abaixo de 1 s. Um clone limpo, sem npm nem rede, inicializou e serviu os dados reais do snapshot.

## Cruzamento de dados

O painel "Sobreposição territorial" compara a área fictícia com os alertas DETER reais:
- sobreposição geométrica, respeitando furos e multipolígonos;
- distância em km até o alerta mais próximo e contagens nos raios de 5, 10 e 20 km;
- verificação de que a área está dentro do limite municipal IBGE.

Os cinco alertas mais próximos são botões que focam a geometria no mapa e mostram classe, data de observação, sensor e fonte. O resultado é uma **triagem para priorizar conferência**. Proximidade não é autoria, e ausência de alerta não é regularidade.

## Estrutura

- [Servidor](app.py): HTTP loopback, validação de protocolo e integração.
- [Domínio](domain.py): livro transacional, idempotência, passaportes, revisão e eventos.
- [Cálculos](calculations.py): pesagem e inventário explicáveis.
- [Fontes](integrations.py): adaptadores IBGE/INPE, cache e cruzamento geométrico.
- [Laboratório](ml.py): kNN sintético com abstenção.
- [Interface](static/index.html): mapa e operações; bibliotecas locais.
- [API](docs/API.md), [esquema](docs/passport.schema.json), [fontes](docs/SOURCES.md), [cartão do modelo](docs/MODEL_CARD.md), [contribuição](docs/CONTRIBUTING.md), [critérios de aceite](docs/ACCEPTANCE.md).

## Segurança e limites

Servidor apenas em127.0.0.1, sem autenticação: destinado à demonstração na própria máquina. Não publique via túnel/proxy na internet. Antes de produção: perfis de acesso, segregação de funções, proteção de coordenadas sensíveis, autenticação, backups, observabilidade e revisão técnica/jurídica.

SHA256 permite conferir consistência do conteúdo e da cadeia; quem controla o banco pode reconstruí-la. Banco coerente não transforma declaração falsa em verdade. Não há assinatura verificável externa, sincronia multi-dispositivo, OCR, emissão oficial ou identificação taxonômica por satélite.

Código [MIT](LICENSE). Leaflet e bases públicas conservam seus avisos e direitos. Documentos originais do desafio foram preservados.
