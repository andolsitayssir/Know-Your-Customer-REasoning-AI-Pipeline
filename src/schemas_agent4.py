from pydantic import BaseModel, Field
from typing import Optional

class MatriceConfiance(BaseModel):
    identite_vs_fatca: str = Field(description="'OK' ou 'SUSPECT'")
    profil_vs_revenus: str = Field(description="'OK' ou 'SUSPECT'")

class CrossCheckResponse(BaseModel):
    decision_finale: str = Field(description="'VALIDE', 'INVESTIGATION_REQUISE', 'REJET'")
    matrice_confiance: MatriceConfiance
    raison_investigation: Optional[str] = Field(None, description="Explication courte de l'anomalie détectée")
