# Model Card — RAIZTRACE Laboratório kNN Sintético (ML-01)

<!-- impeccable:model-card-schema 1 -->

## 1. Visão Geral do Modelo
- **Nome do Modelo:** Laboratório kNN Sintético com Abstenção (`ml.py`)
- **Versão:** `0.1.0`
- **Data:** Novembro de 2026
- **Stack & Dependências:** Python 3 standard library apenas (`math`, `random`, `json`, `typing`). Nenhuma dependência externa (sem numpy, sem scikit-learn, sem pandas).
- **Tipo de Algoritmo:** k-Nearest Neighbors ($k=3$) supervisionado em espaço euclidiano normalizado, com portas explícitas de abstenção por limiar de distância e consenso.

---

## 2. Finalidade e Escopo

### 2.1 Uso Pretendido
- Ambiente de laboratório e demonstração algorítmica para a plataforma **RAIZTRACE**.
- Validação conceitual de reconciliação e classificação geométrica com capacidade de abstenção (*rejection option*) diante de amostras desconhecidas, ruidosas ou com desacordo entre vizinhos.

### 2.2 Usos Estritamente Proibidos (Zero Validade Botânica ou Jurídica)
> [!CAUTION]
> **ESTE MODELO NÃO POSSUI VALIDADE BOTÂNICA, OPERACIONAL OU LEGAL.**
- **Não lê imagens:** Não processa fotografias macroscópicas ou microscópicas de estrutura anatômica de madeira.
- **Não identifica espécies botânicas reais:** Opera exclusivamente sobre rótulos artificiais (`A`, `B`, `C`) e variáveis sintéticas (`sinal_1`, `sinal_2`, `sinal_3`).
- **Não fundamenta decisões regulatórias ou fiscais:** Não substitui vistorias de campo, perícias botânicas do IBAMA/IPAAM nem sistemas oficiais como DOF+ e Sinaflor.
- **Não fabrica acurácia de campo:** A acurácia obtida é restrita ao conjunto sintético artificial de laboratório e não reflete desempenho no mundo real.

---

## 3. Esquema de Dados e Geração Sintética

### 3.1 Nomes de Features e Classes
- **Classes:** `['A', 'B', 'C']` (rótulos categóricos artificiais).
- **Features:** Três variáveis numéricas contínuas sem correspondência taxonômica:
  1. `sinal_1`
  2. `sinal_2`
  3. `sinal_3`
- Nenhuma feature é nomeada com referência a táxons florestais, famílias botânicas ou propriedades dendrológicas reais.

### 3.2 Partição e Determinismo
- **Gerador Determinístico:** Gerado via `random.Random(seed=42)`.
- **Contagem de Treino:** 90 amostras (30 amostras por classe).
- **Contagem de Teste:** 30 amostras (10 amostras por classe).
- **Total de Amostras:** 120 registros.
- **Identificadores Únicos:**
  - Treino: `syn_train_A_001` .. `syn_train_C_030`
  - Teste: `syn_test_A_001` .. `syn_test_C_010`
  - Separação estrita: interseção entre IDs de treino e teste é nula ($\emptyset$).

---

## 4. Pré-processamento e Prevenção de Vazamento (Non-Leakage)

1. **Separação Prévia:** A divisão entre treino (90) e teste (30) ocorre antes de qualquer ajuste estatístico.
2. **Ajuste Restrito ao Treino:** O normalizador Min-Max calcula parâmetros de escala ($\min_j$ e $\text{alcance}_j$) exclusivamente sobre as 90 amostras de treino.
3. **Transformação sem Refit:** As 30 amostras de teste e quaisquer vetores submetidos a `predict()` são transformados utilizando estritamente os parâmetros do treino, sem recálculo, garantindo ausência total de vazamento de dados (*data leakage*).

---

## 5. Tratamento de Entradas Ausentes e Inválidas

A função pública `predict(features)` valida exaustivamente os argumentos antes de qualquer operação:
- **Tipo e Comprimento:** Exige `list` com exatamente 3 elementos. Rejeita tuplas, dicionários, escalares e comprimentos diferentes de 3 com `ValueError`.
- **Rejeição de Booleanos:** Em Python, `bool` herda de `int`. A validação checa explicitamente `isinstance(val, bool)` e lança `ValueError`.
- **Rejeição de Nulos:** Valores `None` lançam `ValueError`.
- **Rejeição de Não-Numéricos:** Strings, objetos ou outros tipos lançam `ValueError`.
- **Rejeição de Infinitos e NaN:** `math.isnan(val)` ou `math.isinf(val)` lançam `ValueError`.
- **Faixa suportada:** valores com magnitude acima de 10¹² são rejeitados antes do cálculo de distância (evita `OverflowError`); a API HTTP também recusa inteiros acima de 10¹⁵.

> **Leitura correta das métricas:** a acurácia de 100% vem de três agrupamentos artificiais bem separados por construção. Ela demonstra que a avaliação e a abstenção funcionam, **não** que o método funcionaria em madeira real. Em campo, a separação de classes é muito menor e a métrica relevante é a taxa de abstenção somada ao recall por espécie, medidos em área e campanha independentes.

---

## 6. Regras de Decisão, Limiares e Abstenção

O modelo não força uma classificação cega caso a amostra esteja distante do domínio de treinamento ou haja discordância entre vizinhos.

### 6.1 Hiperparâmetros Fixados Antes da Avaliação
- **Número de Vizinhos:** $k = 3$.
- **Limiar de Distância Euclidiana Normalizada:** $\text{threshold}_{\text{dist}} = 0.50$.
- **Limiar de Consenso:** $\text{threshold}_{\text{consenso}} = 0.60$ (para $k=3$, exige que ao menos 2 dos 3 vizinhos concordem com a classe líder, sem empate).

### 6.2 Comportamento de Abstenção
Se $\text{distância} > 0.50$ OU $\text{concordância} < 0.60$:
- `status`: `'inconclusive'`
- `label`: `None` (serializado como `null` em JSON)

Exemplo: para a entrada anômala `[999.0, 999.0, 999.0]`, a distância calculada é $\approx 30.33 > 0.50$, resultando imediatamente em status inconclusivo.

> [!NOTE]
> **Concordância de Vizinhos $\neq$ Probabilidade Calibrada:**
> A métrica `neighbor_agreement` representa apenas a proporção de vizinhos mais próximos que votaram na classe majoritária ($\text{votos} / k$). Ela **não** representa probabilidade posterior calibrada ou grau de certeza bayesiana.

---

## 7. Métricas Obtidas no Split de Teste

Execução determinística com `seed=42`:

| Métrica | Valor Obtido |
| :--- | :--- |
| **Acurácia Geral** | `1.0000` (100% nas 30 amostras de teste) |
| **Macro F1-Score** | `1.0000` |
| **Taxa de Abstenção em Teste** | `0.0000` |
| **Recall Classe A** | `1.0000` (10/10) |
| **Recall Classe B** | `1.0000` (10/10) |
| **Recall Classe C** | `1.0000` (10/10) |
| **Abstenção em Outliers (`[999, 999, 999]`)** | `1.0000` (Abstenção correta) |

### Matriz de Confusão
Linhas: Classe Real (`A`, `B`, `C`); Colunas: Classe Predita (`A`, `B`, `C`):
```
           Predito A   Predito B   Predito C
Real A        10           0           0
Real B         0          10           0
Real C         0           0          10
```

---

## 8. Plano de Referência para Piloto Externo

Em um eventual piloto de campo com parceiros institucionais ou sensores físicos:
1. **Calibração Espectral/Física Real:** Coleta de espectros NIR/visível ou medições de densitometria padronizadas sob protocolo formal.
2. **Governança Taxonômica:** Auditoria botânica por taxonomistas credenciados com vouchers de herbário depositados.
3. **Curva de Abstenção Operacional:** Ajuste empírico dos limiares de distância de Mahalanobis e consenso com comitê humano de revisão para casos inconclusivos.
4. **Isolamento Funcional:** Manutenção da separação entre conciliação física de saldo e decisão legal expedida pelos órgãos competentes.
