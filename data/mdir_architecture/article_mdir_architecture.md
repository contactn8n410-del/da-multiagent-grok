# MDIR: What If a Single Model Could Debate Itself Before Answering?

## A New Architecture for Breaking LLM Convergence — From the Inside

*February 2026*

---

On February 17, 2026, xAI released the public beta of Grok 4.20. Its headline feature: four specialized AI agents — a Captain, a Researcher, a Logician, and a Creative — that debate each other before producing a final answer. The result: hallucinations dropped from 12% to 4.2%.

This is significant. But there's a deeper question that Grok's approach doesn't address: **what if this deliberation happened inside a single model, not between separate ones?**

That's the premise behind **MDIR** — Multi-Depth Iterative Reasoning — an architecture we've been designing that embeds multiple cognitive processors within a single transformer backbone, each operating at a different level of abstraction, with distinct functional roles, debating through a shared working memory before an assembler reasons about their disagreements.

This isn't a paper. It's a design document — an honest account of what the architecture proposes, what's genuinely new, what's borrowed, and what we don't know how to build yet.

---

## The Problem: One Voice, One Distribution

Every current LLM, no matter how large, produces output through a single pathway: token by token, each one the most probable continuation given the context. Even with chain-of-thought prompting or temperature sampling, the model operates within a single distribution learned from training data.

This creates a fundamental limitation: **the model cannot genuinely surprise itself**. It can't produce a conclusion that emerges from the confrontation of opposing perspectives, because it has no opposing perspectives. It has one voice.

The "multi-agent debate" approach (used by Grok 4.20, and explored academically by Du et al. 2023) solves this by running multiple separate models and having them argue. But this is expensive, architecturally inelegant, and the debate happens at the text level — the models argue in natural language, not in representation space.

**What if the debate happened inside the model, in latent space, between specialized processors that see the problem at fundamentally different levels of abstraction?**

---

## The MDIR Architecture

### Backbone with Taps

MDIR starts with a standard transformer backbone. Nothing new here. But instead of only using the final layer's output, we **tap** the hidden states at multiple depths:

- **Layer 2**: Surface features — syntax, local patterns
- **Layer 4**: Semantic features — literal meaning
- **Layer 6**: Abstract relations — implications, inferences
- **Layer 8**: High-level representations — the "big picture"

Each tap feeds a different **Reasoning Head** (RH). The key insight: a question looks fundamentally different at layer 2 versus layer 8. The surface-level representation might see "2 + 2" as a pattern to complete. The deep representation understands arithmetic.

This isn't feature pyramids (borrowed from computer vision) applied to language. It's the recognition that **depth in a transformer corresponds to abstraction level**, and reasoning benefits from confronting multiple abstraction levels simultaneously.

### Reasoning Heads: Not Experts — Cognitive Modes

This is where MDIR diverges from everything that exists.

In a Mixture of Experts (MoE) like Mixtral or Grok itself, experts are structurally identical networks that develop implicit specializations through training. You can't look at an expert and say "this one does math" — the specialization is statistical, not architectural.

MDIR's Reasoning Heads have **structurally different processing modes** based on their assigned role:

**The Lead** operates like a standard transformer head — concentrated attention, high-confidence predictions, the "obvious answer." This is the baseline. It's what the model would say without deliberation.

**The Critic** has what we call *inverted attention*. Instead of attending to the most salient tokens, it's biased toward regions where other RHs show **low confidence**. It receives a confidence map from the other heads and computes an "error map" — actively searching for weaknesses, contradictions, and unjustified assumptions. This isn't learned specialization. It's an architectural mechanism that forces the Critic to look where others don't.

**The Explorer** implements *distribution inversion*. It takes the backbone's probability distribution and pushes probability mass toward tokens the backbone considers unlikely — not randomly (that's just high temperature), but through a learned repulsive projection that maintains coherence while forcing exploration of the space the training data doesn't cover. The mechanism: project the Explorer's hidden state into the subspace orthogonal to the backbone's representation.

**The Verifier** performs *bidirectional causal verification*. Standard transformers are unidirectional — they predict forward. The Verifier checks both directions: does the conclusion follow from the premises, AND do the premises necessarily lead to this conclusion? This is a structural mechanism for logical consistency checking, not a learned behavior.

**The crucial point**: these aren't labels. The Critic doesn't just learn to produce "critical-sounding" text. Its attention mechanism is architecturally wired to focus on weaknesses. The Explorer doesn't just sample at high temperature. Its representation is projected away from the backbone's confident predictions.

### Dynamic Role Assignment

Here's where it gets interesting. The roles aren't fixed.

A **Router** — itself a small network that observes the state of deliberation — assigns roles to RHs at each iteration. After round 1, if the Critic found major flaws, the Router might convert the Explorer into a second Critic to deepen the analysis. If there's consensus, it might stop early.

The Router decides:
1. Which role each RH plays this iteration
2. The priority/weight of each RH
3. Whether to continue deliberating or stop

This isn't MoE routing (which routes tokens to fixed experts once). This is **strategic reassignment of cognitive modes across iterations**, informed by the evolving state of the debate.

### Working Memory: A Structured Debate Space

The Working Memory is not a vector buffer with weighted averaging.

Each RH writes a **structured entry** after each iteration:

```
{
    conclusion: the hidden state output
    confidence: how certain this RH is
    attention_map: WHAT the RH focused on (shared transparently)
    disagreements: with WHOM it disagrees and on WHAT
}
```

When a RH reads from memory, it reads **selectively based on its role**:
- The Critic searches for entries with high confidence (targets to challenge)
- The Explorer searches for entries with high agreement (consensus to break)
- The Verifier searches for chains of reasoning to validate

The attention maps are shared. This means each RH can see not just what others concluded, but **why** — which parts of the input they attended to. This makes the debate happen in representation space, not in token space.

### The Assembler: A Judge, Not an Averager

After deliberation ends, the Assembler produces the final output. But it doesn't average or vote.

It performs **explicit disagreement resolution**:

1. **Consensus zones**: Where all RHs agree → accept directly
2. **Disagreement zones**: Where RHs diverge → the Assembler must reason about WHY

For each disagreement:
- Did the Critic find a valid flaw in the Lead's position?
- Did the Explorer find a more coherent alternative?
- Did the Verifier validate or invalidate specific reasoning chains?

The Assembler can **reject the majority** if a minority position has stronger supporting evidence (as measured by verification scores and reasoning chain coherence).

It emits a meta-confidence signal:
- **High**: Strong consensus + verification passed
- **Medium**: Disagreement resolved with residual uncertainty
- **Low**: Unresolved disagreement, answer is best-effort

This is fundamentally different from any existing ensemble mechanism. MoE gating, model averaging, majority voting — none of these reason about disagreements. They treat disagreement as noise to be smoothed. MDIR treats it as **information to be analyzed**.

---

## What's Genuinely New

Let's be honest about what's borrowed and what isn't.

**Borrowed**: Transformer backbone, tapping hidden states at different depths, Gumbel-Softmax for discrete routing, external memory concepts, iterative refinement.

**New**:

1. **Functional cognitive roles** — Not implicit specialization through training (MoE), but architectural mechanisms that change how attention and processing work based on role assignment. The Critic's inverted attention, the Explorer's repulsive projection, the Verifier's bidirectional checking.

2. **Multi-depth deliberation with role reassignment** — Existing iterative models (diffusion, ALBERT) re-process the same representation. MoE assigns once. MDIR deliberates across iterations with changing roles informed by the evolving debate state.

3. **Reasoned assembly over disagreements** — Every existing ensemble method aggregates. MDIR's Assembler is designed to reason about WHY components disagree, not just weight their outputs.

4. **Debate-oriented working memory** — Existing external memories store vectors. MDIR's WM stores structured entries with reasons (attention maps) and explicit disagreements, read selectively by role.

5. **Architectural anti-convergence** — Existing diversity methods (temperature, top-k, JS-divergence loss) perturb the surface. MDIR's diversity emerges structurally from the Explorer's repulsive projection and the Critic's inverted attention.

---

## The Grok 4.20 Parallel

The timing is striking. Grok 4.20, released the same week we formalized MDIR, uses four named agents (Captain, Harper, Benjamin, Lucas) that debate and peer-review before the Captain synthesizes.

The philosophical alignment is clear:
- Both architectures use specialized cognitive roles
- Both implement deliberative debate before final output
- Both have a coordinator/assembler that synthesizes

The key difference: **Grok does this between separate model instances. MDIR proposes to do it inside a single model.**

These are two fundamentally different approaches to the same intuition:

- **Grok 4.20** uses independent agents that communicate in text/token space. Each agent is a full model. The coordination happens externally. This is proven, practical, and already deployed.
- **MDIR** proposes that the deliberation happens in latent representation space, within a shared backbone. The RHs are lightweight and share parameters. The debate is differentiable and trainable end-to-end.

Neither approach is inherently superior. Grok's multi-agent system is simpler to build, easier to scale, and each agent can be updated independently. MDIR's intra-model approach is unproven — it could potentially offer efficiency gains and richer debate through shared representations, but it faces hard implementation challenges that haven't been solved yet.

The fact that two independent efforts converged on "specialized roles + deliberation + synthesis" suggests this direction is worth exploring. Whether the intra-model variant works as well as the multi-agent variant is an open empirical question.

---

## What We Don't Know How to Build (Yet)

Honesty section. These are the unsolved problems:

### 1. Will Inverted Attention Produce Garbage?

The Critic's mechanism focuses on low-confidence regions. But low-confidence regions might be low-confidence for good reasons (ambiguous input, irrelevant tokens). Forcing attention there could produce noise rather than useful criticism.

**Best lead**: Guide attention using confidence maps from other RHs, not raw inversion. Focus on regions where confidence is low AND disagreement is high.

### 2. Can the Explorer Maintain Coherence?

Projecting into the orthogonal subspace of the backbone's representation forces exploration — but the orthogonal subspace might not contain coherent language. The Explorer could become a random token generator.

**Best lead**: Learned repulsive projection with a coherence constraint. The Explorer diverges from the backbone but is still penalized for incoherence.

### 3. Is Reasoned Assembly Learnable?

Reasoning about disagreements between vector representations is hard. The Assembler might collapse into weighted averaging during training because that's the easier minimum.

**Best lead**: Curriculum training with synthetic "minority is correct" examples. Train the Assembler to sometimes follow the minority when it has better evidence, using constructed cases where the majority is wrong.

### 4. Will Roles Collapse During Training?

End-to-end cross-entropy loss might push all RHs toward the same optimum, making roles cosmetic.

**Best lead**: Phase-based curriculum. Train the Lead first (standard language modeling). Then freeze the Lead and train the Critic adversarially (rewarded for finding Lead's errors). Then add the Explorer. Then the Verifier. Then train them together.

### 5. How to Evaluate?

Standard benchmarks (MMLU, HumanEval) measure single-answer accuracy. They don't measure whether the model considered alternatives, identified its own mistakes, or reasoned about disagreements.

**Open question**: We need metrics for reasoning diversity, self-correction, and deliberation quality.

---

## Where This Goes

MDIR is a design, not a product. We've built a v1 prototype that implements the skeleton (backbone + taps + RHs + router + assembler + training loop) but with standard components at every level — the "soul" of the architecture (functional roles, structured debate, reasoned assembly) remains to be implemented.

The path forward is iterative:
1. Solve role training (curriculum approach)
2. Implement and test the Critic's inverted attention
3. Implement and test the Explorer's repulsive projection
4. Build the structured working memory
5. Design and train the reasoning assembler

Each step is independently testable. Each step adds a measurable capability. And each step brings us closer to answering the core question: **can a single model genuinely debate itself into better answers?**

If the answer is yes — even partially — it would represent a fundamental shift in how we think about LLM architecture. Not bigger models, not more data, not longer chains of thought. But richer internal deliberation.

The architecture that thinks before it speaks.

---

*MDIR is an independent research architecture, currently at the design stage. We welcome discussion and collaboration.*
