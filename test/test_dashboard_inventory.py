from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from dashboard import render, view
from dashboard_inventory import inventory
from portfolio_data import identity, load_holdings
from test_global_analysis import market_fixture


def inventory_fixture(root):
    directory=root/'data/processed';directory.mkdir(parents=True)
    names=[f'Case {i:02d}' for i in range(31)]
    pd.DataFrame(dict(case_name=names,quantity=[None,0]+[2]*29)).to_csv(directory/'drop_cases_inventory.csv',index=False)
    holdings,_=load_holdings(root)
    prices=market_fixture(holdings).loc[lambda f:f.item_name.ne('Case 02')]
    prices.loc[prices.item_name.eq('Case 03'),'date']='2022-01-01'
    prices.to_csv(directory/'market_observations.csv',index=False)
    return holdings


class InventoryTests(unittest.TestCase):
    def test_pagination_totals_and_stable_sort_missing_last(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);inventory_fixture(root)
            data=view(root,category='case',now='2023-04-01',components='inventory')
            first=inventory(data,page_size='10')
            second=inventory(data,page_size='10',page_number='2')
            self.assertEqual(first['count'],30)
            self.assertFalse(set(first['page_rows'].item_id)&set(second['page_rows'].item_id))
            pd.testing.assert_frame_equal(first['summary'],second['summary'])
            self.assertTrue(pd.isna(first['summary'].total_value.iloc[0]))
            self.assertEqual(first['summary'].known_value.iloc[0],28*2*30)
            descending=inventory(data,sort='quantity',direction='desc')
            self.assertTrue(pd.isna(descending['rows'].quantity.iloc[-1]))
            self.assertEqual(inventory(data,page_number='999',page_size='10')['page'],3)
            for kwargs in ({'sort':'invalid'},{'page_size':'100000'},{'page_number':'0'},{'quantity_status':'invalid'}):
                with self.assertRaises(ValueError):inventory(data,**kwargs)

    def test_combined_search_status_and_no_catalog_quantities(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);inventory_fixture(root)
            data=view(root,category='case',now='2023-04-01',components='inventory')
            self.assertEqual(inventory(data,search='case 02',price_status='missing')['count'],1)
            self.assertEqual(inventory(data,quantity_status='unknown')['rows'].item_name.tolist(),['Case 00'])
            self.assertEqual(inventory(data,price_status='stale')['rows'].item_name.tolist(),['Case 03'])
            self.assertEqual(inventory(data,search='[not regex]')['count'],0)
            before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with patch('socket.socket',side_effect=AssertionError('network')):
                page=render(root,{'page':'inventory','category':'case','page_size':'10'},now='2023-04-01')
            self.assertIn('Totaux indépendants de la pagination',page)
            self.assertIn('scope="col"',page)
            self.assertIn('Page 1 / 3',page)
            self.assertNotIn('Case 01</a>',page)
            self.assertEqual(before,{p:p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_exact_variant_links_and_zero_price(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'data/processed';target.mkdir(parents=True)
            names=['AK-47 | Test (Factory New)','StatTrak™ AK-47 | Test (Factory New)','AK-47 | Test (Field-Tested)']
            pd.DataFrame(dict(item_name=names,quantity=[1,1,1])).to_csv(target/'skins_inventory.csv',index=False)
            holdings,_=load_holdings(root)
            market_fixture(holdings).assign(unit_price=0).to_csv(target/'market_observations.csv',index=False)
            page=render(root,{'page':'inventory','category':'skin'},now='2023-04-01')
            for name in names:self.assertIn('item_id='+identity('skin',name),page)
            result=inventory(view(root,category='skin',now='2023-04-01',components='inventory'))
            self.assertEqual(result['summary'].total_value.iloc[0],0)
