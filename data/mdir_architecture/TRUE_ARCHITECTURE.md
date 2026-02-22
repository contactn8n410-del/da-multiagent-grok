# MDIR — Multi-Depth Iterative Reasoning
# Architecture Réelle (Vision Utilisateur)

> Ce document décrit l'architecture **telle que l'utilisateur l'a conçue**.
> Ce n'est PAS ce qui a été implémenté dans `mdir_model.py` (v1).
> Chaque section indique ce qui est nouveau vs ce qui existe déjà.

---

## 1. Intuition Fondamentale

Les LLMs actuels produisent une seule "voix" — un flux de tokens qui converge vers la distribution la plus probable du training data. Il n'y a pas de débat interne, pas de perspectives multiples, pas de remise en question.

**L'idée MDIR** : Et si un modèle avait plusieurs "penseurs" qui :
- Voient le problème à des niveaux d'abstraction différents (profondeurs du backbone)
- Ont des RÔLES cognitifs distincts qui changent fondamentalement leur façon de traiter l'information
- Débattent entre eux sur plusieurs itérations avant de produire une réponse
- Produisent une réponse finale qui RAISONNE sur leurs désaccords plutôt que de moyenner

**L'objectif** : Briser la convergence vers le training data en forçant des perspectives divergentes à se confronter.

---

## 2. Les Reasoning Heads — Pas des Mini-Transformers

### Ce que c'est VRAIMENT

Chaque RH n'est **pas** juste un petit transformer qui génère des tokens. C'est un **processeur cognitif spécialisé** dont le comportement interne change selon le rôle assigné.

### Les 4 Rôles (pas des étiquettes — des modes de fonctionnement)

#### Lead (Meneur)
- **Fonction** : Produit la réponse la plus directe et confiante
- **Comportement** : Attention concentrée, faible température, favorise les continuations à haute probabilité
- **Mécanisme** : L'attention interne est biaisée vers les tokens les plus saillants. Le Lead ne doute pas — il produit la "meilleure réponse évidente"
- **Pourquoi c'est important** : C'est la baseline. Sans Lead, on ne sait pas quelle est la réponse "par défaut" que le modèle produirait normalement

#### Critic (Critique)
- **Fonction** : Cherche activement les failles, contradictions, et erreurs dans ce que les autres RH produisent
- **Comportement** : Attention inversée — se concentre sur ce qui est FAIBLE dans les autres outputs, pas sur ce qui est fort
- **Mécanisme** : Reçoit les outputs des autres RH (via working memory) et compute une "carte d'erreur" — où les autres sont incohérents ou peu confiants. Produit des tokens qui CONTREDISENT les parties faibles
- **Ce qui est NOUVEAU** : L'attention inversée et la carte d'erreur. Un transformer normal ne sait pas "chercher les erreurs". Le Critic doit avoir un mécanisme qui le pousse à diverger des zones de haute confiance des autres

#### Explorer
- **Fonction** : Explore des alternatives non-évidentes, des chemins que les autres RH ignorent
- **Comportement** : Haute entropie délibérée, exploration stochastique, favorise les tokens à FAIBLE probabilité selon le backbone
- **Mécanisme** : Reçoit la distribution du backbone et en fait l'INVERSE pondéré — les tokens rares deviennent probables, les tokens communs deviennent rares. Puis raisonne à partir de ces alternatives
- **Ce qui est NOUVEAU** : L'inversion de distribution. Ce n'est pas juste "temperature élevée" (qui reste centré sur le training data). C'est un mécanisme qui force l'exploration de l'espace NON couvert par le training

#### Verifier
- **Fonction** : Vérifie la cohérence logique et factuelle des outputs
- **Comportement** : Re-dérive les conclusions à partir des prémisses, vérifie que chaque étape suit de la précédente
- **Mécanisme** : Attention causale stricte avec vérification bi-directionnelle — regarde si la conclusion est atteignable à partir des prémisses ET si les prémisses mènent nécessairement à la conclusion
- **Ce qui est NOUVEAU** : La vérification bi-directionnelle. Un transformer normal ne vérifie pas la validité logique — il prédit le token suivant le plus probable

### Ce qui change selon la profondeur

Chaque RH tape le backbone à une profondeur différente :
- **Profondeur basse (couche 2)** : Features syntaxiques, patterns locaux → ce RH voit la structure de surface
- **Profondeur moyenne-basse (couche 4)** : Features sémantiques basiques → ce RH comprend le sens littéral
- **Profondeur moyenne-haute (couche 6)** : Relations abstraites → ce RH capture les implications
- **Profondeur haute (couche 8)** : Représentations de haut niveau → ce RH voit le "big picture"

**L'insight** : Un Critic à profondeur 2 critique la syntaxe. Un Critic à profondeur 8 critique le raisonnement. Le MÊME rôle produit un comportement différent selon la profondeur.

---

## 3. Le Router — Pas un Switch, un Stratège

### Ce que c'est VRAIMENT

Le Router ne fait pas juste "assigner Lead au RH-1". Il :

1. **Analyse la difficulté** de l'input — est-ce une question factuelle simple ou un problème de raisonnement complexe ?
2. **Décide de la stratégie** — pour un problème simple, 1 itération avec un Lead suffit. Pour un problème complexe, il faut 5+ itérations avec tous les rôles actifs
3. **Réassigne les rôles à chaque itération** — après la première itération, si le Critic a trouvé des failles, le Router peut convertir l'Explorer en un deuxième Critic pour approfondir
4. **Ajuste le nombre d'itérations dynamiquement** — s'il détecte un consensus tôt, il arrête. S'il détecte un désaccord persistant, il continue

### Mécanisme de décision

Le Router ne regarde pas juste l'input. Il regarde :
- La **confiance** de chaque RH à l'itération précédente
- Le **désaccord** entre les RH (divergence de leurs outputs)
- L'**historique** des itérations (est-ce que les RH convergent ou divergent ?)
- La **complexité estimée** de l'input

### Ce qui est NOUVEAU

Les Mixture-of-Experts (MoE) existants routent des tokens vers des experts fixes. Le Router MDIR :
- Route des STRATÉGIES COGNITIVES, pas des tokens
- Change les assignations entre itérations
- Décide quand s'arrêter (itérations adaptatives)

---

## 4. La Working Memory — Pas un Buffer, un Espace de Débat

### Ce que c'est VRAIMENT

La WM n'est pas un buffer où on stocke des vecteurs et on fait une moyenne pondérée.

C'est un **espace partagé structuré** où chaque RH :
1. **Écrit** sa conclusion + sa confiance + ses RAISONS (pas juste un hidden state)
2. **Lit** les conclusions des autres + leurs raisons
3. **Réagit** en fonction de son rôle — le Critic lit pour critiquer, l'Explorer lit pour diverger, le Verifier lit pour vérifier

### Structure d'un slot mémoire

```
{
    iteration: int,
    rh_id: int,
    role: str,
    conclusion: tensor,        # Le hidden state de sortie
    confidence: float,         # À quel point ce RH est sûr
    attention_map: tensor,     # SUR QUOI ce RH s'est concentré
    disagreement_with: dict,   # Avec qui il est en désaccord et pourquoi
}
```

### Ce qui est NOUVEAU

- Les **attention maps** sont partagées — chaque RH peut voir non seulement CE QUE les autres ont conclu, mais POURQUOI (quelles parties de l'input ils ont regardées)
- Le champ **disagreement_with** rend les désaccords explicites et tracables
- Les RH ne relisent pas tout — ils lisent sélectivement en fonction de leur rôle (le Critic cherche les points faibles, le Verifier cherche les prémisses)

---

## 5. L'Assembler — Pas un Moyenneur, un Juge

### Ce que c'est VRAIMENT

L'Assembler ne fait pas `sum(output * confidence) / sum(confidence)`.

C'est un **module de raisonnement sur les désaccords** qui :

1. **Identifie les zones de consensus** — où tous les RH sont d'accord, l'Assembler accepte directement
2. **Identifie les zones de désaccord** — où les RH divergent, l'Assembler doit RAISONNER sur pourquoi
3. **Évalue les arguments** — pour chaque position en désaccord :
   - Quel RH a la meilleure justification ?
   - Le Critic a-t-il trouvé une faille valide dans la position du Lead ?
   - L'Explorer a-t-il trouvé une alternative plus cohérente ?
   - Le Verifier a-t-il validé ou invalidé une des positions ?
4. **Produit une synthèse raisonnée** — pas un compromis, mais une conclusion argumentée qui peut rejeter la position majoritaire si la minorité a de meilleurs arguments
5. **Émet un meta-signal** :
   - "High confidence" : consensus fort + vérification passée
   - "Medium confidence" : désaccord résolu mais avec incertitude résiduelle  
   - "Low confidence" : désaccord non résolu, la réponse est un best-effort

### Ce qui est NOUVEAU

Les mécanismes d'ensemble existants (voting, averaging, MoE gating) ne RAISONNENT pas sur les désaccords. Ils pondèrent. L'Assembler MDIR est le premier composant qui traite explicitement les désaccords comme une source d'information, pas comme du bruit à moyenner.

---

## 6. Le Cycle de Délibération

### Itération complète

```
Pour chaque itération t = 1, 2, ..., T:

1. Le Router assigne les rôles et priorités pour cette itération
   (en fonction de l'état de la WM à t-1)

2. Chaque RH[i] reçoit :
   - Son tap du backbone (profondeur fixe)
   - Son rôle assigné (qui CHANGE son comportement interne)
   - Les entrées pertinentes de la WM (filtrées par rôle)

3. Chaque RH[i] produit :
   - Ses logits (sa "réponse")
   - Sa confiance
   - Son attention map (sur quoi il s'est concentré)
   - Ses points de désaccord (avec qui et pourquoi)

4. Les outputs sont écrits dans la WM

5. Le Router évalue :
   - Le consensus a-t-il augmenté ?
   - Des failles ont-elles été identifiées ?
   - Faut-il continuer ou s'arrêter ?

6. Si continuation : retour à 1 avec nouveaux rôles
   Si arrêt : passer à l'Assembler
```

### Ce qui est NOUVEAU dans le cycle

- Les rôles changent entre itérations (pas fixés)
- L'arrêt est dynamique (pas un nombre fixe d'itérations)
- Chaque itération est informée par les RAISONS des itérations précédentes, pas juste les résultats

---

## 7. Pourquoi Ça Pourrait Briser la Convergence

### Le problème

Un transformer standard converge vers argmax P(next_token | context) — la continuation la plus probable selon le training data. Même avec temperature sampling, on reste dans le voisinage de cette distribution.

### Comment MDIR attaque ce problème

1. **Multi-profondeur** : Des perspectives à différents niveaux d'abstraction empêchent de s'enfermer dans une seule interprétation
2. **Rôles divergents** : L'Explorer force explicitement l'exploration hors distribution. Le Critic force la remise en question de la réponse "évidente"
3. **Délibération** : Le débat itératif peut faire émerger des conclusions qui n'auraient jamais été le top-1 token d'aucun RH individuel
4. **Assembly raisonné** : La réponse finale peut contredire la majorité si un argument minoritaire est plus solide

### L'hypothèse

Si les RH développent VRAIMENT des perspectives différentes (pas juste du bruit), alors la délibération peut produire des réponses qui ne sont dans l'espace de probabilité d'aucun des composants individuels — des réponses véritablement "nouvelles".

---

## 8. Questions Ouvertes

1. **Comment entraîner les rôles ?** Comment forcer un Critic à VRAIMENT critiquer, pas juste à générer des tokens ? Faut-il un reward signal spécifique par rôle ?

2. **L'attention inversée est-elle stable ?** Forcer un réseau à regarder les tokens improbables pourrait mener à du garbage. Comment maintenir la qualité tout en explorant ?

3. **La WM scale-t-elle ?** Avec 4 RH × 5 itérations × attention maps + désaccords, la mémoire pourrait exploser

4. **Le Router peut-il apprendre une bonne stratégie ?** C'est un problème de meta-learning — le Router doit apprendre QUAND utiliser quelle stratégie

5. **Comment évaluer ?** Les benchmarks standards ne mesurent pas la "diversité de raisonnement". Il faut des métriques nouvelles

6. **L'Assembler raisonné est-il réalisable ?** Raisonner sur des désaccords entre représentations vectorielles est un problème ouvert. Comment rendre les "raisons" interprétables et exploitables ?

---

## 9. Différences avec l'Implémentation v1

| Composant | Vision originale | Implémentation v1 |
|-----------|-----------------|-------------------|
| RH | Processeurs cognitifs spécialisés dont le comportement CHANGE selon le rôle | Mini-transformers identiques avec un linear+tanh par rôle |
| Rôles | Modes de fonctionnement distincts (attention inversée, carte d'erreur, etc.) | Étiquettes cosmétiques — tous les RH font la même chose |
| Router | Stratège qui analyse la difficulté et réassigne dynamiquement | Gumbel-Softmax one-shot, pas de vraie analyse de difficulté |
| Working Memory | Espace structuré avec raisons, attention maps, désaccords explicites | Buffer de tenseurs avec moyenne pondérée |
| Assembler | Juge qui raisonne sur les désaccords | Cross-attention + MLP (moyenneur sophistiqué) |
| Délibération | Débat avec rôles changeants et arrêt dynamique | Boucle fixe sans vrai échange d'arguments |
| Diversité | Émergente des rôles différents | Forcée par une loss JS-divergence (artificielle) |

---

## 10. Priorités pour la v2

### P0 — Les rôles doivent CHANGER le comportement
C'est le cœur de l'architecture. Sans rôles fonctionnels, MDIR n'est qu'un ensemble de transformers.

### P1 — L'Assembler doit raisonner, pas moyenner
C'est ce qui distingue MDIR de tout mécanisme d'ensemble existant.

### P2 — La WM doit porter des raisons, pas juste des vecteurs
Sans raisons explicites, le débat est impossible.

### P3 — Le Router doit être adaptatif
Nombre d'itérations et rôles dynamiques selon la difficulté.
