from __future__ import annotations

from typing import Iterable, Tuple


def _confusion_counts(rows: Iterable[dict]) -> Tuple[int, int, int, int, int]:
    """Retourne (tp, fp, tn, fn, total) en prenant "non conforme" comme positif."""

    tp = fp = tn = fn = total = 0
    for row in rows:
        expected_conforme = row.get("attendu_conforme")
        pred = row.get("predit_conforme")
        total += 1

        # Cas d'erreur (None): on considère que c'est une prédiction FAUSSE
        if pred is None:
            if expected_conforme is True:
                fp += 1  # L'IA aurait dû dire True, mais elle n'a rien dit (Rejet par défaut)
            else:
                fn += 1  # L'IA aurait dû dire False, mais elle n'a rien dit (On a raté le rejet)
            continue

        if pred is False and expected_conforme is False:
            tp += 1
        elif pred is False and expected_conforme is True:
            fp += 1
        elif pred is True and expected_conforme is True:
            tn += 1
        else:
            fn += 1
    return tp, fp, tn, fn, total


def classification_report(rows: Iterable[dict]) -> dict:
    """Calcule accuracy, precision, recall, f1 pour les DEUX classes."""

    tp, fp, tn, fn, total = _confusion_counts(rows)
    accuracy = (tp + tn) / total if total else 0.0

    # Classe Positive: Non-Conforme (REJET / INVESTIGATION)
    precision_non = tp / (tp + fp) if (tp + fp) else 0.0
    recall_non = tp / (tp + fn) if (tp + fn) else 0.0
    f1_non = 2 * precision_non * recall_non / (precision_non + recall_non) if (precision_non + recall_non) else 0.0

    # Classe Négative: Conforme (VALIDATION Automatique)
    # On calcule la confiance dans l'approbation (Precision de la classe Conforme)
    precision_conf = tn / (tn + fn) if (tn + fn) else 0.0
    recall_conf = tn / (tn + fp) if (tn + fp) else 0.0
    f1_conf = 2 * precision_conf * recall_conf / (precision_conf + recall_conf) if (precision_conf + recall_conf) else 0.0

    return {
        "accuracy": accuracy,
        "precision_non_conforme": precision_non,
        "recall_non_conforme": recall_non,
        "f1_non_conforme": f1_non,
        "precision_conforme": precision_conf,
        "recall_conforme": recall_conf,
        "f1_conforme": f1_conf,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "total": total,
    }


def mean_time(rows: Iterable[dict]) -> float:
    times = [r["temps_reponse_sec"] for r in rows if r.get("temps_reponse_sec") is not None]
    return sum(times) / len(times) if times else 0.0


def p95_time(rows: Iterable[dict]) -> float:
    times = sorted(
        r["temps_reponse_sec"] for r in rows if r.get("temps_reponse_sec") is not None
    )
    if not times:
        return 0.0
    idx = int(0.95 * (len(times) - 1))
    return times[idx]
