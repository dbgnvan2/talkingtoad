"""D3 — WordPress configuration audit. Read-only, opt-in, never in the crawl.

Purpose: report the operational facts no crawler can reach — inactive plugins,
         pending updates, two plugins claiming the same job — without touching
         anything.
Spec:    docs/pending/2026-08-29_D3-wordpress-configuration-audit.md
Tests:   tests/test_wp_audit.py

**This module cannot write, and that is enforced rather than intended.**
`tests/test_architecture_constraints.py::test_d3_1a_wp_audit_is_read_only`
asserts the source contains no `post(`, `patch(`, `put(` or `delete(` call. It
holds admin credentials to a live client site; "we meant it to be read-only" is
not a property, it is a hope.

It is also **not** part of the crawl. `api/crawler/engine.py` carries an explicit
constraint — the scan uses HTML and HEAD requests only, never the WordPress API —
and that constraint is correct: it keeps the crawl fast and keeps TalkingToad
working on non-WordPress sites. This runs post-scan, user-triggered, exactly like
the Fix Manager.

## What it can and cannot know

Tier 1 (implemented) is everything derivable from the plugin, theme and
site-health payloads: what is installed, what is inactive, what has an update
waiting, and which active plugins claim the same responsibility.

Tier 2 is **not** implemented and is declared as such in the output: "Duplicator
is active but has never taken a backup" needs Duplicator's own tables. There is no
generic REST surface for plugin-internal state, and writing a bespoke probe per
plugin is an open-ended commitment. Saying where the boundary is, is the
difference between a useful finding and an implied guarantee.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from api.config import load_config

logger = logging.getLogger(__name__)

_CFG_KEYS = ("responsibilities", "families")


def _cfg() -> dict:
    return load_config("wp_plugin_advice", required_keys=_CFG_KEYS)


class WPAuditError(RuntimeError):
    """A typed failure carrying whether the caller can do anything about it."""

    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = code


@dataclass
class PluginRow:
    slug: str
    name: str
    version: str = ""
    status: str = ""            # "active" | "inactive"
    update_available: bool = False
    new_version: str = ""

    @property
    def is_active(self) -> bool:
        return self.status == "active"


@dataclass
class Overlap:
    responsibility: str
    label: str
    why_one_owner: str
    plugins: list[str] = field(default_factory=list)


@dataclass
class WPAuditReport:
    plugins: list[PluginRow] = field(default_factory=list)
    themes_inactive: list[str] = field(default_factory=list)
    overlaps: list[Overlap] = field(default_factory=list)
    site_health: list[dict] = field(default_factory=list)
    # Declared boundary — rendered verbatim so the reader knows what was NOT read.
    not_inspected: list[str] = field(default_factory=list)

    @property
    def active(self) -> list[PluginRow]:
        return [p for p in self.plugins if p.is_active]

    @property
    def inactive(self) -> list[PluginRow]:
        return [p for p in self.plugins if not p.is_active]

    @property
    def pending_updates(self) -> list[PluginRow]:
        return [p for p in self.plugins if p.update_available]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _slug(plugin: dict) -> str:
    """WordPress reports `plugin` as "directory/file.php" (or just "file")."""
    raw = str(plugin.get("plugin") or plugin.get("slug") or "")
    return raw.split("/", 1)[0].removesuffix(".php")


def parse_plugins(payload) -> list[PluginRow]:
    """`/wp/v2/plugins` → rows. Tolerant: an unfamiliar shape is skipped, not fatal."""
    if not isinstance(payload, list):
        return []
    rows: list[PluginRow] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        slug = _slug(item)
        if not slug:
            continue
        # WordPress reports an available update either as a version string or as
        # a truthy object, depending on the endpoint and the version.
        update = item.get("update")
        new_version = ""
        if isinstance(update, dict):
            new_version = str(update.get("new_version") or "")
        elif isinstance(update, str):
            new_version = update
        rows.append(PluginRow(
            slug=slug,
            name=str(item.get("name") or slug),
            version=str(item.get("version") or ""),
            status=str(item.get("status") or ""),
            update_available=bool(new_version),
            new_version=new_version,
        ))
    return rows


def find_overlaps(plugins: list[PluginRow]) -> list[Overlap]:
    """Two or more ACTIVE plugins claiming the same responsibility.

    Free/premium pairs of one product are collapsed first: flagging Yoast against
    Yoast Premium, or Duplicator against Duplicator Pro, would be noise and would
    make the whole section easy to dismiss (P7).
    """
    cfg = _cfg()
    families = {k: v for k, v in cfg["families"].items() if not k.startswith("_")}
    # Map every add-on slug back to its parent product.
    to_parent: dict[str, str] = {}
    for parent, children in families.items():
        for child in children:
            to_parent[child] = parent

    active = {to_parent.get(p.slug, p.slug) for p in plugins if p.is_active}

    overlaps: list[Overlap] = []
    for name, spec in cfg["responsibilities"].items():
        owners = sorted(active & {to_parent.get(s, s) for s in spec["slugs"]})
        if len(owners) > 1:
            overlaps.append(Overlap(
                responsibility=name, label=spec["label"],
                why_one_owner=spec["why_one_owner"], plugins=owners,
            ))
    return overlaps


def parse_site_health(payload) -> list[dict]:
    """WordPress's own recommendations, attributed to WordPress.

    Passed through verbatim. These are core's judgements, not TalkingToad's, and
    the report says so — presenting somebody else's check as our finding would
    misrepresent where the evidence comes from.
    """
    if not isinstance(payload, dict):
        return []
    out = []
    for key in ("recommended", "critical"):
        for item in payload.get(key) or []:
            if isinstance(item, dict) and item.get("label"):
                out.append({
                    "label": str(item["label"]),
                    "status": str(item.get("status") or key),
                    "source": "WordPress Site Health",
                })
    return out


NOT_INSPECTED = [
    "Plugin-internal state — whether a backup plugin has ever run, whether a "
    "security plugin is configured, whether a cache is warm. There is no generic "
    "WordPress API for this, so it was not read.",
    "Plugin or theme file contents, and any custom code.",
    "Hosting configuration, server-level caching and WAF rules.",
    "Anything requiring a change: this audit only reads.",
]


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


async def collect_wp_audit(wp) -> WPAuditReport:
    """Read plugins, themes and site health through an authenticated client.

    `wp` is a `WPClient`. Only `.get()` is ever called — see the module docstring
    and the architecture guard.
    """
    # Capability probe FIRST. A half-audit presented as a whole one is the P2
    # shape: the reader cannot tell "no problems" from "we could not look".
    try:
        me = await wp.get("/wp/v2/users/me?context=edit")
    except Exception as exc:  # noqa: BLE001
        raise WPAuditError(f"could not authenticate to WordPress: {exc}",
                           code="WP_AUTH_FAILED") from exc
    if me.status_code in (401, 403):
        raise WPAuditError(
            "the stored WordPress credentials cannot read site configuration",
            code="WP_INSUFFICIENT_CAPABILITY")

    report = WPAuditReport(not_inspected=list(NOT_INSPECTED))

    resp = await wp.get("/wp/v2/plugins")
    if resp.status_code in (401, 403):
        raise WPAuditError(
            "the stored WordPress user lacks the capability to list plugins "
            "(WordPress requires an administrator for this endpoint)",
            code="WP_INSUFFICIENT_CAPABILITY")
    if resp.status_code != 200:
        raise WPAuditError(f"WordPress returned HTTP {resp.status_code} for the "
                           f"plugin list", code="WP_UNEXPECTED_RESPONSE")
    report.plugins = parse_plugins(resp.json())
    report.overlaps = find_overlaps(report.plugins)

    # Themes and Site Health are best-effort: neither is available on every
    # install, and their absence must degrade the report rather than fail it.
    try:
        themes = await wp.get("/wp/v2/themes")
        if themes.status_code == 200 and isinstance(themes.json(), list):
            report.themes_inactive = [
                str(t.get("name", {}).get("raw") or t.get("stylesheet") or "")
                for t in themes.json()
                if isinstance(t, dict) and t.get("status") != "active"
            ]
    except Exception:  # noqa: BLE001
        logger.info("wp_themes_unavailable", exc_info=True)

    try:
        health = await wp.get("/wp-site-health/v1/tests/background-updates")
        if health.status_code == 200:
            report.site_health = parse_site_health(health.json())
    except Exception:  # noqa: BLE001
        logger.info("wp_site_health_unavailable", exc_info=True)

    return report


def report_to_dict(report: WPAuditReport) -> dict:
    return {
        "plugins_total": len(report.plugins),
        "plugins_active": len(report.active),
        "plugins_inactive": len(report.inactive),
        "pending_updates": [
            {"slug": p.slug, "name": p.name, "version": p.version,
             "new_version": p.new_version}
            for p in report.pending_updates
        ],
        "inactive_plugins": [
            {"slug": p.slug, "name": p.name, "version": p.version}
            for p in report.inactive
        ],
        "inactive_themes": report.themes_inactive,
        "overlaps": [
            {"responsibility": o.responsibility, "label": o.label,
             "why_one_owner": o.why_one_owner, "plugins": o.plugins}
            for o in report.overlaps
        ],
        "site_health": report.site_health,
        "not_inspected": report.not_inspected,
    }
