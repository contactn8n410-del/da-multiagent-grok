# MDIR — Multi-Depth Iterative Reasoning

## Document de conception et implémentation

### Date: 2026-02-22
### Auteur: Architecture conçue par l'utilisateur, formalisée et implémentée ici

---

## 1. PROBLÈME FONDAMENTAL

Un Transformer standard fait UN pass à travers ses layers. Résultat :
- Pas de raisonnement itératif réel
- Convergence systématique vers le training data
- Une seule "méthode" de pensée

## 2. INSIGHT CLÉ DE L'ARCHITECTURE

Différentes profondeurs de layers capturent différents niveaux d'abstraction :
- Layers 1-4 : patterns syntaxiques, associations de surface
- Layers 5-12 : structure logique, relations entre concepts  
- Layers 13-24 : sémantique profonde, raisonnement abstrait

**L'idée** : au lieu de traiter ça comme un pipeline séquentiel, 
traiter chaque niveau comme un RAISONNEUR INDÉPENDANT capable de 
produire sa propre réponse, puis faire dialoguer ces raisonneurs.

## 3. TENSION ARCHITECTURALE IDENTIFIÉE

Problème : si RM-2 utilise les layers 1-16, il CONTIENT déjà le calcul de RM-1 (layers 1-8).
Ils ne sont pas vraiment indépendants.

**Solution retenue** : Architecture hybride
- Le backbone (modèle de base) traite la requête normalement
- À différentes profondeurs, on "tape" les hidden states
- Chaque tap alimente un REASONING HEAD séparé (petit modèle indépendant)
- Les reasoning heads sont entraînés avec des objectifs DIFFÉRENTS
- C'est la combinaison tap_depth + objectif_différent qui crée la diversité

## 4. ARCHITECTURE DÉTAILLÉE

```
QUERY (tokens)
    │
    ▼
┌─────────────────────────────────────────┐
│           BASE MODEL (backbone)          │
│                                          │
│   Layer 1 ──→ Layer 2 ──→ ... ──→ Layer 4 ──── TAP ──→ h_shallow
│                                    │
│   Layer 5 ──→ ... ──→ Layer 12 ────────── TAP ──→ h_mid
│                                    │
│   Layer 13 ──→ ... ──→ Layer 24 ───────── TAP ──→ h_deep
│                                          │
└─────────────────────────────────────────┘
    │              │              │
    ▼              ▼              ▼
┌────────┐   ┌────────┐   ┌────────┐
│ RH-1   │   │ RH-2   │   │ RH-3   │    RH = Reasoning Head
│ 4 layers│   │ 4 layers│   │ 4 layers│    (petit modèle indépendant)
│ +LM head│   │ +LM head│   │ +LM head│
│         │   │         │   │         │
│ Objectif│   │ Objectif│   │ Objectif│
│ FAST    │   │ STRUCT  │   │ DEEP   │
└────┬────┘   └────┬────┘   └────┬────┘
     │              │              │
     ▼              ▼              ▼
  Réponse 1     Réponse 2     Réponse 3
     │              │              │
     └──────────────┼──────────────┘
                    ▼
            ┌──────────────┐
            │  ASSEMBLEUR   │
            │  + ROUTER     │
            └──────┬───────┘
                   ▼
             Réponse finale
```

## 5. COMPOSANTS

### 5.1 Query Translator (QT)

Chaque RH opère sur un hidden state d'une profondeur différente.
Mais le hidden state à layer 4 ne "comprend" pas la même chose qu'à layer 24.

Le QT n'est PAS une transformation de la requête textuelle.
C'est une projection du hidden state dans un espace où le RH peut raisonner.

```python
class QueryTranslator(nn.Module):
    """Projette le hidden state d'une profondeur donnée
    dans l'espace d'entrée du Reasoning Head correspondant."""
    
    def __init__(self, backbone_dim, rh_dim, depth_level):
        super().__init__()
        # Projection non-linéaire adaptée à la profondeur
        self.proj = nn.Sequential(
            nn.Linear(backbone_dim, rh_dim * 2),
            nn.GELU(),
            nn.Linear(rh_dim * 2, rh_dim),
            nn.LayerNorm(rh_dim)
        )
        # Embedding de profondeur (le RH sait à quelle profondeur il opère)
        self.depth_embed = nn.Parameter(torch.randn(1, 1, rh_dim) * 0.02)
    
    def forward(self, hidden_state):
        # hidden_state: [batch, seq_len, backbone_dim]
        projected = self.proj(hidden_state)
        return projected + self.depth_embed
```

### 5.2 Reasoning Head (RH)

Chaque RH est un petit transformer (4 layers) avec sa propre LM head.
Crucial : ils ont des OBJECTIFS D'ENTRAÎNEMENT DIFFÉRENTS.

```python
class ReasoningHead(nn.Module):
    """Un petit modèle capable de générer du texte
    à partir d'un hidden state intermédiaire."""
    
    def __init__(self, dim, n_layers=4, n_heads=8, vocab_size=32000):
        super().__init__()
        self.layers = nn.ModuleList([
            TransformerBlock(dim, n_heads) for _ in range(n_layers)
        ])
        self.lm_head = nn.Linear(dim, vocab_size, bias=False)
        self.confidence_head = nn.Linear(dim, 1)  # Score de confiance
        
    def forward(self, x, mask=None):
        for layer in self.layers:
            x = layer(x, mask=mask)
        
        logits = self.lm_head(x)
        confidence = torch.sigmoid(self.confidence_head(x.mean(dim=1)))
        
        return logits, confidence
```

### 5.3 Router (allocation dynamique des rôles)

```python
class DynamicRouter(nn.Module):
    """Analyse la requête et décide :
    - Quel rôle pour chaque RH (Lead/Critic/Explorer/Verifier)
    - Score de priorité par RH
    - Nombre d'itérations nécessaires
    """
    
    ROLES = ['lead', 'critic', 'explorer', 'verifier']
    
    def __init__(self, dim, n_rhs=3, max_iterations=10):
        super().__init__()
        self.n_rhs = n_rhs
        
        # Analyse de la requête
        self.query_analyzer = nn.Sequential(
            nn.Linear(dim, dim),
            nn.GELU(),
            nn.Linear(dim, dim // 2)
        )
        
        # Attribution des rôles : pour chaque RH, probabilité de chaque rôle
        self.role_assigner = nn.Linear(dim // 2, n_rhs * len(self.ROLES))
        
        # Score de priorité par RH
        self.priority_scorer = nn.Linear(dim // 2, n_rhs)
        
        # Nombre d'itérations (régression discrétisée)
        self.iteration_predictor = nn.Linear(dim // 2, max_iterations)
        
        # ADAPTATIF : mise à jour des scores à chaque itération
        self.iteration_updater = nn.GRUCell(dim // 2 + n_rhs, dim // 2)
        
    def forward(self, query_embedding, iteration_context=None):
        """
        query_embedding: [batch, dim] — CLS token ou mean pooling du backbone
        iteration_context: [batch, n_rhs] — confiances des RHs au tour précédent
        """
        h = self.query_analyzer(query_embedding)
        
        if iteration_context is not None:
            # À chaque itération, le router se MET À JOUR
            # basé sur les confiances des RHs
            h = self.iteration_updater(
                torch.cat([h, iteration_context], dim=-1), h
            )
        
        # Rôles : softmax par RH (chaque RH a une distribution sur les rôles)
        role_logits = self.role_assigner(h).view(-1, self.n_rhs, len(self.ROLES))
        role_probs = F.softmax(role_logits, dim=-1)
        # Gumbel-softmax pour sélection discrète mais différentiable
        roles = F.gumbel_softmax(role_logits, tau=0.5, hard=True)
        
        # Priorités
        priorities = torch.sigmoid(self.priority_scorer(h))
        
        # Itérations
        iter_logits = self.iteration_predictor(h)
        n_iterations = iter_logits.argmax(dim=-1) + 1  # minimum 1
        
        return {
            'roles': roles,           # [batch, n_rhs, n_roles] one-hot
            'role_probs': role_probs,  # [batch, n_rhs, n_roles] soft
            'priorities': priorities,  # [batch, n_rhs]
            'n_iterations': n_iterations,  # [batch]
            'hidden': h               # pour l'itération suivante
        }
```

### 5.4 Working Memory

```python
class WorkingMemory:
    """Mémoire externe qui accumule les réponses des RHs
    à travers les itérations. C'est ICI que l'information
    nouvelle (hors training data) se crée."""
    
    def __init__(self, max_slots=50):
        self.max_slots = max_slots
        self.slots = []  # Liste de (iteration, rh_id, role, response, confidence)
    
    def write(self, iteration, rh_id, role, response_hidden, confidence):
        self.slots.append({
            'iter': iteration,
            'rh': rh_id,
            'role': role,
            'hidden': response_hidden,  # Hidden states, pas du texte
            'confidence': confidence,
            'text': None  # Décodé lazily
        })
        # Garder seulement les slots les plus récents/importants
        if len(self.slots) > self.max_slots:
            # Élaguer les slots les moins confiants des itérations anciennes
            self.slots.sort(key=lambda s: (s['iter'], s['confidence']), reverse=True)
            self.slots = self.slots[:self.max_slots]
    
    def read_for_rh(self, rh_id, current_iter):
        """Un RH lit les outputs des AUTRES RHs (pas les siens)
        pour l'itération précédente."""
        relevant = [
            s for s in self.slots 
            if s['rh'] != rh_id and s['iter'] == current_iter - 1
        ]
        if not relevant:
            return None
        # Concaténer les hidden states
        return torch.cat([s['hidden'] for s in relevant], dim=1)
    
    def read_all(self):
        """L'assembleur lit TOUT."""
        return [s['hidden'] for s in self.slots]
```

### 5.5 Assembleur

```python
class Assembler(nn.Module):
    """Ne fait PAS la moyenne des réponses.
    Raisonne SUR les réponses pour construire la réponse finale.
    
    Opère en deux phases :
    1. Analyse structurelle : convergences, divergences, confiances
    2. Génération : produit la réponse finale en tenant compte de l'analyse
    """
    
    def __init__(self, dim, n_rhs, vocab_size, n_layers=6):
        super().__init__()
        
        # Phase 1 : Analyse des réponses des RHs
        self.cross_attention = nn.MultiheadAttention(dim, 8, batch_first=True)
        
        # Détecteur de convergence/divergence
        self.agreement_detector = nn.Sequential(
            nn.Linear(dim * n_rhs, dim),
            nn.GELU(),
            nn.Linear(dim, dim)
        )
        
        # Phase 2 : Génération conditionnée sur l'analyse
        self.generator = nn.ModuleList([
            TransformerBlock(dim, 8) for _ in range(n_layers)
        ])
        self.lm_head = nn.Linear(dim, vocab_size, bias=False)
        
        # Meta-confidence : "à quel point suis-je sûr de cette réponse ?"
        self.meta_confidence = nn.Linear(dim, 3)  # high/medium/low
        
    def forward(self, rh_outputs, rh_confidences, rh_roles, query_hidden):
        """
        rh_outputs: list of [batch, seq, dim] — hidden states finaux de chaque RH
        rh_confidences: [batch, n_rhs]
        rh_roles: [batch, n_rhs, n_roles] — one-hot
        query_hidden: [batch, seq, dim] — requête originale
        """
        # Pondérer les outputs par confiance et priorité
        weighted_outputs = []
        for i, output in enumerate(rh_outputs):
            weight = rh_confidences[:, i:i+1].unsqueeze(-1)  # [batch, 1, 1]
            weighted_outputs.append(output * weight)
        
        # Concaténer tous les outputs
        all_outputs = torch.cat(weighted_outputs, dim=1)  # [batch, n_rhs*seq, dim]
        
        # Cross-attention : la requête "interroge" les réponses des RHs
        attended, attn_weights = self.cross_attention(
            query_hidden, all_outputs, all_outputs
        )
        
        # Détection convergence/divergence
        # Prendre les mean des outputs de chaque RH
        rh_means = torch.cat([o.mean(dim=1) for o in rh_outputs], dim=-1)
        agreement = self.agreement_detector(rh_means)
        
        # Combiner pour la génération
        combined = attended + agreement.unsqueeze(1).expand_as(attended)
        
        for layer in self.generator:
            combined = layer(combined)
        
        logits = self.lm_head(combined)
        confidence = self.meta_confidence(combined.mean(dim=1))
        
        return logits, confidence, attn_weights
```

## 6. LE MODÈLE GLOBAL — FORWARD PASS COMPLET

```python
class MDIRModel(nn.Module):
    """Multi-Depth Iterative Reasoning Model"""
    
    def __init__(self, config):
        super().__init__()
        
        # Backbone : modèle de base (ex: LLaMA-7B)
        self.backbone = load_pretrained_backbone(config.backbone_name)
        self.tap_layers = config.tap_layers  # ex: [4, 12, 24]
        
        # Un Query Translator par tap
        self.qts = nn.ModuleList([
            QueryTranslator(config.backbone_dim, config.rh_dim, depth=i)
            for i in range(len(self.tap_layers))
        ])
        
        # Un Reasoning Head par tap
        self.rhs = nn.ModuleList([
            ReasoningHead(config.rh_dim, config.rh_layers, config.rh_heads, config.vocab_size)
            for _ in range(len(self.tap_layers))
        ])
        
        # Router
        self.router = DynamicRouter(config.backbone_dim, len(self.tap_layers))
        
        # Assembleur
        self.assembler = Assembler(
            config.rh_dim, len(self.tap_layers), 
            config.vocab_size, config.assembler_layers
        )
        
        # Projecteur pour injecter la working memory dans le backbone
        self.wm_projector = nn.Linear(config.rh_dim, config.backbone_dim)
        
    def extract_taps(self, input_ids, attention_mask):
        """Passe la requête dans le backbone et extrait les hidden states
        aux profondeurs tap."""
        hidden_states = []
        x = self.backbone.embed(input_ids)
        
        tap_idx = 0
        for i, layer in enumerate(self.backbone.layers):
            x = layer(x, attention_mask)
            if i + 1 == self.tap_layers[tap_idx]:
                hidden_states.append(x.clone())
                tap_idx += 1
                if tap_idx >= len(self.tap_layers):
                    break
        
        # Compléter si le backbone a plus de layers que le dernier tap
        while tap_idx < len(self.tap_layers):
            for layer in self.backbone.layers[self.tap_layers[tap_idx-1]:self.tap_layers[tap_idx]]:
                x = layer(x, attention_mask)
            hidden_states.append(x.clone())
            tap_idx += 1
            
        return hidden_states
    
    def forward(self, input_ids, attention_mask=None, max_new_tokens=256):
        """Forward pass complet avec itérations."""
        
        # === PHASE 0 : Analyse de la requête ===
        tapped_states = self.extract_taps(input_ids, attention_mask)
        
        # Le router utilise le hidden state le plus profond
        query_embedding = tapped_states[-1].mean(dim=1)  # [batch, dim]
        
        routing = self.router(query_embedding)
        n_iters = routing['n_iterations'].max().item()
        
        # === PHASE 1-N : Itérations de raisonnement ===
        working_memory = WorkingMemory()
        
        for t in range(n_iters):
            rh_outputs = []
            rh_confidences = []
            
            for i, (qt, rh) in enumerate(zip(self.qts, self.rhs)):
                # Traduire le hidden state pour ce RH
                rh_input = qt(tapped_states[i])
                
                # Lire la working memory (outputs des AUTRES RHs au tour précédent)
                wm_context = working_memory.read_for_rh(rh_id=i, current_iter=t)
                if wm_context is not None:
                    # Concaténer le contexte WM à l'input du RH
                    rh_input = torch.cat([rh_input, wm_context], dim=1)
                
                # Appliquer le rôle via modulation
                role = routing['roles'][:, i]  # [batch, n_roles] one-hot
                rh_input = self.apply_role(rh_input, role, i)
                
                # Le RH raisonne
                logits, confidence = rh(rh_input)
                
                rh_outputs.append(rh_input)  # Les hidden states, pas les logits
                rh_confidences.append(confidence)
                
                # Écrire dans la working memory
                working_memory.write(
                    iteration=t, rh_id=i,
                    role=routing['roles'][:, i].argmax(-1).item(),
                    response_hidden=rh_input.detach(),
                    confidence=confidence.item()
                )
            
            # Mettre à jour le router pour l'itération suivante
            iter_context = torch.cat(rh_confidences, dim=-1)
            routing = self.router(query_embedding, iteration_context=iter_context)
            
            # === RE-INJECTION DANS LE BACKBONE (optionnel, pour itérations profondes) ===
            if t < n_iters - 1:
                # Projeter les outputs RH dans l'espace du backbone
                wm_hidden = torch.cat([o.mean(dim=1, keepdim=True) for o in rh_outputs], dim=1)
                wm_projected = self.wm_projector(wm_hidden)
                
                # Ré-extraire les taps avec le contexte enrichi
                enriched_input = torch.cat([
                    self.backbone.embed(input_ids), wm_projected
                ], dim=1)
                tapped_states = self.extract_taps_from_hidden(enriched_input, attention_mask)
        
        # === PHASE FINALE : Assemblage ===
        final_logits, meta_confidence, attn_weights = self.assembler(
            rh_outputs, 
            torch.cat(rh_confidences, dim=-1),
            routing['roles'],
            tapped_states[-1]  # Requête au niveau le plus profond
        )
        
        return {
            'logits': final_logits,
            'meta_confidence': meta_confidence,
            'attention_over_rhs': attn_weights,
            'n_iterations_used': n_iters,
            'rh_confidences': rh_confidences,
            'working_memory': working_memory
        }
    
    def apply_role(self, hidden, role_onehot, rh_idx):
        """Modifie le comportement du RH selon son rôle assigné.
        
        C'est ici que la DIVERSITÉ est forcée :
        - Lead : pas de modification (raisonnement standard)
        - Critic : injection d'un signal adversarial
        - Explorer : bruit dirigé + température haute
        - Verifier : focus sur la cohérence logique
        """
        role_idx = role_onehot.argmax(dim=-1)  # [batch]
        
        # Lead : identité
        # Critic : on inverse certaines dimensions pour forcer le questionnement
        # Explorer : bruit structuré
        # Verifier : on supprime les dimensions les moins certaines
        
        if self.training:
            # Pendant l'entraînement : soft mixing des transformations
            lead_h = hidden
            critic_h = hidden * torch.sign(torch.randn_like(hidden) * 0.3 + 0.7)
            explorer_h = hidden + torch.randn_like(hidden) * hidden.std() * 0.5
            verifier_h = hidden * (hidden.abs() > hidden.abs().median()).float()
            
            all_h = torch.stack([lead_h, critic_h, explorer_h, verifier_h], dim=0)
            # role_onehot: [batch, 4] → [4, batch, 1, 1]
            weights = role_onehot.permute(1, 0).unsqueeze(-1).unsqueeze(-1)
            return (all_h * weights).sum(dim=0)
        else:
            # À l'inférence : sélection dure
            result = hidden.clone()
            for b in range(hidden.size(0)):
                r = role_idx[b].item()
                if r == 1:  # Critic
                    noise = torch.sign(torch.randn_like(hidden[b]) * 0.3 + 0.7)
                    result[b] = hidden[b] * noise
                elif r == 2:  # Explorer
                    result[b] = hidden[b] + torch.randn_like(hidden[b]) * hidden[b].std() * 0.5
                elif r == 3:  # Verifier
                    mask = (hidden[b].abs() > hidden[b].abs().median()).float()
                    result[b] = hidden[b] * mask
            return result
```

## 7. ENTRAÎNEMENT — LE POINT CRITIQUE

### 7.1 Les 4 Loss Functions

```python
class MDIRLoss(nn.Module):
    def __init__(self, lambda_task=1.0, lambda_div=0.3, lambda_role=0.2, lambda_assembly=1.0):
        super().__init__()
        self.lambda_task = lambda_task
        self.lambda_div = lambda_div
        self.lambda_role = lambda_role
        self.lambda_assembly = lambda_assembly
    
    def forward(self, model_output, targets):
        # === 1. TASK LOSS : chaque RH doit produire des réponses utiles ===
        # On entraîne chaque RH à générer la bonne réponse indépendamment
        task_loss = 0
        for i, rh_logits in enumerate(model_output['rh_logits']):
            task_loss += F.cross_entropy(
                rh_logits.view(-1, rh_logits.size(-1)),
                targets.view(-1),
                ignore_index=-100
            )
        task_loss /= len(model_output['rh_logits'])
        
        # === 2. DIVERSITY LOSS : les RHs DOIVENT donner des réponses différentes ===
        # On PÉNALISE la similarité entre distributions de sortie
        div_loss = 0
        rh_distributions = [F.softmax(l, dim=-1) for l in model_output['rh_logits']]
        n_pairs = 0
        for i in range(len(rh_distributions)):
            for j in range(i+1, len(rh_distributions)):
                # KL divergence symétrique (Jensen-Shannon)
                m = (rh_distributions[i] + rh_distributions[j]) / 2
                js_div = (
                    F.kl_div(m.log(), rh_distributions[i], reduction='batchmean') +
                    F.kl_div(m.log(), rh_distributions[j], reduction='batchmean')
                ) / 2
                div_loss -= js_div  # NÉGATIF : on veut MAXIMISER la divergence
                n_pairs += 1
        div_loss /= max(n_pairs, 1)
        
        # === 3. ROLE LOSS : chaque RH doit se comporter selon son rôle ===
        # Lead : proche de la ground truth
        # Critic : doit identifier les erreurs (on a des labels d'erreurs)
        # Explorer : doit être DIFFÉRENT du Lead (mais pas n'importe comment)
        # Verifier : doit donner des confiances calibrées
        role_loss = self.compute_role_loss(model_output)
        
        # === 4. ASSEMBLY LOSS : la réponse finale doit être correcte ===
        assembly_loss = F.cross_entropy(
            model_output['logits'].view(-1, model_output['logits'].size(-1)),
            targets.view(-1),
            ignore_index=-100
        )
        
        total = (
            self.lambda_task * task_loss +
            self.lambda_div * div_loss +
            self.lambda_role * role_loss +
            self.lambda_assembly * assembly_loss
        )
        
        return total, {
            'task': task_loss.item(),
            'diversity': div_loss.item(),
            'role': role_loss.item(),
            'assembly': assembly_loss.item()
        }
    
    def compute_role_loss(self, output):
        """Entraîne chaque RH à jouer son rôle."""
        loss = 0
        roles = output['roles']  # [batch, n_rhs, n_roles]
        
        for i, rh_out in enumerate(output['rh_logits']):
            role = roles[:, i].argmax(-1)  # [batch]
            
            for b in range(role.size(0)):
                r = role[b].item()
                if r == 2:  # Explorer
                    # L'Explorer doit être DIFFÉRENT du Lead
                    lead_idx = (roles[b].argmax(-1) == 0).nonzero()
                    if len(lead_idx) > 0:
                        lead_out = output['rh_logits'][lead_idx[0].item()]
                        # Cosine similarity — on veut la minimiser
                        sim = F.cosine_similarity(
                            rh_out[b].view(1, -1),
                            lead_out[b].view(1, -1)
                        )
                        loss += sim.mean()  # Pénaliser la similarité
                
                elif r == 3:  # Verifier
                    # Le Verifier doit être bien calibré
                    conf = output['rh_confidences'][i][b]
                    actual_accuracy = (rh_out[b].argmax(-1) == output['targets'][b]).float().mean()
                    loss += (conf - actual_accuracy) ** 2  # ECE-like loss
        
        return loss / max(roles.size(0), 1)
```

### 7.2 Stratégie d'Entraînement en 3 Phases

**Phase 1 : Backbone + Taps (50% du budget compute)**
- Geler le backbone pré-entraîné
- Entraîner les QTs + RHs avec task_loss seulement
- Objectif : chaque RH apprend à générer du texte depuis sa profondeur
- Chaque RH est entraîné sur les MÊMES données mais reçoit des hidden states différents
- Résultat : 3 modèles capables de générer du texte, déjà légèrement différents naturellement

**Phase 2 : Diversification (30% du budget compute)**
- Ajouter diversity_loss + role_loss
- Entraîner le Router
- Le Router apprend à attribuer les bons rôles via REINFORCE
  (récompense = qualité de la réponse finale de l'assembleur)
- Augmenter progressivement lambda_div de 0 à 0.3
- Résultat : les RHs se spécialisent dans des styles de raisonnement différents

**Phase 3 : Itérations + Assemblage (20% du budget compute)**
- Entraîner l'Assembleur
- Activer les itérations (commencer à 2, monter à 5-10)
- Fine-tuner le tout end-to-end avec toutes les loss
- Entraîner sur des problèmes qui NÉCESSITENT le raisonnement itératif
  (maths multi-étapes, logique, code debugging)
- Résultat : le système complet fonctionne

## 8. MÉCANISME ANTI-CONVERGENCE : ANALYSE APPROFONDIE

### Pourquoi les Transformers convergent

Le softmax dans l'attention est une moyenne pondérée. 
output = Σ αᵢ · vᵢ  où αᵢ = softmax(qᵢ · kⱼ / √d)

C'est structurellement une INTERPOLATION dans l'espace des values.
On ne peut pas sortir de l'enveloppe convexe des patterns vus pendant l'entraînement.

### Comment MDIR casse ça

**Mécanisme 1 : Composition non-linéaire**
Quand l'Assembleur combine les outputs de RHs qui raisonnent différemment,
il ne fait PAS une moyenne. Il fait une TRANSFORMATION non-linéaire.
Si RM-1 dit "A implique B" et RM-3 dit "B implique C",
l'Assembleur peut déduire "A implique C" — même si cette chaîne
n'existait NULLE PART dans le training data.

**Mécanisme 2 : Le Critic force l'exploration**
Le Critic ne dit pas "la réponse est X". Il dit "la réponse du Lead est FAUSSE parce que Y".
Ce "parce que Y" est une CONTRAINTE NOUVELLE qui n'existait pas dans la requête.
Au tour suivant, le Lead doit satisfaire cette contrainte en plus de la requête originale.
L'espace des solutions se DÉPLACE à chaque itération.

**Mécanisme 3 : L'Explorer avec bruit dirigé**
Le bruit n'est pas aléatoire. C'est :
  h_explorer = h + ε · σ(h) · direction
  
où direction est calculée pour être ORTHOGONALE aux gradients des 
réponses précédentes. On pousse dans des directions que le modèle
n'explore normalement JAMAIS.

**Mécanisme 4 : Accumulation dans la Working Memory**
Au tour 1, tout vient du training data. OK.
Au tour 2, chaque RH répond à ce que les AUTRES ont dit au tour 1.
C'est un stimulus NOUVEAU — les critiques et alternatives des autres RHs.
Au tour 5, le contenu de la WM est suffisamment éloigné du training data
pour que les réponses contiennent de l'information réellement nouvelle.

C'est le même mécanisme que le dialogue humain :
deux personnes qui échangent finissent par dire des choses
qu'aucune n'aurait pensé seule.

### Limites de l'anti-convergence

**Honnêteté** : même avec tout ça, le modèle ne peut pas "inventer" 
des connaissances factuelles qu'il n'a pas. Il peut :
- Combiner des connaissances existantes de manières NOUVELLES
- Déduire des implications que les données ne rendaient pas évidentes  
- Trouver des contre-exemples à ses propres réponses
- Explorer des hypothèses qu'un single-pass model n'explore jamais

Il ne peut PAS :
- Découvrir des faits empiriques (il faut des expériences)
- Prouver des théorèmes fondamentalement nouveaux (probablement)
- Créer de l'information à partir de rien

## 9. ESTIMATION DES COÛTS COMPUTE

Pour un backbone de taille LLaMA-7B (32 layers, 4096 dim) :
- Backbone forward : 1x (référence)
- 3 QTs : ~0.01x chacun (petit MLP) = 0.03x
- 3 RHs (4 layers chacun) : ~0.12x chacun = 0.36x
- Router : ~0.001x
- Assembleur (6 layers) : ~0.18x
- TOTAL PAR ITÉRATION : ~1.57x
- Avec 5 itérations : ~5x le coût d'un forward pass standard

C'est cher mais comparable à ce que fait déjà CoT/ToT.
Et le Router peut décider "1 itération" pour les questions simples → ~1.6x.

## 10. PROCHAINES ÉTAPES POUR IMPLÉMENTER

1. [ ] Choisir un backbone : LLaMA-3.2-1B pour prototyper (petit, rapide)
2. [ ] Implémenter l'extraction de taps (modifier le forward du backbone)
3. [ ] Implémenter QTs + RHs + vérifier que chaque RH peut générer du texte
4. [ ] Implémenter le Router + Working Memory
5. [ ] Implémenter l'Assembleur
6. [ ] Phase 1 d'entraînement : QTs + RHs seuls
7. [ ] Phase 2 : Diversity loss + Router
8. [ ] Phase 3 : Itérations + Assembleur
9. [ ] Évaluation sur des benchmarks de raisonnement (GSM8K, ARC, etc.)
10. [ ] Comparer avec baseline (même backbone, single pass)
