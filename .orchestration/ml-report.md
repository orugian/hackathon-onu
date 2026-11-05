# Relatório de Execução — ML-01 (Rodada 1)

<!-- impeccable:ml-report 1 -->

## 1. Identificação e Escopo
- **Tarefa:** ML-01 — Laboratório kNN Sintético com Abstenção e Métricas
- **Rodada:** 1 de 3
- **Ambiente:** Python 3.11.15 (Windows), Standard Library apenas, sem pacotes externos.
- **Subagentes:** Nenhum subagente invocado (execução direta em sessão única).
- **Integridade do Repositório:** Apenas os 5 arquivos autorizados foram criados/modificados:
  1. `ml.py`
  2. `tests/test_ml.py`
  3. `docs/MODEL_CARD.md`
  4. `data/ml_synthetic.json`
  5. `.orchestration/ml-report.md`
  Nenhum dado operacional foi excluído ou sobrescrito.

---

## 2. Metodologia TDD Vertical (Ciclos RED → GREEN)

O desenvolvimento seguiu rigorosamente a abordagem de fatias verticais com ciclo RED inicial comprovado por terminal antes de cada incremento de código.

### Ciclo 1: Validação de Entrada em `predict(features)`
- **Teste RED:** `TestMLInputValidation` (rejeição de non-list, tamanho errado, bools, nan, inf, None, strings com `ValueError`).
  - Execução: `python -m unittest tests/test_ml.py`
  - Resultado: `ModuleNotFoundError: No module named 'ml'` (4 erros).
- **Implementação GREEN:** Criada validação `validate_features()` em `ml.py` com checagem estrita de `isinstance(x, bool)` e finitude matemática.
  - Resultado: 4 testes aprovados (0.014s).

### Ciclo 2: Geração Sintética e Separação de IDs
- **Teste RED:** `TestDatasetGeneration` (90 treino [30/classe], 30 teste [10/classe], 120 IDs únicos sem sobreposição, reprodutibilidade com seed 42, nomes abstratos `sinal_1/2/3`, sem termos botânicos).
  - Execução: `python -m unittest tests/test_ml.py`
  - Resultado: `ImportError: cannot import name 'generate_dataset' from 'ml'` (4 erros).
- **Implementação GREEN:** Implementado `generate_dataset(seed=42)` com centróides sintéticos e PRNG isolado.
  - Resultado: 8 testes aprovados (0.024s).

### Ciclo 3: Normalização e Prevenção de Vazamento (Anti-Leakage)
- **Teste RED:** `TestNormalizationAntiLeakage` (ajuste estrito de escala sobre os 90 registros de treino; teste usa parâmetros de treino sem refit; dados anômalos não alteram parâmetros de treino).
  - Execução: `python -m unittest tests/test_ml.py`
  - Resultado: `ImportError: cannot import name 'fit_scaler' from 'ml'` (1 erro).
- **Implementação GREEN:** Implementados `fit_scaler()` e `transform_features()` desacoplados.
  - Resultado: 9 testes aprovados (0.022s).

### Ciclo 4 e 5: Classificador kNN, Limiares e Abstenção
- **Teste RED:** `TestKNNPredictionAndAbstention` (schema de saída, acurácia em centróides, abstenção em `[999, 999, 999]`, abstenção por falta de consenso).
  - Execução: `python -m unittest tests/test_ml.py`
  - Resultado: `ImportError: cannot import name 'SyntheticKNN'`, falhas por stub (2 falhas, 1 erro).
- **Implementação GREEN:** Implementada classe `SyntheticKNN` com $k=3$, $\text{dist\_threshold}=0.50$, $\text{consensus\_threshold}=0.60$.
  - Resultado: 13 testes aprovados (0.024s).

### Ciclo 6: Contrato `train_and_evaluate()` e Métricas
- **Teste RED:** `TestTrainAndEvaluateContract` (validação de chaves de contrato, métricas `accuracy`, `macro_f1`, `recall_by_class`, `confusion_matrix`, `abstention_rate`, serialização JSON).
  - Execução: `python -m unittest tests/test_ml.py`
  - Resultado: `ImportError: cannot import name 'train_and_evaluate'` (3 erros).
- **Implementação GREEN:** Implementada função `train_and_evaluate()` com computação exata das métricas e serialização JSON nativa.
  - Resultado: 16 testes aprovados (0.049s).

### Ciclo 7: CLI Standalone e Relatório
- **Teste RED:** `TestCLIExecution` (execução via `subprocess` chamando `python ml.py`, verificação de stdout e escrita de `data/ml_synthetic.json`).
  - Execução: `python -m unittest tests/test_ml.py`
  - Resultado: `AssertionError: 'RELATÓRIO ML-01' not found in ''` (1 falha).
- **Implementação GREEN:** Implementado bloco `if __name__ == '__main__':` com geração segura de `data/ml_synthetic.json` e relatório formatado.
  - Resultado: 17 testes aprovados (0.454s).

---

## 3. Verificação do Contrato `ml.py`

| Requisito do Contrato | Status | Evidência / Implementação |
| :--- | :---: | :--- |
| `train_and_evaluate()` retorna dict serializável | **CONFORME** | Serialização `json.dumps()` testada e confirmada |
| `model_version: "0.1.0"` | **CONFORME** | Presente no dict de retorno |
| `train_count: 90` | **CONFORME** | 30 amostras por classe (A, B, C) |
| `test_count: 30` | **CONFORME** | 10 amostras por classe (A, B, C) |
| `classes: ['A', 'B', 'C']` | **CONFORME** | Classes categóricas artificiais |
| `features: ['sinal_1', 'sinal_2', 'sinal_3']` | **CONFORME** | 3 variáveis artificiais |
| Métricas (`accuracy`, `macro_f1`, `recall_by_class`, `confusion_matrix`, `abstention_rate`) | **CONFORME** | Todas calculadas e presentes no subdict `metrics` |
| `notice` de escopo | **CONFORME** | `Laboratório kNN sintético com perfis artificiais — SEM VALIDADE BOTÂNICA OU LEGAL` |
| `synthetic: true` | **CONFORME** | Booleano nativo `True` |
| Separação de IDs | **CONFORME** | 90 IDs de treino e 30 IDs de teste com interseção nula |
| Anti-leakage na normalização | **CONFORME** | Parâmetros ajustados unicamente no treino; teste sem refit |
| Nenhuma feature botânica real | **CONFORME** | Validado por teste unitário proibindo termos botânicos |
| Portas de abstenção (kNN) | **CONFORME** | $k=3$, limiar distância $0.50$, limiar consenso $0.60$ |
| Validação de entrada em `predict` | **CONFORME** | Rejeita `bool`, `nan`, `inf`, `None`, comprimentos != 3 com `ValueError` |
| Teste de abstenção em `[999, 999, 999]` | **CONFORME** | Retorna `status: 'inconclusive'`, `label: None` |
| `python ml.py` reproduz dados e imprime | **CONFORME** | Gera `data/ml_synthetic.json` sem sobrescrever dados operacionais |

---

## 4. Métricas Efetivamente Obtidas no Teste

Execução com `seed=42`:
```json
{
  "accuracy": 1.0,
  "macro_f1": 1.0,
  "abstention_rate": 0.0,
  "recall_by_class": {
    "A": 1.0,
    "B": 1.0,
    "C": 1.0
  },
  "confusion_matrix": [
    [10, 0, 0],
    [0, 10, 0],
    [0, 0, 10]
  ]
}
```

Comportamento com Outlier Extremo (`[999.0, 999.0, 999.0]`):
```json
{
  "label": null,
  "status": "inconclusive",
  "distance": 30.3267,
  "neighbor_agreement": 1.0,
  "model_version": "0.1.0",
  "notice": "Laboratório kNN sintético com perfis artificiais — SEM VALIDADE BOTÂNICA OU LEGAL",
  "synthetic": true
}
```

---

## 5. Arquivos Gerados
- `ml.py`: 445 linhas
- `tests/test_ml.py`: 370 linhas (17 testes unitários)
- `docs/MODEL_CARD.md`: Documentação técnica completa do modelo
- `data/ml_synthetic.json`: 1101 linhas contendo os 120 registros determinísticos
- `.orchestration/ml-report.md`: Este relatório de rodada
