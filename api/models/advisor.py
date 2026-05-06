"""
Data models for Advisor (Tool A) — content quality evaluation.

Spec: /Users/davemini2/.claude/plans/moonlit-beaming-thacker.md
"""

from dataclasses import dataclass, field


@dataclass
class AdvisorRequest:
    """Input to Advisor evaluation."""
    url: str | None = None
    content: str | None = None
    original_content: str | None = None
    job_id: str | None = None  # Optional: for cached content fallback

    def __post_init__(self):
        if not self.url and not self.content:
            raise ValueError("Either url or content must be provided")


@dataclass
class Finding:
    """A single finding with citation."""
    text: str
    citation: str | None = None
    is_specific: bool | None = None
    issue: str | None = None


@dataclass
class Section:
    """Self-containment per H2/H3 section."""
    heading: str
    can_stand_alone: bool
    requires_context: list[str] = field(default_factory=list)


@dataclass
class StructuralMismatch:
    """Where prose doesn't match structure."""
    pattern: str
    location: str


@dataclass
class CitationFinding:
    """Authority signal finding."""
    text: str
    source: str | None = None
    issue: str | None = None


@dataclass
class PlaceholderFinding:
    """Placeholder analysis."""
    text: str
    gap_type: str | None = None
    reason: str | None = None


@dataclass
class SourceFidelity:
    """Comparison findings (only if original provided)."""
    is_critical: bool
    fabrications: list[str] = field(default_factory=list)
    losses: list[str] = field(default_factory=list)
    degradations: list[str] = field(default_factory=list)
    preserved_strengths: list[str] = field(default_factory=list)


@dataclass
class FactualGrounding:
    """Factual grounding assessment."""
    is_critical: bool
    specific_facts: list[Finding] = field(default_factory=list)
    generalities: list[Finding] = field(default_factory=list)
    verdict: str = "minimal"  # grounded | weak | minimal


@dataclass
class SelfContainment:
    """Self-containment analysis."""
    sections: list[Section] = field(default_factory=list)


@dataclass
class StructuralFitness:
    """Structural fitness analysis."""
    mismatches: list[StructuralMismatch] = field(default_factory=list)
    unnecessary_structure: list[StructuralMismatch] = field(default_factory=list)


@dataclass
class AuthoritySignals:
    """Authority and attribution signals."""
    citations_present: list[CitationFinding] = field(default_factory=list)
    citations_missing: list[dict] = field(default_factory=list)
    placeholder_citations: list[CitationFinding] = field(default_factory=list)


@dataclass
class HonestPlaceholders:
    """Placeholder honesty analysis."""
    at_real_gaps: list[PlaceholderFinding] = field(default_factory=list)
    decorative: list[PlaceholderFinding] = field(default_factory=list)


@dataclass
class AdvisorReport:
    """Full evaluation report."""
    overall_assessment: str
    source_fidelity: SourceFidelity | None = None
    factual_grounding: FactualGrounding | None = None
    self_containment: SelfContainment | None = None
    structural_fitness: StructuralFitness | None = None
    authority_signals: AuthoritySignals | None = None
    honest_placeholders: HonestPlaceholders | None = None
    strengths: list[str] = field(default_factory=list)
    confidence_notes: list[dict] = field(default_factory=list)
    what_cannot_be_fixed: str | None = None
    critical_issues: list[str] = field(default_factory=list)
    rewrite_prompt: str | None = None
    should_generate_prompt: bool = False


@dataclass
class RewriterRequest:
    """Input to Rewriter (Tool B)."""
    content: str
    prompt: str


@dataclass
class RewriterResult:
    """Output from Rewriter."""
    rewrite: str
    stopped_by_limit: bool = False
