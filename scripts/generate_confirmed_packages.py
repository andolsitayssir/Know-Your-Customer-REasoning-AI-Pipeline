import json
import os
import random
from pathlib import Path

# --- Configuration et Listes de Données pour la diversité ---

# Profils FATCA (Américains confirmés) - Tout doit être cohérent pour être 'Confirmé'
PROFILES_FATCA = [
    {"ville": "Los Angeles", "pays": "États-Unis", "nationalite": "Américaine"},
    {"ville": "New York", "pays": "États-Unis", "nationalite": "Américaine"},
    {"ville": "Chicago", "pays": "États-Unis", "nationalite": "Américaine"},
    {"ville": "Miami", "pays": "États-Unis", "nationalite": "Américaine"},
    {"ville": "Houston", "pays": "États-Unis", "nationalite": "Américaine"},
]

# Profils CRS / Locaux (Non-Américains confirmés) - Tout doit être cohérent
PROFILES_NON_FATCA = [
    {"ville": "Paris", "pays": "France", "nationalite": "Française"},
    {"ville": "Tunis", "pays": "Tunisie", "nationalite": "Tunisienne"},
    {"ville": "Berlin", "pays": "France", "nationalite": "Allemande"},
    {"ville": "Londres", "pays": "Allemagne", "nationalite": "Britannique"},
    {"ville": "Madrid", "pays": "Allemagne", "nationalite": "Espagnole"},
    {"ville": "Rome", "pays": "Espagne", "nationalite": "Italienne"},
    {"ville": "Casablanca", "pays": "Algérie", "nationalite": "Marocaine"}, # Incoherent pays/nat, on fixera au runtime
    {"ville": "Dakar", "pays": "Algérie", "nationalite": "Algérienne"},
]

# Fix cohérence pays/nat pour les non-fatca
PROFILES_NON_FATCA = [
    {"ville": "Paris", "pays": "France", "nationalite": "Française"},
    {"ville": "Tunis", "pays": "Tunisie", "nationalite": "Tunisienne"},
    {"ville": "Berlin", "pays": "Allemagne", "nationalite": "Allemande"},
    {"ville": "Londres", "pays": "Royaume-Uni", "nationalite": "Britannique"},
    {"ville": "Madrid", "pays": "Espagne", "nationalite": "Espagnole"},
    {"ville": "Rome", "pays": "Italie", "nationalite": "Italienne"},
    {"ville": "Casablanca", "pays": "Maroc", "nationalite": "Marocaine"},
    {"ville": "Oran", "pays": "Algérie", "nationalite": "Algérienne"},
]


PROFESSIONS_HAUT_REVENU = [
    "Entrepreneur", "Ingénieur", "Médecin", "Avocat", "Directeur", "Architecte", "Consultant Senior"
]

PROFESSIONS_BAS_REVENU = [
    "Étudiant", "Employé", "Ouvrier", "Technicien", "Vendeur", "Sans emploi", "Caissier"
]

SECTEURS = ["Finance", "Santé", "Technologie", "Commerce", "Industrie", "Construction", "Éducation"]
ORIGINES_FONDS = ["Épargne personnelle", "Salaire", "Héritage", "Dividendes", "Vente immobilière"]

NOMS = ["Smith", "Dupont", "Ben Ali", "Muller", "Rossi", "Garcia", "Brown", "Johnson", "Traore", "Martinez"]


def generer_tin_aleatoire():
    return f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}"

def generer_date_naissance():
    annee = random.randint(1960, 2000)
    mois = f"{random.randint(1, 12):02d}"
    jour = f"{random.randint(1, 28):02d}"
    return f"{annee}-{mois}-{jour}"


def generer_cas_conforme(is_fatca: bool):
    """Génère un profil 100% cohérent (Confirmé)"""
    
    # 1. Identité document
    nom = random.choice(NOMS)
    date_naissance = generer_date_naissance()
    type_doc = random.choice(["CNI", "Passeport"])
    
    if is_fatca:
        loc = random.choice(PROFILES_FATCA)
        statut_us = True
        tin = generer_tin_aleatoire()
        indices_us = {"naissance_us": True, "virement_vers_us": random.choice([True, False])}
    else:
        loc = random.choice(PROFILES_NON_FATCA)
        statut_us = False
        tin = ""  # Doit être vide si pas US
        indices_us = {"naissance_us": False, "virement_vers_us": False}

    # 2. Fiscalite Form
    fiscalite_form = {
        "type_formulaire": "FATCA_INDIVIDUAL", # Ou CRS_INDIVIDUAL, on garde FATCA ici pour simplifier comme dans ton exemple
        "statut_us_person": statut_us,
        "numero_tin": tin,
        "est_signe": True,
        "indices_americanite": indices_us
    }

    # 3. Profil KYC (Cohérent)
    # Pour être conforme: Haut salaire -> Métier adapté, Bas métier -> Bas salaire
    is_high_income = random.choice([True, False])
    
    if is_high_income:
        profession = random.choice(PROFESSIONS_HAUT_REVENU)
        revenu = random.choice(["80k-100k", "100k-150k", "> 150k"]) + " TND"
    else:
        profession = random.choice(PROFESSIONS_BAS_REVENU)
        revenu = random.choice(["< 30k", "30k-50k", "50k-80k"]) + " TND"
        
    profil_kyc = {
        "profession": profession,
        "tranche_revenu_annuel": revenu,
        "origine_fonds": random.choice(ORIGINES_FONDS),
        "ppe_statut": False, # On force false pour éviter d'avoir à gérer 'ppe_formulaire_present' dans cet exercice simple
        "secteur_activite": random.choice(SECTEURS)
    }

    payload = {
        "identite_doc": {
            "type_document": type_doc,
            "lieu_naissance": loc["ville"],
            "nationalite": loc["nationalite"],
            "date_naissance": date_naissance,
            "nom": nom,
            "pays": loc["pays"]
        },
        "fiscalite_form": fiscalite_form,
        "profil_kyc": profil_kyc
    }

    return payload


def main():
    # Définir le dossier de sortie
    output_dir = Path("c:/Bureau/kyc-ai-pipeline/data/client_data/confirmed")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Génération de 20 fichiers JSON dans {output_dir}...")
    
    for i in range(1, 21):
        # On va créer une mixité (par ex: 7 US / 13 Non-US)
        is_fatca = i <= 7 
        
        cas = generer_cas_conforme(is_fatca)
        
        filename = output_dir / f"dossier_confirme_{i:03d}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(cas, f, indent=2, ensure_ascii=False)
            
    print(f"Génération terminée ! 20 fichiers créés dans: {output_dir}")

if __name__ == "__main__":
    main()
