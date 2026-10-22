import json
import os
import time
import argparse
import csv
import hashlib
import platform
from pathlib import Path
from typing import List, Dict, Any

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.prompts import AGENT4_CROSSCHECK_PROMPT, AGENT4_VERSION
from src.evaluator import classification_report, mean_time, p95_time
from src.llm_client import _get_llm

def evaluate_cross_check(payload: Dict[str, Any], model_name: str):
    parser = JsonOutputParser()
    
    prompt = ChatPromptTemplate.from_template(
        AGENT4_CROSSCHECK_PROMPT + "\n\nJSON A ANALYSER :\n{payload}"
    )
    
    # Configuration LLM (Gestion automatique Ollama / Cloud via llm_client)
    llm = _get_llm(model_name)

    start_time = time.perf_counter()
    try:
        # Si c'est un wrapper custom (Foundry), on ne peut pas utiliser le pipe LangChain |
        if hasattr(llm, "invoke") and not hasattr(llm, "bind"): # Detection simplifie wrapper custom
            prompt_value = prompt.format_prompt(payload=json.dumps(payload, ensure_ascii=False))
            response = llm.invoke(prompt_value)
        else:
            # Mode standard LangChain
            chain = prompt | llm
            response = chain.invoke({"payload": json.dumps(payload, ensure_ascii=False)})
        
        # Extraction du texte
        if hasattr(response, "content"):
            raw_text = response.content
        else:
            raw_text = str(response)

        # Extraction JSON robuste
        from src.llm_client import _extract_json_block
        json_text = _extract_json_block(raw_text)
        result = parser.parse(json_text)
        success = True
    except Exception as e:
        print(f"Erreur benchmark Agent 4 : {e}")
        result = {"decision_finale": "ERREUR", "matrice_confiance": {}, "raison_investigation": str(e)}
        success = False
    
    end_time = time.perf_counter()
    return result, end_time - start_time, success

def _log_to_mlflow_agent4(
    model: str,
    rows: List[Dict[str, Any]],
    report: Dict[str, float],
    avg_time: float,
    p95: float,
    output_path: Path,
) -> None:
    try:
        import mlflow
    except ImportError:
        return

    experiment_name = os.environ.get("MLFLOW_EXPERIMENT", "kyc-agent4-crosscheck")
    mlflow.set_experiment(experiment_name)

    prompt_hash = hashlib.sha256(AGENT4_CROSSCHECK_PROMPT.encode("utf-8")).hexdigest()[:12]
    run_label = f"agent4-{model}-{AGENT4_VERSION}-{prompt_hash}"

    with mlflow.start_run(run_name=run_label):
        mlflow.log_params({
            "model": model,
            "cases_total": len(rows),
            "prompt_version": AGENT4_VERSION,
            "prompt_hash": prompt_hash,
        })
        mlflow.log_metrics({
            "accuracy": report.get("accuracy", 0.0),
            "precision_non_conforme": report.get("precision_non_conforme", 0.0),
            "recall_non_conforme": report.get("recall_non_conforme", 0.0),
            "f1_non_conforme": report.get("f1_non_conforme", 0.0),
            "mean_time_s": avg_time,
            "p95_time_s": p95,
        })
        mlflow.log_text(AGENT4_CROSSCHECK_PROMPT, "agent4_prompt.txt")
        if output_path.exists():
            mlflow.log_artifact(str(output_path))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    data_dir = Path("data/client_data")
    results_dir = Path("results/agent4")
    results_dir.mkdir(parents=True, exist_ok=True)
    
    all_files = []
    # Dossiers confirmés (VALIDE attendu)
    if (data_dir / "confirmed").exists():
        for p in sorted((data_dir / "confirmed").glob("*.json")):
            all_files.append((p, "VALIDE"))
    
    # Dossiers non confirmés (NON-VALIDE attendu)
    if (data_dir / "non_confirmed").exists():
        for p in sorted((data_dir / "non_confirmed").glob("*.json")):
            all_files.append((p, "NON_VALIDE"))

    if not all_files:
        print(f"Erreur: Aucun fichier JSON trouvé dans {data_dir}")
        return

    rows = []
    bench_metrics_rows = []

    print(f"\n--- Lancement Benchmark Agent 4 (Cross-Check) - Modele: {args.model} ---")
    
    for i, (path, expected_label) in enumerate(all_files):
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        
        print(f"\n {i+1}/{len(all_files)}: {path.name}:")
        res, duration, success = evaluate_cross_check(payload, args.model)
        
        prediction = res.get("decision_finale")
        is_correct = False
        if expected_label == "VALIDE" and prediction == "VALIDE":
            is_correct = True
        elif expected_label == "NON_VALIDE" and prediction in ["REJET", "INVESTIGATION_REQUISE"]:
            is_correct = True
            
        status = "CORRECT" if is_correct else "FAUX"
        
        # On affiche la raison seulement si ce n'est pas VALIDE ou si l'IA s'est trompée
        raison = res.get("raison_investigation", "")
        print(f"-> {prediction} ({status}) | {duration:.2f}s")
        if prediction != "VALIDE":
             print(f"-->Raison: {raison}")

        rows.append({
            "fichier": path.name,
            "attendu": expected_label,
            "predit": prediction,
            "correct": is_correct,
            "raison": raison,
            "temps": duration
        })
        
        bench_metrics_rows.append({
            "predit_conforme": True if prediction == "VALIDE" else False,
            "attendu_conforme": True if expected_label == "VALIDE" else False,
            "temps_reponse_sec": duration
        })

    # Calcul des métriques globales
    report = classification_report(bench_metrics_rows)
    avg_time = mean_time(bench_metrics_rows)
    p95 = p95_time(bench_metrics_rows)

    # Sauvegarde CSV avec métriques à la fin
    safe_model_name = args.model.replace(":", "_").replace("/", "_").replace("\\", "_")
    output_csv = results_dir / f"benchmark_agent4_{safe_model_name}.csv"
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["fichier", "attendu", "predit", "correct", "raison", "temps"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        
        f.write("\n\n--- METRIQUES GLOBALES ---\n")
        f.write(f"Accuracy,{report['accuracy']:.3f}\n")
        f.write(f"Precision (REJET/INV),{report.get('precision_non_conforme', 0.0):.3f}\n")
        f.write(f"Recall (REJET/INV),{report.get('recall_non_conforme', 0.0):.3f}\n")
        f.write(f"F1 Score (REJET/INV),{report.get('f1_non_conforme', 0.0):.3f}\n")
        f.write(f"Confiance Approbation Automatic (Precision Conforme),{report.get('precision_conforme', 0.0):.3f}\n")
        f.write(f"Recall Conforme,{report.get('recall_conforme', 0.0):.3f}\n")
        f.write(f"Temps moyen (s),{avg_time:.3f}\n")
        f.write(f"Temps p95 (s),{p95:.3f}\n")

    # Tracking MLflow
    _log_to_mlflow_agent4(args.model, rows, report, avg_time, p95, output_csv)

    print(f"\nAccuracy: {report['accuracy']:.3f} | F1 (Non-Conf): {report.get('f1_non_conforme', 0.0):.3f}")
    print(f"CONFIANCE APPROBATION (Precision Conforme): {report.get('precision_conforme', 0.0):.3f}")
    print(f"Temps moyen: {avg_time:.3f}s | p95: {p95:.3f}s")

if __name__ == "__main__":
    main()
