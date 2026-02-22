# MDIR — Index des Fichiers

## Documentation Architecture

| Fichier | Description | Statut |
|---------|-------------|--------|
| `TRUE_ARCHITECTURE.md` | **Vision originale** de l'utilisateur — ce que MDIR doit être | ✅ Référence |
| `NOVELTY_ANALYSIS.md` | Ce qui est nouveau vs existant dans MDIR | ✅ Référence |
| `IMPLEMENTATION_CHALLENGES.md` | Les vrais problèmes durs à résoudre | ✅ Référence |
| `ARCHITECTURE.md` | Description de l'implémentation v1 (assemblage de composants existants) | ⚠️ Décrit v1, pas la vision |

## Code

| Fichier | Description | Statut |
|---------|-------------|--------|
| `mdir_model.py` | Implémentation v1 — assemblage de transformers standards | ⚠️ Ne correspond PAS à la vision |
| `mdir_train.py` | Script d'entraînement Colab | ⚠️ Fonctionne mais entraîne v1 |
| `MDIR_Training_Colab.ipynb` | Notebook Colab | ⚠️ Contient des bugs non corrigés |

## Logs

| Fichier | Description |
|---------|-------------|
| `IMPLEMENTATION_LOG.md` | Log de l'implémentation v1 |

## Conversations Futures

Ce dossier est conçu pour évoluer à travers plusieurs conversations :

1. **Discussion de l'architecture** — `TRUE_ARCHITECTURE.md` est la référence
2. **Résolution des défis** — `IMPLEMENTATION_CHALLENGES.md` sera mis à jour avec les solutions trouvées
3. **Implémentation v2** — Un nouveau `mdir_model_v2.py` sera créé quand les défis seront résolus
4. **Expérimentation** — Des fichiers de résultats seront ajoutés
