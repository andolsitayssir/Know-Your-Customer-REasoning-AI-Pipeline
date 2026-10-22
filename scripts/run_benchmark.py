from __future__ import annotations

import argparse
import csv
import json
import sys
import os
import platform
import hashlib
from pathlib import Path
from typing import Any, Dict, List

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.evaluator import classification_report, mean_time, p95_time
from src.llm_client import evaluate_single_case
from src.prompts import AGENT3_PROMPT_TEMPLATE, PROMPT_VERSION





def find_data_dir(script_path: Path) -> Path:
    root = script_path.parent.parent
    local = root / "data" / "json_cases"
    if local.exists():
        return local
    parent = root.parent / "data" / "json_cases"
    return parent


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def run(model: str) -> List[Dict[str, Any]]:
    script_path = Path(__file__).resolve()
    data_dir = find_data_dir(script_path)
    conforme_dir = data_dir / "confirmed"
    non_conforme_dir = data_dir / "non_confirmed"

    all_files = []
    for path in sorted(conforme_dir.glob("*.json")):
        all_files.append((path, True))
    for path in sorted(non_conforme_dir.glob("*.json")):
        all_files.append((path, False))

    if not all_files:
        print(f"Erreur: Aucun fichier JSON trouve dans {data_dir}")
        return []

    print(f"\n--- Debut du benchmark: modele={model} ---")
    print(f"Nombre de cas a evaluer: {len(all_files)}\n")

    rows: List[Dict[str, Any]] = []

    for i, (path, attendu_conforme) in enumerate(all_files, 1):
        print(f"[{i}/{len(all_files)}] {path.name}:", end=" ", flush=True)
        
        payload = load_json(path)
        outcome = evaluate_single_case(payload, model)
        
        if outcome["result"]:
            res = outcome["result"]
            pred = res.is_conforme
            viol = ",".join(res.violations)
            
            # Affichage detaille
            status_ia = "CONFIRMED" if pred else "NON CONFIRMED"
            verdict = "CORRECT" if pred == attendu_conforme else "FAUX"
            alerte = f" | Alertes: [{viol}]" if viol else ""
            
            # On ajoute un petit label si c'est le fallback qui a servi
            suffix = " (FALLBACK RULES)" if not outcome["success"] else ""
            print(f"IA:{status_ia} ({verdict}){alerte} | {outcome['time_seconds']:.2f}s{suffix}")
        else:
            pred = None
            viol = ""
            print(f"ERREUR (Parsing/LLM)")

        rows.append(
            {
                "fichier": str(path),
                "attendu_conforme": attendu_conforme,
                "predit_conforme": pred,
                "temps_reponse_sec": outcome.get("time_seconds"),
                "violations": viol,
                "succes_parsing": outcome.get("success", False),
            }
        )

    return rows


def _unique_output_path(model: str) -> Path:
    """Generate a unique CSV path per run to avoid overwriting previous benchmarks."""

    base_dir = Path(__file__).resolve().parent.parent / "results"
    base_dir.mkdir(parents=True, exist_ok=True)

    safe_model = model.replace(":", "_")
    base_name = f"benchmark_{safe_model}.csv"
    candidate = base_dir / base_name

    if not candidate.exists():
        return candidate

    # Incremental suffix when a file already exists
    counter = 2
    while True:
        candidate = base_dir / f"benchmark_{safe_model}_v{counter}.csv"
        if not candidate.exists():
            return candidate
        counter += 1


def _log_to_mlflow(
    model: str,
    rows: List[Dict[str, Any]],
    report: Dict[str, float],
    avg_time: float,
    p95: float,
    output_path: Path,
) -> None:
    if os.environ.get("DISABLE_MLFLOW", "").lower() in {"1", "true", "yes"}:
        return

    try:
        import mlflow
    except ImportError:
        print("MLflow non installe. Ajoutez mlflow a l'environnement pour activer le tracking.")
        return

    experiment_name = os.environ.get("MLFLOW_EXPERIMENT", "kyc-ai-benchmark")
    mlflow.set_experiment(experiment_name)

    parse_success = sum(1 for r in rows if r.get("succes_parsing"))
    prompt_hash = hashlib.sha256(AGENT3_PROMPT_TEMPLATE.encode("utf-8")).hexdigest()[:12]

    # Ajoute le hash du prompt dans le nom du run pour distinguer chaque changement de prompt
    run_label = f"{model}-prompt-{PROMPT_VERSION}-{prompt_hash}"

    with mlflow.start_run(run_name=run_label):
        mlflow.log_params(
            {
                "model": model,
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cases_total": len(rows),
                "dataset": output_path.name.replace("benchmark_", "").replace(".csv", ""),
                "prompt_version": PROMPT_VERSION,
                "prompt_hash": prompt_hash,
            }
        )

        mlflow.log_text(AGENT3_PROMPT_TEMPLATE, "prompt_template.txt")

        mlflow.log_metrics(
            {
                "accuracy": report.get("accuracy", 0.0),
                "precision_non_conforme": report.get("precision_non_conforme", 0.0),
                "recall_non_conforme": report.get("recall_non_conforme", 0.0),
                "f1_non_conforme": report.get("f1_non_conforme", 0.0),
                "precision_conforme": report.get("precision_conforme", 0.0),
                "recall_conforme": report.get("recall_conforme", 0.0),
                "f1_conforme": report.get("f1_conforme", 0.0),
                "tp": report.get("tp", 0),
                "fp": report.get("fp", 0),
                "tn": report.get("tn", 0),
                "fn": report.get("fn", 0),
                "parse_success_rate": parse_success / len(rows) if rows else 0.0,
                "mean_time_s": avg_time,
                "p95_time_s": p95,
            }
        )

        for idx, row in enumerate(rows):
            if row.get("temps_reponse_sec") is not None:
                mlflow.log_metric("response_time_s", row["temps_reponse_sec"], step=idx)

        if output_path.exists():
            mlflow.log_artifact(str(output_path), artifact_path="results")


def write_csv(rows: List[Dict[str, Any]], output_path: Path, report: Dict[str, float], avg_time: float, p95: float) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "fichier",
        "attendu_conforme",
        "predit_conforme",
        "temps_reponse_sec",
        "violations",
        "succes_parsing",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            
        # Ajouter des lignes vides pour separer les donnees des metriques
        f.write("\n\n")
        
        # Ajouter les metriques globales a la fin du CSV
        writer = csv.writer(f)
        writer.writerow(["--- METRIQUES GLOBALES ---"])
        writer.writerow(["Accuracy", f"{report['accuracy']:.3f}"])
        writer.writerow(["Precision (non conf)", f"{report['precision_non_conforme']:.3f}"])
        writer.writerow(["Recall (non conf)", f"{report['recall_non_conforme']:.3f}"])
        writer.writerow(["F1 Score (non conf)", f"{report['f1_non_conforme']:.3f}"])
        writer.writerow(["Confiance Approbation (Precision conf)", f"{report.get('precision_conforme', 0.0):.3f}"])
        writer.writerow(["Temps moyen (s)", f"{avg_time:.3f}"])
        


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Agent 3/4 avec LLM")
    parser.add_argument("--model", required=True, help="Nom du modele Ollama / HF")
    args = parser.parse_args()

    

    rows = run(args.model)

    report = classification_report(rows)
    avg_time = mean_time(rows)
    p95 = p95_time(rows)

    output_path = _unique_output_path(args.model)
    write_csv(rows, output_path, report, avg_time, p95)

    _log_to_mlflow(args.model, rows, report, avg_time, p95, output_path)

    print(
        f"\nAccuracy: {report['accuracy']:.3f} | "
        f"Precision(non conf): {report['precision_non_conforme']:.3f} | "
        f"Recall(non conf): {report['recall_non_conforme']:.3f} | "
        f"F1(non conf): {report['f1_non_conforme']:.3f}"
    )
    print(f"CONFIANCE APPROBATION (Precision Conforme): {report.get('precision_conforme', 0.0):.3f}")
    print(f"Temps moyen (s): {avg_time:.3f} | p95 (s): {p95:.3f}")


if __name__ == "__main__":
    main()
