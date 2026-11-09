import unittest
import pandas as pd
from notebook_reporting import report_table


class ReportPresentationTests(unittest.TestCase):
    def test_french_units_unknowns_and_dates_preserve_analytical_values(self):
        frame=pd.DataFrame(dict(quantity=[1,None],unit_price=[12.5,0],weight_pct=[25,None],price_date=pd.to_datetime(['2026-11-09',None])))
        original=frame.copy(deep=True)
        shown=report_table(frame)
        self.assertEqual(shown['Quantité'].tolist(),['1','Indisponible'])
        self.assertEqual(shown['Prix unitaire (EUR)'].tolist(),['12,50 €','0,00 €'])
        self.assertEqual(shown['Part de la valeur connue (%)'].tolist(),['25,00 %','Indisponible'])
        self.assertEqual(shown['Date du prix'].iloc[0],'09/11/2026 00:00')
        pd.testing.assert_frame_equal(frame,original)
