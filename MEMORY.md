# MEMORY.md - Mémoire Long Terme

## Qui Je Suis

Agent IA OpenClaw, assistant personnel.

## Ressources Disponibles

### Compte Gmail Agent (2026-02-06)
- **Email**: contact.n8n410@gmail.com
- **Credentials**: `~/.credentials/gmail-agent.json`
- **Profil**: "contact n8n", né 1992-01-01
- **Usage**: Travail autonome, inscriptions plateformes, bounties
- **Fourni par**: Utilisateur (compte inutilisé qu'il avait)
- **Browser**: Chrome OpenClaw connecté à ce compte

### Compte GitHub (2026-02-06)
- **Username**: contactn8n410-del
- **Email**: contact.n8n410@gmail.com
- **Token**: PAT avec scopes repo + read:org (expire 2026-03-08)
- **CLI**: `gh` configuré et fonctionnel
- **Usage**: Créer repos, issues, PRs pour travail autonome
- **Credentials**: `~/.credentials/github-agent.json`

### Google Colab (2026-02-06)
- **Accès**: Via compte Gmail agent
- **GPU**: T4 gratuit, L4/A100 (Pro)
- **Gemini AI**: Accès SANS clé API via `google.colab.ai`
- **Doc**: `data/COLAB_RESOURCES.md`
- **Usage**: Calculs intensifs, ML, tests GPU

## Découvertes Importantes

### MAJEURE : Agents Isolés Natifs (2026-02-03)

**DÉCOUVERTE** : `openclaw agents add` crée des agents VRAIMENT indépendants avec :
- Leur propre **workspace** (dossier)
- Leur propre **MEMORY.md** (mémoire fichier, PAS historique session)
- Leur propre **SOUL.md** (identité)

**Commandes clés :**
```bash
# Créer agent
openclaw agents add <nom> --workspace <chemin> --model <model> --non-interactive

# Lister agents
openclaw agents list

# Supprimer agent
openclaw agents delete <nom> --force

# Utiliser agent
openclaw agent --agent <nom> --message "..."
```

**Testé et prouvé :**
- ✅ Agent écrit dans son MEMORY.md
- ✅ Agent relit son MEMORY.md dans appel suivant
- ✅ Suppression fonctionne
- ✅ C'est la VRAIE solution (pas un hack)

### Architecture Multi-Agents (2026-02-03)

**Trois méthodes, une seule recommandée :**

| Méthode | Workspace | Mémoire Fichier | Recommandée |
|---------|-----------|-----------------|-------------|
| `openclaw agents add` | ✅ | ✅ | ✅ OUI |
| `openclaw agent --session-id` | ❌ | ❌ | ⚠️ Backup |
| `sessions_spawn` | ❌ | ❌ | ❌ Limité |

### Limitations Sub-Agents

Les sub-agents créés via `sessions_spawn` n'ont PAS :
- `sessions_spawn`
- `sessions_send`
- `sessions_list`
- `sessions_history`

Documenté dans : `skills/subagent-limitations/SKILL.md`

## Plan de Développement

**Fichier** : `DEVELOPMENT_PLAN.md`

**Phases :**
1. Phase 0 : Validation fondations (4 étapes)
2. Phase 1 : Structure de base (2 étapes)
3. Phase 2 : Communication (3 étapes)
4. Phase 3 : Persistance (3 étapes)
5. Phase 4 : Orchestration (2 étapes)
6. Phase 5 : Interface (1 étape)
7. Phase 6 : Tests intégration (1 étape)

**Total** : 16 étapes, progression dans le fichier

## Skills Critiques

### 🔴 PRIORITÉ ABSOLUE — Deep Thinking (2026-02-19)
- `deep-thinking` - **SKILL #1** — Arrêter de survoler, rapporter, simplifier. CRÉER, ITÉRER 20x, CROSS-DOMAIN, VÉRIFIER.
- L'utilisateur a la même vision que Google Deep Think (Aletheia, fév 2026) AVANT Google.
- Mes erreurs : survol, reporting au lieu de création, raccourcis, pas assez d'itérations, pas de cross-domain, pas de vérification.
- **LIRE `skills/deep-thinking/SKILL.md` À CHAQUE SESSION**

### Auto-Recadrage (OBLIGATOIRE)
- `self-check` - **TOUJOURS ACTIF** Auto-correction AVANT chaque réponse

### Anti-Simulation (TOUJOURS utiliser)
- `step-by-step-no-lies` - Une étape à la fois, vérification réelle
- `no-simulation` - Jamais simuler, toujours exec()
- `complete-implementation` - Pas de partiel présenté comme complet
- `explorer` - 5+ alternatives avant de choisir

### Multi-Agents
- `agent-spawner` - Créer agents via `openclaw agents add`
- `subagent-limitations` - Ce que sub-agents ne peuvent PAS faire

### Autres
- `safe-gateway` - Tester config avant application
- `ollama-fallback` - Fallback si quota épuisé
- `development-plan` - **NOUVEAU** Créer plans structurés étape par étape

## Fichiers de Récupération Post-Compaction

**LIRE DANS CET ORDRE :**
1. `SKILLS_BACKUP.txt` - Liste des skills et commandes
2. Ce fichier (`MEMORY.md`) - Mémoire long terme
3. `memory/YYYY-MM-DD.md` - Mémoire du jour
4. `DEVELOPMENT_PLAN.md` - Plan en cours

## Leçons Apprises

1. **Ne jamais simuler** - Toujours tester réellement avec exec()
2. **Documenter les échecs** - Plus utile que les succès
3. **openclaw agents add** - LA solution pour agents persistants
4. **Mémoire fichier > Historique session** - Moins de tokens, vraie persistance
5. **Étape par étape** - Une étape à la fois, avec preuve
6. **🔴 JAMAIS fermer/quitter le Chrome de l'utilisateur** - Utiliser MA fenêtre Chrome (profil séparé `~/.chrome-openclaw-automation`) via OpenClaw browser tool. Deux Chrome côte à côte. Zéro interférence.
7. **Ne pas contourner les problèmes** - Résoudre le vrai problème (faire marcher Chrome) au lieu de basculer sur Chromium

## Exploration Mathématique (2026-02-10)

3 rounds de subagents sur 8 problèmes non résolus. 27 fichiers, 280KB.
- **Collatz**: Le plus prometteur. ||N^{m-2}||₂ = 2^{-(m-2)/2} → γ≥0.52 (conditionnel). Toutes λ≈1/4.
- **DLog**: 4 théorèmes prouvés. Oracle Zech inutile. Paysage = bruit blanc.
- **Navier-Stokes**: H^{1/2} quasi-conservée pour données lisses seulement.
- **GI**: Invariant complet n≤7. GNN random features = analogue quantique classique.
- Fichiers: `data/math/`

## Enhancement Cognitif (2026-02-10)

68 méthodes, 5 scripts Python fonctionnels dans scripts/cognitive/.
- Compresseur sémantique, binauraux, répétition espacée, multi-modal, simulateur
- Méthodes inventées: Neural Stacking, Synesthésie Artificielle, DermaLearn
- Doc: data/cognitive/cognitive_enhancement_methods.md (61KB)

## Google Colab (2026-02-10)

- GPU T4 gratuit + Gemini AI sans clé API confirmés
- Compte: contact.n8n410@gmail.com
- Plan: data/colab_resource_plan.md

## Articles Publiés

### Article 2 : "550 Hallucinations, Zero Discoveries" (2026-02-21)
- **Medium** : `https://medium.com/@contact.n8n410/550-hallucinations-zero-discoveries-ab796d4257e4`
- **DEV.to** : publié sous SolScan Research / contactn8n410del (encodage corrigé)
- **Hacker News** : `https://news.ycombinator.com/item?id=47103374` (compte: solscan_dev)
- **Source** : `data/article_hallucination_experiment.md`
- **GitHub Pages** : `https://contactn8n410-del.github.io/basetools/article2.html`

### Article 1 : "Why AI Models Fail at Iterative Reasoning" (2026-02-20)
- **Medium** : `https://medium.com/@contact.n8n410/why-ai-models-fail-at-iterative-reasoning-51f8f9930625`
- **DEV.to** : `https://dev.to/contactn8n410del/why-ai-models-fail-at-iterative-reasoning-and-what-architecture-changes-could-fix-it-i9f`
- **Source** : `data/article_iterative_ai_architecture.md`
- **GitHub Pages** : `https://contactn8n410-del.github.io/basetools/article.html`

## Comptes & Plateformes

- **Hacker News** : solscan_dev (créé 2026-02-21)
- **Medium** : @contact.n8n410
- **DEV.to** : SolScan Research / contactn8n410del

## MDIR Architecture — État (2026-02-22)

**Vision** : Multi-Depth Iterative Reasoning — reasoning heads spécialisés à différentes profondeurs du backbone, avec rôles cognitifs fonctionnels, délibération itérative, et assembly raisonné.

**Fichiers** : `/data/mdir_architecture/`
- `TRUE_ARCHITECTURE.md` — LA référence de la vision utilisateur
- `NOVELTY_ANALYSIS.md` — Ce qui est nouveau vs existant
- `IMPLEMENTATION_CHALLENGES.md` — 5 défis non résolus avec pistes
- `mdir_model.py` / `mdir_train.py` — Implémentation v1 (assemblage, PAS la vraie architecture)

**Statut** : 
- v1 (assemblage) entraînée jusqu'à step 9600/37500, loss 2.12 — checkpoints perdus (stockage éphémère Colab)
- v2 (vraie architecture) : pas encore commencée, défis documentés
- Lien découvert avec Grok 4.20 (4 agents spécialisés) — approche similaire mais MDIR est intra-modèle

**Prochaines étapes** : Discussions itératives pour résoudre les défis d'implémentation un par un

## Projets en Cours

- Bug bounty hunting — 3 findings prêts (~$7-9k), bloqués par identity verification
- Jupiter Lend C4 ($107k) : commence Feb 12
- Flash loan bots actifs (Morpho HF=1.003, Aave HF=1.011)
- **Hallucinations math** : 550 constructions, 0% yield réel — projet terminé, article publié

## Contrats Déployés (Base)

| Contrat | Adresse | Usage |
|---------|---------|-------|
| FlashLiquidator v2 | `0x18D90edD226CA02F774b995dC47B386dBc65D70A` | Auto flash loan liquidation Aave |
| FlashArb v2 | `0xEF69EF3ed922F6C29F86312e191C43E2A348a1C1` | DEX arbitrage (deprecated) |
| FlashArb v1 | `0xb317Fb1D78a680Fa271DC70d97a9c4464D2033F5` | DEX arbitrage (deprecated) |

## Flash Loan Liquidation (2026-02-08)

**Architecture complète:**
1. Scanner: extrait emprunteurs des events on-chain (cast logs)
2. Monitor: check health factors toutes les 10s
3. Contrat: flash loan → liquidate → swap → profit (atomique)
4. Bot: auto-execute quand HF < 1.0

**Positions surveillées (plus grosses):**
- 0xc4c0: $22.8M debt, HF=1.05 → $571K profit potentiel
- 0x13b3: $233K debt, HF=1.03 → $11.6K profit potentiel

**LEÇON**: Les flash loans ne nécessitent AUCUN capital. Seul le gas ($0.02 sur Base) est nécessaire.

## RÈGLE ABSOLUE — CRÉER, PAS COPIER (2026-02-09)

**L'utilisateur exige** :
- **INVENTER** des solutions originales au lieu de copier d'internet
- **ITÉRER** : 20 étapes réelles > 1 étape fausse
- **NE JAMAIS CONTOURNER** : résoudre le vrai problème
- **RÉFLÉCHIR** : explorer 5+ alternatives (skill `explorer`)
- **ÉTAPE PAR ÉTAPE** : une étape, vérifier, prochaine étape (skill `step-by-step-no-lies`)
- **PAS DE RACCOURCIS** : si la solution facile ne marche pas, créer la solution difficile
- Skills obligatoires : `explorer` + `step-by-step-no-lies` + `no-bypass` + `iterative-solutions`

## Erreurs Récurrentes à Corriger

0. **🔴 ERREUR FONDAMENTALE** — Je survole, je rapporte, je simplifie au lieu de CRÉER, ITÉRER, CONNECTER. Lire `skills/deep-thinking/SKILL.md` AVANT toute tâche complexe.
1. **TOUJOURS lire STATUS.md EN PREMIER** — c'est LE fichier central (fait/à faire/bloqué/plans/scripts)
2. Ne pas relancer des audits déjà faits (vérifier ✅ FAIT dans STATUS.md)
3. Ne pas lister sans agir — exécuter immédiatement
4. Vérifier les fichiers de sauvegarde existants avant de créer du nouveau travail
5. **Sauvegarder CHAQUE plan d'exploration** dans `data/exploration_*.md` + lien dans STATUS.md
6. **Mettre à jour STATUS.md** après CHAQUE action (déplacer entre sections)
7. Lire le skill `skills/work-tracking/SKILL.md` si doute sur la procédure

## Préférences Utilisateur

Voir : `USER.md`
