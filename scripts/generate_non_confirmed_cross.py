import json
import os
import random
from pathlib import Path

# --- Configuration et Listes de Données ---

PROFESSIONS_HAUT_REVENU = [
    "Entrepreneur", "Ingénieur", "Médecin", "Avocat", "Directeur", "Architecte", "Consultant Senior"
]

PROFESSIONS_BAS_REVENU = [
    "Étudiant", "Employé", "Ouvrier", "Technicien", "Chômeur", "Sans emploi", "Caissier"
]

SECTEURS = ["Finance", "Santé", "Technologie", "Commerce", "Industrie", "Construction", "Éducation"]
ORIGINES_FONDS = ["Épargne personnelle", "Salaire", "Héritage", "Dividendes", "Vente immobilière", "Inconnue", "Cash"]

NOMS = ["Smith", "Dupont", "Ben Ali", "Muller", "Rossi", "Garcia", "Brown", "Johnson", "Traore", "Martinez"]

def generer_tin_aleatoire():
    return f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}"

def generer_date_naissance():
    annee = random.randint(1960, 2000)
    mois = f"{random.randint(1, 12):02d}"
    jour = f"{random.randint(1, 28):02d}"
    return f"{annee}-{mois}-{jour}"


def generer_cas_non_conforme_cross(type_incoherence: str):
    """
    Génère un profil contenant expressément au moins UNE incohérence CROSS-CHECK.
    
    Types d'incohérences (Scénarios de l'Agent de Contrôle) :
    1. FATCA_HUNT : Né aux US mais a coché 'us_person' = False et n'a pas de TIN
    2. RESIDENCE_INCOHERENTE : Pays (Facture/CRS) différent de la Nationalité / Lieu de naissance sans justification (Passeport étranger)
    3. KYC_INCOHERENT : Profession à faible revenu (ex: Sans emploi, Ouvrier) mais déclare +100k
    4. MULTI_ANOMALIE : Cumule plusieurs des anomalies ci-dessus.
    """
    
    # 1. Base (identite_doc) normal
    nom = random.choice(NOMS)
    date_naissance = generer_date_naissance()
    type_doc = random.choice(["CNI", "Passeport"])
    
    lieu_naissance = "Paris"
    pays = "France"
    nationalite = "Française"
    
    # 2. Base (fiscalite)
    statut_us = False
    tin = ""
    indices_us = {"naissance_us": False, "virement_vers_us": False}
    
    # 3. Base KYC
    profession = random.choice(PROFESSIONS_HAUT_REVENU)
    revenu = random.choice(["40k-60k", "60k-80k"]) + " TND"
    
    # --- APPLICATION DU SCENARIO D'INCOHERENCE ---
    
    if type_incoherence in ["FATCA_HUNT", "MULTI_ANOMALIE"]:
        # Le suspect est né aux USA mais cache son statut FATCA
        lieu_naissance = random.choice(["Los Angeles", "New York", "Chicago", "Boston"])
        nationalite = random.choice(["Américaine", "Tunisienne"]) # Parfois un mix
        statut_us = False # MENSONGE : Il déclare ne pas être Américain
        tin = ""          # MENSONGE : Ne donne pas son TIN
        indices_us["naissance_us"] = True # CNI a cramé qu'il est né aux US
    
    if type_incoherence in ["RESIDENCE_INCOHERENTE", "MULTI_ANOMALIE"]:
        # Le client fourni un doc d'un pays mais vit dans un autre (Cas typique CRS suspect)
        type_doc = "Passeport"
        nationalite = random.choice(["Allemande", "Britannique", "Espagnole"])
        lieu_naissance = "Berlin" if nationalite == "Allemande" else "Londres"
        # Mais l'adresse / pays dans le dossier bancaire indique la Tunisie
        pays = "Tunisie" 

    if type_incoherence in ["KYC_INCOHERENT", "MULTI_ANOMALIE"]:
        # Incohérence AML (Anti-Money Laundering)
        # Il a un job précaire/aucun job MAIS rentre des sommes colossales (cash/crypto/inconnue)
        profession = random.choice(PROFESSIONS_BAS_REVENU) # Ex: "Sans emploi", "Ouvrier"
        revenu = random.choice(["> 100k", "> 150k", "100k-150k"]) + " TND"
        origine_fonds = random.choice(["Espèces", "Virements étrangers", "Inconnue"])

    # Assemblage du JSON final
    fiscalite_form = {
        "type_formulaire": "FATCA_INDIVIDUAL",
        "statut_us_person": statut_us,
        "numero_tin": tin,
        "est_signe": True,
        "indices_americanite": indices_us
    }

    profil_kyc = {
        "profession": profession,
        "tranche_revenu_annuel": revenu,
        "origine_fonds": origine_fonds if type_incoherence in ["KYC_INCOHERENT", "MULTI_ANOMALIE"] else random.choice(ORIGINES_FONDS),
        "ppe_statut": False,
        "secteur_activite": random.choice(SECTEURS)
    }

    payload = {
        "identite_doc": {
            "type_document": type_doc,
            "lieu_naissance": lieu_naissance,
            "nationalite": nationalite,
            "date_naissance": date_naissance,
            "nom": nom,
            "pays": pays
        },
        "fiscalite_form": fiscalite_form,
        "profil_kyc": profil_kyc,
        "_meta_truth": f"Incohérence insérée: {type_incoherence}" # Juste pour nous aider à vérifier que le LLM a trouvé la bonne anomalie
    }

    return payload


def main():
    output_dir = Path("c:/Bureau/kyc-ai-pipeline/data/client_data/non_confirmed")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Génération de 20 fichiers JSON NON-CONFIRMES (Cross Check) dans {output_dir}...")
    
    scenarios = [
        "FATCA_HUNT", "FATCA_HUNT", "FATCA_HUNT", "FATCA_HUNT", "FATCA_HUNT",
        "KYC_INCOHERENT", "KYC_INCOHERENT", "KYC_INCOHERENT", "KYC_INCOHERENT", "KYC_INCOHERENT",
        "RESIDENCE_INCOHERENTE", "RESIDENCE_INCOHERENTE", "RESIDENCE_INCOHERENTE", "RESIDENCE_INCOHERENTE", "RESIDENCE_INCOHERENTE",
        "MULTI_ANOMALIE", "MULTI_ANOMALIE", "MULTI_ANOMALIE", "MULTI_ANOMALIE", "MULTI_ANOMALIE"
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        cas = generer_cas_non_conforme_cross(scenario)
        
        # Format "file01", "file02" ... "file010", "file020" demandé
        # J'utilise le format demandé file0X et file0XX pour garder la cohérence de ta consigne
        if i < 10:
            filename_str = f"file0{i}.json"
        else:
            filename_str = f"file0{i}.json"
            
        filename = output_dir / filename_str
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(cas, f, indent=2, ensure_ascii=False)
            
    print(f"Génération terminée ! 20 fichiers créés dans: {output_dir}")


if __name__ == "__main__":
    main()
