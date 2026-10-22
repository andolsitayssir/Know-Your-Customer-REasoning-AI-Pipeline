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
JSON_PATH = "../data_test/_3/kyc_011_conf.json"
# ------------------------------

def run_agent3(json_path: str):
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

    print(f"\n--- Analyse Agent 3 ( {MODEL}) : {path.name} ---")
    
    # 1. Configuration du prompt (LangChain)
    try:
        from src.prompts import AGENT3_PROMPT_TEMPLATE
    except ImportError:
        from prompts import AGENT3_PROMPT_TEMPLATE
    prompt = ChatPromptTemplate.from_template(
        AGENT3_PROMPT_TEMPLATE
        + "\nTu es un moteur d'extraction de données. Tu dois extraire les informations au format JSON.\n"
        "NE REPONDS PAS AVEC DU CODE PYTHON. NE FAIS PAS DE COMMENTAIRES.\n"
        "REPONDS UNIQUEMENT AVEC LE JSON CI-DESSOUS :\n"
        "{{ \"is_conforme\": boolean, \"violations\": [\"code1\"], \"explication_courte\": \"...\" }}\n"
        "\nJSON a analyser:\n{payload}"
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

        # Normalisation identique au llm_client pour garantir les codes
        allowed_codes = {
            "FATCA_TIN_REQUIRED",
            "FATCA_TIN_INCOHERENT",
            "FATCA_SIGNATURE_REQUIRED",
            "KYC_PROFILE_INCOME_INCOHERENT",
            "KYC_PPE_DOC_REQUIRED",
        }

        violations_raw = res.get("violations", [])
        violations = [v for v in violations_raw if v in allowed_codes]
        
        is_conforme = res.get("is_conforme")
        if is_conforme is None:
            is_conforme = len(violations) == 0

        status = "VALIDE " if is_conforme else "NON CONFORME "
        
        print("-" * 50)
        print(f"DÉCISION : {status}")
        
        if violations:
            print(f"VIOLATIONS DÉTECTÉES :")
            for v in violations:
                print(f"  - {v}")
        
        print(f"EXPLICATION : {res.get('explication_courte', 'N/A')}")
        print(f"TEMPS D'EXÉCUTION : {duration:.2f}s")
        print("-" * 50)

    except Exception as e:
        print(f"ERREUR D'EXÉCUTION LANGCHAIN : {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent 3 : Analyse de conformité d'un document JSON")
    parser.add_argument("path", nargs="?", default=JSON_PATH, help="Chemin vers le fichier JSON à analyser")
    args = parser.parse_args()
    
    run_agent3(args.path)
