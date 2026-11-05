"""Tests for ML-01 module (ml.py).
Follows vertical TDD cycles.
"""
import math
import unittest

class TestMLInputValidation(unittest.TestCase):
    """Cycle 1: Test input validation on predict(features)."""

    def test_predict_rejects_non_list_or_wrong_length(self):
        from ml import predict

        invalid_inputs = [
            None,
            "1,2,3",
            123,
            {"a": 1, "b": 2, "c": 3},
            [],
            [1.0],
            [1.0, 2.0],
            [1.0, 2.0, 3.0, 4.0],
        ]
        for inp in invalid_inputs:
            with self.subTest(inp=inp):
                with self.assertRaises(ValueError):
                    predict(inp)

    def test_predict_rejects_booleans(self):
        from ml import predict

        # In Python, bool is a subclass of int (isinstance(True, int) is True).
        # We must explicitly reject bool.
        invalid_inputs = [
            [True, 1.0, 2.0],
            [1.0, False, 2.0],
            [1.0, 2.0, True],
            [False, False, False],
        ]
        for inp in invalid_inputs:
            with self.subTest(inp=inp):
                with self.assertRaises(ValueError):
                    predict(inp)

    def test_predict_rejects_nan_and_inf(self):
        from ml import predict

        invalid_inputs = [
            [float("nan"), 1.0, 2.0],
            [1.0, float("nan"), 2.0],
            [1.0, 2.0, float("nan")],
            [float("inf"), 1.0, 2.0],
            [1.0, float("-inf"), 2.0],
            [1.0, 2.0, float("inf")],
        ]
        for inp in invalid_inputs:
            with self.subTest(inp=inp):
                with self.assertRaises(ValueError):
                    predict(inp)

    def test_predict_rejects_nulls_and_non_numbers(self):
        from ml import predict

        invalid_inputs = [
            [None, 1.0, 2.0],
            [1.0, None, 2.0],
            ["1.0", 2.0, 3.0],
            [1.0, "2.0", 3.0],
            [1.0, 2.0, {}],
        ]
        for inp in invalid_inputs:
            with self.subTest(inp=inp):
                with self.assertRaises(ValueError):
                    predict(inp)

class TestDatasetGeneration(unittest.TestCase):
    """Cycle 2: Test synthetic dataset generation, determinism, and ID separation."""

    def test_generate_dataset_structure_and_counts(self):
        from ml import generate_dataset

        dataset = generate_dataset(seed=42)
        self.assertIn("train_samples", dataset)
        self.assertIn("test_samples", dataset)
        self.assertEqual(len(dataset["train_samples"]), 90)
        self.assertEqual(len(dataset["test_samples"]), 30)

        # Count per class
        for c in ["A", "B", "C"]:
            train_c = [s for s in dataset["train_samples"] if s["label"] == c]
            test_c = [s for s in dataset["test_samples"] if s["label"] == c]
            self.assertEqual(len(train_c), 30, f"Class {c} train count should be 30")
            self.assertEqual(len(test_c), 10, f"Class {c} test count should be 10")

    def test_generate_dataset_id_separation(self):
        from ml import generate_dataset

        dataset = generate_dataset(seed=42)
        train_ids = [s["id"] for s in dataset["train_samples"]]
        test_ids = [s["id"] for s in dataset["test_samples"]]

        # All IDs in train are unique
        self.assertEqual(len(train_ids), len(set(train_ids)))
        # All IDs in test are unique
        self.assertEqual(len(test_ids), len(set(test_ids)))
        # Intersection between train and test IDs is empty
        overlap = set(train_ids).intersection(set(test_ids))
        self.assertEqual(len(overlap), 0, f"Train and test IDs must not overlap: {overlap}")
        # Total distinct IDs must be 120
        self.assertEqual(len(set(train_ids).union(set(test_ids))), 120)

    def test_generate_dataset_reproducibility(self):
        from ml import generate_dataset

        d1 = generate_dataset(seed=42)
        d2 = generate_dataset(seed=42)
        self.assertEqual(d1, d2, "Identical seed must yield identical dataset")

        # Different seed yields different numbers
        d3 = generate_dataset(seed=999)
        self.assertNotEqual(
            d1["train_samples"][0]["features"],
            d3["train_samples"][0]["features"],
            "Different seed must yield different features"
        )

    def test_features_artificial_names_no_botanical(self):
        from ml import generate_dataset, FEATURES, CLASSES

        dataset = generate_dataset(seed=42)
        self.assertEqual(dataset["features"], ["sinal_1", "sinal_2", "sinal_3"])
        self.assertEqual(dataset["classes"], ["A", "B", "C"])
        self.assertEqual(FEATURES, ["sinal_1", "sinal_2", "sinal_3"])
        self.assertEqual(CLASSES, ["A", "B", "C"])

        prohibited_botanical_words = [
            "mogno", "cedro", "ipê", "ipe", "jatobá", "jatoba",
            "castanheira", "espécie", "especie", "madeira", "árvore", "arvore"
        ]
        for f in dataset["features"]:
            for word in prohibited_botanical_words:
                self.assertNotIn(word, f.lower())

class TestNormalizationAntiLeakage(unittest.TestCase):
    """Cycle 3: Test normalization fitted ONLY on train, preventing data leakage."""

    def test_scaler_fitted_strictly_on_train(self):
        from ml import generate_dataset, fit_scaler, transform_features

        dataset = generate_dataset(seed=42)
        train_features = [s["features"] for s in dataset["train_samples"]]
        test_features = [s["features"] for s in dataset["test_samples"]]

        # Fit scaler ONLY on train
        scaler = fit_scaler(train_features)
        self.assertIn("mins", scaler)
        self.assertIn("ranges", scaler)
        self.assertEqual(len(scaler["mins"]), 3)
        self.assertEqual(len(scaler["ranges"]), 3)

        # Mins should equal the exact min of each train feature
        for j in range(3):
            actual_train_min = min(f[j] for f in train_features)
            self.assertAlmostEqual(scaler["mins"][j], actual_train_min, places=4)

        # Transform train: values must be in [0, 1]
        norm_train = [transform_features(f, scaler) for f in train_features]
        for row in norm_train:
            for val in row:
                self.assertGreaterEqual(val, -1e-6)
                self.assertLessEqual(val, 1.0 + 1e-6)

        # Transform test: must use train parameters without refitting
        scaler_copy_before = dict(scaler)
        norm_test = [transform_features(f, scaler) for f in test_features]
        self.assertEqual(scaler, scaler_copy_before, "Scaler params must not be mutated by transforming test")

        # Test with an extreme outlier: verify it is transformed using train params without affecting scaler
        extreme = [999.0, 999.0, 999.0]
        norm_extreme = transform_features(extreme, scaler)
        expected_norm_0 = (999.0 - scaler["mins"][0]) / scaler["ranges"][0]
        self.assertAlmostEqual(norm_extreme[0], expected_norm_0, places=4)
        self.assertEqual(scaler, scaler_copy_before, "Scaler params must remain strictly train-based")

class TestKNNPredictionAndAbstention(unittest.TestCase):
    """Cycle 4 & 5: Test KNN classification, output schema, and distance/consensus abstention."""

    def test_predict_schema(self):
        from ml import predict, MODEL_VERSION, NOTICE

        res = predict([10.0, 20.0, 30.0])
        self.assertIsInstance(res, dict)
        self.assertIn("label", res)
        self.assertIn("status", res)
        self.assertIn("distance", res)
        self.assertIn("neighbor_agreement", res)
        self.assertIn("model_version", res)
        self.assertIn("notice", res)
        self.assertIn("synthetic", res)

        self.assertEqual(res["model_version"], MODEL_VERSION)
        self.assertEqual(res["notice"], NOTICE)
        self.assertIs(res["synthetic"], True)
        self.assertIn(res["status"], ["classified", "inconclusive"])
        if res["status"] == "classified":
            self.assertIn(res["label"], ["A", "B", "C"])
        else:
            self.assertIsNone(res["label"])

    def test_predict_in_distribution_classes(self):
        from ml import predict

        # Samples very close to cluster centroids
        res_a = predict([10.0, 20.0, 30.0])
        self.assertEqual(res_a["status"], "classified")
        self.assertEqual(res_a["label"], "A")
        self.assertGreaterEqual(res_a["neighbor_agreement"], 0.6)

        res_b = predict([50.0, 15.0, 70.0])
        self.assertEqual(res_b["status"], "classified")
        self.assertEqual(res_b["label"], "B")
        self.assertGreaterEqual(res_b["neighbor_agreement"], 0.6)

        res_c = predict([25.0, 80.0, 45.0])
        self.assertEqual(res_c["status"], "classified")
        self.assertEqual(res_c["label"], "C")
        self.assertGreaterEqual(res_c["neighbor_agreement"], 0.6)

    def test_predict_outlier_abstention_999(self):
        from ml import predict

        # Outlier [999, 999, 999] must abstain
        res = predict([999.0, 999.0, 999.0])
        self.assertEqual(res["status"], "inconclusive")
        self.assertIsNone(res["label"])
        self.assertGreater(res["distance"], 1.0)
        self.assertIs(res["synthetic"], True)

    def test_abstention_on_lack_of_consensus(self):
        from ml import SyntheticKNN

        # Synthetic KNN with mock training points creating a split vote
        train_data = [
            {"id": "t1", "features": [0.0, 0.0, 0.0], "label": "A"},
            {"id": "t2", "features": [0.0, 0.0, 0.0], "label": "B"},
            {"id": "t3", "features": [0.0, 0.0, 0.0], "label": "C"},
        ]
        # k=3 with 3 equal votes: agreement is 1/3 = 0.333 < 0.60
        model = SyntheticKNN(k=3, distance_threshold=2.0, consensus_threshold=0.60)
        model.fit(train_data)

        res = model.predict([0.0, 0.0, 0.0])
        self.assertEqual(res["status"], "inconclusive")
        self.assertIsNone(res["label"])
        self.assertAlmostEqual(res["neighbor_agreement"], 1 / 3, places=3)

class TestTrainAndEvaluateContract(unittest.TestCase):
    """Cycle 6: Test train_and_evaluate() exact contract, metrics, and JSON serializability."""

    def test_train_and_evaluate_contract_keys_and_types(self):
        import json
        from ml import train_and_evaluate

        res = train_and_evaluate()
        self.assertIsInstance(res, dict)

        # Top-level contract keys
        expected_keys = {
            "model_version",
            "train_count",
            "test_count",
            "classes",
            "features",
            "metrics",
            "notice",
            "synthetic",
        }
        self.assertEqual(set(res.keys()), expected_keys)

        self.assertEqual(res["train_count"], 90)
        self.assertEqual(res["test_count"], 30)
        self.assertEqual(res["classes"], ["A", "B", "C"])
        self.assertEqual(res["features"], ["sinal_1", "sinal_2", "sinal_3"])
        self.assertIs(res["synthetic"], True)
        self.assertIsInstance(res["model_version"], str)
        self.assertIsInstance(res["notice"], str)

        # Metrics contract
        metrics = res["metrics"]
        expected_metrics_keys = {
            "accuracy",
            "macro_f1",
            "recall_by_class",
            "confusion_matrix",
            "abstention_rate",
        }
        self.assertEqual(set(metrics.keys()), expected_metrics_keys)

        self.assertIsInstance(metrics["accuracy"], float)
        self.assertIsInstance(metrics["macro_f1"], float)
        self.assertIsInstance(metrics["abstention_rate"], float)
        self.assertIsInstance(metrics["recall_by_class"], dict)
        self.assertEqual(set(metrics["recall_by_class"].keys()), {"A", "B", "C"})

        # Confusion matrix is 3x3
        cm = metrics["confusion_matrix"]
        self.assertIsInstance(cm, list)
        self.assertEqual(len(cm), 3)
        for row in cm:
            self.assertIsInstance(row, list)
            self.assertEqual(len(row), 3)

        # Must be fully JSON-serializable
        serialized = json.dumps(res)
        deserialized = json.loads(serialized)
        self.assertEqual(deserialized["train_count"], 90)
        self.assertEqual(deserialized["test_count"], 30)

    def test_train_and_evaluate_reproducibility(self):
        from ml import train_and_evaluate

        res1 = train_and_evaluate(seed=42)
        res2 = train_and_evaluate(seed=42)
        self.assertEqual(res1, res2, "train_and_evaluate with identical seed must return identical results")

    def test_train_and_evaluate_metrics_soundness(self):
        from ml import train_and_evaluate

        res = train_and_evaluate(seed=42)
        metrics = res["metrics"]
        self.assertGreaterEqual(metrics["accuracy"], 0.90)
        self.assertGreaterEqual(metrics["macro_f1"], 0.90)
        for c in ["A", "B", "C"]:
            self.assertGreaterEqual(metrics["recall_by_class"][c], 0.90)
        self.assertLessEqual(metrics["abstention_rate"], 0.10)

class TestCLIExecution(unittest.TestCase):
    """Cycle 7: Test python ml.py standalone execution, report printing, and dataset saving."""

    def test_cli_execution_generates_dataset_and_prints_report(self):
        import subprocess
        import sys
        import os
        import json

        cmd = [sys.executable, "ml.py"]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(proc.returncode, 0, f"CLI exited with error: {proc.stderr}")
        self.assertIn("RELATÓRIO ML-01", proc.stdout)
        self.assertIn("Acurácia", proc.stdout)
        self.assertIn("SEM VALIDADE BOTÂNICA OU LEGAL", proc.stdout)

        # Check data/ml_synthetic.json was generated and valid
        json_path = os.path.join("data", "ml_synthetic.json")
        self.assertTrue(os.path.exists(json_path), f"{json_path} was not created")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(len(data["train_samples"]), 90)
        self.assertEqual(len(data["test_samples"]), 30)
        self.assertEqual(data["classes"], ["A", "B", "C"])
        self.assertIs(data["synthetic"], True)

if __name__ == "__main__":
    unittest.main()
