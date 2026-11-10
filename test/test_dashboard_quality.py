import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from dashboard import render, view
from dashboard_inventory import inventory
from dashboard_quality import collection_history, quality
from dashboard_status import coverage
from global_analysis import analyze
from test_multicategory_prices import fixture
from test_global_analysis import market_fixture
from test_steam_inventory_import import export_fixture, catalog_fixture
from steam_inventory import apply, preview


def bytes_at(root):
    return {p:p.read_bytes() for p in root.rglob('*') if p.is_file()}


class QualityTests(unittest.TestCase):
    def test_complete_partial_missing_stale_and_legacy_share_inventory_statuses(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            holdings, imported=fixture(root)
            prices=market_fixture(holdings)
            prices=prices.loc[prices.category.ne('skin')]
            prices.to_csv(root/'data/processed/market_observations.csv',index=False)
            (root/'data/processed/souvenirs_inventory.csv').unlink()
            pd.DataFrame(dict(case_name=['Recoil'],quantity=[None])).to_csv(root/'data/processed/drop_cases_inventory.csv',index=False)
            data=view(root,now='2026-11-04',components='quality')
            result=quality(root,data)
            problems=set(result['issues']['Problème'])
            self.assertTrue({'Quantité inconnue','Prix absent','Prix ancien','Catégorie non importée'}.issubset(problems))
            self.assertEqual(result['status']['stale_items'],inventory(data,price_status='stale')['count'])
            self.assertEqual(result['status']['label'],coverage(data)['label'])
            self.assertEqual(result['collection']['status'],'Absence d’historique')
            self.assertTrue(result['issues']['Correction proposée'].str.len().gt(15).all())
            (root/'data/processed/steam_inventory_override.json').write_text(json.dumps(dict(schema=1,holdings=holdings.to_dict('records'),imported=list(imported))))
            result=quality(root,view(root,now='2026-11-04',components='quality'))
            self.assertIn('Couverture du remplacement non vérifiée',result['issues']['Problème'].tolist())

    def test_collection_success_partial_failure_future_and_malformed_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);runs=root/'data/runtime/runs';runs.mkdir(parents=True)
            for code,label in [(0,'Réussite'),(1,'Résultat partiel'),(2,'Échec')]:
                event=dict(ended=f'2026-11-0{code+1}T12:00:00+00:00',code=code,updated=1,failed=code,missing=0,stale=0)
                (runs/f'{code}.json').write_text(json.dumps(event))
                self.assertEqual(collection_history(root,'2026-11-04')['status'],label)
            self.assertEqual(collection_history(root,'2026-11-01 13:00:00')['status'],'Réussite')
            (runs/'broken.json').write_text('{"code":0}')
            data=view(root,now='2026-11-04',components='quality')
            result=quality(root,data)
            self.assertEqual(result['collection']['status'],'Historique invalide')
            self.assertIn('collection',result['errors'])

    def test_invalid_optional_datasets_leave_independent_current_views_accessible(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);holdings,_=fixture(root)
            market_fixture(holdings).to_csv(root/'data/processed/market_observations.csv',index=False)
            (root/'data/processed/global_inventory_history.csv').write_text('invalid\n')
            (root/'data/processed/market_catalog.csv').write_text('invalid\n')
            (root/'data/processed/steam_inventory_visible.json').write_text('{')
            archives=root/'data/processed/forecast_archive';archives.mkdir();(archives/'bad.json').write_text('{')
            corpus=root/'data/community';corpus.mkdir();(corpus/'corpus.json').write_text('{')
            before=bytes_at(root)
            with patch('socket.socket',side_effect=AssertionError('network')):
                data=view(root,now='2023-04-01',components='overview')
                self.assertEqual(coverage(data)['total_value'],210)
                self.assertNotIn('prices',data['errors'])
                self.assertIn('Patrimoine actuel connu',render(root,now='2023-04-01'))
                result=quality(root,data)
                self.assertTrue({'history','metadata','visible','archive','community'}.issubset(result['errors']))
                for page in ('inventory','quality','reconciliation','community','forecasts','categories'):
                    self.assertIn('CKIN2',render(root,{'page':page},now='2023-04-01'))
                historical=view(root,now='2023-04-01',end='2023-02-01',components='overview')
                self.assertTrue(historical['current'].empty)
            self.assertEqual(before,bytes_at(root))
            with self.assertRaises(ValueError):analyze(root,now='2023-04-01')

    def test_invalid_primary_data_never_becomes_a_zero_or_fallback_total(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);holdings,_=fixture(root)
            prices=root/'data/processed/market_observations.csv'
            prices.write_text('invalid\n')
            data=view(root,now='2023-04-01',components='inventory')
            self.assertIn('prices',data['errors'])
            self.assertTrue(data['current'].total_value.isna().all())
            self.assertTrue(inventory(data)['summary'].known_value.isna().all())
            prices.unlink()
            (root/'data/processed/drop_cases_inventory.csv').write_text('case_name,quantity\nRecoil,-1\n')
            before=bytes_at(root)
            self.assertIn('Calculs indisponibles',render(root,now='2023-04-01'))
            self.assertIn('Quantités indisponibles',render(root,{'page':'inventory'},now='2023-04-01'))
            # Missing independent research is still readable despite malformed holdings.
            self.assertIn('No local corpus',render(root,{'page':'community'},now='2023-04-01'))
            self.assertIn('Correction proposée',render(root,{'page':'quality'},now='2023-04-01'))
            self.assertEqual(before,bytes_at(root))

    def test_unresolved_observations_have_actionable_diagnostics_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            export=export_fixture();export['pages'][0]['descriptions'][0]['market_hash_name']='<script>unresolved</script>'
            plan=preview(export,catalog_fixture(),root)
            apply(export,catalog_fixture(),plan['review_token'],root,'home')
            before=bytes_at(root)
            with patch('socket.socket',side_effect=AssertionError('network')):
                html=render(root,{'page':'quality'},now='2026-11-04')
            self.assertIn('Correspondance Steam non résolue',html)
            self.assertIn('&lt;script&gt;unresolved&lt;/script&gt;',html)
            self.assertEqual(before,bytes_at(root))
