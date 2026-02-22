# MDIR Implementation Log — Journal Complet

**Date**: 2026-02-22
**Statut**: 🟢 Training en cours sur Colab T4

---

## 1. Qu'est-ce que MDIR ?

**Multi-Depth Iterative Reasoning** — une architecture transformer expérimentale conçue pour briser la convergence des LLM vers leur training data.

**Idée clé**: Au lieu d'un seul forward pass, le modèle a :
- **4 Reasoning Heads (RH)** qui "tap" le backbone à différentes profondeurs (couches 2, 4, 6, 8)
- **4 rôles dynamiques** : Lead, Critic, Explorer, Verifier — assignés par un Router via Gumbel-Softmax
- **Délibération itérative** : les RH communiquent via une Working Memory sur plusieurs itérations
- **Un Assembler** qui agrège les outputs en raisonnant sur les désaccords entre RH

**Origine**: Concept de l'utilisateur, formalisé et implémenté par l'assistant.

---

## 2. Fichiers dans ce dossier

| Fichier | Description |
|---------|-------------|
| `ARCHITECTURE.md` | Design complet de l'architecture MDIR |
| `mdir_model.py` | Prototype PyTorch standalone (20.7M params, tests inclus) |
| `mdir_train.py` | **Script d'entraînement complet** pour Colab T4 (le fichier qui tourne actuellement) |
| `MDIR_Training_Colab.ipynb` | Notebook Jupyter original (contient des bugs, voir section erreurs) |
| `IMPLEMENTATION_LOG.md` | **CE FICHIER** — journal complet |

---

## 3. Ce qui a été fait ✅

### 3.1 Design (terminé)
- [x] Architecture MDIR formalisée dans `ARCHITECTURE.md`
- [x] Choix : hybrid tap (pas layer-split) pour éviter la redondance
- [x] 4 RH × 4 rôles × 3 phases d'entraînement
- [x] Dataset : TinyStories (50K train / 2K val)

### 3.2 Implémentation (terminé)
- [x] `mdir_model.py` — prototype complet avec tous les composants :
  - RMSNorm, RotaryEmbedding, Attention (causal), FeedForward (SwiGLU)
  - TransformerBlock, QueryTranslator, ReasoningHead, RoleModulator
  - DynamicRouter (Gumbel-Softmax), WorkingMemory, Assembler
  - MDIRModel (forward + loss multi-composantes)
- [x] Tests unitaires passent (forward, backward, generation)
- [x] `mdir_train.py` — script standalone all-in-one pour Colab

### 3.3 Notebook Colab (partiellement fonctionnel)
- [x] Créé `MDIR_Training_Colab.ipynb` avec 20 cellules
- [x] Uploadé sur Google Drive, lié au compte `contact.n8n410@gmail.com`
- [x] URL : `https://colab.research.google.com/drive/1ISM5dBxsIeGodGB0awA1zyL6ENtWeHyL`
- [x] Runtime T4 GPU actif

### 3.4 Corrections et lancement (en cours)
- [x] Bug `total_mem` → `total_memory` corrigé (cellule 2 du notebook)
- [x] Bug `device` non défini corrigé (dans `mdir_train.py`)
- [x] Batch size réduit 16 → 4 (OOM avec 16)
- [x] Backbone réduit : dim 512→256, layers 16→8, taps (4,8,12,16)→(2,4,6,8)
- [x] RH dim réduit : 384→192
- [x] Script poussé sur GitHub, téléchargé sur Colab via wget
- [x] Runtime crashé avec `os._exit(0)` pour vider la VRAM
- [x] Script relancé — **TRAINING EN COURS** (81.1M params, ~1.0 GB VRAM estimé)

---

## 4. Ce qui reste à faire ❌

### 4.1 Monitoring du training
- [ ] Vérifier que les 3 phases se déroulent sans erreur
  - Phase 1 : 1 iter, div_λ=0.0 (apprendre à générer)
  - Phase 2 : 2 iters, div_λ=0.15 (diversifier)
  - Phase 3 : 3 iters, div_λ=0.3 (itérations complètes)
- [ ] Vérifier la loss descend (asm, task, div)
- [ ] Vérifier les confidences RH divergent (pas toutes identiques)
- [ ] Temps estimé : ~15-30 min pour les 3 epochs

### 4.2 Évaluation (après training)
- [ ] Plots des courbes de training (loss, composants, confidences, LR)
- [ ] Test de génération : comparer 1 iter vs 3 iters
- [ ] Analyse de diversité : est-ce que les RH produisent des outputs différents ?
- [ ] Examiner les rôles assignés par le Router
- [ ] Télécharger les résultats depuis Colab

### 4.3 Évaluation avancée (si le training réussit)
- [ ] Benchmarks : GSM8K, ARC
- [ ] Comparer avec un transformer vanilla de même taille
- [ ] Analyser si plus d'itérations = meilleure qualité
- [ ] Écrire un article sur les résultats

---

## 5. Erreurs rencontrées et solutions

### Erreur 1 : `total_mem` AttributeError
**Cellule 2 du notebook**
```python
# BUG
torch.cuda.get_device_properties(0).total_mem  # ❌ n'existe pas
# FIX
torch.cuda.get_device_properties(0).total_memory  # ✅
```
**Solution**: Rechercher/Remplacer dans le notebook via le panneau Colab.

### Erreur 2 : `device` non défini
**Cellule 8 du notebook** : `model = MDIRModel(config).to(device)` — mais `device` n'était défini que dans la cellule 2 qui avait crashé à cause de l'erreur 1.
**Solution**: Corrigé dans `mdir_train.py` standalone (device défini en haut du script).

### Erreur 3 : OutOfMemoryError (1ère fois)
**Config originale**: backbone_dim=512, 16 layers, batch_size=16, vocab=50257
**Cause**: Le modèle original (config initiale vocab=32K) faisait 20.7M params, mais avec le GPT-2 tokenizer (vocab=50257), il faisait **beaucoup plus** — chaque RH a un lm_head de rh_dim×vocab_size.
**Solution**: Réduire via Rechercher/Remplacer dans le notebook :
- batch_size: 16 → 4
- backbone_dim: 512 → 256
- backbone_layers: 16 → 8
- tap_layers: (4,8,12,16) → (2,4,6,8)
- rh_dim: 384 → 192

### Erreur 4 : OutOfMemoryError (2ème fois)
**Cause**: L'ancien modèle (gros) était encore en VRAM du notebook quand le script standalone a été lancé.
**Solution**: Tuer le kernel avec `os._exit(0)` pour libérer toute la VRAM, puis relancer le script.

### Erreur 5 : Terminal Colab ne reçoit pas les commandes
**Cause**: Le champ `textbox "Terminal input"` dans le DOM Colab ne transmet pas correctement les commandes tapées via le browser automation d'OpenClaw. Les escape codes `[1;3H` apparaissent au lieu des commandes.
**Solution**: Abandonner le terminal. Utiliser l'API JavaScript interne de Colab :
```javascript
const nb = colab.global.notebook;
const cells = nb.getCells();
cells[6].setText('!python3 /content/mdir_train.py');
nb.focusCell(cells[6]);
// Puis Ctrl+Enter pour exécuter
```

### Erreur 6 : Browser OpenClaw timeout constant
**Cause**: Le service browser d'OpenClaw timeout après 20s fréquemment avec Colab (page lourde).
**Solution**: Utiliser `evaluate` (JavaScript) au lieu de click/type pour les interactions critiques. Les évaluations JS sont plus fiables que la navigation DOM.

---

## 6. GitHub — Code poussé

**Repo**: `https://github.com/contactn8n410-del/basetools`
**Fichier**: `mdir_train.py` (commit `67847a3`)
**Branche**: `master`

**Pour télécharger sur Colab** :
```
!wget -q https://raw.githubusercontent.com/contactn8n410-del/basetools/master/mdir_train.py -O /content/mdir_train.py
```

---

## 7. Comment reprendre si tout s'arrête

### Scénario A : Le runtime Colab est encore actif
1. Ouvrir le notebook : `https://colab.research.google.com/drive/1ISM5dBxsIeGodGB0awA1zyL6ENtWeHyL`
2. Vérifier si le training tourne encore (cellule avec le spinner)
3. Si oui, attendre ; si non, voir le log de sortie pour les résultats

### Scénario B : Le runtime Colab s'est déconnecté
1. Ouvrir le notebook
2. Reconnecter le runtime (bouton "Reconnecter" en haut à droite)
3. Vérifier le type de GPU (doit être T4)
4. **Ne PAS relancer le notebook cellule par cellule** — il a des bugs non corrigés
5. Créer une nouvelle cellule et y mettre :
```python
!wget -q https://raw.githubusercontent.com/contactn8n410-del/basetools/master/mdir_train.py -O /content/mdir_train.py && python3 /content/mdir_train.py
```
6. Exécuter cette cellule (Ctrl+Enter)

### Scénario C : Via l'API JavaScript Colab (si le browser automation est utilisé)
```javascript
// Injecter du code dans une cellule vide et l'exécuter
const nb = colab.global.notebook;
const cells = nb.getCells();
// Trouver ou créer une cellule
cells[INDEX].setText('!wget -q https://raw.githubusercontent.com/contactn8n410-del/basetools/master/mdir_train.py -O /content/mdir_train.py && python3 /content/mdir_train.py');
nb.focusCell(cells[INDEX]);
// Puis envoyer Ctrl+Enter
```

### Scénario D : Modifications du script nécessaires
1. Modifier `/Users/invite/clawd/data/mdir_architecture/mdir_train.py` localement
2. Copier vers le repo GitHub :
```bash
cp data/mdir_architecture/mdir_train.py /tmp/basetools_tmp/
cd /tmp/basetools_tmp && git add . && git commit -m "update" && git push
```
3. Sur Colab, re-télécharger et relancer

---

## 8. Configuration actuelle du modèle (celle qui tourne)

```python
@dataclass
class MDIRConfig:
    backbone_dim: int = 256       # réduit de 512
    backbone_layers: int = 8      # réduit de 16
    n_heads: int = 8
    vocab_size: int = 50257       # GPT-2 tokenizer (mis à jour au runtime)
    max_seq_len: int = 256
    tap_layers: tuple = (2, 4, 6, 8)   # réduit de (4,8,12,16)
    rh_dim: int = 192             # réduit de 384
    rh_layers: int = 3
    rh_heads: int = 6
    n_roles: int = 4
    max_iterations: int = 8
    assembler_layers: int = 4
    diversity_lambda: float = 0.3
    role_lambda: float = 0.2
    dropout: float = 0.1
```

**Résultat** : 81.1M paramètres, ~1.0 GB VRAM estimé (fit largement dans T4 15.6 GB)

### Stats de training en direct (observé à 13:39 GMT+4)
- 12500 batches/epoch × 3 epochs = **37500 steps total**
- Warmup: 3750 steps
- Vitesse: ~1 step/s → **~10h** pour le training complet
- Phase 1 (step 600/12500): loss 21.4 → 17.9 (descente régulière ✅)
- Checkpoint sauvegardé à step 500
- **⚠️ Le runtime Colab free se déconnecte après ~90 min d'inactivité et ~12h max**
- Si déconnexion, les checkpoints sont sur le disque Colab (`/content/checkpoints/`)

### Training config
- Optimizer : AdamW (lr=3e-4, weight_decay=0.01, betas=(0.9, 0.95))
- Scheduler : Cosine avec warmup (10% des steps)
- Mixed precision : torch.amp.autocast + GradScaler
- Batch size : 4
- Dataset : TinyStories 50K train / 2K val, GPT-2 tokenizer, seq_len=256
- 3 phases / 3 epochs
- Gradient clipping : 1.0
- Log every 100 steps, save every 500 steps

---

## 9. Architecture du notebook Colab (21 cellules)

| # | Type | Contenu | Statut |
|---|------|---------|--------|
| 0 | Texte | Titre + description | ✅ |
| 1 | Code | pip install | ✅ [3] |
| 2 | Code | imports + device setup | ✅ [4] (corrigé total_memory) |
| 3 | Code | Vide (ancien placeholder) | ✅ [4] |
| 4 | Texte | "Model Definition" | ✅ |
| 5 | Code | MDIRConfig | ⚠️ Modifié (dim=256, layers=8) mais tap_layers et rh_dim PAS corrigés dans le notebook |
| 6 | Code | **Cellule ajoutée** — `!python3 /content/mdir_train.py` | 🟢 EN COURS |
| 7 | Code | Building Blocks | ❌ Pas re-exécuté |
| 8 | Code | MDIR Components | ❌ Pas re-exécuté |
| 9 | Code | Full MDIR Model | ❌ Pas re-exécuté |
| 10 | Texte | "Dataset" | ✅ |
| 11 | Code | Dataset loading + tokenizer | ❌ Pas re-exécuté |
| 12 | Code | Tokenize + DataLoader | ⚠️ batch_size=4 (corrigé) mais pas re-exécuté |
| 13 | Texte | "Training Loop" | ✅ |
| 14 | Code | Training setup | ❌ Pas re-exécuté |
| 15 | Code | Training loop | ❌ Pas re-exécuté |
| 16 | Texte | "Evaluation" | ✅ |
| 17 | Code | Plot training curves | ❌ Pas exécuté |
| 18 | Code | Test generation | ❌ Pas exécuté |
| 19 | Code | Diversity analysis | ❌ Pas exécuté |
| 20 | Code | Save + zip results | ❌ Pas exécuté |

**NOTE IMPORTANTE**: Le notebook a des bugs non corrigés (tap_layers, rh_dim dans cellule 5). Le script standalone `mdir_train.py` sur GitHub est la version correcte et c'est celui qui tourne actuellement via la cellule 6.

---

## 10. Découvertes techniques clés

1. **API JavaScript Colab** : `colab.global.notebook.getCells()[i].setText(code)` + `focusCell()` + Ctrl+Enter permet de contrôler le notebook programmatiquement quand le browser automation est instable.

2. **Vider la VRAM Colab** : `os._exit(0)` tue le kernel proprement et libère toute la VRAM. Plus efficace que `torch.cuda.empty_cache()` + `gc.collect()` (qui ne libèrent que les tensors non-référencés).

3. **Le terminal Colab est inutilisable** via browser automation (escape codes corrompus). Toujours passer par les cellules du notebook.

4. **Sizing pour T4 (15 GB)** : Avec GPT-2 vocab (50257), chaque lm_head coûte `dim × 50257 × 4 bytes`. Avec 4 RH + 1 Assembler = 5 lm_heads. À rh_dim=384 c'est 5×384×50257×4 = 386 MB juste pour les lm_heads. Réduire rh_dim à 192 divise par 2.
