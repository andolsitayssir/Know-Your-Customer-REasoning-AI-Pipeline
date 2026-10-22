from __future__ import annotations

from typing import Any, Dict, List

from .schemas import AgentResponse


def _parse_bool(val: Any) -> bool:
    if isinstance(val, str):
        return val.lower() in ["true", "oui", "yes", "1"]
    return bool(val)

def evaluate_rules(payload: Dict[str, Any]) -> AgentResponse:
    violations: List[str] = []

    # Determine form type
    is_fatca = "statut_us_person" in payload or "numero_tin" in payload
    is_kyc = "profession" in payload or "ppe_statut" in payload

    if is_fatca:
        statut_us = _parse_bool(payload.get("statut_us_person"))
        tin = (payload.get("numero_tin") or "").strip()
        est_signe = _parse_bool(payload.get("est_signe"))

        if statut_us and not tin:
            violations.append("FATCA_TIN_REQUIRED")
        if not statut_us and tin:
            violations.append("FATCA_TIN_INCOHERENT")
        if not est_signe:
            violations.append("FATCA_SIGNATURE_REQUIRED")

    if is_kyc:
        profession = (payload.get("profession") or "").lower()
        tranche_revenu = (payload.get("tranche_revenu_annuel") or "").lower()
        ppe_statut = _parse_bool(payload.get("ppe_statut"))
        ppe_form_present = _parse_bool(payload.get("ppe_formulaire_present"))

        revenu_haut = any(token in tranche_revenu for token in [">", "100", "150", "200"])
        professions_a_risque = ["etudiant", "student", "sans emploi", "chomeur", "ouvrier"]
        
        if any(p in profession for p in professions_a_risque) and revenu_haut:
            violations.append("KYC_PROFILE_INCOME_INCOHERENT")

        if ppe_statut and not ppe_form_present:
            violations.append("KYC_PPE_DOC_REQUIRED")

    is_conforme = len(violations) == 0
    explication = "Conforme" if is_conforme else "; ".join(violations)
    return AgentResponse(is_conforme=is_conforme, violations=violations, explication_courte=explication)
