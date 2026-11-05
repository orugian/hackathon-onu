import json
import sqlite3
import hashlib
from datetime import datetime, timezone
import math
import uuid
from decimal import Decimal, ROUND_HALF_UP
from contextlib import contextmanager


class DomainError(Exception):
    """Exceção base de domínio com mensagem, código e status HTTP."""
    def __init__(self, message: str, code: str = "validation_error", status: int = 422):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status

    def __str__(self):
        return self.message

    def to_dict(self):
        return {
            "error": self.message,
            "code": self.code,
            "status": self.status,
        }


def canonical_json(obj: dict) -> str:

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def compute_hash(obj: dict) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()

def _validate_str(val, name: str, max_len: int = 200) -> str:
    if isinstance(val, bool) or not isinstance(val, str):
        raise DomainError(f"Campo '{name}' deve ser texto.", code="validation_error", status=422)
    s = val.strip()
    if not s:
        raise DomainError(f"Campo '{name}' não pode ser vazio.", code="validation_error", status=422)
    if len(s) > max_len:
        raise DomainError(f"Campo '{name}' excede o tamanho máximo de {max_len} caracteres.", code="validation_error", status=422)
    return s

def _validate_volume(val) -> tuple[int, float]:
    if isinstance(val, bool):
        raise DomainError("Campo 'volume_m3' não pode ser booleano.", code="validation_error", status=422)
    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            raise DomainError("Campo 'volume_m3' deve ser finito.", code="validation_error", status=422)
        if val > 1_000_000 or val <= 0:
            if val <= 0:
                raise DomainError("Campo 'volume_m3' deve ser estritamente positivo (> 0).", code="validation_error", status=422)
            raise DomainError("Campo 'volume_m3' excede o limite de 1.000.000 m³.", code="validation_error", status=422)
        s = str(val)
    elif isinstance(val, str):
        s = val.strip()
        if len(s) > 50:
            raise DomainError("Campo 'volume_m3' excede o tamanho máximo de caracteres permitido.", code="validation_error", status=422)
    elif isinstance(val, Decimal):
        s = str(val)
    else:
        raise DomainError("Campo 'volume_m3' inválido.", code="validation_error", status=422)

    try:
        d = Decimal(s)
    except Exception:
        raise DomainError("Campo 'volume_m3' deve ser um decimal válido.", code="validation_error", status=422)

    if not d.is_finite():
        raise DomainError("Campo 'volume_m3' deve ser finito.", code="validation_error", status=422)

    if d <= Decimal(0):
        raise DomainError("Campo 'volume_m3' deve ser estritamente positivo (> 0).", code="validation_error", status=422)
    if d > Decimal(1_000_000):
        raise DomainError("Campo 'volume_m3' excede o limite de 1.000.000 m³.", code="validation_error", status=422)

    milli_d = d * Decimal(1000)
    if milli_d != milli_d.to_integral_value():
        raise DomainError("Campo 'volume_m3' não pode ter mais de 3 casas decimais.", code="validation_error", status=422)

    milli = int(milli_d)
    if milli <= 0:
        raise DomainError("Campo 'volume_m3' em milésimos deve ser estritamente positivo.", code="validation_error", status=422)
    return milli, float(d)

def _validate_mass(val, name: str, allow_zero: bool = False) -> float:
    if isinstance(val, bool):
        raise DomainError(f"Campo '{name}' não pode ser booleano.", code="validation_error", status=422)
    if not isinstance(val, (int, float)):
        raise DomainError(f"Campo '{name}' deve ser numérico.", code="validation_error", status=422)
    if math.isnan(val) or math.isinf(val):
        raise DomainError(f"Campo '{name}' deve ser finito.", code="validation_error", status=422)
    if allow_zero:
        if val < 0:
            raise DomainError(f"Campo '{name}' não pode ser negativo.", code="validation_error", status=422)
    else:
        if val <= 0:
            raise DomainError(f"Campo '{name}' deve ser estritamente positivo (> 0).", code="validation_error", status=422)
    if val > 100_000_000:
        raise DomainError(f"Campo '{name}' excede o limite de 100.000.000 kg.", code="validation_error", status=422)
    return float(val)


def _begin_immediate(conn):
    for attempt in range(30):
        try:
            conn.execute("BEGIN IMMEDIATE")
            return
        except sqlite3.OperationalError as e:
            if ("locked" in str(e).lower() or "busy" in str(e).lower()) and attempt < 29:
                import time
                time.sleep(0.02 * (attempt + 1))
            else:
                raise


class Ledger:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.isolation_level = None  # Autocommit mode para controle explícito de BEGIN IMMEDIATE
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _connection(self):
        conn = self._get_connection()
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._connection() as conn:
            _begin_immediate(conn)
            try:

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS lots (
                        id TEXT PRIMARY KEY,
                        plot_id TEXT NOT NULL,
                        product TEXT NOT NULL,
                        species TEXT NOT NULL,
                        opening_milli INTEGER NOT NULL,
                        available_milli INTEGER NOT NULL CHECK(available_milli >= 0),
                        reserved_milli INTEGER NOT NULL DEFAULT 0 CHECK(reserved_milli >= 0),
                        unit TEXT NOT NULL,
                        simulated INTEGER NOT NULL DEFAULT 1
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        type TEXT NOT NULL,
                        at TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        previous_hash TEXT NOT NULL,
                        hash TEXT NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS passports (
                        id TEXT PRIMARY KEY,
                        lot_id TEXT NOT NULL,
                        issued_at TEXT NOT NULL,
                        passport_json TEXT NOT NULL,
                        hash TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS idempotency (
                        key TEXT PRIMARY KEY,
                        payload_hash TEXT NOT NULL,
                        passport_id TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS assessments (
                        id TEXT PRIMARY KEY,
                        rule_id TEXT NOT NULL,
                        rule_version TEXT NOT NULL,
                        quantity_m3 REAL NOT NULL,
                        hypothesis TEXT NOT NULL,
                        reviewer TEXT NOT NULL,
                        fine_brl TEXT NOT NULL,
                        fee_brl TEXT NOT NULL,
                        formula TEXT NOT NULL,
                        notice TEXT NOT NULL,
                        status TEXT NOT NULL,
                        review TEXT,
                        created_at TEXT NOT NULL
                    );
                """)

                # Criar lote inicial AM-DEMO-001 se ainda não existir
                cur = conn.execute("SELECT COUNT(*) FROM lots WHERE id = 'AM-DEMO-001'")
                if cur.fetchone()[0] == 0:
                    conn.execute("""
                        INSERT INTO lots (id, plot_id, product, species, opening_milli, available_milli, reserved_milli, unit, simulated)
                        VALUES ('AM-DEMO-001', 'AREA-DEMO-001', 'Madeira em tora', 'Táxon não verificado', 15000, 15000, 0, 'm³', 1)
                    """)
                    now_utc = datetime.now(timezone.utc).isoformat()
                    payload = {
                        "lot_id": "AM-DEMO-001",
                        "plot_id": "AREA-DEMO-001",
                        "opening_milli": 15000,
                        "available_milli": 15000,
                        "unit": "m³",
                        "simulated": True,
                    }
                    prev_hash = "0" * 64
                    # ID do evento inicial será 1
                    event_data_for_hash = {
                        "id": 1,
                        "type": "LOT_OPENED",
                        "at": now_utc,
                        "payload": payload,
                        "previous_hash": prev_hash,
                    }
                    ev_hash = compute_hash(event_data_for_hash)
                    conn.execute("""
                        INSERT INTO events (id, type, at, payload, previous_hash, hash)
                        VALUES (1, 'LOT_OPENED', ?, ?, ?, ?)
                    """, (now_utc, json.dumps(payload, ensure_ascii=False), prev_hash, ev_hash))

                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def _verify_chain_events(self, events: list) -> dict:
        if not events:
            return {"valid": True, "count": 0, "broken_event_id": None}

        expected_prev_hash = "0" * 64
        count = 0
        for ev in events:
            ev_id = ev["id"]
            ev_type = ev["type"]
            ev_at = ev["at"]
            ev_payload = ev["payload"]
            ev_prev_hash = ev["previous_hash"]
            ev_hash = ev["hash"]

            if ev_prev_hash != expected_prev_hash:
                return {"valid": False, "count": count, "broken_event_id": ev_id}

            expected_hash = compute_hash({
                "id": ev_id,
                "type": ev_type,
                "at": ev_at,
                "payload": ev_payload,
                "previous_hash": ev_prev_hash,
            })
            if ev_hash != expected_hash:
                return {"valid": False, "count": count, "broken_event_id": ev_id}

            expected_prev_hash = ev_hash
            count += 1

        return {"valid": True, "count": count, "broken_event_id": None}

    def verify_chain(self) -> dict:
        with self._connection() as conn:
            events = []
            for r in conn.execute("SELECT id, type, at, payload, previous_hash, hash FROM events ORDER BY id ASC"):
                try:
                    payload = json.loads(r["payload"])
                except Exception:
                    return {"valid": False, "count": len(events), "broken_event_id": r["id"]}
                events.append({
                    "id": r["id"],
                    "type": r["type"],
                    "at": r["at"],
                    "payload": payload,
                    "previous_hash": r["previous_hash"],
                    "hash": r["hash"],
                })
            return self._verify_chain_events(events)

    def state(self) -> dict:
        with self._connection() as conn:
            conn.execute("BEGIN")
            try:
                lots = []
                for r in conn.execute("SELECT id, plot_id, product, species, opening_milli, available_milli, reserved_milli, unit, simulated FROM lots ORDER BY id ASC"):
                    lots.append({
                        "id": r["id"],
                        "plot_id": r["plot_id"],
                        "product": r["product"],
                        "species": r["species"],
                        "opening_milli": r["opening_milli"],
                        "available_milli": r["available_milli"],
                        "reserved_milli": r["reserved_milli"],
                        "unit": r["unit"],
                        "simulated": bool(r["simulated"]),
                    })

                shipments = []
                for r in conn.execute("SELECT passport_json FROM passports ORDER BY created_at ASC, id ASC"):
                    shipments.append(json.loads(r["passport_json"]))

                assessments = []
                for r in conn.execute("SELECT id, rule_id, rule_version, quantity_m3, hypothesis, reviewer, fine_brl, fee_brl, formula, notice, status, review FROM assessments ORDER BY created_at ASC, id ASC"):
                    review_val = json.loads(r["review"]) if r["review"] else None
                    assessments.append({
                        "id": r["id"],
                        "rule_id": r["rule_id"],
                        "rule_version": r["rule_version"],
                        "quantity_m3": r["quantity_m3"],
                        "hypothesis": r["hypothesis"],
                        "reviewer": r["reviewer"],
                        "fine_brl": r["fine_brl"],
                        "fee_brl": r["fee_brl"],
                        "formula": r["formula"],
                        "notice": r["notice"],
                        "status": r["status"],
                        "review": review_val,
                    })

                events = []
                for r in conn.execute("SELECT id, type, at, payload, previous_hash, hash FROM events ORDER BY id ASC"):
                    try:
                        p_val = json.loads(r["payload"])
                    except Exception:
                        p_val = {"_corrupt": r["payload"]}
                    events.append({
                        "id": r["id"],
                        "type": r["type"],
                        "at": r["at"],
                        "payload": p_val,
                        "previous_hash": r["previous_hash"],
                        "hash": r["hash"],
                    })

                integrity_res = self._verify_chain_events(events)
                conn.execute("COMMIT")
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise

        return {
            "lots": lots,
            "shipments": shipments,
            "assessments": assessments,
            "events": events,
            "integrity": {
                "valid": integrity_res["valid"],
                "count": integrity_res["count"],
            },
        }

    def reserve(self, payload: dict, idempotency_key: str) -> dict:
        key = _validate_str(idempotency_key, "idempotency_key", max_len=128)
        if not isinstance(payload, dict):
            raise DomainError("Payload de reserva deve ser um objeto JSON.", code="validation_error", status=422)

        lot_id = _validate_str(payload.get("lot_id"), "lot_id", max_len=200)
        volume_milli, volume_m3 = _validate_volume(payload.get("volume_m3"))
        recipient = _validate_str(payload.get("recipient"), "recipient", max_len=200)
        vehicle = _validate_str(payload.get("vehicle"), "vehicle", max_len=200)
        invoice = _validate_str(payload.get("invoice"), "invoice", max_len=200)
        gross_kg = _validate_mass(payload.get("gross_kg"), "gross_kg", allow_zero=False)
        tare_kg = _validate_mass(payload.get("tare_kg"), "tare_kg", allow_zero=True)

        if gross_kg <= tare_kg:
            raise DomainError("Peso bruto deve ser estritamente maior que o peso da tara.", code="validation_error", status=422)

        from calculations import weigh
        weighing_result = weigh(volume_m3=volume_m3, gross_kg=gross_kg, tare_kg=tare_kg)

        canonical_payload = {
            "gross_kg": gross_kg,
            "invoice": invoice,
            "lot_id": lot_id,
            "recipient": recipient,
            "tare_kg": tare_kg,
            "vehicle": vehicle,
            "volume_milli": volume_milli,
        }
        payload_hash = compute_hash(canonical_payload)

        with self._connection() as conn:
            _begin_immediate(conn)
            try:
                # 1. Verificar idempotência
                cur = conn.execute("SELECT payload_hash, passport_id FROM idempotency WHERE key = ?", (key,))
                existing_idem = cur.fetchone()
                if existing_idem:
                    if existing_idem["payload_hash"] == payload_hash:
                        p_cur = conn.execute("SELECT passport_json FROM passports WHERE id = ?", (existing_idem["passport_id"],))
                        p_row = p_cur.fetchone()
                        conn.execute("COMMIT")
                        return json.loads(p_row["passport_json"])
                    else:
                        conn.execute("ROLLBACK")
                        raise DomainError("Chave de idempotência já utilizada com payload divergente.", code="idempotency_conflict", status=409)

                # 2. Obter lote e verificar saldo
                lot_cur = conn.execute("SELECT id, plot_id, product, species, opening_milli, available_milli, reserved_milli FROM lots WHERE id = ?", (lot_id,))
                lot = lot_cur.fetchone()
                if not lot:
                    conn.execute("ROLLBACK")
                    raise DomainError(f"Lote '{lot_id}' não encontrado.", code="not_found", status=404)

                available_milli = lot["available_milli"]
                if available_milli < volume_milli:
                    conn.execute("ROLLBACK")
                    raise DomainError(
                        f"Saldo insuficiente no lote '{lot_id}'. Solicitado: {volume_milli} milli ({volume_m3} m³), Disponível: {available_milli} milli.",
                        code="insufficient_balance",
                        status=409
                    )

                new_available = available_milli - volume_milli
                new_reserved = lot["reserved_milli"] + volume_milli
                conn.execute(
                    "UPDATE lots SET available_milli = ?, reserved_milli = ? WHERE id = ?",
                    (new_available, new_reserved, lot_id)
                )

                # 3. Próximo ID de evento e hash anterior
                ev_cur = conn.execute("SELECT id, hash FROM events ORDER BY id DESC LIMIT 1")
                last_ev = ev_cur.fetchone()
                prev_hash = last_ev["hash"] if last_ev else "0" * 64
                next_ev_id = (last_ev["id"] + 1) if last_ev else 1

                # 4. Construir passaporte
                passport_id = f"PASS-{uuid.uuid4().hex[:12].upper()}"
                now_utc = datetime.now(timezone.utc).isoformat()
                passport = {
                    "schema_version": "1.0.0",
                    "id": passport_id,
                    "issued_at": now_utc,
                    "lot_id": lot_id,
                    "plot_id": lot["plot_id"],
                    "origin": {
                        "name": "Área demonstrativa · Itacoatiara/AM",
                        "simulated": True,
                    },
                    "authorization": {
                        "reference": "AUT-DEMO-001",
                        "issuer": "Referência fictícia",
                        "status": "não verificável",
                    },
                    "recipient": recipient,
                    "product": lot["product"],
                    "species": lot["species"],
                    "volume_m3": round(volume_milli / 1000.0, 3),
                    "volume_milli": volume_milli,
                    "vehicle": vehicle,
                    "invoice": invoice,
                    "weighing": weighing_result,
                    "balance_after_milli": new_available,
                    "event_id": next_ev_id,
                    "notice": "Passaporte experimental de produto florestal — SEM VALIDADE OFICIAL",
                    "simulated": True,
                }
                passport["hash"] = compute_hash(passport)

                # 5. Criar evento na cadeia
                event_payload = {
                    "passport_id": passport_id,
                    "lot_id": lot_id,
                    "volume_milli": volume_milli,
                    "balance_after_milli": new_available,
                    "passport_hash": passport["hash"],
                }
                ev_data = {
                    "id": next_ev_id,
                    "type": "SHIPMENT_RESERVED",
                    "at": now_utc,
                    "payload": event_payload,
                    "previous_hash": prev_hash,
                }
                event_hash = compute_hash(ev_data)
                conn.execute("""
                    INSERT INTO events (id, type, at, payload, previous_hash, hash)
                    VALUES (?, 'SHIPMENT_RESERVED', ?, ?, ?, ?)
                """, (next_ev_id, now_utc, json.dumps(event_payload, ensure_ascii=False), prev_hash, event_hash))

                # 6. Salvar passaporte
                conn.execute("""
                    INSERT INTO passports (id, lot_id, issued_at, passport_json, hash, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (passport_id, lot_id, now_utc, json.dumps(passport, ensure_ascii=False), passport["hash"], now_utc))

                # 7. Salvar chave de idempotência
                conn.execute("""
                    INSERT INTO idempotency (key, payload_hash, passport_id, created_at)
                    VALUES (?, ?, ?, ?)
                """, (key, payload_hash, passport_id, now_utc))

                conn.execute("COMMIT")
                return passport
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise



    def passport(self, passport_id: str) -> dict:
        pid = _validate_str(passport_id, "passport_id", max_len=200)
        with self._connection() as conn:
            cur = conn.execute("SELECT passport_json FROM passports WHERE id = ?", (pid,))
            row = cur.fetchone()
            if not row:
                raise DomainError(f"Passaporte '{pid}' não encontrado.", code="not_found", status=404)
            return json.loads(row["passport_json"])

    def assess(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise DomainError("Payload de avaliação deve ser um objeto JSON.", code="validation_error", status=422)

        _, q_float = _validate_volume(payload.get("quantity_m3"))
        hypothesis = _validate_str(payload.get("hypothesis"), "hypothesis", max_len=500)
        reviewer = _validate_str(payload.get("reviewer"), "reviewer", max_len=200)

        q_dec = Decimal(str(q_float))
        fine = (q_dec * Decimal("300")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        fee = (Decimal("50") + q_dec * Decimal("2")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        fine_brl = f"{fine:.2f}"
        fee_brl = f"{fee:.2f}"

        asm_id = f"ASM-{uuid.uuid4().hex[:12].upper()}"
        rule_id = "SIM-001"
        rule_version = "v1.0"
        formula = f"SIM-001 v1.0: fine_brl = quantity_m3 ({q_float}) * 300 = {fine_brl}; fee_brl = 50 + quantity_m3 ({q_float}) * 2 = {fee_brl}"
        notice = "Simulação paramétrica baseada na regra SIM-001 v1.0 — SEM VALIDADE OFICIAL e sem aplicação do Art. 47."
        status = "pending"
        now_utc = datetime.now(timezone.utc).isoformat()

        result = {
            "id": asm_id,
            "rule_id": rule_id,
            "rule_version": rule_version,
            "quantity_m3": q_float,
            "hypothesis": hypothesis,
            "reviewer": reviewer,
            "fine_brl": fine_brl,
            "fee_brl": fee_brl,
            "formula": formula,
            "notice": notice,
            "status": status,
            "review": None,
        }

        with self._connection() as conn:
            _begin_immediate(conn)
            try:
                conn.execute("""
                    INSERT INTO assessments (id, rule_id, rule_version, quantity_m3, hypothesis, reviewer, fine_brl, fee_brl, formula, notice, status, review, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (asm_id, rule_id, rule_version, q_float, hypothesis, reviewer, fine_brl, fee_brl, formula, notice, status, None, now_utc))

                ev_cur = conn.execute("SELECT id, hash FROM events ORDER BY id DESC LIMIT 1")
                last_ev = ev_cur.fetchone()
                prev_hash = last_ev["hash"] if last_ev else "0" * 64
                next_ev_id = (last_ev["id"] + 1) if last_ev else 1

                event_payload = {
                    "assessment_id": asm_id,
                    "rule_id": rule_id,
                    "rule_version": rule_version,
                    "quantity_m3": q_float,
                    "hypothesis": hypothesis,
                    "reviewer": reviewer,
                    "fine_brl": fine_brl,
                    "fee_brl": fee_brl,
                    "status": status,
                }
                ev_data = {
                    "id": next_ev_id,
                    "type": "ASSESSMENT_CREATED",
                    "at": now_utc,
                    "payload": event_payload,
                    "previous_hash": prev_hash,
                }
                event_hash = compute_hash(ev_data)

                conn.execute("""
                    INSERT INTO events (id, type, at, payload, previous_hash, hash)
                    VALUES (?, 'ASSESSMENT_CREATED', ?, ?, ?, ?)
                """, (next_ev_id, now_utc, json.dumps(event_payload, ensure_ascii=False), prev_hash, event_hash))

                conn.execute("COMMIT")
                return result
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise

    def review(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise DomainError("Payload de revisão deve ser um objeto JSON.", code="validation_error", status=422)

        assessment_id = _validate_str(payload.get("assessment_id"), "assessment_id", max_len=200)
        decision = _validate_str(payload.get("decision"), "decision", max_len=20)
        if decision not in ("agree", "disagree"):
            raise DomainError("Decisão deve ser 'agree' ou 'disagree'.", code="validation_error", status=422)
        reviewer = _validate_str(payload.get("reviewer"), "reviewer", max_len=200)
        reason = _validate_str(payload.get("reason"), "reason", max_len=1000)

        now_utc = datetime.now(timezone.utc).isoformat()
        review_obj = {
            "decision": decision,
            "reviewer": reviewer,
            "reason": reason,
            "reviewed_at": now_utc,
        }
        new_status = "agreed" if decision == "agree" else "disagreed"

        with self._connection() as conn:
            _begin_immediate(conn)
            try:
                cur = conn.execute("SELECT id, rule_id, rule_version, quantity_m3, hypothesis, reviewer, fine_brl, fee_brl, formula, notice, status, review FROM assessments WHERE id = ?", (assessment_id,))
                asm = cur.fetchone()
                if not asm:
                    conn.execute("ROLLBACK")
                    raise DomainError(f"Avaliação '{assessment_id}' não encontrada.", code="not_found", status=404)

                if asm["status"] != "pending" or asm["review"] is not None:
                    conn.execute("ROLLBACK")
                    raise DomainError(f"Avaliação '{assessment_id}' já possui parecer definitivo homologado.", code="conflict", status=409)

                review_json = json.dumps(review_obj, ensure_ascii=False)
                conn.execute("UPDATE assessments SET status = ?, review = ? WHERE id = ?", (new_status, review_json, assessment_id))

                ev_cur = conn.execute("SELECT id, hash FROM events ORDER BY id DESC LIMIT 1")
                last_ev = ev_cur.fetchone()
                prev_hash = last_ev["hash"] if last_ev else "0" * 64
                next_ev_id = (last_ev["id"] + 1) if last_ev else 1

                event_payload = {
                    "assessment_id": assessment_id,
                    "decision": decision,
                    "reviewer": reviewer,
                    "reason": reason,
                    "status": new_status,
                    "reviewed_at": now_utc,
                }
                ev_data = {
                    "id": next_ev_id,
                    "type": "ASSESSMENT_REVIEWED",
                    "at": now_utc,
                    "payload": event_payload,
                    "previous_hash": prev_hash,
                }
                event_hash = compute_hash(ev_data)

                conn.execute("""
                    INSERT INTO events (id, type, at, payload, previous_hash, hash)
                    VALUES (?, 'ASSESSMENT_REVIEWED', ?, ?, ?, ?)
                """, (next_ev_id, now_utc, json.dumps(event_payload, ensure_ascii=False), prev_hash, event_hash))

                conn.execute("COMMIT")

                return {
                    "id": assessment_id,
                    "rule_id": asm["rule_id"],
                    "rule_version": asm["rule_version"],
                    "quantity_m3": asm["quantity_m3"],
                    "hypothesis": asm["hypothesis"],
                    "reviewer": asm["reviewer"],
                    "fine_brl": asm["fine_brl"],
                    "fee_brl": asm["fee_brl"],
                    "formula": asm["formula"],
                    "notice": asm["notice"],
                    "status": new_status,
                    "review": review_obj,
                }
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise
