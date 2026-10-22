from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from dotenv import load_dotenv

from .prompts import AGENT3_PROMPT_TEMPLATE
from .schemas import AgentResponse


# Charge les variables d'environnement depuis un fichier .env (API Keys)
load_dotenv()


class _FoundryChatWrapper:
    """Client minimal pour GitHub Models via SDK azure-ai-inference (Foundry)."""

    def __init__(self, model: str, endpoint: str, token: str):
        from azure.ai.inference import ChatCompletionsClient
        from azure.core.credentials import AzureKeyCredential

        self.model = model
        self.endpoint = endpoint
        self.token = token
        self.client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(token),
        )

    def invoke(self, prompt_value: Any):
        try:
            from azure.ai.inference.models import SystemMessage as FSystemMessage
            from azure.ai.inference.models import UserMessage as FUserMessage
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"azure-ai-inference n'est pas installe: {exc}") from exc

        # Convertit les messages LangChain en messages Foundry
        if hasattr(prompt_value, "to_messages"):
            lc_messages = prompt_value.to_messages()
        else:
            # Fallback simple : tout en user
            lc_messages = [HumanMessage(content=str(prompt_value))]

        f_messages = []
        for msg in lc_messages:
            if isinstance(msg, SystemMessage):
                f_messages.append(FSystemMessage(content=msg.content))
            elif isinstance(msg, HumanMessage):
                f_messages.append(FUserMessage(content=msg.content))
            elif isinstance(msg, AIMessage):
                # On ignore les messages assistant precedents; Foundry complete est auto
                continue
            else:
                f_messages.append(FUserMessage(content=str(msg)))

        response = self.client.complete(
            messages=f_messages,
            model=self.model,
            temperature=0.6,
            top_p=0.95,
            top_k=20,
            presence_penalty=0.0,
            repetition_penalty=1.0,
            max_tokens=4096,
        )

        # Mimique l'interface LangChain: objet avec .content
        class _Resp:
            def __init__(self, content: str):
                self.content = content

        return _Resp(response.choices[0].message.content)


def _get_llm(model_name: str):
    """Factory pour basculer entre modèles locaux (Ollama) et Cloud APIs."""
    
    # 1. Hugging Face Cloud (via API compatible OpenAI)
    if model_name.startswith("hf:"):
        actual_model = model_name.replace("hf:", "")
        print(f"--- Utilisation de Hugging Face Cloud: {actual_model} ---")
        return ChatOpenAI(
            model=actual_model,
            openai_api_key=os.getenv("HF_ACESS_TOKEN"),
            openai_api_base="https://router.huggingface.co/v1/",
            temperature=0.01
        )

    # 2. Together / Perplexity / OpenAI / GitHub / OpenRouter (API compatibles OpenAI)
    elif ":" in model_name and model_name.split(":")[0] in ["together", "perplexity", "openai", "github", "openrouter"]:
        provider, actual_model = model_name.split(":", 1)
        print(f"--- Utilisation de {provider.capitalize()} Cloud: {actual_model} ---")
        
        # Mapping des endpoints
        api_bases = {
            "together": "https://api.together.xyz/v1",
            "perplexity": "https://api.perplexity.ai",
            "openai": "https://api.openai.com/v1",
            "github": "https://models.inference.ai.azure.com",
            "openrouter": "https://openrouter.ai/api/v1"
        }
        api_keys = {
            "together": "TOGETHER_API_KEY",
            "perplexity": "PERPLEXITY_API_KEY",
            "openai": "OPENAI_API_KEY",
            "github": "GITHUB_TOKEN",
            "openrouter": "OPEN_ROUTER_API_KEY"
        }
        
        api_key = os.getenv(api_keys[provider])
        if not api_key:
             print(f"ATTENTION: La variable d'environnement {api_keys[provider]} n'est pas definie.")

        kwargs = {
            "model": actual_model,
            "api_key": api_key, # Utilise api_key directement (compatibilité langchain-openai récente)
            "base_url": api_bases[provider], # base_url à la place de openai_api_base
            "temperature": 0.0
        }
        
        return ChatOpenAI(**kwargs)

    # 3. GitHub Models via Foundry SDK (azure-ai-inference)
    elif model_name.startswith("foundry:"):
        actual_model = model_name.replace("foundry:", "")
        endpoint = os.getenv("FOUNDRY_ENDPOINT", "https://models.github.ai/inference")
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("GITHUB_TOKEN manquant pour foundry:")
        print(f"--- Utilisation de GitHub Models (Foundry SDK): {actual_model} ---")
        return _FoundryChatWrapper(model=actual_model, endpoint=endpoint, token=token)

    # 4. Local via Ollama (Par défaut)
    else:
        print(f"--- Utilisation de Ollama Local: {model_name} ---")
        # On ne force pas stop sur les balises de réflexion pour éviter de couper le JSON
        return ChatOllama(
            model=model_name, 
            temperature=0.0, 
            format="json"
        )


def _extract_json_block(text: str) -> str:
    """Extrait le bloc JSON d'un texte bruité."""
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end != 0:
            return text[start:end]
    except Exception:
        pass
    return text


def evaluate_single_case(json_payload: Dict[str, Any], model_name: str) -> Dict[str, Any]:
    # Use JsonOutputParser instead of PydanticOutputParser for better robustness with small models
    parser = JsonOutputParser()
    
    prompt = ChatPromptTemplate.from_template(
        AGENT3_PROMPT_TEMPLATE
        + "\nTu es un moteur d'extraction de données. Tu dois extraire les informations au format JSON.\n"
        "NE REPONDS PAS AVEC DU CODE PYTHON. NE FAIS PAS DE COMMENTAIRES.\n"
        "REPONDS UNIQUEMENT AVEC LE JSON CI-DESSOUS :\n"
        "{{ \"is_conforme\": boolean, \"violations\": [\"code1\"], \"explication_courte\": \"...\" }}\n"
        "\nJSON a analyser:\n{payload}"
    )
    
    llm = _get_llm(model_name)
    
    # On évite le chainage direct si on veut gérer le nettoyage manuellement
    start_time = time.perf_counter()
    try:
        # 1. Génération
        prompt_value = prompt.format_prompt(payload=json.dumps(json_payload, ensure_ascii=False))
        response = llm.invoke(prompt_value)
        
        # 2. Nettoyage (Robustesse aux bavardages)
        raw_content = response.content if hasattr(response, "content") else str(response)
        cleaned_json = _extract_json_block(raw_content)
        
        # 3. Parsing
        raw_result = parser.parse(cleaned_json)

        # Normalisation defensive mais stricte (on ne garde que les codes attendus)
        allowed_codes = {
            "FATCA_TIN_REQUIRED",
            "FATCA_TIN_INCOHERENT",
            "FATCA_SIGNATURE_REQUIRED",
            "KYC_PROFILE_INCOME_INCOHERENT",
            "KYC_PPE_DOC_REQUIRED",
        }

        violations_raw = raw_result.get("violations", []) if isinstance(raw_result, dict) else []
        violations_norm = []
        for v in violations_raw:
            if isinstance(v, str) and v in allowed_codes:
                violations_norm.append(v)
            elif isinstance(v, dict):
                # on prend les cles (codes) uniquement si elles sont dans la whitelist
                for k in v.keys():
                    if k in allowed_codes:
                        violations_norm.append(k)
            # sinon on ignore pour ne pas introduire de faux positifs

        explication = raw_result.get("explication_courte") if isinstance(raw_result, dict) else None
        if not explication:
            explication = "Conforme" if not violations_norm else "; ".join(violations_norm)

        is_conforme = raw_result.get("is_conforme") if isinstance(raw_result, dict) else None
        if is_conforme is None:
            is_conforme = len(violations_norm) == 0

        normalized = {
            "is_conforme": is_conforme,
            "violations": violations_norm,
            "explication_courte": explication,
        }

        # Convert dict to AgentResponse object
        result = AgentResponse(**normalized)
        success = True
        error = None
    except Exception as exc:  # noqa: BLE001
        print(f"\n[DEBUG] Erreur avec {model_name}: {exc}.")
        result = None
        success = False # On marque comme echec LLM
        error = str(exc)
    end_time = time.perf_counter()

    return {
        "result": result,
        "time_seconds": end_time - start_time,
        "success": success,
        "error": error,
    }
