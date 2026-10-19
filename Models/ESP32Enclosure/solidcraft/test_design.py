"""Regression checks adapted from the solidcraft-checking test_design template.

Frozen expectations are measured from the preserved revision014 source geometry,
not from the migrated SolidCraft export. Imported-body documents have no driving
SolidCraft parameters, so parameter-range walks are intentionally inapplicable.
"""
import json,math,subprocess
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parent/'revision-014'
MANIFEST=json.loads((ROOT/'manifest.json').read_text())
# At least three times the observed relative tessellated-volume/area error.
REL=2e-4

@pytest.mark.parametrize('document',MANIFEST['documents'],ids=lambda d:d['path'])
def test_body_matches_preserved_reference(document):
    done=subprocess.run(['solidcraft-cli','eval',str(ROOT/document['path'])],capture_output=True,text=True)
    assert done.returncode==0,done.stderr
    state=json.loads(done.stdout)
    assert state['body_count']==document['expected_body_count']
    bodies={b['name']:b for b in state['bodies']}
    assert set(bodies)==set(document['body_names'])
    for name,expected in document['frozen_reference'].items():
        actual=bodies[name]
        assert actual['volume_mm3']==pytest.approx(expected['volume_mm3'],rel=REL)
        assert actual['area_mm2']==pytest.approx(expected['area_mm2'],rel=REL)
        tolerance=max(1e-3,1.5e-4*math.dist(expected['bbox']['min'],expected['bbox']['max']))
        assert actual['center_of_mass']==pytest.approx(expected['center_of_mass'],abs=tolerance)
        assert actual['bbox']['min']==pytest.approx(expected['bbox']['min'],abs=tolerance)
        assert actual['bbox']['max']==pytest.approx(expected['bbox']['max'],abs=tolerance)
