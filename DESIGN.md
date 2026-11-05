# RAIZTRACE — sistema visual

Superfície única em modo operacional: o território é a entrada da conciliação. Fonte de verdade dos valores: [styles.css](static/styles.css) (`:root`).

## Composição
- Desktop: cabeçalho de 72px verde-floresta → trilho de navegação de 76px → mapa (cerca de 2/3) → painel do dossiê com 360px.
- Celular (≤ 768px): mapa com 380px de altura acima do painel, navegação inferior compacta e sem rolagem horizontal.
- O mapa é o protagonista. O dossiê responde à seleção (área → lote → carga → evidência). Os outros módulos (Cargas, Revisão, Laboratório, Histórico) ficam em abas que reutilizam o mesmo shell.

## Cores
| Token | Valor | Uso |
|---|---|---|
| `--color-forest` | #173a2c | cabeçalho, tinta principal, limites IBGE |
| `--color-forest-dark` | #0e261d | trilho de navegação |
| `--color-surface-reading` | #f3f4e8 | fundo de leitura (papel) |
| `--color-surface-white` | #ffffff | painéis |
| `--color-lime` | #c5f67c | seleção, parcela demonstrativa, foco |
| `--color-amber` / bg | #78350f / #fffbeb | incerteza, avisos de dado simulado |
| alertas DETER (mapa) | #b45309 / #d97706 | geometrias reais do INPE |
| `--color-error` | #991b1b | bloqueio de saldo, erros |

Nenhuma informação depende só da cor: estados combinam texto explícito (BLOQUEADO, Divergente, Não avaliado).

## Tipografia
- Títulos de seção: Georgia (serifa editorial herdada do pitch), sem eyebrow acima.
- Corpo e controles: fonte sans do sistema, 14–15px. Mínimo de 12px para fontes e datas.
- Números de volume, massa e hash usam `font-variant-numeric: tabular-nums`. A fonte mono só aparece em hash e identificadores.

## Cartografia
- A base OSM é opcional (pede rede) e pode ser desligada; os vetores locais garantem o funcionamento offline.
- Camadas: limite municipal e estadual (IBGE), alertas DETER (INPE) e cenário demonstrativo (contorno tracejado, preenchimento lima). A legenda e o carimbo de fonte com data de consulta e da última observação ficam sobre o mapa.
- A área fictícia nunca é rotulada como imóvel real, e a linha logística é "ilustrativa, não navegável".

## Movimento e estados
Transições curtas de seleção (destaque do caminho de custódia) respeitam `prefers-reduced-motion`. Estados obrigatórios: carregando, erro recuperável, vazio, bloqueado e não avaliado.

## Proibições aplicadas
Sem gradiente em texto, emojis como ícones, cards aninhados, sombras duras, eyebrow acima de título ou métricas-herói decorativas. Ícones em SVG com traço uniforme.
