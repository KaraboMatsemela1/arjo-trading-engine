#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_issue94_telegram_recovery import CUES, bounded_excerpt, clean_text


def main() -> int:
    html = '<div class="tgme_widget_message_text js-message_text" dir="auto">My view on ES consolidating We\'ve just finished a MMBM aka a LRLR, we took the highs which means we took shorts their Stop Loss</div>'
    text = clean_text(html)
    assert CUES["INSTRUMENTS"].search(text)
    assert CUES["MMBM"].search(text)
    assert CUES["LRLR"].search(text)
    assert CUES["MODEL_STATE"].search(text)
    assert CUES["DIRECTION"].search(text)
    hit = CUES["MMBM"].search(text)
    assert hit is not None
    excerpt = bounded_excerpt(text, hit, 20)
    assert len(excerpt.split()) <= 20
    print("Issue 94 recovery regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
