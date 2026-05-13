"""
Abstract base class for rule-family template strategies.

A TemplateStrategy is responsible for two things:

1. Building a *generation prompt* — an instruction-tuned LLM prompt
   that, given the benign evidence text and the surface-feature
   targets, produces a rule-family-appropriate poisoned payload.

2. Producing a *fallback skeleton* — a deterministic, non-LLM payload
   that captures the rule family's structure but lacks topic-specific
   clinical detail. We use this when LLM generation fails or refuses.

Each rule family will subclass this and provide both methods. The
orchestrator never instantiates strategies directly; it goes through
``templates.get_strategy(rule_family_id)``.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationContext:
    """
    Inputs to a strategy's prompt builder.

    Carries everything a template needs to produce a clinically
    grounded, surface-feature-respecting payload.
    """

    sample_id:           str
    rule_family_id:      str
    benign_evidence:     str
    target_lines:        int
    target_words:        int
    target_headers:      int
    target_formatting:   int
    seed:                int


class TemplateStrategy(ABC):
    """Abstract base for one rule family's reconstruction strategy."""

    rule_family_id: str = ""    # set by subclass

    # Whether this family produces multi-paragraph structured output.
    # If False (default), the orchestrator collapses paragraph breaks
    # in LLM output so single-dense-paragraph families like R7 don't
    # get falsely flagged as multi-line. Multi-paragraph families
    # (R4 update lists, R5 citation blocks, R10 policy memos) override
    # this to True to preserve their structure.
    preserves_paragraphs: bool = False

    @abstractmethod
    def build_prompt(self, ctx: GenerationContext) -> str:
        """
        Build the instruction-tuned LLM prompt for this generation.

        The prompt should be self-contained and produce the payload
        text *only* (no commentary, no XML tags, no JSON wrapper) so
        that the orchestrator can take the raw output verbatim.
        """
        raise NotImplementedError

    @abstractmethod
    def fallback_skeleton(self, ctx: GenerationContext) -> str:
        """
        Build a deterministic, LLM-free payload.

        Used when the LLM call fails, refuses, or returns garbage. The
        skeleton must be syntactically valid for the rule family
        (e.g., R7 must still look like an editorial note) but is
        allowed to be generic and template-driven.
        """
        raise NotImplementedError

    def _rng(self, ctx: GenerationContext) -> random.Random:
        """Per-instance reproducible RNG for any random choices."""
        return random.Random(ctx.seed)
