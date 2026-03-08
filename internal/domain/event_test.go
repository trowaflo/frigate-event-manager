package domain_test

import (
    "encoding/json"
    "testing"

    "frigate-event-manager/internal/domain"
)

func TestParseFrigatePayload_NewEvent(t *testing.T) {
    // GIVEN : premier message — une personne est détectée, pas encore dans une zone
    raw := `{
        "type": "new",
        "before": {},
        "after": {
            "id": "1718987129.308396-fqk5ka",
            "camera": "front_cam",
            "start_time": 1718987129.308396,
            "end_time": null,
            "severity": "detection",
            "thumb_path": "/media/frigate/clips/review/thumb-front_cam-1718987129.308396-fqk5ka.webp",
            "data": {
                "detections": ["1718987128.947436-g92ztx"],
                "objects": ["person"],
                "sub_labels": [],
                "zones": [],
                "audio": []
            }
        }
    }`

    var payload domain.FrigatePayload
    err := json.Unmarshal([]byte(raw), &payload)

    if err != nil {
        t.Fatalf("erreur de parsing: %v", err)
    }
    if payload.Type != "new" {
        t.Errorf("type attendu 'new', reçu '%s'", payload.Type)
    }

    after := payload.After
    if after.ID != "1718987129.308396-fqk5ka" {
        t.Errorf("ID attendu '1718987129.308396-fqk5ka', reçu '%s'", after.ID)
    }
    if after.Camera != "front_cam" {
        t.Errorf("camera attendue 'front_cam', reçue '%s'", after.Camera)
    }
    if after.Severity != "detection" {
        t.Errorf("severity attendue 'detection', reçue '%s'", after.Severity)
    }
    if after.StartTime != 1718987129.308396 {
        t.Errorf("start_time attendu 1718987129.308396, reçu %f", after.StartTime)
    }
    if after.EndTime != nil {
        t.Errorf("end_time attendu nil, reçu %v", after.EndTime)
    }
    if after.ThumbPath != "/media/frigate/clips/review/thumb-front_cam-1718987129.308396-fqk5ka.webp" {
        t.Errorf("thumb_path inattendu: %s", after.ThumbPath)
    }
    if len(after.Data.Objects) != 1 || after.Data.Objects[0] != "person" {
        t.Errorf("objects attendus [person], reçus %v", after.Data.Objects)
    }
    if len(after.Data.Zones) != 0 {
        t.Errorf("zones attendues vides, reçues %v", after.Data.Zones)
    }
    if len(after.Data.SubLabels) != 0 {
        t.Errorf("sub_labels attendus vides, reçus %v", after.Data.SubLabels)
    }
    if len(after.Data.Audio) != 0 {
        t.Errorf("audio attendu vide, reçu %v", after.Data.Audio)
    }
}

func TestParseFrigatePayload_UpdateEvent(t *testing.T) {
    // GIVEN : la personne entre dans une zone, une voiture apparaît,
    //         severity monte à "alert", un sub_label est identifié
    //         before = état du "new.after" précédent
    raw := `{
        "type": "update",
        "before": {
            "id": "1718987129.308396-fqk5ka",
            "camera": "front_cam",
            "start_time": 1718987129.308396,
            "end_time": null,
            "severity": "detection",
            "thumb_path": "/media/frigate/clips/review/thumb-front_cam-1718987129.308396-fqk5ka.webp",
            "data": {
                "detections": ["1718987128.947436-g92ztx"],
                "objects": ["person"],
                "sub_labels": [],
                "zones": [],
                "audio": []
            }
        },
        "after": {
            "id": "1718987129.308396-fqk5ka",
            "camera": "front_cam",
            "start_time": 1718987129.308396,
            "end_time": null,
            "severity": "alert",
            "thumb_path": "/media/frigate/clips/review/thumb-front_cam-1718987129.308396-fqk5ka.webp",
            "data": {
                "detections": [
                    "1718987128.947436-g92ztx",
                    "1718987148.879516-d7oq7r",
                    "1718987126.934663-q5ywpt"
                ],
                "objects": ["person", "car"],
                "sub_labels": ["Bob"],
                "zones": ["front_yard"],
                "audio": []
            }
        }
    }`

    var payload domain.FrigatePayload
    err := json.Unmarshal([]byte(raw), &payload)

    if err != nil {
        t.Fatalf("erreur de parsing: %v", err)
    }
    if payload.Type != "update" {
        t.Errorf("type attendu 'update', reçu '%s'", payload.Type)
    }

    // Before = exactement l'état du new.after
    if payload.Before.Severity != "detection" {
        t.Errorf("before.severity attendue 'detection', reçue '%s'", payload.Before.Severity)
    }
    if len(payload.Before.Data.Objects) != 1 {
        t.Errorf("before.objects attendu 1, reçu %d", len(payload.Before.Data.Objects))
    }
    if len(payload.Before.Data.Zones) != 0 {
        t.Errorf("before.zones attendues vides, reçues %v", payload.Before.Data.Zones)
    }
    if len(payload.Before.Data.SubLabels) != 0 {
        t.Errorf("before.sub_labels attendus vides, reçus %v", payload.Before.Data.SubLabels)
    }

    // After = état enrichi
    if payload.After.Severity != "alert" {
        t.Errorf("after.severity attendue 'alert', reçue '%s'", payload.After.Severity)
    }
    if len(payload.After.Data.Objects) != 2 {
        t.Errorf("after.objects attendus 2, reçus %d", len(payload.After.Data.Objects))
    }
    if len(payload.After.Data.Zones) != 1 || payload.After.Data.Zones[0] != "front_yard" {
        t.Errorf("after.zones attendues [front_yard], reçues %v", payload.After.Data.Zones)
    }
    if len(payload.After.Data.SubLabels) != 1 || payload.After.Data.SubLabels[0] != "Bob" {
        t.Errorf("after.sub_labels attendus [Bob], reçus %v", payload.After.Data.SubLabels)
    }
}

func TestParseFrigatePayload_EndEvent(t *testing.T) {
    // GIVEN : l'événement se termine — before = update.after, after = pareil + end_time
    raw := `{
        "type": "end",
        "before": {
            "id": "1718987129.308396-fqk5ka",
            "camera": "front_cam",
            "start_time": 1718987129.308396,
            "end_time": null,
            "severity": "alert",
            "thumb_path": "/media/frigate/clips/review/thumb-front_cam-1718987129.308396-fqk5ka.webp",
            "data": {
                "detections": [
                    "1718987128.947436-g92ztx",
                    "1718987148.879516-d7oq7r",
                    "1718987126.934663-q5ywpt"
                ],
                "objects": ["person", "car"],
                "sub_labels": ["Bob"],
                "zones": ["front_yard"],
                "audio": []
            }
        },
        "after": {
            "id": "1718987129.308396-fqk5ka",
            "camera": "front_cam",
            "start_time": 1718987129.308396,
            "end_time": 1718987189.456,
            "severity": "alert",
            "thumb_path": "/media/frigate/clips/review/thumb-front_cam-1718987129.308396-fqk5ka.webp",
            "data": {
                "detections": [
                    "1718987128.947436-g92ztx",
                    "1718987148.879516-d7oq7r",
                    "1718987126.934663-q5ywpt"
                ],
                "objects": ["person", "car"],
                "sub_labels": ["Bob"],
                "zones": ["front_yard"],
                "audio": []
            }
        }
    }`

    var payload domain.FrigatePayload
    err := json.Unmarshal([]byte(raw), &payload)

    if err != nil {
        t.Fatalf("erreur de parsing: %v", err)
    }
    if payload.Type != "end" {
        t.Errorf("type attendu 'end', reçu '%s'", payload.Type)
    }
    // Before: end_time encore nil
    if payload.Before.EndTime != nil {
        t.Errorf("before.end_time attendu nil, reçu %v", payload.Before.EndTime)
    }
    // After: end_time rempli, le reste identique au before
    if payload.After.EndTime == nil {
        t.Fatal("after.end_time attendu non-nil, reçu nil")
    }
    if *payload.After.EndTime != 1718987189.456 {
        t.Errorf("after.end_time attendu 1718987189.456, reçu %f", *payload.After.EndTime)
    }
    // Les objets n'ont pas disparu
    if len(payload.After.Data.Objects) != 2 {
        t.Errorf("after.objects attendus 2, reçus %d", len(payload.After.Data.Objects))
    }
}
