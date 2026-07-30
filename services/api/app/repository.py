from __future__ import annotations

from contextlib import contextmanager
import json
from shutil import copy2
from datetime import UTC, datetime, timedelta
import os
import secrets
import sqlite3
from pathlib import Path
from typing import Iterable

from .models import CatalogObject, ConfidenceLevel, Evidence, IncomingObservation, Location, LocationSummary, ObjectState, Prediction, QueryResult

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_ulid(now: datetime | None = None) -> str:
    """Return a lexicographically sortable 26-character ULID without an extra dependency."""
    timestamp = int((now or datetime.now(UTC)).timestamp() * 1000)
    value = (timestamp << 80) | secrets.randbits(80)
    chars: list[str] = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def normalize_name(name: str) -> str:
    return "".join(name.strip().lower().split())


class Repository:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @contextmanager
    def session(self):
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        with self.session() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS rooms (room_id TEXT PRIMARY KEY, name TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS locations (
                  location_id TEXT PRIMARY KEY, room_id TEXT NOT NULL REFERENCES rooms(room_id), name TEXT NOT NULL,
                  normalized_name TEXT NOT NULL, polygon_json TEXT NOT NULL DEFAULT '[]'
                );
                CREATE UNIQUE INDEX IF NOT EXISTS location_normalized_name_unique ON locations(room_id, normalized_name);
                CREATE TABLE IF NOT EXISTS objects (
                  object_id TEXT PRIMARY KEY, room_id TEXT NOT NULL REFERENCES rooms(room_id), name TEXT NOT NULL,
                  system_name TEXT NOT NULL, category TEXT NOT NULL, normalized_name TEXT NOT NULL,
                  source_key TEXT UNIQUE,
                  state TEXT NOT NULL, current_location_id TEXT REFERENCES locations(location_id),
                  last_location_id TEXT REFERENCES locations(location_id), relation TEXT, observed_at TEXT, confidence REAL NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS object_normalized_name_unique ON objects(room_id, normalized_name);
                CREATE TABLE IF NOT EXISTS object_aliases (
                  object_id TEXT NOT NULL REFERENCES objects(object_id) ON DELETE CASCADE, alias TEXT NOT NULL,
                  normalized_alias TEXT NOT NULL, PRIMARY KEY(object_id, normalized_alias)
                );
                CREATE TABLE IF NOT EXISTS observations (
                  observation_id TEXT PRIMARY KEY, object_id TEXT NOT NULL REFERENCES objects(object_id),
                  location_id TEXT REFERENCES locations(location_id), observed_at TEXT NOT NULL, bounding_box_json TEXT NOT NULL,
                  confidence REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence_images (
                  evidence_id TEXT PRIMARY KEY, object_id TEXT NOT NULL REFERENCES objects(object_id),
                  observed_at TEXT NOT NULL, path TEXT NOT NULL, bounding_box_json TEXT NOT NULL, retained INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(1, ?)", (datetime.now(UTC).isoformat(),))
            conn.execute("CREATE TABLE IF NOT EXISTS observation_candidates (source_key TEXT PRIMARY KEY, hits INTEGER NOT NULL)")

            try:
                conn.execute("ALTER TABLE objects ADD COLUMN source_key TEXT UNIQUE")
            except sqlite3.OperationalError:
                pass
    def ingest_observations(self, observations: list[IncomingObservation], observed_at: datetime, fixture_image_path: str | None, evidence_dir: Path) -> int:
        """Promote a mock candidate only after three matching frames."""
        with self.session() as conn:
            room = conn.execute("SELECT room_id FROM rooms WHERE name=?", ("Mock \u5367\u5ba4",)).fetchone()
            room_id = room["room_id"] if room else new_ulid()
            if not room:
                conn.execute("INSERT INTO rooms(room_id, name) VALUES(?, ?)", (room_id, "Mock \u5367\u5ba4"))
            created = 0
            for incoming in observations:
                candidate = conn.execute("SELECT hits FROM observation_candidates WHERE source_key=?", (incoming.track_key,)).fetchone()
                hits = (candidate["hits"] if candidate else 0) + 1
                conn.execute("INSERT INTO observation_candidates(source_key, hits) VALUES(?, ?) ON CONFLICT(source_key) DO UPDATE SET hits=excluded.hits", (incoming.track_key, hits))
                location = conn.execute("SELECT location_id FROM locations WHERE room_id=? AND normalized_name=?", (room_id, normalize_name(incoming.location_name))).fetchone()
                location_id = location["location_id"] if location else new_ulid()
                if not location:
                    conn.execute("INSERT INTO locations(location_id, room_id, name, normalized_name) VALUES(?, ?, ?, ?)", (location_id, room_id, incoming.location_name, normalize_name(incoming.location_name)))
                existing = conn.execute("SELECT object_id FROM objects WHERE source_key=?", (incoming.track_key,)).fetchone()
                if not existing and hits < 3:
                    continue
                if not existing:
                    object_id = new_ulid()
                    conn.execute("INSERT INTO objects(object_id, room_id, name, system_name, category, normalized_name, source_key, state, current_location_id, last_location_id, relation, observed_at, confidence) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (object_id, room_id, incoming.name, incoming.system_name, incoming.category, normalize_name(incoming.name), incoming.track_key, ObjectState.CURRENTLY_DETECTED, location_id, location_id, incoming.relation, observed_at.isoformat(), incoming.confidence))
                    for alias in incoming.aliases:
                        conn.execute("INSERT OR IGNORE INTO object_aliases(object_id, alias, normalized_alias) VALUES(?, ?, ?)", (object_id, alias, normalize_name(alias)))
                    created += 1
                else:
                    object_id = existing["object_id"]
                    conn.execute("UPDATE objects SET state=?, current_location_id=?, last_location_id=?, relation=?, observed_at=?, confidence=? WHERE object_id=?", (ObjectState.CURRENTLY_DETECTED, location_id, location_id, incoming.relation, observed_at.isoformat(), incoming.confidence, object_id))
                bbox = json.dumps(incoming.bounding_box)
                conn.execute("INSERT INTO observations(observation_id, object_id, location_id, observed_at, bounding_box_json, confidence) VALUES(?, ?, ?, ?, ?, ?)", (new_ulid(), object_id, location_id, observed_at.isoformat(), bbox, incoming.confidence))
                evidence = conn.execute("SELECT 1 FROM evidence_images WHERE object_id=?", (object_id,)).fetchone()
                if fixture_image_path and not evidence:
                    source = Path(fixture_image_path)
                    if source.is_file():
                        evidence_dir.mkdir(parents=True, exist_ok=True)
                        evidence_id = new_ulid()
                        destination = evidence_dir / f"{evidence_id}{source.suffix.lower()}"
                        copy2(source, destination)
                        conn.execute("INSERT INTO evidence_images(evidence_id, object_id, observed_at, path, bounding_box_json) VALUES(?, ?, ?, ?, ?)", (evidence_id, object_id, observed_at.isoformat(), str(destination), bbox))
            return created

    def seed_demo_data(self) -> None:
        with self.session() as conn:
            if conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0]:
                return
            room_id = new_ulid()
            conn.execute("INSERT INTO rooms(room_id, name) VALUES(?, ?)", (room_id, "我的卧室"))
            locations = [("书桌", "书桌左侧"), ("床", "床上方"), ("左侧床头柜", "床头柜上方"), ("衣柜", "衣柜内侧"), ("未分区区域", "画面中央")]
            location_ids: dict[str, str] = {}
            for name, _ in locations:
                location_id = new_ulid()
                location_ids[name] = location_id
                conn.execute("INSERT INTO locations(location_id, room_id, name, normalized_name) VALUES(?, ?, ?, ?)", (location_id, room_id, name, normalize_name(name)))
            now = datetime.now(UTC)
            objects = [
                ("我的钥匙", "银色钥匙", "钥匙", "currently_detected", "书桌", "书桌左侧", 0.96, ["钥匙", "门钥匙"]),
                ("阅读眼镜", "黑框眼镜", "眼镜", "not_currently_detected", "左侧床头柜", "床头柜上方", 0.91, ["眼镜"]),
                ("黑色水杯", "黑色水杯", "水杯", "currently_detected", "书桌", "书桌右侧", 0.94, ["杯子"]),
                ("白色水杯", "白色水杯", "水杯", "not_currently_detected", "床", "床右侧", 0.83, ["杯子"]),
                ("耳机盒", "黑色小盒子", "耳机", "currently_detected", "书桌", "显示器下方", 0.88, ["耳机"]),
                ("蓝色笔记本", "蓝色笔记本", "文具", "currently_detected", "书桌", "左上角", 0.92, ["笔记本"]),
                ("遥控器", "黑色遥控器", "遥控器", "not_currently_detected", "床", "床中部", 0.86, []),
                ("充电线", "白色充电线", "电子配件", "currently_detected", "书桌", "显示器右侧", 0.79, []),
                ("帆布包", "米白色帆布包", "包", "not_currently_detected", "衣柜", "衣柜下层", 0.78, []),
                ("绿色台灯", "绿色台灯", "灯具", "identity_uncertain", "书桌", "右侧", 0.66, []),
            ]
            for index, (name, system_name, category, state, location_name, relation, confidence, aliases) in enumerate(objects):
                object_id = new_ulid()
                seen = now - timedelta(minutes=index * 3 + 1)
                current_id = location_ids[location_name] if state == "currently_detected" else None
                location_id = location_ids[location_name]
                conn.execute(
                    """INSERT INTO objects(object_id, room_id, name, system_name, category, normalized_name, state, current_location_id, last_location_id, relation, observed_at, confidence)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (object_id, room_id, name, system_name, category, normalize_name(name), state, current_id, location_id, relation, seen.isoformat(), confidence),
                )
                for alias in aliases:
                    conn.execute("INSERT INTO object_aliases(object_id, alias, normalized_alias) VALUES(?, ?, ?)", (object_id, alias, normalize_name(alias)))
                conn.execute("INSERT INTO observations(observation_id, object_id, location_id, observed_at, bounding_box_json, confidence) VALUES(?, ?, ?, ?, ?, ?)", (new_ulid(), object_id, location_id, seen.isoformat(), "[0.54, 0.4, 0.15, 0.2]", confidence))
                conn.execute("INSERT INTO evidence_images(evidence_id, object_id, observed_at, path, bounding_box_json) VALUES(?, ?, ?, ?, ?)", (new_ulid(), object_id, seen.isoformat(), "demo", "[0.54, 0.4, 0.15, 0.2]"))

    @staticmethod
    def _location(row: sqlite3.Row, prefix: str) -> LocationSummary | None:
        location_id = row[f"{prefix}_location_id"]
        if not location_id:
            return None
        return LocationSummary(location_id=location_id, name=row[f"{prefix}_location_name"], relation=row["relation"])

    def _object_from_row(self, conn: sqlite3.Connection, row: sqlite3.Row) -> CatalogObject:
        aliases = [value[0] for value in conn.execute("SELECT alias FROM object_aliases WHERE object_id=? ORDER BY alias", (row["object_id"],))]
        return CatalogObject(
            object_id=row["object_id"], name=row["name"], system_name=row["system_name"], category=row["category"], aliases=aliases,
            state=ObjectState(row["state"]), current_location=self._location(row, "current"), last_location=self._location(row, "last"),
            observed_at=datetime.fromisoformat(row["observed_at"]) if row["observed_at"] else None, confidence=row["confidence"],
        )

    def list_objects(self) -> list[CatalogObject]:
        with self.session() as conn:
            rows = conn.execute(
                """SELECT o.*, cl.name AS current_location_name, ll.name AS last_location_name FROM objects o
                LEFT JOIN locations cl ON cl.location_id=o.current_location_id LEFT JOIN locations ll ON ll.location_id=o.last_location_id
                ORDER BY o.name"""
            ).fetchall()
            return [self._object_from_row(conn, row) for row in rows]

    def list_locations(self) -> list[Location]:
        with self.session() as conn:
            rows = conn.execute(
                """SELECT l.*, COUNT(o.object_id) AS item_count FROM locations l LEFT JOIN objects o ON o.current_location_id=l.location_id
                GROUP BY l.location_id ORDER BY l.name"""
            ).fetchall()
            return [Location(location_id=row["location_id"], name=row["name"], normalized_name=row["normalized_name"], item_count=row["item_count"]) for row in rows]

    def latest_evidence(self, object_id: str, public_url: str) -> Evidence | None:
        with self.session() as conn:
            row = conn.execute("SELECT * FROM evidence_images WHERE object_id=? ORDER BY observed_at DESC LIMIT 1", (object_id,)).fetchone()
            if not row:
                return None
            return Evidence(evidence_id=row["evidence_id"], image_url=f"{public_url}/api/evidence/{row['evidence_id']}", observed_at=datetime.fromisoformat(row["observed_at"]), bounding_box=tuple(json.loads(row["bounding_box_json"])))

    def evidence_path(self, evidence_id: str) -> Path | None:
        with self.session() as conn:
            row = conn.execute("SELECT path FROM evidence_images WHERE evidence_id=?", (evidence_id,)).fetchone()
            return Path(row["path"]) if row else None


    def rename_object(self, object_id: str, name: str, aliases: list[str] | None) -> CatalogObject | None:
        with self.session() as conn:
            try:
                with conn:
                    row = conn.execute("SELECT room_id FROM objects WHERE object_id=?", (object_id,)).fetchone()
                    if not row:
                        return None
                    conn.execute("UPDATE objects SET name=?, normalized_name=? WHERE object_id=?", (name.strip(), normalize_name(name), object_id))
                    if aliases is not None:
                        conn.execute("DELETE FROM object_aliases WHERE object_id=?", (object_id,))
                        conn.executemany("INSERT INTO object_aliases(object_id, alias, normalized_alias) VALUES(?, ?, ?)", [(object_id, alias.strip(), normalize_name(alias)) for alias in aliases if alias.strip()])
            except sqlite3.IntegrityError as error:
                raise ValueError("该名称已被其他物品使用，请添加区分信息。") from error
            joined = conn.execute("""SELECT o.*, cl.name AS current_location_name, ll.name AS last_location_name FROM objects o
                LEFT JOIN locations cl ON cl.location_id=o.current_location_id LEFT JOIN locations ll ON ll.location_id=o.last_location_id WHERE o.object_id=?""", (object_id,)).fetchone()
            return self._object_from_row(conn, joined)

    def rename_location(self, location_id: str, name: str) -> Location | None:
        with self.session() as conn:
            try:
                with conn:
                    row = conn.execute("SELECT * FROM locations WHERE location_id=?", (location_id,)).fetchone()
                    if not row:
                        return None
                    conn.execute("UPDATE locations SET name=?, normalized_name=? WHERE location_id=?", (name.strip(), normalize_name(name), location_id))
            except sqlite3.IntegrityError as error:
                raise ValueError("该位置名称已被使用，请补充方位信息。") from error
            return Location(location_id=location_id, name=name.strip(), normalized_name=normalize_name(name), item_count=0)

    def _find_candidates(self, text: str) -> list[CatalogObject]:
        normalized = normalize_name(text.replace("在哪里", "").replace("在哪", "").replace("我的", ""))
        candidates: list[CatalogObject] = []
        for item in self.list_objects():
            names = [normalize_name(item.name), normalize_name(item.system_name), normalize_name(item.category), *(normalize_name(alias) for alias in item.aliases)]
            if any(term and (term in normalized or normalized in term) for term in names):
                candidates.append(item)
        return candidates

    def query(self, text: str, public_url: str) -> QueryResult:
        started = datetime.now(UTC)
        candidates = self._find_candidates(text)
        resolve_ms = round((datetime.now(UTC) - started).total_seconds() * 1000, 1)
        if not candidates:
            suggestions = self.list_objects()[:3]
            return QueryResult(answer="还没有在物品目录中找到这个对象。你可以从已有物品中选择，或等系统完成下一轮扫描。", status="not_found", clarification_options=suggestions, timings={"resolve_ms": resolve_ms, "lookup_ms": 0, "llm_ms": 0, "total_ms": resolve_ms})
        if len(candidates) > 1:
            return QueryResult(answer="我找到了多个可能的物品，请选择你要找的具体物品。", status="clarification", clarification_options=candidates, timings={"resolve_ms": resolve_ms, "lookup_ms": 0, "llm_ms": 0, "total_ms": resolve_ms})
        item = candidates[0]
        evidence = self.latest_evidence(item.object_id, public_url)
        if item.state == ObjectState.CURRENTLY_DETECTED:
            where = item.current_location or item.last_location
            answer = f"已检测到{item.name}，在{where.name}{'，' + where.relation if where and where.relation else ''}。"
            return QueryResult(answer=answer, status=item.state, object=item, evidence=evidence, timings={"resolve_ms": resolve_ms, "lookup_ms": 4.2, "llm_ms": 0, "total_ms": resolve_ms + 4.2})
        if item.state == ObjectState.IDENTITY_UNCERTAIN:
            return QueryResult(answer=f"检测到可能是{item.name}的物品，但身份尚不确定，因此不能把它当作确定位置。", status=item.state, object=item, evidence=evidence, timings={"resolve_ms": resolve_ms, "lookup_ms": 4.2, "llm_ms": 0, "total_ms": resolve_ms + 4.2})
        last = item.last_location
        predictions: list[Prediction] = []
        if last:
            predictions = [Prediction(location=last, confidence=ConfidenceLevel.HIGH, score=0.68, basis="最后一次确定观测位于此处"), Prediction(location=LocationSummary(location_id="nearby", name="书桌", relation="附近"), confidence=ConfidenceLevel.MEDIUM, score=0.42, basis="与最后出现区域相邻")]
        answer = f"当前未检测到{item.name}。最后一次确定位置在{last.name if last else '未分区区域'}。下面的位置属于推测，建议先从最后出现处开始查看。"
        return QueryResult(answer=answer, status=item.state, object=item, predictions=predictions, evidence=evidence, timings={"resolve_ms": resolve_ms, "lookup_ms": 5.6, "llm_ms": 0, "total_ms": resolve_ms + 5.6})
