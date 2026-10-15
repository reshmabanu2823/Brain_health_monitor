"""Opt-in rendered UI checks: BHM_BROWSER_URL=http://127.0.0.1:8000 pytest ..."""
import os
from pathlib import Path
import pytest

URL=os.getenv('BHM_BROWSER_URL')
pytestmark=pytest.mark.skipif(not URL,reason='Requires running local server and Playwright Chromium')


def test_eeg_desktop_mobile_and_backend_failure(tmp_path):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--disable-gpu'])
        page=browser.new_page(viewport={'width':1440,'height':1000})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(URL+'/eeg')
        page.get_by_text('Backend connected',exact=True).wait_for()
        assert 'EEG Research' in page.title()
        page.get_by_role('button',name='Connect',exact=True).click()
        assert 'Choose an available serial port' in page.locator('#error').inner_text()
        page.locator('#source').select_option('simulated')
        page.get_by_role('button',name='Connect',exact=True).click()
        page.get_by_text('SIMULATED · DEMO',exact=True).wait_for()
        page.get_by_role('button',name='Start recording',exact=True).click()
        page.get_by_role('button',name='Stop recording',exact=True).wait_for(state='visible')
        page.wait_for_function("!document.getElementById('stop-record').disabled")
        page.wait_for_timeout(6500)
        assert 'SIMULATED DATA' in page.locator('#notice').inner_text()
        assert page.locator('#quality').inner_text()=='Checks passed'
        assert page.locator('#prediction').inner_text()=='No prediction'
        page.get_by_role('button',name='Stop recording',exact=True).click()
        page.get_by_role('link',name='Export simulated session',exact=False).first.wait_for()
        page.screenshot(path=str(tmp_path/'eeg-desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(tmp_path/'eeg-mobile.png'),full_page=True)
        page.get_by_role('button',name='Disconnect',exact=True).click()
        page.wait_for_function("document.getElementById('connection').textContent==='disconnected'")
        page.route('**/api/eeg/live',lambda route:route.fulfill(status=503,json={'detail':'Offline test'}))
        page.get_by_text('Backend unavailable',exact=True).wait_for()
        assert page.locator('#prediction').inner_text()=='No prediction'
        assert not errors,errors
        browser.close()


def test_mri_upload_report_and_navigation(tmp_path):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--disable-gpu'])
        page=browser.new_page(viewport={'width':1440,'height':1000})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(URL+'/')
        page.get_by_text('MRI ENGINE LOADED',exact=True).wait_for()
        assert page.locator('#tele-accuracy').inner_text()=='Not evaluated'
        page.locator('#file-input').set_input_files(str(Path(__file__).resolve().parents[1]/'static/samples/glioma.jpg'))
        page.locator('#btn-analyse').click()
        page.wait_for_function("!document.getElementById('btn-export-report').disabled",timeout=60000)
        assert 'MODEL:' in page.locator('#badge-text').inner_text()
        page.locator('#btn-export-report').click()
        page.get_by_text('RESEARCH MODEL ANALYSIS REPORT',exact=True).wait_for()
        with page.expect_download(timeout=30000) as info:
            page.locator('#btn-download-pdf').click()
        file=info.value.path()
        assert Path(file).read_bytes().startswith(b'%PDF')
        page.locator('#modal-close').click()
        page.get_by_role('link',name='EEG workspace',exact=True).click()
        assert page.url.endswith('/eeg')
        assert not errors,errors
        browser.close()
