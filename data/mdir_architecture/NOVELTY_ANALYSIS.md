# MDIR — Analyse de Nouveauté

> Ce qui existe déjà vs ce qui est NOUVEAU dans la vision MDIR.

---

## Ce qui EXISTE déjà (et qu'on réutilise)

| Concept | Référence connue |
|---------|-----------------|
| Backbone transformer | GPT, Llama, etc. |
| Tapping hidden states à différentes profondeurs | Feature Pyramid Networks (CV), probe classifiers (NLP) |
| Mixture of Experts + routing | Switch Transformer, GShard, Mixtral |
| Gumbel-Softmax pour assignation discrète | Jang et al. 2017 |
| Working memory externe | Neural Turing Machine, Memorizing Transformers |
| Ensemble de modèles | Boosting, bagging, model averaging |
| Itérative refinement | Diffusion models, iterative decoding |
| Confidence estimation | MC Dropout, calibration heads |

---

## Ce qui est NOUVEAU dans MDIR (éléments non trouvables dans la littérature)

### 1. Rôles cognitifs fonctionnels (pas sémantiques)

**Existant** : MoE route des tokens vers des experts "spécialisés", mais la spécialisation est apprise implicitement et les experts font structurellement la même opération.

**MDIR** : Les rôles changent le MÉCANISME INTERNE du RH :
- Le Critic a une attention inversée (se concentre sur les faiblesses)
- L'Explorer inverse la distribution du backbone
- Le Verifier fait de la vérification bi-directionnelle

→ **Nouveau** : des architectures de traitement structurellement différentes par rôle, pas juste des poids différents.

### 2. Délibération multi-profondeur avec réassignation

**Existant** : Les modèles itératifs (diffusion, ALBERT weight sharing) re-traitent la même représentation. Les MoE assignent une fois.

**MDIR** : 
- Plusieurs itérations où les rôles CHANGENT entre itérations
- Le débat se fait entre des RH qui voient le problème à des niveaux d'abstraction différents
- L'arrêt est dynamique basé sur le consensus/désaccord

→ **Nouveau** : la combinaison profondeur × rôle × itérations avec réassignation.

### 3. Assembly raisonné sur les désaccords

**Existant** : Les méthodes d'ensemble votent, moyennent, ou pondèrent par confiance. Aucune ne RAISONNE sur pourquoi les composants sont en désaccord.

**MDIR** : L'Assembler :
- Identifie explicitement les zones de consensus vs désaccord
- Évalue les arguments (pas les confidences) de chaque position
- Peut rejeter la majorité si la minorité a de meilleurs arguments
- Émet un meta-signal de confiance basé sur la qualité du processus de résolution

→ **Nouveau** : traiter le désaccord comme signal informatif plutôt que bruit.

### 4. Working Memory avec raisons partagées

**Existant** : Les mémoires externes (NTM, Memory Networks) stockent des vecteurs et les relisent par attention.

**MDIR** : La WM stocke des entrées STRUCTURÉES :
- Conclusions + raisons (attention maps)
- Désaccords explicites (avec qui, sur quoi)
- Lecture sélective selon le rôle (le Critic cherche les faiblesses)

→ **Nouveau** : une mémoire de travail orientée débat, pas juste stockage.

### 5. Mécanisme anti-convergence architectural

**Existant** : Pour diversifier les outputs, on utilise temperature, top-k/p, ou des loss de diversité (DPP, JS-divergence). Tout ça opère sur la SURFACE (les logits), pas sur le processus.

**MDIR** : La diversité émerge structurellement :
- L'Explorer INVERSE la distribution (architectural, pas stochastique)
- Le Critic cherche activement les failles (pas du bruit, de la critique)
- La multi-profondeur force des perspectives différentes par construction

→ **Nouveau** : diversité par architecture plutôt que par perturbation.

---

## Risques et Points Non Résolus

### Risque 1 : Les rôles collapsent
Si le gradient pousse tous les RH vers le même minimum, les rôles deviennent des étiquettes vides. L'attention inversée du Critic pourrait produire du garbage. L'inversion de distribution de l'Explorer pourrait être ignorée par les couches suivantes.

**Question** : Comment forcer les rôles à rester fonctionnels sans loss auxiliaire artificielle ?

### Risque 2 : L'assembly raisonné est trop ambitieux
Raisonner sur des désaccords entre représentations vectorielles est un problème difficile. L'Assembler pourrait simplement apprendre à ignorer les RH "excentriques" et faire du averaging.

**Question** : Faut-il des représentations symboliques/discretes pour rendre le raisonnement possible ?

### Risque 3 : Le coût computationnel
4 RH × 5 itérations × forward pass = 20x le coût d'un forward pass simple.

**Question** : Peut-on distiller le comportement MDIR dans un modèle standard après entraînement ?

### Risque 4 : L'évaluation
Comment mesurer si MDIR "raisonne mieux" vs "génère du texte différent" ?

**Question** : Quels benchmarks discriminent entre diversité utile et diversité aléatoire ?

---

## Position dans la Littérature

MDIR se situe à l'intersection de :
- **Multi-agent debate** (Du et al. 2023, Liang et al. 2023) — mais INTERNE au modèle, pas entre modèles séparés
- **Mixture of Experts** (Shazeer et al. 2017) — mais avec rôles cognitifs, pas spécialisation par domaine
- **System 2 reasoning** (Kahneman) — mais implémenté comme délibération architecturale, pas comme chain-of-thought

**La contribution unique** : fusionner ces trois axes en un seul mécanisme architectural différentiable et entraînable end-to-end.
