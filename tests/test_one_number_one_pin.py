"""P8.3 — `page_size_limit_kb` had four homes, and `cryptography` had a pin nobody chose.

The number was stated in `registry._DEFAULT_PAGE_SIZE_LIMIT_KB`, again as a
literal on the engine's `CrawlSettings`, and twice more in prose (`docs/api.md`,
`docs/fix-agent-spec.md`). `docs/thresholds.md:81` names the registry constant as
the owner, and the engine did not read it. Nothing was wrong on screen — which is
why this is engineering debt — but the next person to change the threshold would
have changed one of four places.

The pin: `docs/TODO-ARCHIVE.md` records that `cryptography~=48.0.0` was chosen
"to match the dev venv", for a security-sensitive library whose only use here is
`Fernet` over the stored GSC credential. `pip index versions` resolves 50.0.1, so
it was decidable on evidence rather than left as a note.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest

from api.crawler.checkers import registry
from api.crawler.engine import CrawlSettings as EngineCrawlSettings

_ROOT = Path(__file__).resolve().parent.parent


class TestOneNumberOneHome:
    def test_the_engine_default_is_the_registry_constant(self):
        """3.1 — necessary, and on its own not sufficient: a hand-written 300 and
        a constant read once both satisfy it today. 3.3 is what separates them."""
        assert (EngineCrawlSettings().page_size_limit_kb
                == registry._DEFAULT_PAGE_SIZE_LIMIT_KB)

    def test_changing_the_constant_moves_the_engine_default(self):
        """3.3 — reference, not coincidence.

        A dataclass default is evaluated at class-definition time, so reading the
        constant there still bakes in a copy. The engine therefore resolves it
        through a `default_factory`, and this patches the constant and constructs
        a fresh settings object to prove the link is live.
        """
        with patch.object(registry, "_DEFAULT_PAGE_SIZE_LIMIT_KB", 1234):
            assert EngineCrawlSettings().page_size_limit_kb == 1234, (
                "the engine default is a copy of the constant, not a reference — "
                "changing the threshold in the registry leaves the engine on 300"
            )

    def test_it_is_still_per_job_configurable(self):
        """3.3b — the other direction. `thresholds.md` says this is
        per-job-configurable, so the fix must not turn the field into a constant."""
        assert EngineCrawlSettings(page_size_limit_kb=42).page_size_limit_kb == 42

    @pytest.mark.parametrize("doc", ["docs/api.md", "docs/fix-agent-spec.md"])
    def test_the_docs_state_the_same_page_size_limit(self, doc):
        """3.2 — read the prose, assert against the constant's live value.

        Two assertions that each restate 300 would agree with each other forever
        (LEARNINGS item 13). These read the sentence and compare it to the code.
        """
        text = (_ROOT / doc).read_text()
        limit = registry._DEFAULT_PAGE_SIZE_LIMIT_KB
        # The sentences that quote the threshold, found by their shape rather
        # than by their exact wording so a rewording does not silently exempt them.
        quoted = re.findall(r"(\d+)\s*KB(?=[^.\n]*(?:limit|exceeds|larger))", text) + \
                 re.findall(r"page_size_limit_kb[^|\n]*\|\s*int\s*\|\s*(\d+)", text)
        assert quoted, f"{doc} no longer states the page-size limit — update this test"
        wrong = [v for v in quoted if int(v) != limit]
        assert not wrong, (
            f"{doc} states {wrong} KB where the registry says {limit} KB"
        )


class TestTheCryptographyPin:
    def test_the_pin_matches_what_is_installed(self):
        """3.4a — the pin and the venv cannot part company silently.

        `tests/test_declared_environment.py` covers the whole set; this names the
        one library the item is about, so a failure here says which.
        """
        import cryptography
        from packaging.requirements import Requirement
        from packaging.version import Version

        line = next(l for l in (_ROOT / "requirements.txt").read_text().splitlines()
                    if l.strip().startswith("cryptography"))
        spec = Requirement(line.strip()).specifier
        assert Version(cryptography.__version__) in spec, (
            f"installed cryptography {cryptography.__version__} does not satisfy {line!r}"
        )

    def test_gsc_credentials_round_trip_through_fernet(self):
        """3.4 — encrypt then decrypt through the real credential path.

        An import-only check passes against a library that loads and then fails
        on use, which is the exact shape of a dependency bump going wrong. This
        is the one thing `cryptography` is used for in this codebase
        (`gsc.py:92,102`), so a green suite without it would not justify the
        version move.
        """
        import json

        from cryptography.fernet import Fernet

        from api.routers import gsc

        # Without a key the helpers deliberately no-op and return the input, so
        # a test that skipped this would assert nothing about the library at all.
        key = Fernet.generate_key().decode()
        payload = json.dumps({"token": "t0k3n", "refresh_token": "r3fr3sh"})

        with patch.object(gsc, "_get_encryption_key", return_value=key):
            encrypted = gsc._encrypt_creds(payload)
            assert encrypted != payload, (
                "the credential came back unencrypted — the key was not applied "
                "and this test is exercising the no-op path"
            )
            assert gsc._decrypt_creds(encrypted) == payload, (
                "a credential encrypted by this build cannot be read back"
            )
