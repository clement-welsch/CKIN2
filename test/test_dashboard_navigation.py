from pathlib import Path
import tempfile
import unittest

from dashboard import render
from dashboard_navigation import normalize,target_url


class NavigationTests(unittest.TestCase):
    def test_presets_show_explicit_bounded_dates(self):
        state,notes,period=normalize({'page':'performance','period':'30d'},'2026-11-09')
        self.assertEqual(state['start'],'2026-10-10');self.assertEqual(state['end'],'2026-11-09')
        self.assertEqual(period,'30d');self.assertEqual(notes,[])
        state,_,_=normalize({'page':'performance','period':'90d','end':'2026-01-01'},'2026-11-09')
        self.assertEqual(state['start'],'2025-10-03')
        with self.assertRaises(ValueError):normalize({'page':'performance','period':'invalid'},'2026-11-09')

    def test_incompatible_controls_reset_visibly_and_compatible_fields_survive(self):
        url=target_url({'category':'skin','end':'2026-01-01','search':'AK','price_status':'stale'},'item')
        self.assertIn('category=skin',url);self.assertIn('search=AK',url);self.assertIn('notice=',url)
        self.assertNotIn('price_status=',url)
        state,notes,_=normalize({'page':'overview','start':'2026-01-01','search':'AK'},'2026-11-09')
        self.assertNotIn('start',state);self.assertEqual(len(notes),2)
        with tempfile.TemporaryDirectory() as d:
            html=render(Path(d),{'item_id':'00000000-0000-0000-0000-000000000000'},now='2026-11-09')
            self.assertIn('Objet réinitialisé',html)
            self.assertIn('Filtres actifs',html)
            self.assertIn('favorite-save',html)
            self.assertNotIn('name="start"',html)
