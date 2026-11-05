"""integrations.py - Geographic data sources integration and spatial context analysis.

Python standard library only.
Provides:
  - SourceService for fetching, validating, and caching IBGE and DETER data.
  - spatial_context for polygon-level intersection analysis.
"""

import os
import io
import json
import gzip
import uuid
import hashlib
import math
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Callable, Optional, Dict, Any, List



MAX_PAYLOAD_BYTES = 8 * 1024 * 1024  # 8 MB
REQUEST_TIMEOUT_SECONDS = 12

ALLOWED_URLS = {
    "ibge_municipality": "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/1301902?formato=application/vnd.geo+json&qualidade=minima",
    "ibge_state": "https://servicodados.ibge.gov.br/api/v3/malhas/estados/13?formato=application/vnd.geo+json&qualidade=minima",
    "deter_alerts": "https://terrabrasilis.dpi.inpe.br/geoserver/deter-amz/ows?service=WFS&version=2.0.0&request=GetFeature&typeNames=deter-amz:deter_amz&outputFormat=application%2Fjson&count=200&sortBy=view_date%20D&CQL_FILTER=mun_geocod%3D%271301902%27&srsName=EPSG:4326",
}

SOURCE_METADATA = {
    "ibge_municipality": {
        "name": "IBGE Malha Municipal - Itacoatiara (1301902)",
        "url": ALLOWED_URLS["ibge_municipality"],
    },
    "ibge_state": {
        "name": "IBGE Malha Estadual - Amazonas (13)",
        "url": ALLOWED_URLS["ibge_state"],
    },
    "deter_alerts": {
        "name": "INPE DETER Amazônia - Alertas Itacoatiara (1301902)",
        "url": ALLOWED_URLS["deter_alerts"],
    },
}

EMPTY_FEATURE_COLLECTION = {"type": "FeatureCollection", "features": []}

GLOBAL_NOTICE = (
    "Origin polygon demonstrativo não é imóvel real autorizado; nenhuma sobreposição prova crime. "
    "DETER são alertas preliminares de satélite para fiscalização, não constituem laudo pericial "
    "nem atestam infração definitiva; sua ausência também não comprova regularidade fundiária/ambiental. "
    "Métodos aproximam projeção em plano local sem presunção de medição geodésica oficial pericial."
)

def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON constant not allowed: {value}")


def _strict_json(text: str) -> Any:
    try:
        return json.loads(text, parse_constant=_reject_constant)
    except (json.JSONDecodeError, RecursionError) as e:
        raise ValueError(f"Failed to parse JSON: {e}") from e


def _is_utc_timestamp(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0


class _AllowlistRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse redirects so the fixed allowlist cannot be bypassed upstream."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(newurl, code, "Redirecionamento recusado (fora da allowlist)", headers, fp)


class SourceService:
    def __init__(self, cache_dir: str = "data/sources", fetcher: Optional[Callable[[str], bytes]] = None):
        self.cache_dir = cache_dir
        self.fetcher = fetcher

    def validate_url(self, url: str) -> str:
        for source_id, allowed_url in ALLOWED_URLS.items():
            if url == allowed_url:
                return source_id
        raise ValueError(f"URL not allowed in fixed allowlist: {url}")

    def check_payload_size(self, data: bytes) -> None:
        if len(data) > MAX_PAYLOAD_BYTES:
            raise ValueError(f"Payload size {len(data)} bytes exceeds limit of {MAX_PAYLOAD_BYTES} bytes (8MB)")

    def _validate_position(self, pos: Any) -> None:
        if not isinstance(pos, (list, tuple)):
            raise ValueError(f"Position must be list or tuple, got {type(pos).__name__}")
        if len(pos) != 2:
            raise ValueError(f"Position must contain exactly 2 numbers [lon, lat], got length {len(pos)}")
        x, y = pos[0], pos[1]
        if isinstance(x, bool) or isinstance(y, bool):
            raise ValueError("Coordinate values must not be boolean")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise ValueError(f"Coordinate values must be numeric: ({x}, {y})")
        if not (math.isfinite(x) and math.isfinite(y)):
            raise ValueError(f"Coordinate values must be finite numbers: ({x}, {y})")
        if not (-180.0 <= x <= 180.0 and -90.0 <= y <= 90.0):
            raise ValueError(f"Coordinates out of bounds [-180, 180], [-90, 90]: ({x}, {y})")

    def _validate_ring(self, ring: Any) -> None:
        if not isinstance(ring, (list, tuple)):
            raise ValueError(f"Linear ring must be a list or tuple, got {type(ring).__name__}")
        if len(ring) < 4:
            raise ValueError(f"Linear ring must contain at least 4 positions, got {len(ring)}")
        for pos in ring:
            self._validate_position(pos)
        first, last = ring[0], ring[-1]
        if not (math.isclose(first[0], last[0], abs_tol=1e-7) and math.isclose(first[1], last[1], abs_tol=1e-7)):
            raise ValueError(f"Linear ring must be closed (first and last positions must match): {first} != {last}")

    def _validate_polygon_coords(self, coords: Any) -> None:
        if not isinstance(coords, (list, tuple)) or len(coords) == 0:
            raise ValueError("Polygon coordinates must be a non-empty list of rings")
        for ring in coords:
            self._validate_ring(ring)

    def _validate_multipolygon_coords(self, coords: Any) -> None:
        if not isinstance(coords, (list, tuple)) or len(coords) == 0:
            raise ValueError("MultiPolygon coordinates must be a non-empty list of polygons")
        for poly_coords in coords:
            self._validate_polygon_coords(poly_coords)

    def _validate_points(self, coords: Any) -> None:
        """Legacy helper for backwards compatibility - validates position or nested coordinates."""
        if isinstance(coords, (list, tuple)):
            if len(coords) == 2 and isinstance(coords[0], (int, float)) and isinstance(coords[1], (int, float)) and not isinstance(coords[0], bool) and not isinstance(coords[1], bool):
                self._validate_position(coords)
            else:
                for sub in coords:
                    self._validate_points(sub)
        else:
            raise ValueError(f"Invalid coordinate format: {coords}")

    def validate_fc_structure(self, data: Dict[str, Any], source_id: str) -> None:
        if not isinstance(data, dict):
            raise ValueError("GeoJSON payload must be a JSON object")
        if data.get("type") != "FeatureCollection":
            raise ValueError(f"Expected FeatureCollection, got {data.get('type')}")
        features = data.get("features")
        if not isinstance(features, list):
            raise ValueError("FeatureCollection 'features' must be a list")

        for idx, feat in enumerate(features):
            if not isinstance(feat, dict) or feat.get("type") != "Feature":
                raise ValueError(f"Feature at index {idx} is not a valid Feature object")
            geom = feat.get("geometry")
            if not isinstance(geom, dict):
                raise ValueError(f"Feature at index {idx} missing valid geometry object")
            geom_type = geom.get("type")
            if geom_type not in ("Polygon", "MultiPolygon"):
                raise ValueError(f"Feature at index {idx} has unsupported geometry type: {geom_type}")
            coords = geom.get("coordinates")
            if not isinstance(coords, list) or len(coords) == 0:
                raise ValueError(f"Feature at index {idx} has empty or invalid coordinates")

            if geom_type == "Polygon":
                self._validate_polygon_coords(coords)
            elif geom_type == "MultiPolygon":
                self._validate_multipolygon_coords(coords)

            props = feat.get("properties")
            if not isinstance(props, dict):
                raise ValueError(f"Feature at index {idx} properties must be a dictionary")

            if source_id == "ibge_municipality":
                if "codarea" not in props:
                    raise ValueError("IBGE municipality feature must contain 'codarea' in properties")
                codarea = str(props.get("codarea", "")).strip()
                if codarea != "1301902":
                    raise ValueError(f"IBGE municipality feature codarea '{codarea}' does not match expected 1301902")
            elif source_id == "ibge_state":
                if "codarea" not in props:
                    raise ValueError("IBGE state feature must contain 'codarea' in properties")
                codarea = str(props.get("codarea", "")).strip()
                if codarea != "13":
                    raise ValueError(f"IBGE state feature codarea '{codarea}' does not match expected 13")
            elif source_id == "deter_alerts":
                if "uf" not in props:
                    raise ValueError(f"DETER alert {props.get('gid', idx)} missing required 'uf' in properties")
                uf = props.get("uf")
                if uf != "AM":
                    raise ValueError(f"DETER alert {props.get('gid', idx)} has unexpected UF '{uf}'; expected 'AM'")
                if "mun_geocod" not in props:
                    raise ValueError(f"DETER alert {props.get('gid', idx)} missing required 'mun_geocod' in properties")
                mun_geocod = str(props.get("mun_geocod", "")).strip()
                if mun_geocod != "1301902":
                    raise ValueError(f"DETER alert {props.get('gid', idx)} has unexpected mun_geocod '{mun_geocod}'; expected '1301902'")
                if "view_date" not in props or not props.get("view_date"):
                    raise ValueError(f"DETER alert {props.get('gid', idx)} missing required 'view_date' in properties")
                gid = props.get("gid") or feat.get("id")
                if not gid:
                    raise ValueError(f"DETER alert at index {idx} missing required identifier ('gid' or 'id')")

    def parse_and_validate(self, raw_bytes: bytes, source_id: str) -> Dict[str, Any]:
        self.check_payload_size(raw_bytes)
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(f"Failed to decode response as UTF-8: {e}") from e
        data = _strict_json(text)
        self.validate_fc_structure(data, source_id)
        if source_id == "deter_alerts":
            total = data.get("totalFeatures", len(data.get("features", [])))
            if isinstance(total, bool) or not isinstance(total, int) or total < 0:
                raise ValueError("totalFeatures must be a non-negative integer")
        return data


    def safe_decompress_gzip(self, data: bytes) -> bytes:
        """Decompress gzip data with strict chunked limit checking to protect against decompression bombs."""
        bio = io.BytesIO(data)
        with gzip.GzipFile(fileobj=bio, mode="rb") as gz:
            chunks = []
            total_read = 0
            while True:
                chunk = gz.read(65536)
                if not chunk:
                    break
                total_read += len(chunk)
                if total_read > MAX_PAYLOAD_BYTES:
                    raise ValueError(f"Decompressed payload exceeded maximum allowed size of {MAX_PAYLOAD_BYTES} bytes")
                chunks.append(chunk)
            return b"".join(chunks)

    def _cache_path(self, source_id: str) -> str:
        return os.path.join(self.cache_dir, f"{source_id}.json")

    def _load_cache(self, source_id: str) -> Optional[Dict[str, Any]]:
        path = self._cache_path(source_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                envelope = json.load(f)
        except Exception:
            return None

        if not isinstance(envelope, dict):
            return None

        # Validate URL against allowlist
        allowed_url = ALLOWED_URLS.get(source_id)
        if envelope.get("url") != allowed_url:
            return None

        # Validate raw_text and sha256 hash match
        raw_text = envelope.get("raw_text")
        expected_sha256 = envelope.get("sha256")
        if not isinstance(raw_text, str) or not isinstance(expected_sha256, str):
            return None

        actual_sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        if actual_sha256 != expected_sha256:
            return None

        # Only raw_text is covered by the hash: rebuild every derived field from it.
        try:
            raw_fc = self.parse_and_validate(raw_text.encode("utf-8"), source_id)
        except Exception:
            return None
        count = len(raw_fc.get("features", []))
        total = raw_fc.get("totalFeatures", count) if source_id == "deter_alerts" else count
        fetched_at = envelope.get("fetched_at")
        if not isinstance(fetched_at, str) or not _is_utc_timestamp(fetched_at):
            fetched_at = None
        trusted = {
            "raw": raw_fc,
            "raw_text": raw_text,
            "sha256": actual_sha256,
            "url": allowed_url,
            "name": SOURCE_METADATA[source_id]["name"],
            "fetched_at": fetched_at,
            "feature_count": count,
            "total_available": total,
            "partial": total > count,
            "status": "stale" if envelope.get("status") == "stale" else "cached",
        }
        if isinstance(envelope.get("error"), str):
            trusted["error"] = envelope["error"][:300]
        last_attempt = envelope.get("last_attempt_at")
        if isinstance(last_attempt, str) and _is_utc_timestamp(last_attempt):
            trusted["last_attempt_at"] = last_attempt
        return trusted

    def _atomic_save_cache(self, source_id: str, envelope: Dict[str, Any]) -> None:
        os.makedirs(self.cache_dir, exist_ok=True)
        target_path = self._cache_path(source_id)
        unique_suffix = f"{os.getpid()}_{uuid.uuid4().hex}"
        tmp_path = os.path.join(self.cache_dir, f".{source_id}_{unique_suffix}.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(envelope, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, target_path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _default_fetch(self, url: str) -> bytes:
        self.validate_url(url)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "RaizTrace/1.0 (Amazonas Forest Traceability)",
                "Accept-Encoding": "gzip",
            },
        )
        opener = urllib.request.build_opener(_AllowlistRedirectHandler)
        with opener.open(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            chunks = []
            total_read = 0
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                total_read += len(chunk)
                if total_read > MAX_PAYLOAD_BYTES:
                    raise ValueError(f"Payload exceeded maximum allowed size of {MAX_PAYLOAD_BYTES} bytes")
                chunks.append(chunk)
            raw = b"".join(chunks)

        if raw[:2] == b"\x1f\x8b":
            raw = self.safe_decompress_gzip(raw)
        return raw

    def get(self, refresh: bool = False) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "municipality": dict(EMPTY_FEATURE_COLLECTION),
            "state": dict(EMPTY_FEATURE_COLLECTION),
            "alerts": dict(EMPTY_FEATURE_COLLECTION),
            "sources": [],
            "notice": GLOBAL_NOTICE,
        }

        key_mapping = {
            "ibge_municipality": "municipality",
            "ibge_state": "state",
            "deter_alerts": "alerts",
        }

        for source_id, meta in SOURCE_METADATA.items():
            target_key = key_mapping[source_id]
            cached_envelope = self._load_cache(source_id)

            if not refresh:
                if cached_envelope is not None and "raw" in cached_envelope:
                    raw_fc = cached_envelope.get("raw", dict(EMPTY_FEATURE_COLLECTION))
                    result[target_key] = raw_fc
                    cached_status = cached_envelope.get("status", "cached")
                    status_to_report = "stale" if cached_status == "stale" else "cached"
                    source_entry: Dict[str, Any] = {
                        "id": source_id,
                        "name": cached_envelope.get("name", meta["name"]),
                        "url": cached_envelope.get("url", meta["url"]),
                        "fetched_at": cached_envelope.get("fetched_at"),
                        "status": status_to_report,
                        "sha256": cached_envelope.get("sha256"),
                        "feature_count": cached_envelope.get("feature_count", len(raw_fc.get("features", []))),
                        "partial": cached_envelope.get("partial", False),
                        "total_available": cached_envelope.get("total_available", len(raw_fc.get("features", []))),
                    }
                    if "error" in cached_envelope:
                        source_entry["error"] = cached_envelope["error"]
                    if "last_attempt_at" in cached_envelope:
                        source_entry["last_attempt_at"] = cached_envelope["last_attempt_at"]
                    result["sources"].append(source_entry)
                else:
                    result["sources"].append({
                        "id": source_id,
                        "name": meta["name"],
                        "url": meta["url"],
                        "fetched_at": None,
                        "status": "unavailable",
                        "sha256": None,
                        "feature_count": 0,
                        "partial": False,
                        "total_available": 0,
                    })
            else:
                # refresh=True: fetch from URL
                url = meta["url"]
                try:
                    if self.fetcher is not None:
                        raw_bytes = self.fetcher(url)
                    else:
                        raw_bytes = self._default_fetch(url)

                    # Validate and parse
                    raw_text = raw_bytes.decode("utf-8")
                    fc_data = self.parse_and_validate(raw_bytes, source_id)
                    sha256_hash = hashlib.sha256(raw_bytes).hexdigest()
                    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                    features = fc_data.get("features", [])
                    feature_count = len(features)

                    if source_id == "deter_alerts":
                        total_available = fc_data.get("totalFeatures", feature_count)
                        partial = total_available > feature_count
                    else:
                        total_available = feature_count
                        partial = False

                    envelope = {
                        "id": source_id,
                        "name": meta["name"],
                        "url": meta["url"],
                        "fetched_at": fetched_at,
                        "status": "live",
                        "sha256": sha256_hash,
                        "feature_count": feature_count,
                        "partial": partial,
                        "total_available": total_available,
                        "raw_text": raw_text,
                        "raw": fc_data,
                    }

                    self._atomic_save_cache(source_id, envelope)
                    result[target_key] = fc_data
                    result["sources"].append({
                        "id": source_id,
                        "name": meta["name"],
                        "url": meta["url"],
                        "fetched_at": fetched_at,
                        "status": "live",
                        "sha256": sha256_hash,
                        "feature_count": feature_count,
                        "partial": partial,
                        "total_available": total_available,
                    })

                except KeyboardInterrupt:
                    raise
                except Exception as exc:
                    # Failed fetch: never live on failure!
                    attempt_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    if cached_envelope is not None and "raw" in cached_envelope:
                        raw_fc = cached_envelope.get("raw", dict(EMPTY_FEATURE_COLLECTION))
                        # Persist stale state and error on disk without overwriting original fetched_at
                        stale_envelope = dict(cached_envelope)
                        stale_envelope["status"] = "stale"
                        stale_envelope["error"] = str(exc)
                        stale_envelope["last_attempt_at"] = attempt_time
                        self._atomic_save_cache(source_id, stale_envelope)

                        result[target_key] = raw_fc
                        result["sources"].append({
                            "id": source_id,
                            "name": cached_envelope.get("name", meta["name"]),
                            "url": cached_envelope.get("url", meta["url"]),
                            "fetched_at": cached_envelope.get("fetched_at"),
                            "status": "stale",
                            "sha256": cached_envelope.get("sha256"),
                            "error": str(exc),
                            "last_attempt_at": attempt_time,
                            "feature_count": cached_envelope.get("feature_count", len(raw_fc.get("features", []))),
                            "partial": cached_envelope.get("partial", False),
                            "total_available": cached_envelope.get("total_available", len(raw_fc.get("features", []))),
                        })
                    else:
                        result[target_key] = dict(EMPTY_FEATURE_COLLECTION)
                        result["sources"].append({
                            "id": source_id,
                            "name": meta["name"],
                            "url": meta["url"],
                            "fetched_at": None,
                            "status": "unavailable",
                            "sha256": None,
                            "error": str(exc),
                            "last_attempt_at": attempt_time,
                            "feature_count": 0,
                            "partial": False,
                            "total_available": 0,
                        })

        return result

        return result


# ---------------------------------------------------------------------------
# Computational Geometry & Spatial Context Analysis (Pure Python Standard Library)
# ---------------------------------------------------------------------------

Point2D = tuple[float, float]
Ring2D = list[Point2D]
Polygon2D = list[Ring2D]  # [exterior_ring, hole_1, hole_2, ...]

def _extract_polygons(geo: Any) -> list[Polygon2D]:
    """Extract list of polygons (each with exterior ring and optional hole rings) from GeoJSON."""
    if not isinstance(geo, dict):
        return []
    if geo.get("type") == "Feature":
        geo = geo.get("geometry", {})
    elif geo.get("type") == "FeatureCollection":
        polys: list[Polygon2D] = []
        for feat in geo.get("features", []):
            polys.extend(_extract_polygons(feat))
        return polys

    geom_type = geo.get("type")
    coords = geo.get("coordinates", [])

    if geom_type == "Polygon":
        poly: Polygon2D = []
        for ring in coords:
            poly.append([(float(pt[0]), float(pt[1])) for pt in ring])
        return [poly] if poly else []
    elif geom_type == "MultiPolygon":
        result_polys: list[Polygon2D] = []
        for poly_coords in coords:
            poly = []
            for ring in poly_coords:
                poly.append([(float(pt[0]), float(pt[1])) for pt in ring])
            if poly:
                result_polys.append(poly)
        return result_polys
    return []

def _polygon_bbox(poly: Polygon2D) -> tuple[float, float, float, float]:
    ext = poly[0]
    xs = [pt[0] for pt in ext]
    ys = [pt[1] for pt in ext]
    return (min(xs), min(ys), max(xs), max(ys))

def _bboxes_overlap(b1: tuple[float, float, float, float], b2: tuple[float, float, float, float], eps: float = 1e-9) -> bool:
    if (b1[2] < b2[0] - eps or b1[0] > b2[2] + eps or
        b1[3] < b2[1] - eps or b1[1] > b2[3] + eps):
        return False
    return True

def _ccw(A: Point2D, B: Point2D, C: Point2D) -> float:
    return (B[0] - A[0]) * (C[1] - A[1]) - (B[1] - A[1]) * (C[0] - A[0])

def _is_point_on_segment(pt: Point2D, p1: Point2D, p2: Point2D, eps: float = 1e-9) -> bool:
    px, py = pt
    x1, y1 = p1
    x2, y2 = p2
    if min(x1, x2) - eps <= px <= max(x1, x2) + eps and min(y1, y2) - eps <= py <= max(y1, y2) + eps:
        cross = (px - x1) * (y2 - y1) - (py - y1) * (x2 - x1)
        if abs(cross) <= eps:
            return True
    return False

def _point_in_ring(pt: Point2D, ring: Ring2D) -> int:
    """Returns 1 if strictly inside, 0 if on boundary, -1 if outside."""
    px, py = pt
    n = len(ring)
    for i in range(n):
        p1 = ring[i]
        p2 = ring[(i + 1) % n]
        if _is_point_on_segment(pt, p1, p2):
            return 0

    inside = False
    for i in range(n):
        p1 = ring[i]
        p2 = ring[(i + 1) % n]
        if (p1[1] > py) != (p2[1] > py):
            x_cross = p1[0] + (py - p1[1]) * (p2[0] - p1[0]) / (p2[1] - p1[1])
            if px < x_cross:
                inside = not inside
    return 1 if inside else -1

def _point_in_polygon(pt: Point2D, poly: Polygon2D) -> bool:
    """Returns True if point is inside solid polygon (exterior minus holes) or on its boundary."""
    ext_status = _point_in_ring(pt, poly[0])
    if ext_status == -1:
        return False

    for hole in poly[1:]:
        hole_status = _point_in_ring(pt, hole)
        if hole_status == 1:
            return False

    return True

def _segments_intersect_and_get_point(A: Point2D, B: Point2D, C: Point2D, D: Point2D) -> tuple[bool, list[Point2D]]:
    eps = 1e-9
    if (max(A[0], B[0]) < min(C[0], D[0]) - eps or
        min(A[0], B[0]) > max(C[0], D[0]) + eps or
        max(A[1], B[1]) < min(C[1], D[1]) - eps or
        min(A[1], B[1]) > max(C[1], D[1]) + eps):
        return False, []

    d1 = _ccw(C, D, A)
    d2 = _ccw(C, D, B)
    d3 = _ccw(A, B, C)
    d4 = _ccw(A, B, D)

    if (((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and
        ((d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps))):
        denom = (A[0] - B[0]) * (C[1] - D[1]) - (A[1] - B[1]) * (C[0] - D[0])
        if abs(denom) > 1e-12:
            t = ((A[0] - C[0]) * (C[1] - D[1]) - (A[1] - C[1]) * (C[0] - D[0])) / denom
            ix = A[0] + t * (B[0] - A[0])
            iy = A[1] + t * (B[1] - A[1])
            return True, [(ix, iy)]

    pts: list[Point2D] = []
    for pt, s1, s2 in [(A, C, D), (B, C, D), (C, A, B), (D, A, B)]:
        if _is_point_on_segment(pt, s1, s2):
            pts.append(pt)
    if pts:
        return True, pts

    return False, []

def _polygons_intersect(p1: Polygon2D, p2: Polygon2D) -> bool:
    b1 = _polygon_bbox(p1)
    b2 = _polygon_bbox(p2)
    if not _bboxes_overlap(b1, b2):
        return False

    # 1. Check if any vertex of p1 is inside solid p2
    for ring in p1:
        for v in ring:
            if _point_in_polygon(v, p2):
                return True

    # 2. Check if any vertex of p2 is inside solid p1
    for ring in p2:
        for v in ring:
            if _point_in_polygon(v, p1):
                return True

    # 3. Check segment intersections across all rings
    for ring1 in p1:
        n1 = len(ring1)
        for i in range(n1):
            a1 = ring1[i]
            a2 = ring1[(i + 1) % n1]
            for ring2 in p2:
                n2 = len(ring2)
                for j in range(n2):
                    b1_pt = ring2[j]
                    b2_pt = ring2[(j + 1) % n2]
                    intersects, pts = _segments_intersect_and_get_point(a1, a2, b1_pt, b2_pt)
                    if intersects:
                        for pt in pts:
                            if _point_in_polygon(pt, p1) and _point_in_polygon(pt, p2):
                                return True
    return False

def spatial_context(polygon_geojson: Any, alerts_fc: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate geometric intersection between origin polygon and DETER alerts FeatureCollection.

    Respects holes, segment intersections, and containment.
    Returns:
      {
        "method": "exact_ray_casting_segment_intersection",
        "intersections": [alert_ids],
        "count": int,
        "notice": str
      }
    """
    origin_polys = _extract_polygons(polygon_geojson)
    intersecting_ids: list[str] = []

    features = alerts_fc.get("features", []) if isinstance(alerts_fc, dict) else []

    for idx, alert_feat in enumerate(features):
        if not isinstance(alert_feat, dict):
            continue
        alert_polys = _extract_polygons(alert_feat)
        hit = False
        for op in origin_polys:
            for ap in alert_polys:
                if _polygons_intersect(op, ap):
                    hit = True
                    break
            if hit:
                break

        if hit:
            props = alert_feat.get("properties") or {}
            gid = props.get("gid") or alert_feat.get("id") or str(idx)
            intersecting_ids.append(str(gid))

    return {
        "method": "local_planar_approximation_ray_casting",
        "intersections": intersecting_ids,
        "count": len(intersecting_ids),
        "notice": GLOBAL_NOTICE,
    }


PROXIMITY_NOTICE = (
    "Distâncias para triagem: aproximação plana local em km a partir das bordas dos polígonos. "
    "Proximidade a alerta não indica autoria, origem da madeira nem infração; serve para priorizar "
    "conferência documental e vistoria. Cobertura limitada ao recorte de alertas carregado."
)


def _segment_distance(p: Point2D, a: Point2D, b: Point2D) -> float:
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    t = 0.0 if length == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _polygon_distance(p1: Polygon2D, p2: Polygon2D) -> float:
    if _polygons_intersect(p1, p2):
        return 0.0
    best = math.inf
    for ra in p1:
        for rb in p2:
            for pt in ra:
                for i in range(len(rb) - 1):
                    best = min(best, _segment_distance(pt, rb[i], rb[i + 1]))
            for pt in rb:
                for i in range(len(ra) - 1):
                    best = min(best, _segment_distance(pt, ra[i], ra[i + 1]))
    return best


def proximity_context(plot_geojson: Any, alerts_fc: Dict[str, Any], municipality_fc: Dict[str, Any],
                      radii_km: tuple = (5, 10, 20)) -> Dict[str, Any]:
    """Distance screening between a plot and alert polygons using a local equirectangular plane."""
    plot_polys = _extract_polygons(plot_geojson)
    if not plot_polys:
        raise ValueError("Polígono da área é obrigatório.")
    ref_lat = plot_polys[0][0][0][1]
    kx, ky = 111.32 * math.cos(math.radians(ref_lat)), 110.57

    def project(polys):
        return [[[(x * kx, y * ky) for x, y in ring] for ring in poly] for poly in polys]

    plot_km = project(plot_polys)
    distances = []
    features = alerts_fc.get("features", []) if isinstance(alerts_fc, dict) else []
    for idx, feat in enumerate(features):
        alert_km = project(_extract_polygons(feat))
        if not alert_km:
            continue
        d = min(_polygon_distance(a, b) for a in plot_km for b in alert_km)
        props = feat.get("properties") or {}
        distances.append({
            "gid": str(props.get("gid") or feat.get("id") or idx),
            "distance_km": round(d, 2),
            "classname": props.get("classname"),
            "view_date": props.get("view_date"),
        })
    distances.sort(key=lambda item: item["distance_km"])

    municipality_polys = _extract_polygons(municipality_fc)
    inside = None
    if municipality_polys:
        x, y = plot_polys[0][0][0]
        inside = any(_point_in_polygon((x, y), poly) for poly in municipality_polys)

    return {
        "method": "local_equirectangular_edge_distance",
        "nearest": distances[0] if distances else None,
        "closest": distances[:5],
        "within": [{"radius_km": r, "count": sum(1 for item in distances if item["distance_km"] <= r)} for r in radii_km],
        "alerts_evaluated": len(distances),
        "plot_inside_municipality": inside,
        "notice": PROXIMITY_NOTICE,
    }



