"""Optional real-browser acceptance of navigation/favorites; synthetic data only."""

import importlib.util
from pathlib import Path
import shutil
import tempfile
import threading
import unittest

from dashboard import make_server
from global_snapshots import save_snapshot
from portfolio_data import load_holdings
from test_dashboard_inventory import inventory_fixture

AVAILABLE=bool(importlib.util.find_spec('playwright')) and bool(shutil.which('chromium'))


@unittest.skipUnless(AVAILABLE,'Optional Chromium/Playwright acceptance environment unavailable')
class BrowserAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.temporary=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temporary.name);inventory_fixture(cls.root)
        holdings,imported=load_holdings(cls.root)
        path=cls.root/'data/processed/global_inventory_history.csv'
        save_snapshot(holdings,imported,'2026-10-01',path)
        save_snapshot(holdings.assign(quantity=3),imported,'2026-11-01',path)
        cls.before={p:p.read_bytes() for p in cls.root.rglob('*') if p.is_file()}
        cls.server=make_server(cls.root,0);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
        cls.pw=sync_playwright().start()
        cls.browser=cls.pw.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop();cls.server.shutdown();cls.server.server_close();cls.thread.join()
        assert cls.before=={p:p.read_bytes() for p in cls.root.rglob('*') if p.is_file()}
        cls.temporary.cleanup()

    def context(self,**kwargs):
        context=self.browser.new_context(**kwargs)
        context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(self.url) else route.abort())
        self.addCleanup(context.close)
        return context

    def test_favorite_lifecycle_navigation_periods_comparison_and_mobile(self):
        from playwright.sync_api import expect
        context=self.context(viewport={'width':1440,'height':1000})
        page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(self.url+'/?page=inventory&category=case&search=Case&page_size=10',wait_until='networkidle')
        page.get_by_label('Nom de la vue').fill('Caisses à revoir')
        page.get_by_role('button',name='Enregistrer la vue actuelle').click()
        expect(page.locator('#favorite-status')).to_have_text('Vue enregistrée localement.')
        page.get_by_label('Nom de la vue').fill('Caisses renommées')
        page.get_by_role('button',name='Renommer',exact=True).click()
        expect(page.locator('#favorite-status')).to_have_text('Vue renommée.')
        page.goto(self.url+'/?page=performance&category=case&period=30d',wait_until='networkidle')
        self.assertTrue(page.locator('input[name="start"]').input_value())
        page.get_by_role('navigation',name='Vues du dashboard').get_by_role('link',name='Inventaire',exact=True).click()
        expect(page.get_by_role('heading',name='Inventaire détenu')).to_be_visible()
        self.assertIn('category=case',page.url);self.assertNotIn('start=',page.url)
        self.assertIn('Filtres réinitialisés',page.inner_text('body'))
        page.go_back(wait_until='networkidle')
        self.assertIn('page=performance',page.url)
        page.get_by_label('Vue enregistrée').select_option(label='Caisses renommées')
        page.get_by_role('button',name='Ouvrir',exact=True).click()
        expect(page.get_by_role('heading',name='Inventaire détenu')).to_be_visible()
        self.assertEqual(page.get_by_label('Rechercher un nom ou une variante').input_value(),'Case')
        page.get_by_label('Nom de la vue').focus();page.keyboard.press('Tab')
        self.assertEqual(page.evaluate('document.activeElement.id'),'favorite-save')
        page.get_by_label('Vue enregistrée').select_option(label='Caisses renommées')
        page.get_by_role('button',name='Supprimer',exact=True).click()
        expect(page.locator('#favorite-status')).to_have_text('Vue supprimée.')
        self.assertEqual(page.evaluate('JSON.parse(localStorage.getItem("ckin2.views.v1")).length'),0)
        page.goto(self.url+'/?page=comparison&category=case',wait_until='networkidle')
        self.assertEqual(page.get_by_label('État initial').input_value(),'2026-10-01T00:00:00')
        page.get_by_label('État final').select_option('2026-10-01T00:00:00')
        page.get_by_role('button',name='Comparer les snapshots').click()
        expect(page.get_by_text('Variation totale :',exact=False)).to_be_visible()
        page.set_viewport_size({'width':390,'height':844})
        output=Path('/tmp/ckin2-final-ui');output.mkdir(exist_ok=True)
        for view in ('overview','inventory','comparison','quality','categories','item'):
            page.goto(self.url+'/?page='+view+'&category=case',wait_until='networkidle')
            self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth'),view)
            page.screenshot(path=str(output/(view+'-mobile.png')),full_page=True)
        self.assertEqual(errors,[])

    def test_invalid_obsolete_and_unavailable_browser_storage(self):
        from playwright.sync_api import expect
        context=self.context();page=context.new_page();page.goto(self.url,wait_until='networkidle')
        page.evaluate('localStorage.setItem("ckin2.views.v1",JSON.stringify([{id:"bad",name:"External",url:"https://example.com"},{id:"date",name:"Date invalide",url:"/?page=performance&end=2026-02-31"},{id:"old",name:"Ancien objet",url:"/?page=item&item_id=00000000-0000-0000-0000-000000000000"}]))')
        page.reload(wait_until='networkidle')
        expect(page.locator('#favorite-status')).to_have_text('Certaines vues invalides ou obsolètes ont été ignorées.')
        self.assertEqual(page.locator('#favorite-select option').count(),2)
        page.get_by_label('Vue enregistrée').select_option('old');page.get_by_role('button',name='Ouvrir',exact=True).click()
        expect(page.get_by_text('Objet réinitialisé',exact=False)).to_be_visible()
        page.evaluate('localStorage.setItem("ckin2.views.v1","{}")')
        page.reload(wait_until='networkidle')
        self.assertIn('Liste de favoris invalide',page.locator('#favorite-status').inner_text())
        self.assertFalse(page.locator('#favorite-save').is_disabled())
        self.assertEqual(page.evaluate('localStorage.getItem("ckin2.views.v1")'),'{}')
        unavailable=self.context()
        unavailable.add_init_script('Object.defineProperty(window,"localStorage",{get(){throw new DOMException("Denied","SecurityError")}})')
        denied=unavailable.new_page();denied.goto(self.url,wait_until='networkidle')
        self.assertTrue(denied.locator('#favorite-save').is_disabled())
        self.assertIn('Stockage local indisponible',denied.locator('#favorite-status').inner_text())
        self.assertEqual(denied.get_by_role('heading',level=1).inner_text(),'Mon portefeuille CS2')

    def test_inventory_pagination_combined_filters_and_keyboard_on_mobile(self):
        from playwright.sync_api import expect
        for width in (1440, 390):
            with self.subTest(width=width):
                context=self.context(viewport={'width':width,'height':844})
                page=context.new_page()
                page.goto(self.url+'/?page=inventory&category=case&page_size=10',wait_until='networkidle')
                table=page.get_by_role('table',name='Objets détenus · identités exactes et couverture')
                expect(table.locator('tbody tr')).to_have_count(10)
                first_names=table.locator('tbody tr td:first-child').all_text_contents()
                subtotal=page.locator('p').filter(has_text='Valeur totale de la sélection :').inner_text()
                page.get_by_role('navigation',name='Pagination inventaire').get_by_role('link',name='Suivante').click()
                expect(page.get_by_text('Page 2 / 3',exact=True)).to_be_visible()
                self.assertFalse(set(first_names)&set(table.locator('tbody tr td:first-child').all_text_contents()))
                self.assertEqual(subtotal,page.locator('p').filter(has_text='Valeur totale de la sélection :').inner_text())
                # Submitting changed filters must reset the page and preserve scope.
                page.get_by_label('Prix',exact=True).select_option('missing')
                page.get_by_label('Quantités',exact=True).select_option('known')
                search=page.get_by_label('Rechercher un nom ou une variante')
                search.fill('case 02')
                search.focus()
                page.keyboard.press('Enter')
                expect(table.locator('tbody tr')).to_have_count(1)
                expect(table.get_by_role('link',name='Case 02',exact=True)).to_be_visible()
                expect(page.get_by_text('Page 1 / 1',exact=True)).to_be_visible()
                self.assertIn('category=case',page.url)
                self.assertIn('Filtres actifs',page.inner_text('body'))
                # Exact-object navigation and browser back keep the filtered view usable.
                table.get_by_role('link',name='Case 02',exact=True).click()
                self.assertIn('page=item',page.url)
                page.go_back(wait_until='networkidle')
                expect(table.locator('tbody tr')).to_have_count(1)
                search.fill('[no matching object]')
                search.press('Enter')
                expect(page.get_by_text('Aucun objet détenu ne correspond à cette sélection.',exact=True)).to_be_visible()
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
