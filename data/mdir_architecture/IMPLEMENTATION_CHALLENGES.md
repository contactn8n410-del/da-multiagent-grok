# MDIR — Défis d'Implémentation

> Les vrais problèmes à résoudre pour implémenter l'architecture réelle.
> Chaque section = un problème dur. Pas de solutions faciles.

---

## Défi 1 : Comment implémenter l'Attention Inversée du Critic ?

### Le problème
Le Critic doit se concentrer sur les FAIBLESSES des autres RH. Mais dans un transformer, l'attention va naturellement vers les tokens les plus saillants (les forces, pas les faiblesses).

### Pistes possibles

**A) Inversion littérale des scores d'attention**
```
attn_scores = Q @ K^T / sqrt(d)
critic_scores = -attn_scores  # ou 1/attn_scores
```
Problème : ça produit probablement du garbage. Les tokens ignorés le sont souvent pour de bonnes raisons.

**B) Attention sur la confiance basse**
Le Critic reçoit les confidence maps des autres RH et concentre son attention là où les autres ont FAIBLE confiance.
```
critic_bias = -log(other_rh_confidence + eps)  # Haute valeur = faible confiance
attn_scores = Q @ K^T / sqrt(d) + critic_bias
```
Plus raisonnable — on guide l'attention vers les zones incertaines.

**C) Adversarial attention**
Entraîner le Critic avec une loss adversariale : le Critic est récompensé quand il trouve des prédictions que les autres RH se trompent.
```
critic_reward = -log P(correct_token | other_rh_prediction)
```
Plus principled mais plus dur à entraîner (instabilité GAN-like).

**D) Différence d'attention**
Le Critic compute SA PROPRE attention, puis soustrait l'attention des autres RH.
```
critic_attn = self_attn - mean(other_rh_attns)
```
Force le Critic à regarder des endroits différents.

### Statut : NON RÉSOLU — nécessite expérimentation

---

## Défi 2 : Comment l'Explorer Inverse la Distribution ?

### Le problème
L'Explorer doit explorer l'espace de tokens que le backbone considère improbables. Mais les tokens improbables sont souvent improbables pour de bonnes raisons (non-sens grammatical, hors-sujet).

### Pistes possibles

**A) Inversion pondérée**
```
explorer_logits = -backbone_logits * alpha + explorer_own_logits * (1 - alpha)
```
Problème : l'inversion pure donne du charabia. Il faut un mélange.

**B) Top-k inversé**
Masquer les top-k tokens du backbone et ne garder que les tokens de rang k+1 à 2k.
```
top_k_mask = backbone_logits.topk(k).indices
explorer_logits[top_k_mask] = -inf
```
Plus sûr — on exclut le "évident" mais on ne force pas le non-sens.

**C) Repulsive attention**
L'Explorer a un mécanisme d'attention qui est REPOUSSÉ par les patterns du backbone.
```
repulsion = cosine_similarity(explorer_hidden, backbone_hidden)
explorer_hidden = explorer_hidden - repulsion * backbone_hidden
```
Projette l'Explorer dans le sous-espace orthogonal au backbone.

**D) Noise injection contrôlée**
Ajouter du bruit structuré aux hidden states du backbone avant de les donner à l'Explorer. Le bruit est appris, pas aléatoire.
```
noise = learned_noise_generator(backbone_hidden)
explorer_input = backbone_hidden + noise
```

### Statut : NON RÉSOLU — la piste (C) semble la plus prometteuse

---

## Défi 3 : Comment l'Assembler Raisonne sur les Désaccords ?

### Le problème
Cross-attention entre les outputs des RH ne suffit pas — ça pondère, ça ne raisonne pas. Comment faire un module qui COMPREND pourquoi deux RH ne sont pas d'accord et qui DÉCIDE qui a raison ?

### Pistes possibles

**A) Comparaison par paires explicite**
Pour chaque paire (RH_i, RH_j) en désaccord :
```
diff = RH_i_hidden - RH_j_hidden
agreement = RH_i_hidden * RH_j_hidden  # element-wise
disagreement_features = concat(diff, agreement, abs(diff))
score = MLP(disagreement_features)  # Qui a "raison" ?
```
Plus riche qu'une simple attention, mais toujours un pattern matching, pas du raisonnement.

**B) Débat structuré dans l'Assembler**
L'Assembler a ses propres couches de transformer qui traitent les outputs des RH comme une "conversation" :
```
conversation = [RH_1_output, RH_2_output, ..., RH_4_output]
# Chaque "turn" est un output de RH
# L'attention croisée peut capturer les relations argument/contre-argument
assembled = transformer_layers(conversation)
```
L'Assembler traite les outputs comme un dialogue, pas comme des features.

**C) Vote par preuve**
Chaque RH ne produit pas juste un output mais une CHAÎNE de raisonnement (sequence de hidden states intermédiaires). L'Assembler évalue la qualité de la chaîne, pas juste la conclusion.
```
rh_chain = [hidden_1, hidden_2, ..., hidden_L]  # L couches du RH
chain_coherence = evaluate_chain(rh_chain)  # Les étapes sont-elles cohérentes ?
weight = chain_coherence  # Plus la chaîne est cohérente, plus le vote compte
```

**D) Meta-apprentissage**
L'Assembler est entraîné avec un signal spécifique : dans les cas où la majorité des RH se trompe mais la minorité a raison, l'Assembler doit apprendre à suivre la minorité.
```
# Cas d'entraînement spéciaux :
# 3 RH prédisent A (faux), 1 RH prédit B (vrai)
# Loss pousse l'Assembler vers B
minority_correct_loss = -log P(correct | minority_rh_output)
```

### Statut : NON RÉSOLU — probablement une combinaison de (B) et (D)

---

## Défi 4 : Comment Entraîner les Rôles ?

### Le problème
Si on entraîne end-to-end avec juste cross-entropy loss, les rôles vont collapser — tous les RH apprendront à minimiser la loss de la même façon.

### Pistes possibles

**A) Loss auxiliaires par rôle**
```
lead_loss = cross_entropy(lead_output, target)  # Doit être bon
critic_loss = -cross_entropy(lead_output, target) * critic_found_error  # Récompensé pour trouver des erreurs
explorer_loss = diversity_reward(explorer_output, lead_output)  # Récompensé pour diverger utilement
verifier_loss = consistency_check(chain_of_reasoning)  # Récompensé pour vérifier correctement
```
Problème : concevoir les bonnes loss est très dur. Comment mesurer "erreur utile" vs "bruit" ?

**B) Curriculum de rôles**
- Phase 1 : Tous les RH apprennent à générer (pas de rôles)
- Phase 2 : On active les rôles progressivement — le Lead continue à générer, le Critic est entraîné adversarialement
- Phase 3 : L'Explorer est activé avec repulsive attention
- Phase 4 : Le Verifier est activé avec vérification bi-directionnelle

**C) Reinforcement Learning des rôles**
Utiliser RL pour entraîner le Router à assigner les bons rôles :
```
reward = quality(assembled_output) - quality(single_rh_output)
# Le reward est positif quand la délibération AMÉLIORE la réponse
```
Le Router apprend à assigner les rôles qui maximisent le gain de la délibération.

### Statut : NON RÉSOLU — (B) semble la plus réaliste pour commencer

---

## Défi 5 : Comment Rendre la WM Efficace ?

### Le problème
Stocker des attention maps + hidden states + désaccords pour 4 RH × N itérations → explosion mémoire.

### Pistes
- Compression : ne stocker que les top-k positions d'attention, pas la map complète
- Quantification : stocker les hidden states en int8
- Élagage : ne garder que les slots avec confiance > seuil
- Résumé : un petit réseau qui compresse chaque slot en un vecteur fixe

### Statut : Résolvable avec de l'ingénierie, pas un problème fondamental

---

## Ordre d'Attaque Suggéré

1. **D'abord** : Résoudre le Défi 4 (entraînement des rôles) avec l'approche curriculum
2. **Ensuite** : Implémenter le Défi 1 (Critic) avec l'approche (B) — attention guidée par confiance basse
3. **Puis** : Implémenter le Défi 2 (Explorer) avec l'approche (C) — repulsive attention
4. **Puis** : Implémenter le Défi 3 (Assembler) avec l'approche (B) — débat structuré
5. **Enfin** : Optimiser le Défi 5 (WM) si nécessaire

Chaque étape est testable indépendamment. On peut évaluer si chaque composant ajoute de la valeur avant de passer au suivant.
