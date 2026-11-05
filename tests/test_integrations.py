import unittest
import os
import tempfile
from unittest.mock import MagicMock

import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import MagicMock

class TestIntegrationsAllowlistAndLimits(unittest.TestCase):
    def test_allowlist_enforcement(self):
        """Only allowlisted URLs can be fetched; arbitrary URLs must be rejected."""
        from integrations import SourceService, ALLOWED_URLS
        service = SourceService()
        self.assertIn("ibge_municipality", ALLOWED_URLS)
        self.assertIn("ibge_state", ALLOWED_URLS)
        self.assertIn("deter_alerts", ALLOWED_URLS)
        with self.assertRaises(ValueError):
            service.validate_url("https://malicious-site.com/data.json")

    def test_payload_size_limit_8mb(self):
        """Payloads exceeding 8MB (8 * 1024 * 1024 bytes) must be rejected."""
        from integrations import SourceService, MAX_PAYLOAD_BYTES
        self.assertEqual(MAX_PAYLOAD_BYTES, 8 * 1024 * 1024)
        service = SourceService()
        huge_bytes = b"x" * (MAX_PAYLOAD_BYTES + 1)
        with self.assertRaises(ValueError):
            service.check_payload_size(huge_bytes)

class TestIntegrationsCacheOffline(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_refresh_false_when_cache_missing(self):
        """When cache does not exist, get(refresh=False) returns empty FC and status unavailable without calling fetcher."""
        from integrations import SourceService
        fetcher_mock = MagicMock()
        service = SourceService(cache_dir=self.test_dir, fetcher=fetcher_mock)

        result = service.get(refresh=False)

        fetcher_mock.assert_not_called()
        self.assertEqual(result["municipality"], {"type": "FeatureCollection", "features": []})
        self.assertEqual(result["state"], {"type": "FeatureCollection", "features": []})
        self.assertEqual(result["alerts"], {"type": "FeatureCollection", "features": []})
        self.assertEqual(len(result["sources"]), 3)
        for s in result["sources"]:
            self.assertEqual(s["status"], "unavailable")
            self.assertEqual(s["feature_count"], 0)
            self.assertIsNone(s["sha256"])
            self.assertIsNone(s["fetched_at"])
        self.assertIn("notice", result)

    def test_get_refresh_false_when_cache_present(self):
        """When cache exists, get(refresh=False) returns cached FCs and status cached without calling fetcher."""
        import hashlib
        from integrations import SourceService
        fetcher_mock = MagicMock()

        mun_fc = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-58.5, -3.1], [-58.4, -3.1], [-58.4, -3.2], [-58.5, -3.1]]]}, "properties": {"codarea": "1301902"}}]
        }
        mun_raw_text = json.dumps(mun_fc)

        state_fc = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-60.0, -3.0], [-55.0, -3.0], [-55.0, -6.0], [-60.0, -3.0]]]}, "properties": {"codarea": "13"}}]
        }
        state_raw_text = json.dumps(state_fc)

        deter_fc = {
            "type": "FeatureCollection",
            "totalFeatures": 800,
            "features": [{"type": "Feature", "geometry": {"type": "MultiPolygon", "coordinates": [[[[-58.45, -3.15], [-58.44, -3.15], [-58.44, -3.16], [-58.45, -3.15]]]]}, "properties": {"gid": "alert1", "classname": "DESMATAMENTO_CR", "view_date": "2026-10-20", "uf": "AM", "mun_geocod": "1301902"}}]
        }
        deter_raw_text = json.dumps(deter_fc)

        # Write cached envelopes with raw_text and valid sha256
        cached_data = {
            "ibge_municipality": {
                "id": "ibge_municipality",
                "name": "IBGE Malha Municipal - Itacoatiara (1301902)",
                "url": "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/1301902?formato=application/vnd.geo+json&qualidade=minima",
                "fetched_at": "2026-11-05T20:00:00Z",
                "status": "cached",
                "sha256": hashlib.sha256(mun_raw_text.encode("utf-8")).hexdigest(),
                "feature_count": 1,
                "partial": False,
                "total_available": 1,
                "raw_text": mun_raw_text,
                "raw": mun_fc,
            },
            "ibge_state": {
                "id": "ibge_state",
                "name": "IBGE Malha Estadual - Amazonas (13)",
                "url": "https://servicodados.ibge.gov.br/api/v3/malhas/estados/13?formato=application/vnd.geo+json&qualidade=minima",
                "fetched_at": "2026-11-05T20:00:00Z",
                "status": "cached",
                "sha256": hashlib.sha256(state_raw_text.encode("utf-8")).hexdigest(),
                "feature_count": 1,
                "partial": False,
                "total_available": 1,
                "raw_text": state_raw_text,
                "raw": state_fc,
            },
            "deter_alerts": {
                "id": "deter_alerts",
                "name": "INPE DETER Amazônia - Alertas Itacoatiara (1301902)",
                "url": "https://terrabrasilis.dpi.inpe.br/geoserver/deter-amz/ows?service=WFS&version=2.0.0&request=GetFeature&typeNames=deter-amz:deter_amz&outputFormat=application%2Fjson&count=200&sortBy=view_date%20D&CQL_FILTER=mun_geocod%3D%271301902%27&srsName=EPSG:4326",
                "fetched_at": "2026-11-05T20:00:00Z",
                "status": "cached",
                "sha256": hashlib.sha256(deter_raw_text.encode("utf-8")).hexdigest(),
                "feature_count": 1,
                "partial": True,
                "total_available": 800,
                "raw_text": deter_raw_text,
                "raw": deter_fc,
            }
        }
        for k, v in cached_data.items():
            with open(os.path.join(self.test_dir, f"{k}.json"), "w", encoding="utf-8") as f:
                json.dump(v, f)

        service = SourceService(cache_dir=self.test_dir, fetcher=fetcher_mock)
        result = service.get(refresh=False)

        fetcher_mock.assert_not_called()
        self.assertEqual(len(result["municipality"]["features"]), 1)
        self.assertEqual(len(result["state"]["features"]), 1)
        self.assertEqual(len(result["alerts"]["features"]), 1)
        for s in result["sources"]:
            self.assertEqual(s["status"], "cached")
            self.assertIsNotNone(s["sha256"])
            self.assertEqual(s["fetched_at"], "2026-11-05T20:00:00Z")

    def test_tampered_cache_hash_mismatch_rejected(self):
        """If cache raw_text or sha256 is tampered with, cache must be rejected (status unavailable)."""
        import hashlib
        from integrations import SourceService
        valid_fc = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-58.5, -3.1], [-58.4, -3.1], [-58.4, -3.2], [-58.5, -3.1]]]}, "properties": {"codarea": "1301902"}}]
        }
        raw_text = json.dumps(valid_fc)
        envelope = {
            "id": "ibge_municipality",
            "name": "IBGE Malha Municipal - Itacoatiara (1301902)",
            "url": "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/1301902?formato=application/vnd.geo+json&qualidade=minima",
            "fetched_at": "2026-11-05T20:00:00Z",
            "status": "cached",
            "sha256": "tampered_fake_hash_1234567890abcdef1234567890abcdef1234567890abcdef",  # Wrong hash!
            "feature_count": 1,
            "partial": False,
            "total_available": 1,
            "raw_text": raw_text,
            "raw": valid_fc,
        }
        with open(os.path.join(self.test_dir, "ibge_municipality.json"), "w", encoding="utf-8") as f:
            json.dump(envelope, f)

        service = SourceService(cache_dir=self.test_dir)
        result = service.get(refresh=False)
        mun_source = next(s for s in result["sources"] if s["id"] == "ibge_municipality")
        self.assertEqual(mun_source["status"], "unavailable")
        self.assertEqual(result["municipality"]["features"], [])

    def test_untrusted_url_in_cache_rejected(self):
        """If cached envelope contains an altered URL not matching allowlist, cache must be rejected."""
        import hashlib
        from integrations import SourceService
        valid_fc = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-58.5, -3.1], [-58.4, -3.1], [-58.4, -3.2], [-58.5, -3.1]]]}, "properties": {"codarea": "1301902"}}]
        }
        raw_text = json.dumps(valid_fc)
        envelope = {
            "id": "ibge_municipality",
            "name": "IBGE Malha Municipal - Itacoatiara (1301902)",
            "url": "https://attacker.com/malicious_malha.json",  # Untrusted URL!
            "fetched_at": "2026-11-05T20:00:00Z",
            "status": "cached",
            "sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            "feature_count": 1,
            "partial": False,
            "total_available": 1,
            "raw_text": raw_text,
            "raw": valid_fc,
        }
        with open(os.path.join(self.test_dir, "ibge_municipality.json"), "w", encoding="utf-8") as f:
            json.dump(envelope, f)

        service = SourceService(cache_dir=self.test_dir)
        result = service.get(refresh=False)
        mun_source = next(s for s in result["sources"] if s["id"] == "ibge_municipality")
        self.assertEqual(mun_source["status"], "unavailable")
        self.assertEqual(result["municipality"]["features"], [])

    def test_invalid_schema_in_cache_rejected(self):
        """If cached envelope contains GeoJSON failing schema validation, cache must be rejected."""
        import hashlib
        from integrations import SourceService
        invalid_fc = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[True, -3.1], [-58.4, -3.1], [-58.4, -3.2], [True, -3.1]]]}, "properties": {"codarea": "1301902"}}]
        }
        raw_text = json.dumps(invalid_fc)
        envelope = {
            "id": "ibge_municipality",
            "name": "IBGE Malha Municipal - Itacoatiara (1301902)",
            "url": "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/1301902?formato=application/vnd.geo+json&qualidade=minima",
            "fetched_at": "2026-11-05T20:00:00Z",
            "status": "cached",
            "sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            "feature_count": 1,
            "partial": False,
            "total_available": 1,
            "raw_text": raw_text,
            "raw": invalid_fc,
        }
        with open(os.path.join(self.test_dir, "ibge_municipality.json"), "w", encoding="utf-8") as f:
            json.dump(envelope, f)

        service = SourceService(cache_dir=self.test_dir)
        result = service.get(refresh=False)
        mun_source = next(s for s in result["sources"] if s["id"] == "ibge_municipality")
        self.assertEqual(mun_source["status"], "unavailable")
        self.assertEqual(result["municipality"]["features"], [])

class TestIntegrationsValidation(unittest.TestCase):
    def setUp(self):
        from integrations import SourceService
        self.service = SourceService()

    def test_malformed_json_bytes_rejected(self):
        """Malformed JSON bytes must raise ValueError."""
        with self.assertRaises(ValueError):
            self.service.parse_and_validate(b"{not json", "ibge_municipality")

    def test_non_feature_collection_rejected(self):
        """JSON that is not a FeatureCollection must raise ValueError."""
        with self.assertRaises(ValueError):
            self.service.parse_and_validate(b'{"type": "Point", "coordinates": [0, 0]}', "ibge_municipality")

    def test_invalid_coordinates_infinite_or_nan(self):
        """Features with non-finite coordinates (Inf, NaN, out of range) must be rejected."""
        invalid_geo = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[float("nan"), -3.1], [-58.4, -3.1], [-58.4, -3.2], [float("nan"), -3.1]]]},
                "properties": {"codarea": "1301902"}
            }]
        }
        with self.assertRaises(ValueError):
            self.service.validate_fc_structure(invalid_geo, "ibge_municipality")

    def test_resposta_pa_rejeitada(self):
        """DETER alerts with uf != 'AM' or mun_geocod != '1301902' (e.g. Pará PA) must be rejected."""
        pa_alerts = {
            "type": "FeatureCollection",
            "totalFeatures": 1,
            "numberReturned": 1,
            "features": [{
                "type": "Feature",
                "geometry": {"type": "MultiPolygon", "coordinates": [[[[-52.0, -3.0], [-51.9, -3.0], [-51.9, -3.1], [-52.0, -3.0]]]]},
                "properties": {
                    "gid": "alert_pa_1",
                    "classname": "DESMATAMENTO_CR",
                    "view_date": "2026-10-15",
                    "uf": "PA",  # Pará! Should be rejected
                    "mun_geocod": "1500107",
                    "municipality": "Abaetetuba"
                }
            }]
        }
        with self.assertRaises(ValueError):
            self.service.validate_fc_structure(pa_alerts, "deter_alerts")

    def test_deter_alert_foreign_municipality_rejected(self):
        """DETER alerts from Amazonas but wrong municipality code must be rejected."""
        wrong_mun_alerts = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "MultiPolygon", "coordinates": [[[[-60.0, -3.0], [-59.9, -3.0], [-59.9, -3.1], [-60.0, -3.0]]]]},
                "properties": {
                    "gid": "alert_manaus_1",
                    "classname": "DESMATAMENTO_CR",
                    "view_date": "2026-10-15",
                    "uf": "AM",
                    "mun_geocod": "1302603",
                    "municipality": "Manaus"
                }
            }]
        }
        with self.assertRaises(ValueError):
            self.service.validate_fc_structure(wrong_mun_alerts, "deter_alerts")

    def test_ibge_municipality_codarea_mismatch_rejected(self):
        """IBGE municipality data with wrong codarea must be rejected."""
        wrong_ibge = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[-60.0, -3.0], [-59.9, -3.0], [-59.9, -3.1], [-60.0, -3.0]]]},
                "properties": {"codarea": "1302603"}
            }]
        }
        with self.assertRaises(ValueError):
            self.service.validate_fc_structure(wrong_ibge, "ibge_municipality")

    def test_ibge_state_codarea_mismatch_rejected(self):
        """IBGE state data with wrong codarea must be rejected."""
        wrong_state = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[-50.0, -3.0], [-49.9, -3.0], [-49.9, -3.1], [-50.0, -3.0]]]},
                "properties": {"codarea": "15"}
            }]
        }
        with self.assertRaises(ValueError):
            self.service.validate_fc_structure(wrong_state, "ibge_state")

    def test_coordinates_reject_booleans(self):
        """Coordinates containing boolean values must be rejected."""
        geo_with_bool = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[True, -3.1], [-58.4, -3.1], [-58.4, -3.2], [True, -3.1]]]},
                "properties": {"codarea": "1301902"}
            }]
        }
        with self.assertRaises(ValueError):
            self.service.validate_fc_structure(geo_with_bool, "ibge_municipality")

    def test_unclosed_ring_rejected(self):
        """A linear ring where first and last positions do not match must be rejected."""
        unclosed_geo = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[-58.5, -3.1], [-58.4, -3.1], [-58.4, -3.2], [-58.5, -3.3]]]},
                "properties": {"codarea": "1301902"}
            }]
        }
        with self.assertRaises(ValueError):
            self.service.validate_fc_structure(unclosed_geo, "ibge_municipality")

    def test_ring_fewer_than_four_positions_rejected(self):
        """A linear ring with fewer than 4 positions must be rejected."""
        short_ring = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[-58.5, -3.1], [-58.4, -3.1], [-58.5, -3.1]]]},
                "properties": {"codarea": "1301902"}
            }]
        }
        with self.assertRaises(ValueError):
            self.service.validate_fc_structure(short_ring, "ibge_municipality")

    def test_position_not_two_numbers_rejected(self):
        """A position with length other than 2 must be rejected."""
        three_coords = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[-58.5, -3.1, 10.0], [-58.4, -3.1, 10.0], [-58.4, -3.2, 10.0], [-58.5, -3.1, 10.0]]]},
                "properties": {"codarea": "1301902"}
            }]
        }
        with self.assertRaises(ValueError):
            self.service.validate_fc_structure(three_coords, "ibge_municipality")

    def test_missing_required_properties_rejected(self):
        """Missing codarea in IBGE or missing date/UF/code in DETER alerts must be rejected."""
        # Missing codarea in municipality
        ibge_no_codarea = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[-58.5, -3.1], [-58.4, -3.1], [-58.4, -3.2], [-58.5, -3.1]]]},
                "properties": {}
            }]
        }
        with self.assertRaises(ValueError):
            self.service.validate_fc_structure(ibge_no_codarea, "ibge_municipality")

        # Missing view_date in DETER
        deter_no_date = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "MultiPolygon", "coordinates": [[[[-58.45, -3.15], [-58.44, -3.15], [-58.44, -3.16], [-58.45, -3.15]]]]},
                "properties": {"gid": "alert1", "uf": "AM", "mun_geocod": "1301902"}
            }]
        }
        with self.assertRaises(ValueError):
            self.service.validate_fc_structure(deter_no_date, "deter_alerts")

        # Missing gid/id in DETER
        deter_no_id = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "MultiPolygon", "coordinates": [[[[-58.45, -3.15], [-58.44, -3.15], [-58.44, -3.16], [-58.45, -3.15]]]]},
                "properties": {"view_date": "2026-10-20", "uf": "AM", "mun_geocod": "1301902"}
            }]
        }
        with self.assertRaises(ValueError):
            self.service.validate_fc_structure(deter_no_id, "deter_alerts")


class TestIntegrationsLiveRefreshAndResilience(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_refresh_success_atomic_cache_and_live_status(self):
        """Successful refresh validates data, writes cache atomically, and returns status live with sha256."""
        from integrations import SourceService, ALLOWED_URLS
        valid_mun_bytes = json.dumps({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[-58.5, -3.1], [-58.4, -3.1], [-58.4, -3.2], [-58.5, -3.1]]]},
                "properties": {"codarea": "1301902"}
            }]
        }).encode("utf-8")

        valid_state_bytes = json.dumps({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[-60.0, -3.0], [-55.0, -3.0], [-55.0, -6.0], [-60.0, -3.0]]]},
                "properties": {"codarea": "13"}
            }]
        }).encode("utf-8")

        valid_deter_bytes = json.dumps({
            "type": "FeatureCollection",
            "totalFeatures": 540,
            "numberReturned": 200,
            "features": [{
                "type": "Feature",
                "geometry": {"type": "MultiPolygon", "coordinates": [[[[-58.45, -3.15], [-58.44, -3.15], [-58.44, -3.16], [-58.45, -3.15]]]]},
                "properties": {
                    "gid": "alert1",
                    "classname": "DESMATAMENTO_CR",
                    "view_date": "2026-10-20",
                    "sensor": "AWFI",
                    "satellite": "CBERS-4",
                    "areamunkm": 1.25,
                    "municipality": "Itacoatiara",
                    "mun_geocod": "1301902",
                    "uf": "AM",
                    "publish_month": "2026-10-01"
                }
            }]
        }).encode("utf-8")

        def mock_fetcher(url: str) -> bytes:
            if url == ALLOWED_URLS["ibge_municipality"]:
                return valid_mun_bytes
            elif url == ALLOWED_URLS["ibge_state"]:
                return valid_state_bytes
            elif url == ALLOWED_URLS["deter_alerts"]:
                return valid_deter_bytes
            raise ValueError(f"Unexpected url: {url}")

        service = SourceService(cache_dir=self.test_dir, fetcher=mock_fetcher)
        result = service.get(refresh=True)

        self.assertEqual(len(result["municipality"]["features"]), 1)
        self.assertEqual(len(result["state"]["features"]), 1)
        self.assertEqual(len(result["alerts"]["features"]), 1)

        # Check sources entries
        sources_by_id = {s["id"]: s for s in result["sources"]}
        self.assertEqual(sources_by_id["ibge_municipality"]["status"], "live")
        self.assertIsNotNone(sources_by_id["ibge_municipality"]["sha256"])
        self.assertEqual(sources_by_id["deter_alerts"]["status"], "live")
        self.assertTrue(sources_by_id["deter_alerts"]["partial"])
        self.assertEqual(sources_by_id["deter_alerts"]["total_available"], 540)
        self.assertEqual(sources_by_id["deter_alerts"]["feature_count"], 1)

        # Verify disk cache files exist
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "ibge_municipality.json")))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "ibge_state.json")))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "deter_alerts.json")))

    def test_refresh_failure_with_existing_cache_preserves_stale_data_never_live(self):
        """When network/fetch fails but prior cache exists, status must be 'stale' and old data preserved."""
        import hashlib
        from integrations import SourceService

        valid_mun_fc = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-58.5, -3.1], [-58.4, -3.1], [-58.4, -3.2], [-58.5, -3.1]]]}, "properties": {"codarea": "1301902"}}]
        }
        raw_text = json.dumps(valid_mun_fc)

        # Pre-seed cache
        prior_envelope = {
            "id": "ibge_municipality",
            "name": "IBGE Malha Municipal - Itacoatiara (1301902)",
            "url": "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/1301902?formato=application/vnd.geo+json&qualidade=minima",
            "fetched_at": "2026-11-01T12:00:00Z",
            "status": "cached",
            "sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            "feature_count": 1,
            "partial": False,
            "total_available": 1,
            "raw_text": raw_text,
            "raw": valid_mun_fc,
        }
        with open(os.path.join(self.test_dir, "ibge_municipality.json"), "w", encoding="utf-8") as f:
            json.dump(prior_envelope, f)

        def failing_fetcher(url: str) -> bytes:
            raise ConnectionError("Network down: connection timed out")

        service = SourceService(cache_dir=self.test_dir, fetcher=failing_fetcher)
        result = service.get(refresh=True)

        sources_by_id = {s["id"]: s for s in result["sources"]}
        mun_source = sources_by_id["ibge_municipality"]
        self.assertEqual(mun_source["status"], "stale")
        self.assertIn("error", mun_source)
        self.assertIn("connection timed out", mun_source["error"])
        # Never live!
        self.assertNotEqual(mun_source["status"], "live")
        # Retains prior cached data
        self.assertEqual(len(result["municipality"]["features"]), 1)
        self.assertEqual(mun_source["sha256"], prior_envelope["sha256"])
        self.assertEqual(mun_source["fetched_at"], "2026-11-01T12:00:00Z")
        self.assertIsNotNone(mun_source.get("last_attempt_at"))

    def test_refresh_failure_persists_stale_to_subsequent_get_false(self):
        """Failed refresh persists stale state, error, and last_attempt_at into disk cache for subsequent get(False)."""
        import hashlib
        from integrations import SourceService

        valid_mun_fc = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-58.5, -3.1], [-58.4, -3.1], [-58.4, -3.2], [-58.5, -3.1]]]}, "properties": {"codarea": "1301902"}}]
        }
        raw_text = json.dumps(valid_mun_fc)

        prior_envelope = {
            "id": "ibge_municipality",
            "name": "IBGE Malha Municipal - Itacoatiara (1301902)",
            "url": "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/1301902?formato=application/vnd.geo+json&qualidade=minima",
            "fetched_at": "2026-11-01T12:00:00Z",
            "status": "cached",
            "sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            "feature_count": 1,
            "partial": False,
            "total_available": 1,
            "raw_text": raw_text,
            "raw": valid_mun_fc,
        }
        with open(os.path.join(self.test_dir, "ibge_municipality.json"), "w", encoding="utf-8") as f:
            json.dump(prior_envelope, f)

        def failing_fetcher(url: str) -> bytes:
            raise ConnectionError("Server unavailable 503")

        service1 = SourceService(cache_dir=self.test_dir, fetcher=failing_fetcher)
        service1.get(refresh=True)

        # Now test subsequent offline get(refresh=False)
        service2 = SourceService(cache_dir=self.test_dir)
        offline_result = service2.get(refresh=False)
        mun_source = next(s for s in offline_result["sources"] if s["id"] == "ibge_municipality")

        self.assertEqual(mun_source["status"], "stale")
        self.assertEqual(mun_source["fetched_at"], "2026-11-01T12:00:00Z")
        self.assertIn("503", mun_source.get("error", ""))
        self.assertIsNotNone(mun_source.get("last_attempt_at"))
        self.assertEqual(len(offline_result["municipality"]["features"]), 1)

    def test_keyboard_interrupt_not_caught(self):
        """KeyboardInterrupt must not be swallowed by get()."""
        from integrations import SourceService

        def interrupt_fetcher(url: str) -> bytes:
            raise KeyboardInterrupt("Simulated Ctrl+C")

        service = SourceService(cache_dir=self.test_dir, fetcher=interrupt_fetcher)
        with self.assertRaises(KeyboardInterrupt):
            service.get(refresh=True)

    def test_gzip_stream_decompression_protects_against_bomb(self):
        """Gzip decompression must enforce MAX_PAYLOAD_BYTES limit without expanding unbounded in memory."""
        import gzip
        from integrations import SourceService, MAX_PAYLOAD_BYTES

        service = SourceService(cache_dir=self.test_dir)
        # Create a compressed bomb: 9 MB of zeros compresses to ~9 KB
        huge_data = b"0" * (MAX_PAYLOAD_BYTES + 512)
        compressed_bomb = gzip.compress(huge_data)

        # Decompressing through safe decompressor must raise ValueError
        with self.assertRaises(ValueError):
            service.safe_decompress_gzip(compressed_bomb)

    def test_refresh_failure_without_cache_returns_unavailable_with_error(self):
        """When refresh fails and no cache exists, status must be 'unavailable' and error recorded."""
        from integrations import SourceService

        def failing_fetcher(url: str) -> bytes:
            raise RuntimeError("HTTP 500 Internal Server Error")

        service = SourceService(cache_dir=self.test_dir, fetcher=failing_fetcher)
        result = service.get(refresh=True)

        for s in result["sources"]:
            self.assertEqual(s["status"], "unavailable")
            self.assertIn("error", s)
            self.assertIn("HTTP 500", s["error"])
            self.assertEqual(s["feature_count"], 0)
        self.assertEqual(result["municipality"]["features"], [])

class TestIntegrationsSpatialContext(unittest.TestCase):
    def test_spatial_context_disjoint(self):
        """Polygon far away from alert geometries has 0 intersections."""
        from integrations import spatial_context
        origin = {
            "type": "Polygon",
            "coordinates": [[[-58.5, -3.1], [-58.4, -3.1], [-58.4, -3.2], [-58.5, -3.2], [-58.5, -3.1]]]
        }
        alerts_fc = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"gid": "alert_far", "classname": "DESMATAMENTO_CR"},
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [[[[-57.0, -2.0], [-56.9, -2.0], [-56.9, -2.1], [-57.0, -2.1], [-57.0, -2.0]]]]
                }
            }]
        }
        res = spatial_context(origin, alerts_fc)
        self.assertEqual(res["count"], 0)
        self.assertEqual(res["intersections"], [])
        self.assertIn("Origin polygon demonstrativo", res["notice"])

    def test_spatial_context_intersect(self):
        """Polygon overlapping alert geometry detects intersection ID."""
        from integrations import spatial_context
        origin = {
            "type": "Polygon",
            "coordinates": [[[-58.5, -3.1], [-58.4, -3.1], [-58.4, -3.2], [-58.5, -3.2], [-58.5, -3.1]]]
        }
        alerts_fc = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"gid": "alert_hit_1", "classname": "CICATRIZ_DE_QUEIMADA"},
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [[[[-58.45, -3.15], [-58.35, -3.15], [-58.35, -3.25], [-58.45, -3.25], [-58.45, -3.15]]]]
                }
            }]
        }
        res = spatial_context(origin, alerts_fc)
        self.assertEqual(res["count"], 1)
        self.assertIn("alert_hit_1", res["intersections"])

    def test_spatial_context_hole_exclusion(self):
        """Polygon placed strictly inside the hole of a donut alert must NOT intersect."""
        from integrations import spatial_context
        # Donut alert: outer square [0, 10] x [0, 10], hole [2, 8] x [2, 8]
        donut_alert = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"gid": "donut_alert"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        # Exterior ring
                        [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]],
                        # Interior hole
                        [[2.0, 2.0], [8.0, 2.0], [8.0, 8.0], [2.0, 8.0], [2.0, 2.0]]
                    ]
                }
            }]
        }
        # Origin inside the hole [3, 7] x [3, 7]
        origin_inside_hole = {
            "type": "Polygon",
            "coordinates": [[[3.0, 3.0], [7.0, 3.0], [7.0, 7.0], [3.0, 7.0], [3.0, 3.0]]]
        }
        res = spatial_context(origin_inside_hole, donut_alert)
        self.assertEqual(res["count"], 0)
        self.assertEqual(res["intersections"], [])

    def test_spatial_context_bbox_false_positive(self):
        """Overlapping bounding boxes with disjoint geometries must NOT report intersection."""
        from integrations import spatial_context
        # Triangle 1 in [0, 2] x [0, 2] below x + y = 2
        poly_a = {
            "type": "Polygon",
            "coordinates": [[[0.0, 0.0], [2.0, 0.0], [0.0, 2.0], [0.0, 0.0]]]
        }
        # Triangle 2 in [1, 2] x [1, 2] above x + y = 3
        poly_b_fc = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"gid": "diag_alert"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[2.0, 2.0], [2.0, 1.2], [1.2, 2.0], [2.0, 2.0]]]
                }
            }]
        }
        res = spatial_context(poly_a, poly_b_fc)
        self.assertEqual(res["count"], 0)
        self.assertEqual(res["intersections"], [])

    def test_spatial_context_hole_in_origin_alert_inside_origin_hole(self):
        """When the origin polygon has a hole and an alert is placed entirely inside that hole, no intersection must be reported."""
        from integrations import spatial_context
        # Origin polygon with hole: exterior 0..20, hole 5..15
        origin_with_hole = {
            "type": "Polygon",
            "coordinates": [
                [[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 20.0], [0.0, 0.0]],
                [[5.0, 5.0], [15.0, 5.0], [15.0, 15.0], [5.0, 15.0], [5.0, 5.0]],
            ]
        }
        # Alert strictly inside the hole [7..12]
        alert_in_hole = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"gid": "alert_inside_origin_hole"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[7.0, 7.0], [12.0, 7.0], [12.0, 12.0], [7.0, 12.0], [7.0, 7.0]]]
                }
            }]
        }
        res = spatial_context(origin_with_hole, alert_in_hole)
        self.assertEqual(res["count"], 0)
        self.assertEqual(res["intersections"], [])

    def test_spatial_context_multipolygon_origin_and_alert(self):
        """Spatial context correctly checks MultiPolygon origin against MultiPolygon alerts."""
        from integrations import spatial_context
        origin_multipoly = {
            "type": "MultiPolygon",
            "coordinates": [
                # Island 1
                [[[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0], [0.0, 0.0]]],
                # Island 2
                [[[10.0, 10.0], [12.0, 10.0], [12.0, 12.0], [10.0, 12.0], [10.0, 10.0]]],
            ]
        }
        alert_multipoly = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"gid": "multi_alert_1"},
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [
                        # Overlaps Island 2
                        [[[11.0, 11.0], [13.0, 11.0], [13.0, 13.0], [11.0, 13.0], [11.0, 11.0]]]
                    ]
                }
            }]
        }
        res = spatial_context(origin_multipoly, alert_multipoly)
        self.assertEqual(res["count"], 1)
        self.assertIn("multi_alert_1", res["intersections"])

    def test_spatial_context_method_declares_planar_approximation(self):
        """Method and notice must declare local planar approximation without claiming exact legal geodetic precision."""
        from integrations import spatial_context
        origin = {
            "type": "Polygon",
            "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]]
        }
        res = spatial_context(origin, {"type": "FeatureCollection", "features": []})
        self.assertIn("planar_approximation", res["method"])
        self.assertIn("plano local", res["notice"].lower())
        self.assertNotIn("precisão geodésica exata", res["notice"].lower())

class TestIntegrationsRealSnapshots(unittest.TestCase):
    def test_real_snapshots_offline_integrity_and_provenance(self):
        """Real downloaded snapshots in data/sources must load offline, have valid sha256, UTC timestamps, and pass schema checks."""
        from integrations import SourceService, spatial_context
        sources_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sources")
        if not os.path.exists(sources_dir):
            self.skipTest("data/sources directory does not exist")

        service = SourceService(cache_dir=sources_dir)
        result = service.get(refresh=False)

        # Check sources
        sources_map = {s["id"]: s for s in result["sources"]}
        self.assertIn("ibge_municipality", sources_map)
        self.assertIn("ibge_state", sources_map)
        self.assertIn("deter_alerts", sources_map)

        for sid in ["ibge_municipality", "ibge_state", "deter_alerts"]:
            info = sources_map[sid]
            self.assertEqual(info["status"], "cached")
            self.assertIsNotNone(info["sha256"])
            self.assertEqual(len(info["sha256"]), 64)  # Valid SHA-256 hex string
            self.assertTrue(info["fetched_at"].endswith("Z"))
            self.assertGreater(info["feature_count"], 0)

        # Municipality specifics
        self.assertEqual(len(result["municipality"]["features"]), 1)
        mun_feat = result["municipality"]["features"][0]
        self.assertEqual(mun_feat["properties"]["codarea"], "1301902")

        # State specifics
        self.assertEqual(len(result["state"]["features"]), 1)
        state_feat = result["state"]["features"][0]
        self.assertEqual(state_feat["properties"]["codarea"], "13")

        # DETER specifics
        deter_info = sources_map["deter_alerts"]
        self.assertEqual(deter_info["feature_count"], 200)
        self.assertTrue(deter_info["partial"])
        self.assertGreater(deter_info["total_available"], 200)
        self.assertEqual(len(result["alerts"]["features"]), 200)

        # Validate that all 200 DETER alerts belong to AM / 1301902
        for alert in result["alerts"]["features"]:
            self.assertEqual(alert["properties"]["uf"], "AM")
            self.assertEqual(alert["properties"]["mun_geocod"], "1301902")

        # Validate spatial context on real alert geometry
        sample_alert = result["alerts"]["features"][0]
        hit_res = spatial_context(sample_alert["geometry"], result["alerts"])
        self.assertGreaterEqual(hit_res["count"], 1)
        self.assertIn(str(sample_alert["properties"]["gid"]), hit_res["intersections"])

        # Validate spatial context with disjoint geometry
        disjoint_geom = {
            "type": "Polygon",
            "coordinates": [[[-43.2, -22.9], [-43.1, -22.9], [-43.1, -23.0], [-43.2, -22.9]]]
        }
        disjoint_res = spatial_context(disjoint_geom, result["alerts"])
        self.assertEqual(disjoint_res["count"], 0)
        self.assertEqual(disjoint_res["intersections"], [])

if __name__ == "__main__":
    unittest.main()





