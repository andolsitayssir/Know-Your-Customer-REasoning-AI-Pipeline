import json
import argparse
from pathlib import Path
import sys

# On définit le ROOT du projet (kyc-ai-pipeline)
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# Modèle gagnant identifié lors du benchmark
MODEL = "qwen3:1.7b"

# --- CONFIGURATION MANUELLE ---
# Vous pouvez renseigner le chemin du fichier ici pour l'exécuter directement
JSON_PATH = "../data_test/_4/file013.json"
# ------------------------------

def run_agent4(json_path: str):
    path = Path(json_path)
    # Si le chemin relatif directe échoue, on tente depuis le ROOT
    if not path.exists():
        path = ROOT_DIR / json_path

    if not path.exists():
        print(f"Erreur : Le fichier {json_path} n'existe pas.")
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        print(f"Erreur de lecture du JSON : {e}")
        return

    print(f"\n--- Analyse Agent 4 (Cross-Verification / {MODEL}) : {path.name} ---")
    
    # 1. Configuration du prompt (LangChain)
    try:
        from src.prompts import AGENT4_CROSSCHECK_PROMPT
    except ImportError:
        from prompts import AGENT4_CROSSCHECK_PROMPT
    prompt = ChatPromptTemplate.from_template(
        AGENT4_CROSSCHECK_PROMPT + "\n\nJSON A ANALYSER :\n{payload}"
    )
    
    # 2. Configuration du LLM (LangChain)
    llm = ChatOllama(model=MODEL, temperature=0.0, format="json")
    
    # 3. Parser (LangChain)
    parser = JsonOutputParser()
    
    # 4. Construction de la Chaîne (LCEL)
    chain = prompt | llm | parser

    import time
    start_time = time.perf_counter()
    
    try:
        # Exécution de la chaîne
        res = chain.invoke({"payload": json.dumps(payload, ensure_ascii=False)})
        duration = time.perf_counter() - start_time
        
        # Affichage structuré des résultats
        decision = res.get("decision_finale", "ERREUR")
        print("-" * 50)
        print(f"DÉCISION GLOBALE : {decision}")
        
        raison = res.get("raison_investigation", "Aucune raison spécifiée")
        print(f"RAISONNEMENT : {raison}")
        
        matrice = res.get("matrice_confiance", {})
        if matrice:
            print(f"MATRICE CONFIANCE :")
            for k, v in matrice.items():
                print(f"  - {k} : {v}")
        
        print(f"TEMPS D'EXÉCUTION : {duration:.2f}s")
        print("-" * 50)

    except Exception as e:
        print(f"ERREUR D'EXÉCUTION LANGCHAIN : {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent 4 : Validation croisée des données client")
    parser.add_argument("path", nargs="?", default=JSON_PATH, help="Chemin vers le fichier JSON combiné à analyser")
    args = parser.parse_args()
    
    run_agent4(args.path)
