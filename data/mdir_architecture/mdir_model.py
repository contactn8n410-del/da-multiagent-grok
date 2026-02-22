"""
MDIR — Multi-Depth Iterative Reasoning
Prototype implementation using PyTorch

Architecture designed by user, formalized and implemented here.
2026-02-22
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
import math


# ============================================================
# CONFIG
# ============================================================

@dataclass
class MDIRConfig:
    # Backbone
    backbone_dim: int = 768       # Hidden dim of backbone (small for prototype)
    backbone_layers: int = 12     # Total layers in backbone
    n_heads: int = 12             # Attention heads in backbone
    vocab_size: int = 32000       # Vocabulary size
    max_seq_len: int = 512
    
    # Taps (where to extract hidden states)
    tap_layers: tuple = (4, 8, 12)   # After which layers to tap
    
    # Reasoning Heads
    rh_dim: int = 512             # Hidden dim for reasoning heads
    rh_layers: int = 4            # Layers per reasoning head
    rh_heads: int = 8             # Attention heads per RH
    
    # Router
    n_roles: int = 4              # lead, critic, explorer, verifier
    max_iterations: int = 10
    
    # Assembler
    assembler_layers: int = 6
    
    # Training
    diversity_lambda: float = 0.3
    role_lambda: float = 0.2


# ============================================================
# BUILDING BLOCKS
# ============================================================

class RMSNorm(nn.Module):
    def __init__(self, dim, eps=1e-6):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))
    
    def forward(self, x):
        norm = torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)
        return x * norm * self.weight


class RotaryEmbedding(nn.Module):
    def __init__(self, dim, max_seq_len=512):
        super().__init__()
        inv_freq = 1.0 / (10000 ** (torch.arange(0, dim, 2).float() / dim))
        self.register_buffer('inv_freq', inv_freq)
        self.max_seq_len = max_seq_len
    
    def forward(self, seq_len):
        t = torch.arange(seq_len, device=self.inv_freq.device).float()
        freqs = torch.einsum('i,j->ij', t, self.inv_freq)
        return torch.cat([freqs, freqs], dim=-1)


def rotate_half(x):
    x1, x2 = x.chunk(2, dim=-1)
    return torch.cat([-x2, x1], dim=-1)


def apply_rotary_emb(x, freqs):
    cos = freqs.cos().unsqueeze(0).unsqueeze(0)  # [1, 1, seq, dim]
    sin = freqs.sin().unsqueeze(0).unsqueeze(0)
    return x * cos + rotate_half(x) * sin


class Attention(nn.Module):
    def __init__(self, dim, n_heads):
        super().__init__()
        self.n_heads = n_heads
        self.head_dim = dim // n_heads
        
        self.q_proj = nn.Linear(dim, dim, bias=False)
        self.k_proj = nn.Linear(dim, dim, bias=False)
        self.v_proj = nn.Linear(dim, dim, bias=False)
        self.o_proj = nn.Linear(dim, dim, bias=False)
        
        self.rotary = RotaryEmbedding(self.head_dim)
    
    def forward(self, x, mask=None):
        B, S, D = x.shape
        
        q = self.q_proj(x).view(B, S, self.n_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, S, self.n_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, S, self.n_heads, self.head_dim).transpose(1, 2)
        
        freqs = self.rotary(S).to(x.device)
        q = apply_rotary_emb(q, freqs)
        k = apply_rotary_emb(k, freqs)
        
        # Scaled dot product attention
        attn = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        if mask is not None:
            attn = attn.masked_fill(mask == 0, float('-inf'))
        attn = F.softmax(attn, dim=-1)
        
        out = torch.matmul(attn, v)
        out = out.transpose(1, 2).contiguous().view(B, S, D)
        return self.o_proj(out)


class FeedForward(nn.Module):
    def __init__(self, dim, hidden_dim=None):
        super().__init__()
        hidden_dim = hidden_dim or dim * 4
        self.gate = nn.Linear(dim, hidden_dim, bias=False)
        self.up = nn.Linear(dim, hidden_dim, bias=False)
        self.down = nn.Linear(hidden_dim, dim, bias=False)
    
    def forward(self, x):
        return self.down(F.silu(self.gate(x)) * self.up(x))


class TransformerBlock(nn.Module):
    def __init__(self, dim, n_heads):
        super().__init__()
        self.norm1 = RMSNorm(dim)
        self.attn = Attention(dim, n_heads)
        self.norm2 = RMSNorm(dim)
        self.ff = FeedForward(dim)
    
    def forward(self, x, mask=None):
        x = x + self.attn(self.norm1(x), mask)
        x = x + self.ff(self.norm2(x))
        return x


# ============================================================
# MDIR COMPONENTS
# ============================================================

class QueryTranslator(nn.Module):
    """Projects backbone hidden states at a given depth
    into the reasoning head's input space.
    
    Each depth captures different features:
    - Shallow: syntactic patterns, surface associations
    - Mid: logical structure, entity relations
    - Deep: abstract semantics, complex reasoning
    
    The QT adapts the projection to what each depth provides.
    """
    
    def __init__(self, backbone_dim: int, rh_dim: int, depth_index: int):
        super().__init__()
        self.proj = nn.Sequential(
            nn.Linear(backbone_dim, rh_dim * 2),
            nn.GELU(),
            nn.Linear(rh_dim * 2, rh_dim),
            RMSNorm(rh_dim)
        )
        # Learned depth embedding — the RH knows which abstraction level it's at
        self.depth_embed = nn.Parameter(torch.randn(1, 1, rh_dim) * 0.02)
        self.depth_index = depth_index
    
    def forward(self, hidden_state: torch.Tensor) -> torch.Tensor:
        projected = self.proj(hidden_state)
        return projected + self.depth_embed


class ReasoningHead(nn.Module):
    """Small transformer that can independently generate text
    from a projected hidden state.
    
    Each RH is trained with a potentially different objective,
    creating diversity in reasoning approaches.
    """
    
    def __init__(self, dim: int, n_layers: int, n_heads: int, vocab_size: int):
        super().__init__()
        self.layers = nn.ModuleList([
            TransformerBlock(dim, n_heads) for _ in range(n_layers)
        ])
        self.norm = RMSNorm(dim)
        self.lm_head = nn.Linear(dim, vocab_size, bias=False)
        self.confidence_head = nn.Sequential(
            nn.Linear(dim, dim // 4),
            nn.GELU(),
            nn.Linear(dim // 4, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None):
        for layer in self.layers:
            x = layer(x, mask)
        
        h = self.norm(x)
        logits = self.lm_head(h)
        confidence = self.confidence_head(h.mean(dim=1))  # [batch, 1]
        
        return logits, confidence, h  # Return hidden states for WM


class DynamicRouter(nn.Module):
    """Analyzes the query and dynamically assigns:
    - A role to each Reasoning Head (Lead/Critic/Explorer/Verifier)
    - A priority score per RH
    - Number of iterations needed
    
    Updates its decisions at each iteration based on RH confidences.
    """
    
    ROLE_NAMES = ['lead', 'critic', 'explorer', 'verifier']
    
    def __init__(self, input_dim: int, n_rhs: int, n_roles: int = 4, max_iters: int = 10):
        super().__init__()
        self.n_rhs = n_rhs
        self.n_roles = n_roles
        
        hidden = input_dim // 2
        
        self.query_encoder = nn.Sequential(
            nn.Linear(input_dim, hidden),
            nn.GELU(),
            nn.Linear(hidden, hidden),
            RMSNorm(hidden)
        )
        
        # Role assignment: for each RH, probability over roles
        self.role_head = nn.Linear(hidden, n_rhs * n_roles)
        
        # Priority scores
        self.priority_head = nn.Linear(hidden, n_rhs)
        
        # Iteration count predictor
        self.iter_head = nn.Linear(hidden, max_iters)
        
        # Iterative update: GRU that takes previous RH confidences
        self.iter_gru = nn.GRUCell(hidden + n_rhs, hidden)
        
        self._hidden = hidden
    
    def forward(
        self, 
        query_embed: torch.Tensor,
        prev_confidences: Optional[torch.Tensor] = None,
        prev_state: Optional[torch.Tensor] = None,
        temperature: float = 0.5
    ) -> Dict[str, torch.Tensor]:
        
        h = self.query_encoder(query_embed)  # [batch, hidden]
        
        # Update state if we have previous iteration context
        if prev_confidences is not None and prev_state is not None:
            gru_input = torch.cat([h, prev_confidences], dim=-1)
            h = self.iter_gru(gru_input, prev_state)
        
        # Role assignment with Gumbel-Softmax for discrete but differentiable selection
        role_logits = self.role_head(h).view(-1, self.n_rhs, self.n_roles)
        
        if self.training:
            roles = F.gumbel_softmax(role_logits, tau=temperature, hard=True)
        else:
            roles = F.one_hot(role_logits.argmax(dim=-1), self.n_roles).float()
        
        role_probs = F.softmax(role_logits, dim=-1)
        
        # Priority scores
        priorities = torch.sigmoid(self.priority_head(h))
        
        # Iteration count
        iter_logits = self.iter_head(h)
        if self.training:
            n_iters = F.gumbel_softmax(iter_logits, tau=1.0, hard=True).argmax(-1) + 1
        else:
            n_iters = iter_logits.argmax(dim=-1) + 1
        
        return {
            'roles': roles,
            'role_probs': role_probs,
            'priorities': priorities,
            'n_iterations': n_iters,
            'state': h  # Pass to next iteration
        }


class RoleModulator(nn.Module):
    """Modulates a Reasoning Head's hidden states based on its assigned role.
    
    This is WHERE diversity is enforced at inference time:
    - Lead: standard processing
    - Critic: adversarial signal injection
    - Explorer: directed noise to escape attraction basins
    - Verifier: certainty-focused filtering
    """
    
    def __init__(self, dim: int, n_roles: int = 4):
        super().__init__()
        # Learned role-specific transformations
        self.role_transforms = nn.ModuleList([
            nn.Sequential(nn.Linear(dim, dim), nn.Tanh())
            for _ in range(n_roles)
        ])
        # Scale factor per role (learned)
        self.role_scales = nn.Parameter(torch.ones(n_roles))
    
    def forward(
        self, 
        hidden: torch.Tensor,      # [batch, seq, dim]
        role_onehot: torch.Tensor,  # [batch, n_roles]
    ) -> torch.Tensor:
        
        B, S, D = hidden.shape
        
        if self.training:
            # Soft mixing during training for gradient flow
            transformed = torch.stack(
                [transform(hidden) * self.role_scales[i] 
                 for i, transform in enumerate(self.role_transforms)],
                dim=0
            )  # [n_roles, batch, seq, dim]
            
            weights = role_onehot.permute(1, 0).unsqueeze(-1).unsqueeze(-1)
            # [n_roles, batch, 1, 1]
            return (transformed * weights).sum(dim=0)
        else:
            # Hard selection at inference
            role_idx = role_onehot.argmax(dim=-1)
            result = hidden.clone()
            for b in range(B):
                r = role_idx[b].item()
                result[b] = self.role_transforms[r](hidden[b]) * self.role_scales[r]
            return result


class WorkingMemory:
    """External memory that accumulates RH responses across iterations.
    
    This is where NOVEL information (beyond training data) is created:
    - At t=1, each RH responds from training knowledge
    - At t=2+, each RH responds to what OTHERS said — new stimulus
    - By t=5+, the internal conversation has diverged enough from
      training data to produce genuinely new combinations
    """
    
    def __init__(self, max_slots: int = 50):
        self.max_slots = max_slots
        self.slots: List[Dict] = []
    
    def write(
        self, 
        iteration: int, 
        rh_id: int, 
        role: int,
        hidden: torch.Tensor,   # [batch, seq, dim]
        confidence: float
    ):
        self.slots.append({
            'iter': iteration,
            'rh': rh_id,
            'role': role,
            'hidden': hidden.detach(),
            'confidence': confidence
        })
        
        if len(self.slots) > self.max_slots:
            # Keep most recent and most confident
            self.slots.sort(
                key=lambda s: (s['iter'] * 10 + s['confidence']), 
                reverse=True
            )
            self.slots = self.slots[:self.max_slots]
    
    def read_for_rh(self, rh_id: int, current_iter: int) -> Optional[torch.Tensor]:
        """A RH reads outputs from OTHER RHs at the previous iteration."""
        relevant = [
            s for s in self.slots 
            if s['rh'] != rh_id and s['iter'] == current_iter - 1
        ]
        if not relevant:
            return None
        
        # Average the hidden states of other RHs (weighted by confidence)
        total_conf = sum(s['confidence'] for s in relevant)
        if total_conf == 0:
            return None
        
        weighted = sum(
            s['hidden'] * (s['confidence'] / total_conf) 
            for s in relevant
        )
        return weighted
    
    def read_all_for_assembly(self) -> Tuple[List[torch.Tensor], List[Dict]]:
        """The Assembler reads everything."""
        hiddens = [s['hidden'] for s in self.slots]
        metadata = [
            {'iter': s['iter'], 'rh': s['rh'], 'role': s['role'], 'conf': s['confidence']}
            for s in self.slots
        ]
        return hiddens, metadata
    
    def clear(self):
        self.slots.clear()


class Assembler(nn.Module):
    """Does NOT average responses. Reasons ABOUT them.
    
    Two phases:
    1. Structural analysis: convergences, divergences, confidence patterns
    2. Generation: produces final answer conditioned on the analysis
    """
    
    def __init__(self, dim: int, n_rhs: int, vocab_size: int, n_layers: int = 6):
        super().__init__()
        
        # Cross-attention: query attends to all RH outputs
        self.cross_attn_layers = nn.ModuleList([
            nn.MultiheadAttention(dim, 8, batch_first=True)
            for _ in range(2)
        ])
        self.cross_norms = nn.ModuleList([RMSNorm(dim) for _ in range(2)])
        
        # Agreement/Disagreement detector
        self.agreement_net = nn.Sequential(
            nn.Linear(dim * n_rhs, dim * 2),
            nn.GELU(),
            nn.Linear(dim * 2, dim),
            RMSNorm(dim)
        )
        
        # Final generation layers
        self.gen_layers = nn.ModuleList([
            TransformerBlock(dim, 8) for _ in range(n_layers)
        ])
        self.gen_norm = RMSNorm(dim)
        self.lm_head = nn.Linear(dim, vocab_size, bias=False)
        
        # Meta-confidence: how sure is the system overall?
        self.meta_conf = nn.Sequential(
            nn.Linear(dim, dim // 4),
            nn.GELU(),
            nn.Linear(dim // 4, 3)  # high / medium / low
        )
    
    def forward(
        self,
        rh_hiddens: List[torch.Tensor],    # List of [batch, seq, dim]
        rh_confidences: torch.Tensor,       # [batch, n_rhs]
        rh_roles: torch.Tensor,             # [batch, n_rhs, n_roles]
        query_hidden: torch.Tensor,         # [batch, seq, dim]
    ):
        B = query_hidden.size(0)
        
        # Weight RH outputs by confidence
        weighted = []
        for i, h in enumerate(rh_hiddens):
            w = rh_confidences[:, i:i+1].unsqueeze(-1)  # [B, 1, 1]
            weighted.append(h * w)
        
        # Concatenate all RH outputs as KV for cross-attention
        all_kv = torch.cat(weighted, dim=1)  # [B, n_rhs * seq, dim]
        
        # Cross-attention: query interrogates RH responses
        x = query_hidden
        for cross_attn, norm in zip(self.cross_attn_layers, self.cross_norms):
            residual = x
            x = norm(x)
            x, attn_weights = cross_attn(x, all_kv, all_kv)
            x = x + residual
        
        # Agreement detection
        rh_summaries = torch.cat(
            [h.mean(dim=1) for h in rh_hiddens], dim=-1
        )  # [B, n_rhs * dim]
        agreement_signal = self.agreement_net(rh_summaries)  # [B, dim]
        
        # Inject agreement signal
        x = x + agreement_signal.unsqueeze(1).expand_as(x)
        
        # Generate final answer
        for layer in self.gen_layers:
            x = layer(x)
        
        x = self.gen_norm(x)
        logits = self.lm_head(x)
        
        meta_confidence = self.meta_conf(x.mean(dim=1))
        
        return logits, meta_confidence, attn_weights


# ============================================================
# FULL MODEL
# ============================================================

class MDIRModel(nn.Module):
    """Multi-Depth Iterative Reasoning Model
    
    A transformer backbone with multiple reasoning heads at different depths,
    dynamic role assignment, iterative deliberation via working memory,
    and a final assembler that reasons about the RHs' outputs.
    """
    
    def __init__(self, config: MDIRConfig):
        super().__init__()
        self.config = config
        
        # === Backbone ===
        self.embed = nn.Embedding(config.vocab_size, config.backbone_dim)
        self.backbone_layers = nn.ModuleList([
            TransformerBlock(config.backbone_dim, config.n_heads)
            for _ in range(config.backbone_layers)
        ])
        
        n_taps = len(config.tap_layers)
        
        # === Query Translators ===
        self.qts = nn.ModuleList([
            QueryTranslator(config.backbone_dim, config.rh_dim, depth_index=i)
            for i in range(n_taps)
        ])
        
        # === Reasoning Heads ===
        self.rhs = nn.ModuleList([
            ReasoningHead(config.rh_dim, config.rh_layers, config.rh_heads, config.vocab_size)
            for _ in range(n_taps)
        ])
        
        # === Role Modulators ===
        self.role_modulators = nn.ModuleList([
            RoleModulator(config.rh_dim, config.n_roles)
            for _ in range(n_taps)
        ])
        
        # === Router ===
        self.router = DynamicRouter(
            config.backbone_dim, n_taps, config.n_roles, config.max_iterations
        )
        
        # === Assembler ===
        self.assembler = Assembler(
            config.rh_dim, n_taps, config.vocab_size, config.assembler_layers
        )
        
        # === WM → Backbone projector (for iterative re-injection) ===
        self.wm_to_backbone = nn.Linear(config.rh_dim, config.backbone_dim)
        
        # Initialize
        self.apply(self._init_weights)
        self._count_params()
    
    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
    
    def _count_params(self):
        total = sum(p.numel() for p in self.parameters())
        backbone = sum(p.numel() for p in self.backbone_layers.parameters()) + \
                   sum(p.numel() for p in self.embed.parameters())
        rhs = sum(p.numel() for p in self.rhs.parameters())
        rest = total - backbone - rhs
        
        self._param_counts = {
            'total': total,
            'backbone': backbone,
            'reasoning_heads': rhs,
            'infrastructure': rest
        }
    
    @property
    def param_counts(self):
        return self._param_counts
    
    def extract_taps(
        self, 
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        extra_context: Optional[torch.Tensor] = None
    ) -> List[torch.Tensor]:
        """Run backbone and extract hidden states at tap points."""
        
        x = self.embed(input_ids)
        
        if extra_context is not None:
            x = torch.cat([x, extra_context], dim=1)
        
        tapped = []
        tap_idx = 0
        
        for i, layer in enumerate(self.backbone_layers):
            x = layer(x, attention_mask)
            
            if tap_idx < len(self.config.tap_layers) and (i + 1) == self.config.tap_layers[tap_idx]:
                tapped.append(x.clone())
                tap_idx += 1
        
        return tapped
    
    def forward(
        self, 
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        targets: Optional[torch.Tensor] = None,
        force_iterations: Optional[int] = None,
    ) -> Dict[str, torch.Tensor]:
        """Full forward pass with iterative reasoning.
        
        1. Backbone extracts hidden states at multiple depths
        2. Router assigns roles and iteration count
        3. For each iteration:
           a. Each RH reasons independently (modulated by role)
           b. Outputs go to Working Memory
           c. Next iteration reads WM for cross-RH communication
        4. Assembler produces final output
        """
        
        B = input_ids.size(0)
        n_taps = len(self.config.tap_layers)
        
        # === Step 0: Extract tapped hidden states ===
        tapped = self.extract_taps(input_ids, attention_mask)
        
        # Query embedding for router (deepest tap, mean pooled)
        query_embed = tapped[-1].mean(dim=1)  # [B, backbone_dim]
        
        # === Step 1: Router decides roles and iterations ===
        routing = self.router(query_embed)
        
        if force_iterations is not None:
            n_iters = force_iterations
        else:
            n_iters = routing['n_iterations'].max().item()
            n_iters = min(n_iters, self.config.max_iterations)
        
        # === Step 2: Iterative reasoning ===
        working_memory = WorkingMemory()
        all_rh_logits = [[] for _ in range(n_taps)]  # Track all iterations
        
        for t in range(n_iters):
            rh_hiddens = []
            rh_logits_t = []
            rh_confidences_t = []
            
            for i in range(n_taps):
                # Translate hidden state for this RH
                rh_input = self.qts[i](tapped[i])
                
                # Read working memory (what OTHER RHs said last iteration)
                wm_context = working_memory.read_for_rh(rh_id=i, current_iter=t)
                if wm_context is not None:
                    # Inject WM context by concatenating to sequence
                    # This is the NEW information the RH hasn't seen before
                    rh_input = torch.cat([rh_input, wm_context], dim=1)
                
                # Apply role modulation
                role = routing['roles'][:, i]  # [B, n_roles]
                rh_input = self.role_modulators[i](rh_input, role)
                
                # RH reasons
                logits, confidence, hidden = self.rhs[i](rh_input)
                
                rh_hiddens.append(hidden)
                rh_logits_t.append(logits)
                rh_confidences_t.append(confidence.squeeze(-1))
                
                all_rh_logits[i].append(logits)
                
                # Write to working memory
                working_memory.write(
                    iteration=t, rh_id=i,
                    role=routing['roles'][:, i].argmax(-1).item() if B == 1 else 0,
                    hidden=hidden,
                    confidence=confidence.mean().item()
                )
            
            # Update router for next iteration
            confidences = torch.stack(rh_confidences_t, dim=-1)  # [B, n_rhs]
            routing = self.router(
                query_embed, 
                prev_confidences=confidences,
                prev_state=routing['state']
            )
            
            # Re-inject into backbone for next iteration (if not last)
            if t < n_iters - 1:
                # Summarize RH outputs and project back to backbone space
                rh_summary = torch.cat(
                    [h.mean(dim=1, keepdim=True) for h in rh_hiddens], dim=1
                )  # [B, n_taps, rh_dim]
                extra_context = self.wm_to_backbone(rh_summary)  # [B, n_taps, backbone_dim]
                tapped = self.extract_taps(input_ids, attention_mask, extra_context)
        
        # === Step 3: Assembly ===
        final_confidences = torch.stack(rh_confidences_t, dim=-1)
        
        final_logits, meta_confidence, attn_weights = self.assembler(
            rh_hiddens,
            final_confidences,
            routing['roles'],
            self.qts[-1](tapped[-1])  # Query in RH space for assembly
        )
        
        result = {
            'logits': final_logits,
            'meta_confidence': meta_confidence,
            'rh_confidences': final_confidences,
            'n_iterations': n_iters,
            'routing': routing,
            'attn_weights': attn_weights,
        }
        
        # === Compute loss if targets provided ===
        if targets is not None:
            result['loss'], result['loss_components'] = self.compute_loss(
                final_logits, all_rh_logits, routing, final_confidences, targets
            )
        
        return result
    
    def compute_loss(self, final_logits, all_rh_logits, routing, confidences, targets):
        """Combined loss: task + diversity + role + assembly."""
        
        cfg = self.config
        
        # 1. Assembly loss (primary) — trim to target length
        seq_len_out = min(final_logits.size(1), targets.size(1))
        assembly_loss = F.cross_entropy(
            final_logits[:, :seq_len_out].reshape(-1, final_logits.size(-1)),
            targets[:, :seq_len_out].reshape(-1),
            ignore_index=-100
        )
        
        # 2. Task loss per RH (each should produce useful outputs)
        task_loss = 0
        count = 0
        for i in range(len(all_rh_logits)):
            for t_logits in all_rh_logits[i]:
                # Only compute loss on the original sequence length
                seq_len = min(t_logits.size(1), targets.size(1))
                task_loss += F.cross_entropy(
                    t_logits[:, :seq_len].reshape(-1, t_logits.size(-1)),
                    targets[:, :seq_len].reshape(-1),
                    ignore_index=-100
                )
                count += 1
        task_loss /= max(count, 1)
        
        # 3. Diversity loss (penalize similarity between RH outputs)
        div_loss = torch.tensor(0.0, device=final_logits.device)
        if len(all_rh_logits) > 1:
            # Use last iteration's logits
            last_logits = [rh[-1] for rh in all_rh_logits]
            n_pairs = 0
            for i in range(len(last_logits)):
                for j in range(i + 1, len(last_logits)):
                    seq_len = min(last_logits[i].size(1), last_logits[j].size(1))
                    pi = F.softmax(last_logits[i][:, :seq_len], dim=-1)
                    pj = F.softmax(last_logits[j][:, :seq_len], dim=-1)
                    
                    # Jensen-Shannon divergence (we want to MAXIMIZE it)
                    m = (pi + pj) / 2
                    js = (
                        F.kl_div(m.log(), pi, reduction='batchmean') +
                        F.kl_div(m.log(), pj, reduction='batchmean')
                    ) / 2
                    div_loss -= js  # Negative: we want MORE divergence
                    n_pairs += 1
            div_loss /= max(n_pairs, 1)
        
        # 4. Role loss (Explorer should differ from Lead)
        role_loss = torch.tensor(0.0, device=final_logits.device)
        roles = routing['roles']  # [B, n_rhs, n_roles]
        if len(all_rh_logits) >= 2:
            last_logits = [rh[-1] for rh in all_rh_logits]
            for i in range(roles.size(1)):
                role_idx = roles[:, i].argmax(-1)  # [B]
                if (role_idx == 2).any():  # Explorer
                    for j in range(roles.size(1)):
                        if (roles[:, j].argmax(-1) == 0).any():  # Lead
                            seq_len = min(last_logits[i].size(1), last_logits[j].size(1))
                            sim = F.cosine_similarity(
                                last_logits[i][:, :seq_len].reshape(last_logits[i].size(0), -1),
                                last_logits[j][:, :seq_len].reshape(last_logits[j].size(0), -1),
                                dim=-1
                            )
                            role_loss += sim.mean()
        
        total = (
            assembly_loss + 
            task_loss +
            cfg.diversity_lambda * div_loss +
            cfg.role_lambda * role_loss
        )
        
        return total, {
            'assembly': assembly_loss.item(),
            'task': task_loss.item(),
            'diversity': div_loss.item(),
            'role': role_loss.item(),
            'total': total.item()
        }
    
    @torch.no_grad()
    def generate(
        self, 
        input_ids: torch.Tensor,
        max_new_tokens: int = 128,
        temperature: float = 0.7,
        force_iterations: Optional[int] = None,
    ) -> Dict:
        """Autoregressive generation with MDIR."""
        
        self.eval()
        generated = input_ids.clone()
        
        for step in range(max_new_tokens):
            output = self.forward(
                generated, 
                force_iterations=force_iterations
            )
            
            # Sample from final logits
            next_logits = output['logits'][:, -1, :] / temperature
            probs = F.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            
            generated = torch.cat([generated, next_token], dim=1)
            
            # Check for EOS (assuming token 2 = EOS)
            if (next_token == 2).all():
                break
        
        return {
            'tokens': generated,
            'meta_confidence': output['meta_confidence'],
            'n_iterations': output['n_iterations'],
            'rh_confidences': output['rh_confidences']
        }


# ============================================================
# QUICK TEST
# ============================================================

def test_mdir():
    """Quick sanity check that the model runs."""
    
    config = MDIRConfig(
        backbone_dim=256,
        backbone_layers=12,
        n_heads=4,
        vocab_size=1000,
        max_seq_len=64,
        tap_layers=(4, 8, 12),
        rh_dim=192,
        rh_layers=2,
        rh_heads=4,
        assembler_layers=3,
    )
    
    model = MDIRModel(config)
    
    print(f"=== MDIR Model ===")
    print(f"Total parameters: {model.param_counts['total']:,}")
    print(f"  Backbone:         {model.param_counts['backbone']:,}")
    print(f"  Reasoning Heads:  {model.param_counts['reasoning_heads']:,}")
    print(f"  Infrastructure:   {model.param_counts['infrastructure']:,}")
    print()
    
    # Test forward pass
    batch_size = 2
    seq_len = 32
    input_ids = torch.randint(0, 1000, (batch_size, seq_len))
    targets = torch.randint(0, 1000, (batch_size, seq_len))
    
    print("Testing forward pass (2 iterations)...")
    output = model(input_ids, targets=targets, force_iterations=2)
    
    print(f"  Output logits shape:  {output['logits'].shape}")
    print(f"  Meta confidence:      {output['meta_confidence']}")
    print(f"  RH confidences:       {output['rh_confidences']}")
    print(f"  Iterations used:      {output['n_iterations']}")
    print(f"  Loss:                 {output['loss'].item():.4f}")
    print(f"  Loss components:      {output['loss_components']}")
    print()
    
    print("Testing generation...")
    gen_output = model.generate(input_ids[:1, :8], max_new_tokens=16, force_iterations=2)
    print(f"  Generated shape: {gen_output['tokens'].shape}")
    print(f"  Meta confidence: {gen_output['meta_confidence']}")
    
    print("\n✅ All tests passed!")
    return model


if __name__ == "__main__":
    test_mdir()
