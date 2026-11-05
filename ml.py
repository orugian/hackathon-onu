"""ML-01 — Laboratório kNN sintético com perfis artificiais e abstenção.

AVISO DE ESCOPO E LIMITAÇÃO:
Este módulo opera exclusivamente sobre dados sintéticos com classes artificiais ('A', 'B', 'C')
e características abstratas ('sinal_1', 'sinal_2', 'sinal_3').
NÃO lê imagens botânicas, NÃO identifica espécies botânicas reais, NÃO comprova legalidade
e NÃO habilita decisão legal, fiscal ou regulatória.
"""

import math
import random
from typing import Any, Dict, List, Optional, Tuple

MODEL_VERSION = "0.1.0"
NOTICE = (
    "Laboratório kNN sintético com perfis artificiais — "
    "SEM VALIDADE BOTÂNICA OU LEGAL"
)
FEATURES = ["sinal_1", "sinal_2", "sinal_3"]
CLASSES = ["A", "B", "C"]

# Synthetic cluster definitions (mean vector and standard deviation)
CLASS_CENTROIDS = {
    "A": ([10.0, 20.0, 30.0], 2.0),
    "B": ([50.0, 15.0, 70.0], 2.0),
    "C": ([25.0, 80.0, 45.0], 2.0),
}


def generate_dataset(seed: int = 42) -> Dict[str, Any]:
    """Generate deterministic synthetic dataset with distinct IDs and clear separation.
    
    Generates 30 train and 10 test samples per class (90 train, 30 test total).
    """
    rng = random.Random(seed)

    train_samples: List[Dict[str, Any]] = []
    test_samples: List[Dict[str, Any]] = []

    for cls in CLASSES:
        mu_vec, sigma = CLASS_CENTROIDS[cls]

        # 30 training samples per class
        for i in range(1, 31):
            sample_id = f"syn_train_{cls}_{i:03d}"
            feat_vals = [
                round(rng.gauss(mu, sigma), 4) for mu in mu_vec
            ]
            train_samples.append({
                "id": sample_id,
                "label": cls,
                "features": feat_vals,
            })

        # 10 testing samples per class
        for i in range(1, 11):
            sample_id = f"syn_test_{cls}_{i:03d}"
            feat_vals = [
                round(rng.gauss(mu, sigma), 4) for mu in mu_vec
            ]
            test_samples.append({
                "id": sample_id,
                "label": cls,
                "features": feat_vals,
            })

    return {
        "seed": seed,
        "features": list(FEATURES),
        "classes": list(CLASSES),
        "train_count": len(train_samples),
        "test_count": len(test_samples),
        "train_samples": train_samples,
        "test_samples": test_samples,
        "notice": NOTICE,
        "synthetic": True,
    }


def fit_scaler(features_list: List[List[float]]) -> Dict[str, List[float]]:
    """Compute min and range for each feature dimension strictly from training features."""
    if not features_list:
        raise ValueError("Cannot fit scaler on empty feature list.")
    dim = len(features_list[0])
    mins = [min(row[j] for row in features_list) for j in range(dim)]
    maxs = [max(row[j] for row in features_list) for j in range(dim)]
    ranges = [
        (maxs[j] - mins[j]) if (maxs[j] - mins[j]) > 1e-12 else 1.0
        for j in range(dim)
    ]
    return {
        "mins": mins,
        "ranges": ranges,
    }


def transform_features(
    features: List[float], scaler: Dict[str, List[float]]
) -> List[float]:
    """Normalize features using pre-computed scaler parameters (no refit/leakage)."""
    mins = scaler["mins"]
    ranges = scaler["ranges"]
    return [
        (features[j] - mins[j]) / ranges[j] for j in range(len(features))
    ]




def validate_features(features: Any) -> List[float]:
    """Validate that features is a list of exactly 3 finite real numbers (no bool, nan, inf, None)."""
    if not isinstance(features, list) or len(features) != 3:
        raise ValueError(
            f"features deve ser uma lista com exatamente 3 elementos, recebido: {type(features).__name__} de tamanho {len(features) if isinstance(features, (list, tuple, dict)) else 'N/A'}"
        )

    validated: List[float] = []
    for i, val in enumerate(features):
        # In Python, isinstance(True, (int, float)) is True, so check bool explicitly first!
        if isinstance(val, bool):
            raise ValueError(
                f"Elemento no índice {i} é booleano ({val}), esperado número finito."
            )
        if val is None:
            raise ValueError(
                f"Elemento no índice {i} é nulo (None), esperado número finito."
            )
        if not isinstance(val, (int, float)):
            raise ValueError(
                f"Elemento no índice {i} possui tipo inválido ({type(val).__name__}), esperado int ou float."
            )
        if val < -1_000_000_000_000 or val > 1_000_000_000_000:
            raise ValueError('Sinais artificiais devem estar entre -10¹² e 10¹²; valores fora dessa faixa não são suportados.')
        if math.isnan(val) or math.isinf(val):
            raise ValueError(
                f"Elemento no índice {i} não é finito ({val}), esperado número finito."
            )
        validated.append(float(val))

    return validated


DEFAULT_K = 3
DEFAULT_DISTANCE_THRESHOLD = 0.50
DEFAULT_CONSENSUS_THRESHOLD = 0.60


class SyntheticKNN:
    """k-Nearest Neighbors classifier on synthetic profiles with distance and consensus abstention."""

    def __init__(
        self,
        k: int = DEFAULT_K,
        distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
        consensus_threshold: float = DEFAULT_CONSENSUS_THRESHOLD,
    ):
        if k <= 0:
            raise ValueError(f"k deve ser positivo, recebido: {k}")
        self.k = k
        self.distance_threshold = distance_threshold
        self.consensus_threshold = consensus_threshold
        self.scaler: Optional[Dict[str, List[float]]] = None
        self.train_samples: List[Dict[str, Any]] = []
        self._normalized_train: List[Tuple[List[float], str]] = []

    def fit(self, train_samples: List[Dict[str, Any]]) -> "SyntheticKNN":
        """Fit scaler and store training samples strictly without looking at test data."""
        if not train_samples:
            raise ValueError("train_samples não pode ser vazio")

        self.train_samples = train_samples
        train_features = [s["features"] for s in train_samples]
        self.scaler = fit_scaler(train_features)

        self._normalized_train = []
        for s in train_samples:
            norm_feat = transform_features(s["features"], self.scaler)
            self._normalized_train.append((norm_feat, s["label"]))

        return self

    def predict(self, features: Any) -> Dict[str, Any]:
        """Classify input features or abstain if distant or lacking consensus."""
        validated = validate_features(features)

        if not self._normalized_train or self.scaler is None:
            raise RuntimeError("Modelo não foi ajustado (fit) antes da predição.")

        # Transform using training scaler (no refit/leakage)
        norm_input = transform_features(validated, self.scaler)

        # Compute Euclidean distance to all training points
        distances_and_labels: List[Tuple[float, str]] = []
        for train_norm, label in self._normalized_train:
            dist = math.sqrt(
                sum((a - b) ** 2 for a, b in zip(norm_input, train_norm))
            )
            distances_and_labels.append((dist, label))

        # Sort by distance ascending
        distances_and_labels.sort(key=lambda item: item[0])

        k_nearest = distances_and_labels[: self.k]
        nearest_dist = k_nearest[0][0]

        # Count votes among k nearest neighbors
        vote_counts: Dict[str, int] = {}
        for _, lbl in k_nearest:
            vote_counts[lbl] = vote_counts.get(lbl, 0) + 1

        # Determine leader and agreement fraction
        sorted_votes = sorted(
            vote_counts.items(), key=lambda item: item[1], reverse=True
        )
        leader_class, leader_votes = sorted_votes[0]
        neighbor_agreement = leader_votes / self.k

        # Check for tie among leaders
        is_tie = (
            len(sorted_votes) > 1
            and sorted_votes[1][1] == leader_votes
        )

        # Abstention decision:
        # Distance too large OR agreement below threshold OR ambiguous tie
        too_distant = nearest_dist > self.distance_threshold
        lacks_consensus = neighbor_agreement < self.consensus_threshold or is_tie

        if too_distant or lacks_consensus:
            status = "inconclusive"
            label = None
        else:
            status = "classified"
            label = leader_class

        return {
            "label": label,
            "status": status,
            "distance": round(nearest_dist, 4),
            "neighbor_agreement": round(neighbor_agreement, 4),
            "model_version": MODEL_VERSION,
            "notice": NOTICE,
            "synthetic": True,
        }


_DEFAULT_MODEL: Optional[SyntheticKNN] = None


def get_default_model() -> SyntheticKNN:
    """Return singleton instance of default trained model."""
    global _DEFAULT_MODEL
    if _DEFAULT_MODEL is None:
        dataset = generate_dataset(seed=42)
        model = SyntheticKNN()
        model.fit(dataset["train_samples"])
        _DEFAULT_MODEL = model
    return _DEFAULT_MODEL


def predict(features: Any) -> Dict[str, Any]:
    """Predict class label ('A' | 'B' | 'C' | None) with abstention logic using default model."""
    # validate_features is also called inside model.predict, but validating early ensures consistent error semantics
    validate_features(features)
    model = get_default_model()
    return model.predict(features)


def train_and_evaluate(
    seed: int = 42,
    k: int = DEFAULT_K,
    distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
    consensus_threshold: float = DEFAULT_CONSENSUS_THRESHOLD,
) -> Dict[str, Any]:
    """Train synthetic kNN and evaluate on deterministic test split.
    
    Adheres strictly to the ML-01 contract:
    - Split prior to normalization;
    - Normalization fitted exclusively on train set;
    - Test evaluated using train parameters without refit;
    - Explicit distance and consensus thresholds;
    - Full metrics: accuracy, macro_f1, recall_by_class, confusion_matrix, abstention_rate.
    """
    dataset = generate_dataset(seed=seed)
    train_samples = dataset["train_samples"]
    test_samples = dataset["test_samples"]

    # Model fitted ONLY on train_samples
    model = SyntheticKNN(
        k=k,
        distance_threshold=distance_threshold,
        consensus_threshold=consensus_threshold,
    )
    model.fit(train_samples)

    # Evaluate on test_samples
    predictions: List[Tuple[str, Dict[str, Any]]] = []
    for s in test_samples:
        pred = model.predict(s["features"])
        predictions.append((s["label"], pred))

    test_count = len(test_samples)
    abstained_count = sum(
        1 for _, pred in predictions if pred["status"] == "inconclusive"
    )
    abstention_rate = round(abstained_count / test_count, 4)

    correct_count = sum(
        1 for true_lbl, pred in predictions if pred["label"] == true_lbl
    )
    accuracy = round(correct_count / test_count, 4)

    # Confusion matrix (3x3 rows: true class, cols: predicted class)
    cls_to_idx = {cls: idx for idx, cls in enumerate(CLASSES)}
    cm: List[List[int]] = [[0 for _ in CLASSES] for _ in CLASSES]
    for true_lbl, pred in predictions:
        pred_lbl = pred["label"]
        if pred_lbl in cls_to_idx:
            cm[cls_to_idx[true_lbl]][cls_to_idx[pred_lbl]] += 1

    # Recall by class and Macro F1
    recall_by_class: Dict[str, float] = {}
    f1_by_class: Dict[str, float] = {}
    for c in CLASSES:
        tp = sum(
            1
            for true_lbl, pred in predictions
            if true_lbl == c and pred["label"] == c
        )
        fn = sum(
            1
            for true_lbl, pred in predictions
            if true_lbl == c and pred["label"] != c
        )
        fp = sum(
            1
            for true_lbl, pred in predictions
            if true_lbl != c and pred["label"] == c
        )

        recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        f1 = (
            (2 * precision * recall / (precision + recall))
            if (precision + recall) > 0
            else 0.0
        )

        recall_by_class[c] = round(recall, 4)
        f1_by_class[c] = f1

    macro_f1 = round(sum(f1_by_class.values()) / len(CLASSES), 4)

    return {
        "model_version": MODEL_VERSION,
        "train_count": len(train_samples),
        "test_count": len(test_samples),
        "classes": list(CLASSES),
        "features": list(FEATURES),
        "metrics": {
            "accuracy": accuracy,
            "macro_f1": macro_f1,
            "recall_by_class": recall_by_class,
            "confusion_matrix": cm,
            "abstention_rate": abstention_rate,
        },
        "notice": NOTICE,
        "synthetic": True,
    }


def save_synthetic_dataset(
    output_path: str = "data/ml_synthetic.json", seed: int = 42
) -> str:
    """Save deterministic synthetic dataset to JSON file without touching operational data."""
    import json
    import os

    dataset = generate_dataset(seed=seed)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
    return output_path


def format_report(eval_result: Dict[str, Any]) -> str:
    """Format evaluation results into a human-readable text report."""
    metrics = eval_result["metrics"]
    cm = metrics["confusion_matrix"]
    recalls = metrics["recall_by_class"]

    lines = [
        "============================================================",
        "RELATÓRIO ML-01 — Laboratório kNN Sintético com Abstenção",
        "============================================================",
        f"Versão do Modelo      : {eval_result['model_version']}",
        f"Amostras de Treino    : {eval_result['train_count']} (30 por classe)",
        f"Amostras de Teste     : {eval_result['test_count']} (10 por classe)",
        f"Classes Artificiais   : {', '.join(eval_result['classes'])}",
        f"Features Artificiais  : {', '.join(eval_result['features'])}",
        f"Parâmetros Fixados    : k={DEFAULT_K}, limiar_distancia={DEFAULT_DISTANCE_THRESHOLD}, limiar_consenso={DEFAULT_CONSENSUS_THRESHOLD}",
        "------------------------------------------------------------",
        "MÉTRICAS OBTIDAS NO SPLIT DE TESTE:",
        f"  - Acurácia            : {metrics['accuracy']:.4f}",
        f"  - Macro F1            : {metrics['macro_f1']:.4f}",
        f"  - Taxa de Abstenção   : {metrics['abstention_rate']:.4f}",
        "  - Recall por Classe   :",
        f"      Classe A          : {recalls['A']:.4f}",
        f"      Classe B          : {recalls['B']:.4f}",
        f"      Classe C          : {recalls['C']:.4f}",
        "  - Matriz de Confusão (Linhas=Real, Colunas=Predito [A, B, C]):",
        f"      Real A            : {cm[0]}",
        f"      Real B            : {cm[1]}",
        f"      Real C            : {cm[2]}",
        "------------------------------------------------------------",
        f"AVISO INSTITUCIONAL   : {eval_result['notice']}",
        "RESTRIÇÕES DO SISTEMA : Não lê imagens botânicas.",
        "                        Sem validade jurídica ou decisão regulatória.",
        "============================================================",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    out_file = save_synthetic_dataset()
    eval_res = train_and_evaluate(seed=42)
    report_text = format_report(eval_res)
    print(report_text)
    print(f"\n[OK] Dataset sintético reproduzido com sucesso em: {out_file}")





