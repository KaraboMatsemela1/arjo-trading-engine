#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_issue91_telegram_recovery import CUES, bounded_excerpt, clean_text


def main() -> int:
    html = '<div class="tgme_widget_message_text js-message_text" dir="auto">ES has been here for a while, why? Because it\'s equilibrium and at equilibrium thats where you\'ll likely get a stop run as well</div>'
    text = clean_text(html)
    assert "equilibrium" in text.casefold()
    assert "stop run" in text.casefold()
    assert CUES["INSTRUMENTS"].search(text)
    assert CUES["EQUILIBRIUM"].search(text)
    hit = CUES["STOP_RUN"].search(text)
    assert hit is not None
    excerpt = bounded_excerpt(text, hit, 20)
    assert len(excerpt.split()) <= 20

    outcome_text = "This strategy had a 90% win rate"
    assert not CUES["EQUILIBRIUM"].search(outcome_text)

    print("Issue 91 recovery regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
