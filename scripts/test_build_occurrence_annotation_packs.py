#!/usr/bin/env python3
from __future__ import annotations
import json
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_occurrence_annotation_packs import (  # noqa: E402
    ARTIFACT_BY_YEAR, PackError, build_pack, canonical_sha256, validate_manifest,
)

def row(ts: datetime, minutes: int, px: str = '100.0') -> dict:
    return {
        'ts_start_utc': ts.isoformat().replace('+00:00','Z'), 'session_start_local': ts.isoformat(),
        'minutes': minutes, 'open': px, 'high': '101.0', 'low': '99.0', 'close': px, 'price_count': 15,
    }

def main() -> int:
    manifest = {
        'provider':'OANDA_V20','environment':'practice','instrument':'NAS100_USD',
        'instrument_identity':'OANDA_NASDAQ100_CFD_PROXY_FOR_LOCKED_NQ_SEED','price_component':'MID',
        'holdout_accessed':False,'holdout_requested':False,'mutation_endpoints_used':False,
        'm1_first':'2024-01-02T00:00:00Z','m1_last':'2024-12-31T20:00:00Z','m1_sha256':'abc'
    }
    validate_manifest(manifest, year=2024, artifact_id=ARTIFACT_BY_YEAR[2024])
    bad = dict(manifest); bad['holdout_accessed'] = True
    try: validate_manifest(bad, year=2024, artifact_id=ARTIFACT_BY_YEAR[2024])
    except PackError: pass
    else: raise AssertionError('holdout manifest must fail')

    # January 8 2024 is EST: WoO 14:30-16:00 UTC.
    day = date(2024,1,8)
    cutoff = datetime(2024,1,8,16,0,tzinfo=UTC)
    bars15=[]
    ts=datetime(2024,1,7,16,0,tzinfo=UTC)
    while ts < cutoff + timedelta(minutes=15):
        bars15.append(row(ts,15)); ts += timedelta(minutes=15)
    bars60=[]; ts=datetime(2024,1,5,16,0,tzinfo=UTC)
    while ts < cutoff + timedelta(hours=1): bars60.append(row(ts,60)); ts += timedelta(hours=1)
    bars240=[]; ts=datetime(2024,1,1,16,0,tzinfo=UTC)
    while ts < cutoff + timedelta(hours=4): bars240.append(row(ts,240)); ts += timedelta(hours=4)

    with tempfile.TemporaryDirectory() as td:
        mp=Path(td)/'manifest.json'; mp.write_text(json.dumps(manifest))
        pack=build_pack(day=day,bars={'15m':bars15,'60m':bars60,'240m':bars240},manifest=manifest,manifest_path=mp,artifact_id=ARTIFACT_BY_YEAR[2024])
        assert pack['annotation_boundary']['outcome_blind'] is True
        assert pack['annotation_boundary']['post_woo_bars_included'] is False
        woo_start=datetime(2024,1,8,14,30,tzinfo=UTC)
        woo=[r for r in pack['context']['15m'] if woo_start <= datetime.fromisoformat(r['ts_start_utc'].replace('Z','+00:00')) < cutoff]
        assert len(woo) == 6
        for tf, minutes in [('15m',15),('60m',60),('240m',240)]:
            for r in pack['context'][tf]:
                end=datetime.fromisoformat(r['ts_start_utc'].replace('Z','+00:00'))+timedelta(minutes=minutes)
                assert end <= cutoff
        first_sha=pack['pack_sha256']
        again=build_pack(day=day,bars={'15m':bars15,'60m':bars60,'240m':bars240},manifest=manifest,manifest_path=mp,artifact_id=ARTIFACT_BY_YEAR[2024])
        assert first_sha == again['pack_sha256']
        tmp=dict(again); tmp.pop('pack_sha256'); assert first_sha == canonical_sha256(tmp)

    # A 15m bar crossing cutoff must never appear.
    crossing = row(datetime(2024,1,8,15,55,tzinfo=UTC),15)
    bars15.append(crossing)
    with tempfile.TemporaryDirectory() as td:
        mp=Path(td)/'manifest.json'; mp.write_text(json.dumps(manifest))
        pack=build_pack(day=day,bars={'15m':bars15,'60m':bars60,'240m':bars240},manifest=manifest,manifest_path=mp,artifact_id=ARTIFACT_BY_YEAR[2024])
        assert crossing not in pack['context']['15m']
    print('occurrence annotation pack tests passed')
    return 0
if __name__=='__main__': raise SystemExit(main())
