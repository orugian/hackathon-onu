import unittest
import tempfile
import os
from domain import DomainError, Ledger

class TestDomainError(unittest.TestCase):

    def test_domain_error_attributes(self):
        err = DomainError("Erro de teste", code="validation_error", status=422)
        self.assertEqual(str(err), "Erro de teste")
        self.assertEqual(err.message, "Erro de teste")
        self.assertEqual(err.code, "validation_error")
        self.assertEqual(err.status, 422)

        err_default = DomainError("Mensagem simples")
        self.assertEqual(err_default.code, "validation_error")
        self.assertEqual(err_default.status, 422)

        d = err.to_dict()
        self.assertEqual(d["error"], "Erro de teste")
        self.assertEqual(d["code"], "validation_error")
        self.assertEqual(d["status"], 422)

class TestLedgerInit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_ledger_initialization_and_state(self):
        ledger = Ledger(self.db_path)
        st = ledger.state()

        self.assertIn("lots", st)
        self.assertIn("shipments", st)
        self.assertIn("assessments", st)
        self.assertIn("events", st)
        self.assertIn("integrity", st)

        self.assertEqual(len(st["lots"]), 1)
        lot = st["lots"][0]
        self.assertEqual(lot["id"], "AM-DEMO-001")
        self.assertEqual(lot["plot_id"], "AREA-DEMO-001")
        self.assertEqual(lot["product"], "Madeira em tora")
        self.assertEqual(lot["species"], "Táxon não verificado")
        self.assertEqual(lot["opening_milli"], 15000)
        self.assertEqual(lot["available_milli"], 15000)
        self.assertEqual(lot["reserved_milli"], 0)
        self.assertEqual(lot["unit"], "m³")
        self.assertTrue(lot["simulated"])

        self.assertEqual(st["shipments"], [])
        self.assertEqual(st["assessments"], [])
        self.assertEqual(len(st["events"]), 1)
        ev = st["events"][0]
        self.assertEqual(ev["type"], "LOT_OPENED")
        self.assertEqual(ev["previous_hash"], "0" * 64)
        self.assertTrue(len(ev["hash"]) == 64)

        self.assertTrue(st["integrity"]["valid"])
        self.assertEqual(st["integrity"]["count"], 1)

    def test_ledger_reopen_persists_without_duplication(self):
        ledger1 = Ledger(self.db_path)
        st1 = ledger1.state()
        self.assertEqual(len(st1["events"]), 1)

        # Reopen on same database file
        ledger2 = Ledger(self.db_path)
        st2 = ledger2.state()
        self.assertEqual(len(st2["events"]), 1)
        self.assertEqual(len(st2["lots"]), 1)
        self.assertEqual(st2["lots"][0]["available_milli"], 15000)

class TestReserveValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        self.ledger = Ledger(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_reserve_validation_errors_and_rollback(self):
        base_payload = {
            "lot_id": "AM-DEMO-001",
            "volume_m3": 10.0,
            "recipient": "Madeireira Central Ltda",
            "vehicle": "ABC-1234",
            "invoice": "NF-00123",
            "gross_kg": 20000,
            "tare_kg": 12000,
        }

        # Idempotency key ausente, vazia ou > 128 chars
        with self.assertRaises(DomainError) as ctx:
            self.ledger.reserve(base_payload, "")
        self.assertEqual(ctx.exception.status, 422)

        with self.assertRaises(DomainError) as ctx:
            self.ledger.reserve(base_payload, "x" * 129)
        self.assertEqual(ctx.exception.status, 422)

        # lot_id ausente ou vazio
        p = dict(base_payload)
        del p["lot_id"]
        with self.assertRaises(DomainError):
            self.ledger.reserve(p, "k1")

        p = dict(base_payload, lot_id="   ")
        with self.assertRaises(DomainError):
            self.ledger.reserve(p, "k1")

        # volume_m3 booleano, negativo, zero, NaN, Inf, > 1000000
        for bad_vol in [True, False, -1, 0, float("nan"), float("inf"), 1_000_001]:
            p = dict(base_payload, volume_m3=bad_vol)
            with self.assertRaises(DomainError):
                self.ledger.reserve(p, "k1")

        # volume_m3 como string NaN, Infinity, -Infinity, huge numbers não devem causar decimal.InvalidOperation ou OverflowError
        for bad_str in ["NaN", "nan", "Infinity", "-Infinity", "-nan", "1e308", "1e99999999999", "9" * 100, 1e308]:
            p = dict(base_payload, volume_m3=bad_str)
            with self.assertRaises(DomainError) as ctx:
                self.ledger.reserve(p, "k1")
            self.assertEqual(ctx.exception.status, 422)

        # volume_m3 com mais de 3 casas decimais
        for bad_decimals in [10.0001, "10.0005", "1.2345"]:
            p = dict(base_payload, volume_m3=bad_decimals)
            with self.assertRaises(DomainError):
                self.ledger.reserve(p, "k1")

        # strings vazias ou > 200 caracteres
        for field in ["recipient", "vehicle", "invoice"]:
            p = dict(base_payload, **{field: "   "})
            with self.assertRaises(DomainError):
                self.ledger.reserve(p, "k1")
            p = dict(base_payload, **{field: "a" * 201})
            with self.assertRaises(DomainError):
                self.ledger.reserve(p, "k1")

        # Pesos: tara negativa, bruto <= tara, massas > 100000000, booleans
        p = dict(base_payload, tare_kg=-10)
        with self.assertRaises(DomainError):
            self.ledger.reserve(p, "k1")

        p = dict(base_payload, gross_kg=12000, tare_kg=12000)
        with self.assertRaises(DomainError):
            self.ledger.reserve(p, "k1")

        p = dict(base_payload, gross_kg=100_000_001)
        with self.assertRaises(DomainError):
            self.ledger.reserve(p, "k1")

        p = dict(base_payload, gross_kg=True)
        with self.assertRaises(DomainError):
            self.ledger.reserve(p, "k1")

        # Verificar integridade e ausência de efeitos colaterais após tentativas inválidas
        st = self.ledger.state()
        self.assertEqual(st["lots"][0]["available_milli"], 15000)
        self.assertEqual(len(st["shipments"]), 0)
        self.assertEqual(len(st["events"]), 1)
        self.assertTrue(st["integrity"]["valid"])

class TestReserveFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        self.ledger = Ledger(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_reserve_successful_and_passport_structure(self):
        payload = {
            "lot_id": "AM-DEMO-001",
            "volume_m3": 10.0,
            "recipient": "Destino Teste",
            "vehicle": "ABC-1234",
            "invoice": "NF-001",
            "gross_kg": 20000,
            "tare_kg": 12000,
        }
        passport = self.ledger.reserve(payload, "key-1")

        self.assertEqual(passport["schema_version"], "1.0.0")
        self.assertTrue(passport["id"].startswith("PASS-"))
        self.assertIn("T", passport["issued_at"])
        self.assertEqual(passport["lot_id"], "AM-DEMO-001")
        self.assertEqual(passport["plot_id"], "AREA-DEMO-001")
        self.assertEqual(passport["origin"]["name"], "Área demonstrativa · Itacoatiara/AM")
        self.assertTrue(passport["origin"]["simulated"])
        self.assertEqual(passport["authorization"]["reference"], "AUT-DEMO-001")
        self.assertEqual(passport["authorization"]["issuer"], "Referência fictícia")
        self.assertEqual(passport["authorization"]["status"], "não verificável")
        self.assertEqual(passport["recipient"], "Destino Teste")
        self.assertEqual(passport["product"], "Madeira em tora")
        self.assertEqual(passport["species"], "Táxon não verificado")
        self.assertEqual(passport["volume_m3"], 10.0)
        self.assertEqual(passport["volume_milli"], 10000)
        self.assertEqual(passport["vehicle"], "ABC-1234")
        self.assertEqual(passport["invoice"], "NF-001")
        self.assertEqual(passport["balance_after_milli"], 5000)
        self.assertEqual(passport["event_id"], 2)
        self.assertIn("SEM VALIDADE OFICIAL", passport["notice"])
        self.assertTrue(passport["simulated"])

        # Pesagem embutida
        self.assertEqual(passport["weighing"]["net_kg"], 8000)
        self.assertEqual(passport["weighing"]["status"], "compatible")

        # Verificação do hash SHA256 canônico
        passport_without_hash = {k: v for k, v in passport.items() if k != "hash"}
        import json, hashlib
        expected_hash = hashlib.sha256(
            json.dumps(passport_without_hash, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        self.assertEqual(passport["hash"], expected_hash)

        # Verificar reflexo no state()
        st = self.ledger.state()
        self.assertEqual(st["lots"][0]["available_milli"], 5000)
        self.assertEqual(st["lots"][0]["reserved_milli"], 10000)
        self.assertEqual(len(st["shipments"]), 1)
        self.assertEqual(st["shipments"][0]["id"], passport["id"])
        self.assertEqual(len(st["events"]), 2)
        self.assertTrue(st["integrity"]["valid"])

    def test_reserve_15_10_10_sequential(self):
        # Test essential: 15/10/10 sequencial
        payload1 = {
            "lot_id": "AM-DEMO-001",
            "volume_m3": 10.0,
            "recipient": "Cliente A",
            "vehicle": "AAA-1111",
            "invoice": "NF-001",
            "gross_kg": 20000,
            "tare_kg": 12000,
        }
        p1 = self.ledger.reserve(payload1, "key-seq-1")
        self.assertEqual(p1["balance_after_milli"], 5000)

        payload2 = {
            "lot_id": "AM-DEMO-001",
            "volume_m3": 10.0,
            "recipient": "Cliente B",
            "vehicle": "BBB-2222",
            "invoice": "NF-002",
            "gross_kg": 20000,
            "tare_kg": 12000,
        }
        # Segunda tentativa de 10 m3 deve falhar com 409 insufficient_balance
        with self.assertRaises(DomainError) as ctx:
            self.ledger.reserve(payload2, "key-seq-2")
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(ctx.exception.code, "insufficient_balance")

        # Verificar que saldo permanece 5000 milli e nenhuma autuação/multa automática foi gerada
        st = self.ledger.state()
        self.assertEqual(st["lots"][0]["available_milli"], 5000)
        self.assertEqual(len(st["assessments"]), 0)
        self.assertEqual(len(st["shipments"]), 1)
        self.assertTrue(st["integrity"]["valid"])

    def test_reserve_three_times_point_one_exact_milli(self):
        # Test essential: 3x0.1 => 14.7 (sem drift de ponto flutuante)
        for i in range(1, 4):
            payload = {
                "lot_id": "AM-DEMO-001",
                "volume_m3": 0.1,
                "recipient": f"Cliente {i}",
                "vehicle": f"VEH-{i}",
                "invoice": f"NF-{i}",
                "gross_kg": 1000,
                "tare_kg": 900,
            }
            p = self.ledger.reserve(payload, f"key-sub-{i}")
            self.assertEqual(p["volume_milli"], 100)
            self.assertEqual(p["balance_after_milli"], 15000 - i * 100)

        st = self.ledger.state()
        self.assertEqual(st["lots"][0]["available_milli"], 14700)
        self.assertEqual(st["lots"][0]["reserved_milli"], 300)
        self.assertEqual(len(st["shipments"]), 3)
        self.assertTrue(st["integrity"]["valid"])





class TestPassportRetrieval(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        self.ledger = Ledger(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_passport_retrieval_and_not_found(self):
        payload = {
            "lot_id": "AM-DEMO-001",
            "volume_m3": 10.0,
            "recipient": "Cliente X",
            "vehicle": "ABC-9999",
            "invoice": "NF-999",
            "gross_kg": 20000,
            "tare_kg": 12000,
        }
        created = self.ledger.reserve(payload, "key-pass-1")
        retrieved = self.ledger.passport(created["id"])
        self.assertEqual(retrieved, created)

        # Inexistente
        with self.assertRaises(DomainError) as ctx:
            self.ledger.passport("PASS-NONEXISTENT")
        self.assertEqual(ctx.exception.status, 404)
        self.assertEqual(ctx.exception.code, "not_found")

        # Inválido
        with self.assertRaises(DomainError) as ctx:
            self.ledger.passport("   ")
        self.assertEqual(ctx.exception.status, 422)


class TestAssessAndReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        self.ledger = Ledger(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_assess_sim001_and_validation(self):
        payload = {
            "quantity_m3": 5,
            "hypothesis": "Divergência volumétrica entre fuste de campo e transporte",
            "reviewer": "Fiscal Demonstrativo",
        }
        res = self.ledger.assess(payload)
        self.assertTrue(res["id"].startswith("ASM-"))
        self.assertEqual(res["rule_id"], "SIM-001")
        self.assertEqual(res["rule_version"], "v1.0")
        self.assertEqual(res["quantity_m3"], 5.0)
        self.assertEqual(res["hypothesis"], payload["hypothesis"])
        self.assertEqual(res["reviewer"], payload["reviewer"])
        self.assertEqual(res["fine_brl"], "1500.00")
        self.assertEqual(res["fee_brl"], "60.00")
        self.assertIn("SIM-001", res["formula"])
        self.assertIn("SEM VALIDADE OFICIAL", res["notice"])
        self.assertEqual(res["status"], "pending")
        self.assertIsNone(res["review"])

        # Verificar state e cadeia
        st = self.ledger.state()
        self.assertEqual(len(st["assessments"]), 1)
        self.assertEqual(st["assessments"][0]["id"], res["id"])
        self.assertTrue(st["integrity"]["valid"])
        audit = self.ledger.verify_chain()
        self.assertTrue(audit["valid"])
        self.assertEqual(audit["count"], 2)

        # Validações inválidas
        for bad_qty in [0, -1, float("nan"), 1_000_001, True]:
            with self.assertRaises(DomainError) as ctx:
                self.ledger.assess(dict(payload, quantity_m3=bad_qty))
            self.assertEqual(ctx.exception.status, 422)

        for empty_field in ["hypothesis", "reviewer"]:
            with self.assertRaises(DomainError) as ctx:
                self.ledger.assess(dict(payload, **{empty_field: "   "}))
            self.assertEqual(ctx.exception.status, 422)

    def test_review_definitive_and_conflict(self):
        assess_res = self.ledger.assess({
            "quantity_m3": 5,
            "hypothesis": "Diferença hipotética de volume",
            "reviewer": "Revisor inicial",
        })
        asm_id = assess_res["id"]

        # Revisão com razão vazia deve falhar 422
        with self.assertRaises(DomainError) as ctx:
            self.ledger.review({
                "assessment_id": asm_id,
                "decision": "disagree",
                "reviewer": "Engenheiro Carlos",
                "reason": "   ",
            })
        self.assertEqual(ctx.exception.status, 422)

        # Revisão com decisão inválida deve falhar 422
        with self.assertRaises(DomainError) as ctx:
            self.ledger.review({
                "assessment_id": asm_id,
                "decision": "maybe",
                "reviewer": "Engenheiro Carlos",
                "reason": "Motivação válida",
            })
        self.assertEqual(ctx.exception.status, 422)

        # Revisão com parecerista vazio deve falhar 422
        with self.assertRaises(DomainError) as ctx:
            self.ledger.review({
                "assessment_id": asm_id,
                "decision": "agree",
                "reviewer": "  ",
                "reason": "Motivação válida",
            })
        self.assertEqual(ctx.exception.status, 422)

        # Revisão válida conclusiva
        rev_res = self.ledger.review({
            "assessment_id": asm_id,
            "decision": "disagree",
            "reviewer": "Engenheiro Carlos",
            "reason": "Solicitar medição de campo antes de qualquer enquadramento.",
        })
        self.assertEqual(rev_res["id"], asm_id)
        self.assertIn(rev_res["status"], ["disagreed", "reviewed"])
        self.assertIsNotNone(rev_res["review"])
        self.assertEqual(rev_res["review"]["decision"], "disagree")
        self.assertEqual(rev_res["review"]["reviewer"], "Engenheiro Carlos")
        self.assertIn("T", rev_res["review"]["reviewed_at"])

        # Segunda revisão definitiva DEVE falhar com 409
        with self.assertRaises(DomainError) as ctx:
            self.ledger.review({
                "assessment_id": asm_id,
                "decision": "agree",
                "reviewer": "Outro Revisor",
                "reason": "Tentativa de alteração posterior",
            })
        self.assertEqual(ctx.exception.status, 409)

        # Verificar integridade da cadeia de auditoria
        audit = self.ledger.verify_chain()
        self.assertTrue(audit["valid"])
        self.assertEqual(audit["count"], 3)  # LOT_OPENED, ASSESSMENT_CREATED, ASSESSMENT_REVIEWED

    def test_review_nonexistent_assessment_404(self):
        with self.assertRaises(DomainError) as ctx:
            self.ledger.review({
                "assessment_id": "ASM-NONEXISTENT",
                "decision": "agree",
                "reviewer": "Carlos",
                "reason": "Tentando avaliar algo que não existe",
            })
        self.assertEqual(ctx.exception.status, 404)


class TestIdempotencyAndConcurrency(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        self.ledger = Ledger(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_idempotency_sequential_same_payload_returns_same_passport(self):
        payload = {
            "lot_id": "AM-DEMO-001",
            "volume_m3": 5.0,
            "recipient": "Cliente Idem",
            "vehicle": "XYZ-1234",
            "invoice": "NF-100",
            "gross_kg": 20000,
            "tare_kg": 12000,
        }
        p1 = self.ledger.reserve(payload, "key-idem-1")
        p2 = self.ledger.reserve(payload, "key-idem-1")
        self.assertEqual(p1["id"], p2["id"])
        self.assertEqual(p1["hash"], p2["hash"])

        st = self.ledger.state()
        self.assertEqual(st["lots"][0]["available_milli"], 10000)
        self.assertEqual(len(st["shipments"]), 1)
        self.assertEqual(len(st["events"]), 2)  # LOT_OPENED, 1x SHIPMENT_RESERVED

    def test_idempotency_conflict_divergent_payload(self):
        payload1 = {
            "lot_id": "AM-DEMO-001",
            "volume_m3": 5.0,
            "recipient": "Cliente Idem",
            "vehicle": "XYZ-1234",
            "invoice": "NF-100",
            "gross_kg": 20000,
            "tare_kg": 12000,
        }
        self.ledger.reserve(payload1, "key-conflict-1")

        payload2 = dict(payload1, recipient="Outro Cliente Divergente")
        with self.assertRaises(DomainError) as ctx:
            self.ledger.reserve(payload2, "key-conflict-1")
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(ctx.exception.code, "idempotency_conflict")

    def test_concurrency_simultaneous_idempotency(self):
        # 8 threads disparando simultaneamente a mesma reserva com a MESMA chave de idempotência
        payload = {
            "lot_id": "AM-DEMO-001",
            "volume_m3": 5.0,
            "recipient": "Cliente Concorrente",
            "vehicle": "CONC-1234",
            "invoice": "NF-CONC",
            "gross_kg": 20000,
            "tare_kg": 12000,
        }
        import threading
        results = []
        errors = []

        def worker():
            try:
                p = self.ledger.reserve(payload, "same-concurrent-key")
                results.append(p)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Erros inesperados: {errors}")
        self.assertEqual(len(results), 8)
        first_id = results[0]["id"]
        for p in results:
            self.assertEqual(p["id"], first_id)

        # Saldo deve ter sido debitado apenas UMA vez (15000 - 5000 = 10000)
        st = self.ledger.state()
        self.assertEqual(st["lots"][0]["available_milli"], 10000)
        self.assertEqual(len(st["shipments"]), 1)
        self.assertEqual(len(st["events"]), 2)
        self.assertTrue(st["integrity"]["valid"])

    def test_concurrency_simultaneous_different_keys_no_overbooking(self):
        # 6 threads requisitando 3.0 m³ (3000 milli) cada sobre 15000 disponíveis (total requerido 18000)
        # Exatamente 5 devem passar (5 * 3000 = 15000), 1 deve receber 409 insufficient_balance
        import threading
        successes = []
        insufficient = []
        other_errors = []

        def worker(idx):
            payload = {
                "lot_id": "AM-DEMO-001",
                "volume_m3": 3.0,
                "recipient": f"Cliente {idx}",
                "vehicle": f"VEH-{idx}",
                "invoice": f"NF-{idx}",
                "gross_kg": 10000,
                "tare_kg": 6000,
            }
            try:
                p = self.ledger.reserve(payload, f"key-diff-{idx}")
                successes.append(p)
            except DomainError as de:
                if de.code == "insufficient_balance":
                    insufficient.append(de)
                else:
                    other_errors.append(de)
            except Exception as e:
                other_errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(other_errors), 0, f"Erros inesperados: {other_errors}")
        self.assertEqual(len(successes), 5)
        self.assertEqual(len(insufficient), 1)

        # Saldo restante deve ser rigorosamente 0, sem overbooking
        st = self.ledger.state()
        self.assertEqual(st["lots"][0]["available_milli"], 0)
        self.assertEqual(st["lots"][0]["reserved_milli"], 15000)
        self.assertEqual(len(st["shipments"]), 5)
        self.assertEqual(len(st["events"]), 6)  # 1 LOT_OPENED + 5 reservas
        self.assertTrue(st["integrity"]["valid"])


class TestChainTampering(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        self.ledger = Ledger(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_chain_tampering_payload_detection(self):
        payload = {
            "lot_id": "AM-DEMO-001",
            "volume_m3": 5.0,
            "recipient": "Cliente Adulteracao",
            "vehicle": "ABC-1234",
            "invoice": "NF-001",
            "gross_kg": 20000,
            "tare_kg": 12000,
        }
        self.ledger.reserve(payload, "key-tamper-1")

        # Antes da adulteração: integridade válida
        self.assertTrue(self.ledger.verify_chain()["valid"])

        # Adulterar diretamente o payload do evento 2 no SQLite
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE events SET payload = '{\"hacked\": true}' WHERE id = 2")
        conn.commit()
        conn.close()

        # Depois da adulteração: verify_chain deve detectar
        res = self.ledger.verify_chain()
        self.assertFalse(res["valid"])
        self.assertEqual(res["broken_event_id"], 2)

        st = self.ledger.state()
        self.assertFalse(st["integrity"]["valid"])

    def test_chain_tampering_previous_hash_detection(self):
        payload = {
            "lot_id": "AM-DEMO-001",
            "volume_m3": 5.0,
            "recipient": "Cliente Adulteracao 2",
            "vehicle": "ABC-1234",
            "invoice": "NF-002",
            "gross_kg": 20000,
            "tare_kg": 12000,
        }
        self.ledger.reserve(payload, "key-tamper-2")

        # Adulterar previous_hash do evento 2
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE events SET previous_hash = '1' || substr(previous_hash, 2) WHERE id = 2")
        conn.commit()
        conn.close()

        res = self.ledger.verify_chain()
        self.assertFalse(res["valid"])
        self.assertEqual(res["broken_event_id"], 2)


if __name__ == "__main__":
    unittest.main()
