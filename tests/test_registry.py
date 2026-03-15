"""Tests du registre de caméras Frigate — CameraRegistry.

Couvre :
- get() : auto-découverte (caméra inconnue → CameraState avec enabled=True)
- update() type=new  : motion=True, event_count_24h incrémenté, severity/objects mis à jour
- update() type=update : motion inchangé, event_count_24h non incrémenté
- update() type=end  : motion=False, last_event_time = end_time ou start_time
- set_enabled() : activation/désactivation sur caméra existante et inconnue
- all_cameras() : retourne toutes les caméras connues
- async_save() : écriture atomique déléguée à hass.async_add_executor_job
- async_load() : chargement depuis JSON valide
- async_load() fichier absent → démarrage à vide, sans exception
- async_load() JSON corrompu → démarrage à vide, sans exception
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.frigate_event_manager.coordinator import (
    CameraState,
    FrigateEvent,
)
from custom_components.frigate_event_manager.registry import CameraRegistry


# ---------------------------------------------------------------------------
# Helpers — constructeurs minimaux
# ---------------------------------------------------------------------------


def make_event(
    *,
    camera: str = "jardin",
    event_type: str = "new",
    severity: str = "alert",
    objects: list[str] | None = None,
    zones: list[str] | None = None,
    start_time: float = 1710000000.0,
    end_time: float | None = None,
) -> FrigateEvent:
    """Construit un FrigateEvent minimal pour les tests du registre."""
    return FrigateEvent(
        type=event_type,
        camera=camera,
        severity=severity,
        objects=objects if objects is not None else ["personne"],
        zones=zones if zones is not None else ["entree"],
        start_time=start_time,
        end_time=end_time,
    )


def make_hass(state_path: str) -> MagicMock:
    """Construit un MagicMock HomeAssistant avec config.path() pointant vers state_path."""
    hass = MagicMock()
    hass.config.path.return_value = state_path
    # async_add_executor_job exécute la fonction de manière synchrone dans les tests
    async def _executor_job(func, *args):
        return func(*args)

    hass.async_add_executor_job = _executor_job
    return hass


# ---------------------------------------------------------------------------
# Fixture : répertoire temporaire + chemin de state
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_state_path(tmp_path):
    """Retourne un chemin de fichier d'état temporaire (non créé)."""
    return str(tmp_path / "frigate_em_state.json")


@pytest.fixture()
def registry(tmp_state_path):
    """Retourne un CameraRegistry vide avec un hass mocké."""
    hass = make_hass(tmp_state_path)
    return CameraRegistry(hass)


# ---------------------------------------------------------------------------
# Tests — get() : auto-découverte
# ---------------------------------------------------------------------------


class TestGet:
    """Tests de get() — auto-découverte des caméras inconnues."""

    def test_camera_inconnue_cree_avec_enabled_true(self, registry):
        """Une caméra inconnue est créée automatiquement avec enabled=True."""
        state = registry.get("nouvelle_cam")

        assert isinstance(state, CameraState)
        assert state.name == "nouvelle_cam"
        assert state.enabled is True

    def test_camera_inconnue_ajoutee_au_dict(self, registry):
        """La caméra créée est bien persistée dans le registre interne."""
        registry.get("cam_x")
        assert len(registry.all_cameras()) == 1

    def test_get_camera_existante_retourne_meme_objet(self, registry):
        """Appeler get() deux fois retourne le même objet (pas de doublon)."""
        state1 = registry.get("jardin")
        state2 = registry.get("jardin")
        assert state1 is state2

    def test_get_camera_existante_n_incremente_pas(self, registry):
        """get() sur une caméra connue ne crée pas de doublon."""
        registry.get("jardin")
        registry.get("jardin")
        assert len(registry.all_cameras()) == 1

    def test_camera_inconnue_defauts_complets(self, registry):
        """CameraState créée a tous les champs par défaut corrects."""
        state = registry.get("cam_defaut")
        assert state.motion is False
        assert state.last_severity is None
        assert state.last_objects == []
        assert state.event_count_24h == 0
        assert state.last_event_time is None


# ---------------------------------------------------------------------------
# Tests — update() type=new
# ---------------------------------------------------------------------------


class TestUpdateNew:
    """Tests de update() avec type=new."""

    def test_motion_passe_a_true(self, registry):
        event = make_event(event_type="new")
        registry.update(event)
        assert registry.get("jardin").motion is True

    def test_event_count_incremente(self, registry):
        event = make_event(event_type="new")
        registry.update(event)
        assert registry.get("jardin").event_count_24h == 1

    def test_event_count_incremente_a_chaque_new(self, registry):
        for _ in range(3):
            registry.update(make_event(event_type="new"))
        assert registry.get("jardin").event_count_24h == 3

    def test_last_severity_mis_a_jour(self, registry):
        event = make_event(event_type="new", severity="alert")
        registry.update(event)
        assert registry.get("jardin").last_severity == "alert"

    def test_last_objects_mis_a_jour(self, registry):
        event = make_event(event_type="new", objects=["voiture", "personne"])
        registry.update(event)
        assert registry.get("jardin").last_objects == ["voiture", "personne"]

    def test_last_event_time_mis_a_jour(self, registry):
        event = make_event(event_type="new", start_time=1710000042.0)
        registry.update(event)
        assert registry.get("jardin").last_event_time == 1710000042.0

    def test_auto_decouverte_camera_inconnue(self, registry):
        """update() sur une caméra inconnue la crée via get()."""
        event = make_event(camera="cam_inconnue", event_type="new")
        registry.update(event)
        assert "cam_inconnue" in [c.name for c in registry.all_cameras()]


# ---------------------------------------------------------------------------
# Tests — update() type=update
# ---------------------------------------------------------------------------


class TestUpdateUpdate:
    """Tests de update() avec type=update."""

    def test_motion_inchange_si_false(self, registry):
        """type=update ne doit pas modifier motion."""
        # Initialise la caméra sans motion (par défaut False)
        registry.get("jardin")
        event = make_event(event_type="update")
        registry.update(event)
        assert registry.get("jardin").motion is False

    def test_motion_inchange_si_true(self, registry):
        """Si motion était True (après type=new), type=update ne le remet pas à False."""
        registry.update(make_event(event_type="new"))
        registry.update(make_event(event_type="update"))
        assert registry.get("jardin").motion is True

    def test_event_count_non_incremente(self, registry):
        """type=update ne doit pas incrémenter event_count_24h."""
        registry.update(make_event(event_type="update"))
        assert registry.get("jardin").event_count_24h == 0

    def test_severity_mise_a_jour(self, registry):
        event = make_event(event_type="update", severity="detection")
        registry.update(event)
        assert registry.get("jardin").last_severity == "detection"

    def test_objects_mis_a_jour(self, registry):
        event = make_event(event_type="update", objects=["chien"])
        registry.update(event)
        assert registry.get("jardin").last_objects == ["chien"]

    def test_last_event_time_mis_a_jour(self, registry):
        event = make_event(event_type="update", start_time=1710000099.0)
        registry.update(event)
        assert registry.get("jardin").last_event_time == 1710000099.0


# ---------------------------------------------------------------------------
# Tests — update() type=end
# ---------------------------------------------------------------------------


class TestUpdateEnd:
    """Tests de update() avec type=end."""

    def test_motion_passe_a_false(self, registry):
        """type=end doit mettre motion à False."""
        # D'abord un new pour mettre motion=True
        registry.update(make_event(event_type="new"))
        registry.update(make_event(event_type="end"))
        assert registry.get("jardin").motion is False

    def test_last_event_time_utilise_end_time_si_present(self, registry):
        event = make_event(event_type="end", start_time=1710000000.0, end_time=1710000099.0)
        registry.update(event)
        assert registry.get("jardin").last_event_time == 1710000099.0

    def test_last_event_time_fallback_start_time_si_end_time_absent(self, registry):
        """Si end_time est None, last_event_time doit utiliser start_time."""
        event = make_event(event_type="end", start_time=1710000000.0, end_time=None)
        registry.update(event)
        assert registry.get("jardin").last_event_time == 1710000000.0

    def test_event_count_non_incremente(self, registry):
        """type=end ne doit pas incrémenter event_count_24h."""
        registry.update(make_event(event_type="end"))
        assert registry.get("jardin").event_count_24h == 0

    def test_severity_inchangee_sur_end(self, registry):
        """type=end ne modifie pas last_severity."""
        registry.update(make_event(event_type="new", severity="alert"))
        registry.update(make_event(event_type="end"))
        assert registry.get("jardin").last_severity == "alert"


# ---------------------------------------------------------------------------
# Tests — set_enabled()
# ---------------------------------------------------------------------------


class TestSetEnabled:
    """Tests de set_enabled() — activation/désactivation des notifications."""

    def test_desactiver_camera_existante(self, registry):
        registry.get("jardin")  # crée la caméra
        registry.set_enabled("jardin", False)
        assert registry.get("jardin").enabled is False

    def test_activer_camera_desactivee(self, registry):
        registry.get("jardin")
        registry.set_enabled("jardin", False)
        registry.set_enabled("jardin", True)
        assert registry.get("jardin").enabled is True

    def test_set_enabled_cree_camera_inconnue(self, registry):
        """set_enabled sur une caméra inconnue la crée via get()."""
        registry.set_enabled("nouvelle_cam", False)
        state = registry.get("nouvelle_cam")
        assert state.enabled is False

    def test_set_enabled_camera_inconnue_conserve_enabled_true_apres_reenable(self, registry):
        registry.set_enabled("cam_x", False)
        registry.set_enabled("cam_x", True)
        assert registry.get("cam_x").enabled is True

    def test_enabled_initial_true_pour_nouvelle_camera(self, registry):
        """Une caméra créée via set_enabled doit avoir enabled=True par défaut avant la mutation."""
        # Vérification indirecte : après set_enabled(True), enabled == True
        registry.set_enabled("cam_y", True)
        assert registry.get("cam_y").enabled is True


# ---------------------------------------------------------------------------
# Tests — all_cameras()
# ---------------------------------------------------------------------------


class TestAllCameras:
    """Tests de all_cameras() — listing complet du registre."""

    def test_registre_vide(self, registry):
        assert registry.all_cameras() == []

    def test_retourne_une_camera(self, registry):
        registry.get("jardin")
        cams = registry.all_cameras()
        assert len(cams) == 1
        assert cams[0].name == "jardin"

    def test_retourne_toutes_les_cameras(self, registry):
        for name in ("jardin", "garage", "entree"):
            registry.get(name)
        names = {c.name for c in registry.all_cameras()}
        assert names == {"jardin", "garage", "entree"}

    def test_retourne_liste_pas_vue_du_dict(self, registry):
        """all_cameras() doit retourner une liste (copie), pas une vue du dict."""
        registry.get("jardin")
        result = registry.all_cameras()
        assert isinstance(result, list)

    def test_modifications_post_all_cameras_n_impactent_pas_la_liste(self, registry):
        """La liste retournée ne change pas si on ajoute une caméra ensuite."""
        registry.get("jardin")
        snapshot = registry.all_cameras()
        registry.get("garage")
        assert len(snapshot) == 1


# ---------------------------------------------------------------------------
# Tests — async_save() : écriture atomique
# ---------------------------------------------------------------------------


class TestAsyncSave:
    """Tests de async_save() — écriture atomique via executor_job."""

    @pytest.mark.asyncio
    async def test_async_save_appelle_write_atomic(self, tmp_state_path):
        """async_save() délègue l'écriture à hass.async_add_executor_job."""
        hass = make_hass(tmp_state_path)
        reg = CameraRegistry(hass)
        reg.get("jardin")

        # On espionne _write_atomic pour vérifier qu'il est appelé
        write_calls: list = []
        original_write = reg._write_atomic

        def spy_write(data):
            write_calls.append(data)
            return original_write(data)

        with patch.object(reg, "_write_atomic", side_effect=spy_write):
            await reg.async_save()

        assert len(write_calls) == 1

    @pytest.mark.asyncio
    async def test_async_save_produit_fichier_json_valide(self, tmp_state_path):
        """async_save() crée un fichier JSON lisible avec les données correctes."""
        hass = make_hass(tmp_state_path)
        reg = CameraRegistry(hass)
        reg.get("jardin")
        reg.update(make_event(event_type="new", severity="alert", objects=["personne"]))

        await reg.async_save()

        assert os.path.isfile(tmp_state_path)
        with open(tmp_state_path, encoding="utf-8") as f:
            data = json.load(f)

        assert "jardin" in data
        assert data["jardin"]["last_severity"] == "alert"
        assert data["jardin"]["event_count_24h"] == 1

    @pytest.mark.asyncio
    async def test_async_save_ecriture_atomique_tmp_supprime(self, tmp_state_path):
        """Après async_save(), le fichier .tmp ne doit pas exister (os.replace)."""
        hass = make_hass(tmp_state_path)
        reg = CameraRegistry(hass)
        reg.get("garage")

        await reg.async_save()

        tmp_path = tmp_state_path + ".tmp"
        assert not os.path.isfile(tmp_path)

    @pytest.mark.asyncio
    async def test_async_save_registre_vide(self, tmp_state_path):
        """async_save() sur un registre vide écrit un JSON objet vide {}."""
        hass = make_hass(tmp_state_path)
        reg = CameraRegistry(hass)

        await reg.async_save()

        with open(tmp_state_path, encoding="utf-8") as f:
            data = json.load(f)
        assert data == {}


# ---------------------------------------------------------------------------
# Tests — async_load() : chargement depuis JSON valide
# ---------------------------------------------------------------------------


class TestAsyncLoad:
    """Tests de async_load() — désérialisation depuis fichier d'état."""

    @pytest.mark.asyncio
    async def test_charge_cameras_depuis_json_valide(self, tmp_state_path):
        """async_load() reconstitue les CameraState depuis un JSON valide."""
        data = {
            "jardin": {
                "name": "jardin",
                "last_severity": "alert",
                "last_objects": ["personne"],
                "event_count_24h": 5,
                "last_event_time": 1710000000.0,
                "motion": False,
                "enabled": True,
            }
        }
        with open(tmp_state_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        hass = make_hass(tmp_state_path)
        reg = CameraRegistry(hass)
        await reg.async_load()

        state = reg.get("jardin")
        assert state.last_severity == "alert"
        assert state.last_objects == ["personne"]
        assert state.event_count_24h == 5
        assert state.last_event_time == 1710000000.0
        assert state.enabled is True

    @pytest.mark.asyncio
    async def test_charge_plusieurs_cameras(self, tmp_state_path):
        """async_load() reconstruit toutes les caméras du fichier."""
        data = {
            "jardin": {"name": "jardin", "enabled": True},
            "garage": {"name": "garage", "enabled": False},
        }
        with open(tmp_state_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        hass = make_hass(tmp_state_path)
        reg = CameraRegistry(hass)
        await reg.async_load()

        assert len(reg.all_cameras()) == 2
        assert reg.get("garage").enabled is False

    @pytest.mark.asyncio
    async def test_champs_manquants_ont_valeurs_defaut(self, tmp_state_path):
        """Les champs absents dans le JSON sont remplacés par des valeurs par défaut."""
        data = {"cam_minimale": {"name": "cam_minimale"}}
        with open(tmp_state_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        hass = make_hass(tmp_state_path)
        reg = CameraRegistry(hass)
        await reg.async_load()

        state = reg.get("cam_minimale")
        assert state.last_severity is None
        assert state.last_objects == []
        assert state.event_count_24h == 0
        assert state.enabled is True

    @pytest.mark.asyncio
    async def test_fichier_absent_demarre_vide_sans_exception(self, tmp_state_path):
        """Si le fichier d'état est absent, le registre démarre vide sans lever d'exception."""
        assert not os.path.isfile(tmp_state_path)

        hass = make_hass(tmp_state_path)
        reg = CameraRegistry(hass)

        # Ne doit pas lever d'exception
        await reg.async_load()

        assert reg.all_cameras() == []

    @pytest.mark.asyncio
    async def test_json_corrompu_demarre_vide_sans_exception(self, tmp_state_path):
        """Si le fichier JSON est corrompu, le registre démarre vide sans lever d'exception."""
        with open(tmp_state_path, "w", encoding="utf-8") as f:
            f.write("{ ceci n'est pas du JSON valide !!!")

        hass = make_hass(tmp_state_path)
        reg = CameraRegistry(hass)

        # Ne doit pas lever d'exception
        await reg.async_load()

        assert reg.all_cameras() == []

    @pytest.mark.asyncio
    async def test_json_pas_un_dict_racine_demarre_vide(self, tmp_state_path):
        """Si la racine JSON n'est pas un dict (ex: liste), le registre démarre vide."""
        with open(tmp_state_path, "w", encoding="utf-8") as f:
            json.dump(["ce", "n'est", "pas", "un", "dict"], f)

        hass = make_hass(tmp_state_path)
        reg = CameraRegistry(hass)
        await reg.async_load()

        assert reg.all_cameras() == []

    @pytest.mark.asyncio
    async def test_entree_invalide_ignoree_gracieusement(self, tmp_state_path):
        """Une entrée avec une valeur non-dict est ignorée, les autres chargées."""
        data = {
            "cam_valide": {"name": "cam_valide", "enabled": True},
            "cam_invalide": "pas un dict",
        }
        with open(tmp_state_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        hass = make_hass(tmp_state_path)
        reg = CameraRegistry(hass)
        await reg.async_load()

        cameras = [c.name for c in reg.all_cameras()]
        assert "cam_valide" in cameras
        assert "cam_invalide" not in cameras

    @pytest.mark.asyncio
    async def test_async_load_puis_async_save_roundtrip(self, tmp_state_path):
        """Charger puis sauvegarder préserve les données (round-trip)."""
        data = {
            "jardin": {
                "name": "jardin",
                "last_severity": "detection",
                "last_objects": ["chien"],
                "event_count_24h": 2,
                "last_event_time": 1710001234.0,
                "motion": False,
                "enabled": False,
            }
        }
        with open(tmp_state_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        hass = make_hass(tmp_state_path)
        reg = CameraRegistry(hass)
        await reg.async_load()
        await reg.async_save()

        with open(tmp_state_path, encoding="utf-8") as f:
            reloaded = json.load(f)

        assert reloaded["jardin"]["last_severity"] == "detection"
        assert reloaded["jardin"]["event_count_24h"] == 2
        assert reloaded["jardin"]["enabled"] is False
