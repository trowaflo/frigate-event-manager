"""Tests du ring buffer EventStore.

Couvre :
- add() : création correcte de EventRecord depuis FrigateEvent,
          copies défensives des listes
- list() sans filtre : ordre plus-récent-en-premier, limite respectée
- list(severity="alert") : filtre correctement, ignore les autres sévérités
- list() sur store vide : retourne []
- stats() : events_24h et alerts_24h corrects (time.time mocké)
- stats() sur store vide : 0/0
- Ring buffer maxlen : le 201ème event évince le 1er
- Timestamp fallback : start_time=0.0 → time.time() utilisé
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.frigate_event_manager.coordinator import FrigateEvent
from custom_components.frigate_event_manager.event_store import EventRecord, EventStore


# ---------------------------------------------------------------------------
# Helpers de fabrication d'événements Frigate
# ---------------------------------------------------------------------------

def _make_event(
    camera: str = "jardin",
    severity: str = "alert",
    objects: list[str] | None = None,
    zones: list[str] | None = None,
    start_time: float = 1_700_000_000.0,
    thumb_path: str = "/media/thumb.jpg",
) -> FrigateEvent:
    """Construit un FrigateEvent minimal et réaliste."""
    return FrigateEvent(
        type="new",
        camera=camera,
        severity=severity,
        objects=objects if objects is not None else ["personne"],
        zones=zones if zones is not None else ["entree"],
        score=0.85,
        thumb_path=thumb_path,
        review_id="abc123",
        start_time=start_time,
    )


# ---------------------------------------------------------------------------
# add() — création d'EventRecord
# ---------------------------------------------------------------------------

class TestAdd:
    def test_record_created_correctement(self) -> None:
        """add() crée un EventRecord avec tous les champs du FrigateEvent."""
        store = EventStore()
        event = _make_event(
            camera="entree",
            severity="detection",
            objects=["voiture"],
            zones=["rue"],
            start_time=1_700_000_042.0,
            thumb_path="/media/entree.jpg",
        )

        store.add(event)

        records = store.list()
        assert len(records) == 1
        r = records[0]
        assert r.camera == "entree"
        assert r.severity == "detection"
        assert r.objects == ["voiture"]
        assert r.zones == ["rue"]
        assert r.timestamp == 1_700_000_042.0
        assert r.thumb_path == "/media/entree.jpg"

    def test_copies_defensives_objects(self) -> None:
        """add() stocke une copie indépendante de la liste objects."""
        store = EventStore()
        objects = ["personne", "vélo"]
        event = _make_event(objects=objects)
        store.add(event)

        # Modifier la liste source ne doit pas altérer le record
        objects.append("chien")

        records = store.list()
        assert records[0].objects == ["personne", "vélo"]

    def test_copies_defensives_zones(self) -> None:
        """add() stocke une copie indépendante de la liste zones."""
        store = EventStore()
        zones = ["entree", "jardin"]
        event = _make_event(zones=zones)
        store.add(event)

        zones.clear()

        records = store.list()
        assert records[0].zones == ["entree", "jardin"]

    def test_timestamp_depuis_start_time(self) -> None:
        """Le timestamp de l'EventRecord reprend start_time quand > 0.0."""
        store = EventStore()
        store.add(_make_event(start_time=1_234_567_890.0))

        assert store.list()[0].timestamp == 1_234_567_890.0

    def test_timestamp_fallback_quand_start_time_zero(self) -> None:
        """Si start_time == 0.0, add() utilise time.time() comme timestamp."""
        store = EventStore()
        fake_now = 9_999_999_999.0

        with patch(
            "custom_components.frigate_event_manager.event_store.time.time",
            return_value=fake_now,
        ):
            store.add(_make_event(start_time=0.0))

        assert store.list()[0].timestamp == fake_now

    def test_plusieurs_add_conserves(self) -> None:
        """Plusieurs add() consécutifs sont tous conservés."""
        store = EventStore()
        for i in range(5):
            store.add(_make_event(start_time=float(i + 1)))

        assert len(store.list(limit=100)) == 5


# ---------------------------------------------------------------------------
# list() — ordre et limite
# ---------------------------------------------------------------------------

class TestList:
    def test_store_vide_retourne_liste_vide(self) -> None:
        """list() sur un store vide retourne []."""
        store = EventStore()
        assert store.list() == []

    def test_ordre_plus_recent_en_premier(self) -> None:
        """list() retourne les événements du plus récent au plus ancien."""
        store = EventStore()
        timestamps = [1_700_000_001.0, 1_700_000_002.0, 1_700_000_003.0]
        for ts in timestamps:
            store.add(_make_event(start_time=ts))

        records = store.list(limit=10)
        assert [r.timestamp for r in records] == [
            1_700_000_003.0,
            1_700_000_002.0,
            1_700_000_001.0,
        ]

    def test_limite_respectee(self) -> None:
        """list(limit=N) retourne au plus N éléments."""
        store = EventStore()
        for i in range(20):
            store.add(_make_event(start_time=float(i + 1)))

        result = store.list(limit=5)
        assert len(result) == 5

    def test_limite_superieure_au_nombre_total(self) -> None:
        """list(limit=100) avec 3 éléments retourne les 3 éléments."""
        store = EventStore()
        for i in range(3):
            store.add(_make_event(start_time=float(i + 1)))

        result = store.list(limit=100)
        assert len(result) == 3

    def test_sans_filtre_retourne_toutes_les_severites(self) -> None:
        """list() sans filtre severity inclut alert ET detection."""
        store = EventStore()
        store.add(_make_event(severity="alert", start_time=1.0))
        store.add(_make_event(severity="detection", start_time=2.0))

        result = store.list(limit=10)
        severities = {r.severity for r in result}
        assert severities == {"alert", "detection"}


# ---------------------------------------------------------------------------
# list(severity=...) — filtre par sévérité
# ---------------------------------------------------------------------------

class TestListSeverityFilter:
    def test_filtre_alert_seulement(self) -> None:
        """list(severity='alert') ne retourne que les événements alert."""
        store = EventStore()
        store.add(_make_event(severity="alert", start_time=1.0))
        store.add(_make_event(severity="detection", start_time=2.0))
        store.add(_make_event(severity="alert", start_time=3.0))

        result = store.list(severity="alert", limit=10)

        assert len(result) == 2
        assert all(r.severity == "alert" for r in result)

    def test_filtre_detection_seulement(self) -> None:
        """list(severity='detection') exclut les events alert."""
        store = EventStore()
        store.add(_make_event(severity="alert", start_time=1.0))
        store.add(_make_event(severity="detection", start_time=2.0))

        result = store.list(severity="detection", limit=10)

        assert len(result) == 1
        assert result[0].severity == "detection"

    def test_filtre_severity_inexistante_retourne_vide(self) -> None:
        """list(severity='critique') avec uniquement des 'alert' retourne []."""
        store = EventStore()
        store.add(_make_event(severity="alert", start_time=1.0))

        result = store.list(severity="critique", limit=10)
        assert result == []

    def test_filtre_sur_store_vide(self) -> None:
        """list(severity='alert') sur store vide retourne []."""
        store = EventStore()
        assert store.list(severity="alert") == []

    def test_filtre_respecte_la_limite(self) -> None:
        """list(severity='alert', limit=2) retourne au plus 2 alert même s'il y en a 5."""
        store = EventStore()
        for i in range(5):
            store.add(_make_event(severity="alert", start_time=float(i + 1)))

        result = store.list(severity="alert", limit=2)
        assert len(result) == 2

    def test_filtre_ordre_plus_recent_en_premier(self) -> None:
        """list(severity='alert') respecte l'ordre plus-récent-en-premier."""
        store = EventStore()
        store.add(_make_event(severity="alert", start_time=10.0))
        store.add(_make_event(severity="detection", start_time=20.0))
        store.add(_make_event(severity="alert", start_time=30.0))

        result = store.list(severity="alert", limit=10)
        assert result[0].timestamp == 30.0
        assert result[1].timestamp == 10.0


# ---------------------------------------------------------------------------
# stats() — fenêtre glissante 24h
# ---------------------------------------------------------------------------

class TestStats:
    def test_store_vide_retourne_zeros(self) -> None:
        """stats() sur un store vide retourne events_24h=0, alerts_24h=0."""
        store = EventStore()
        result = store.stats()
        assert result == {"events_24h": 0, "alerts_24h": 0}

    def test_events_dans_la_fenetre_24h(self) -> None:
        """stats() compte correctement les events récents (< 24h)."""
        store = EventStore()
        now = 1_700_100_000.0
        seuil = now - 86400  # 24h en arrière

        # 2 events dans la fenêtre, 1 alert
        store.add(_make_event(severity="alert", start_time=seuil + 100))
        store.add(_make_event(severity="detection", start_time=seuil + 200))

        with patch(
            "custom_components.frigate_event_manager.event_store.time.time",
            return_value=now,
        ):
            result = store.stats()

        assert result["events_24h"] == 2
        assert result["alerts_24h"] == 1

    def test_events_hors_fenetre_exclus(self) -> None:
        """stats() ignore les events plus anciens que 24h."""
        store = EventStore()
        now = 1_700_100_000.0
        seuil = now - 86400

        # 1 event trop ancien
        store.add(_make_event(severity="alert", start_time=seuil - 1))
        # 1 event dans la fenêtre
        store.add(_make_event(severity="detection", start_time=seuil + 1))

        with patch(
            "custom_components.frigate_event_manager.event_store.time.time",
            return_value=now,
        ):
            result = store.stats()

        assert result["events_24h"] == 1
        assert result["alerts_24h"] == 0

    def test_events_exactement_au_seuil(self) -> None:
        """Un event dont le timestamp == seuil est inclus (>= seuil)."""
        store = EventStore()
        now = 1_700_100_000.0
        seuil = now - 86400

        store.add(_make_event(severity="alert", start_time=seuil))

        with patch(
            "custom_components.frigate_event_manager.event_store.time.time",
            return_value=now,
        ):
            result = store.stats()

        assert result["events_24h"] == 1
        assert result["alerts_24h"] == 1

    def test_alerts_24h_zero_si_aucun_alert(self) -> None:
        """alerts_24h vaut 0 si tous les events ont severity='detection'."""
        store = EventStore()
        now = 1_700_100_000.0
        seuil = now - 86400

        for i in range(3):
            store.add(_make_event(severity="detection", start_time=seuil + float(i + 1)))

        with patch(
            "custom_components.frigate_event_manager.event_store.time.time",
            return_value=now,
        ):
            result = store.stats()

        assert result["events_24h"] == 3
        assert result["alerts_24h"] == 0

    def test_tous_les_events_sont_des_alerts(self) -> None:
        """alerts_24h == events_24h si tous les events sont severity='alert'."""
        store = EventStore()
        now = 1_700_100_000.0
        seuil = now - 86400

        for i in range(4):
            store.add(_make_event(severity="alert", start_time=seuil + float(i + 1)))

        with patch(
            "custom_components.frigate_event_manager.event_store.time.time",
            return_value=now,
        ):
            result = store.stats()

        assert result["events_24h"] == 4
        assert result["alerts_24h"] == 4

    def test_stats_retourne_dict_avec_bonnes_cles(self) -> None:
        """stats() retourne bien un dict avec les clés events_24h et alerts_24h."""
        store = EventStore()
        result = store.stats()
        assert "events_24h" in result
        assert "alerts_24h" in result


# ---------------------------------------------------------------------------
# Ring buffer — maxlen
# ---------------------------------------------------------------------------

class TestRingBuffer:
    def test_201eme_event_evince_le_premier(self) -> None:
        """Le 201ème event ajouté évince le 1er (ring buffer maxlen=200)."""
        store = EventStore(maxlen=200)

        # Premier event avec un timestamp distinctif
        premier_timestamp = 1.0
        store.add(_make_event(start_time=premier_timestamp))

        # 199 events supplémentaires pour remplir le buffer
        for i in range(2, 201):
            store.add(_make_event(start_time=float(i)))

        # Le buffer est plein (200 éléments)
        assert len(store.list(limit=300)) == 200

        # Le 201ème event pousse le premier dehors
        store.add(_make_event(start_time=201.0))

        records = store.list(limit=300)
        assert len(records) == 200

        # Le premier event (timestamp=1.0) ne doit plus être présent
        timestamps = {r.timestamp for r in records}
        assert premier_timestamp not in timestamps
        assert 201.0 in timestamps

    def test_maxlen_personnalise(self) -> None:
        """Un EventStore(maxlen=5) ne conserve que 5 events."""
        store = EventStore(maxlen=5)
        for i in range(10):
            store.add(_make_event(start_time=float(i + 1)))

        records = store.list(limit=100)
        assert len(records) == 5
        # Les 5 derniers événements (timestamps 6 à 10)
        timestamps = sorted(r.timestamp for r in records)
        assert timestamps == [6.0, 7.0, 8.0, 9.0, 10.0]

    def test_buffer_vide_par_defaut(self) -> None:
        """Un EventStore nouvellement créé est vide."""
        store = EventStore()
        assert store.list() == []
        assert store.stats() == {"events_24h": 0, "alerts_24h": 0}


# ---------------------------------------------------------------------------
# EventRecord — typage et structure
# ---------------------------------------------------------------------------

class TestEventRecord:
    def test_event_record_est_un_dataclass(self) -> None:
        """EventRecord est instanciable directement avec tous ses champs."""
        record = EventRecord(
            camera="cour",
            severity="alert",
            objects=["chat"],
            zones=["pelouse"],
            timestamp=1_700_000_000.0,
            thumb_path="/media/cour.jpg",
        )
        assert record.camera == "cour"
        assert record.severity == "alert"
        assert record.objects == ["chat"]
        assert record.zones == ["pelouse"]
        assert record.timestamp == 1_700_000_000.0
        assert record.thumb_path == "/media/cour.jpg"
