"""Prueba UI con lecturas sintéticas. Requiere playwright + Chromium; no cámara."""
import argparse
import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from playwright.sync_api import sync_playwright
from src.mobile.server import ScanControl, create_mobile_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshot', default='/tmp/derma-mobile-diagnostic.png')
    args = parser.parse_args()
    control = ScanControl()
    result = {'datos': {'sesion_id': 'synthetic-analysis', 'clinica': {
        'edad_biologica_estimada': 34, 'porcentaje_hiperpigmentacion': 1.25,
        'clasificacion_severidad': 'LEVE', 'fototipo_fitzpatrick': 3,
        'fototipo_label': 'Fototipo III', 'ita_deg': 35.6, 'estrato_etario': 'ADULTO',
        'indicacion_primaria': 'Indicación sintética para probar la interfaz.', 'gafas_detectadas': False},
        'prescripciones': [{'nombre_comun': 'Recomendación de prueba', 'especie': 'Especie de prueba',
                            'precauciones': 'Texto sintético. Revisar las precauciones indicadas por el equipo.'}]}}
    stop = threading.Event()
    mode = {'state': 'DIAGNOSTICADO', 'result': result}

    def camera():
        while not stop.wait(.05):
            def restart():
                mode.update(state='BUSCANDO', result=None)
            control.apply_pending(restart)
            control.publish(mode['state'], 3, mode['result'], 'sesion-sintetica')
    threading.Thread(target=camera, daemon=True).start()
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    sock.listen(32)
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_mobile_app(control, 'test-code'), log_level='error'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{port}')
            page.locator('#token').fill('wrong')
            page.locator('#connect').click()
            page.get_by_text('Código de acceso incorrecto o vencido.').wait_for()
            page.locator('#token').fill('test-code')
            page.locator('#show-token').click()
            assert page.locator('#token').get_attribute('type') == 'text'
            page.locator('#connect').click()
            page.locator('#diagnostic').wait_for(state='visible')
            assert page.locator('#age').inner_text() == '34'
            assert page.locator('#phototype').inner_text() == 'III'
            assert page.locator('#session-id').text_content() == 'sesion-sintetica'
            assert page.locator('#prescriptions article').count() == 1
            page.screenshot(path=args.screenshot, full_page=True)
            for width in (320, 390, 768, 1280):
                page.set_viewport_size({'width': width, 'height': 844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.set_viewport_size({'width': 390, 'height': 844})
            page.evaluate("Object.defineProperty(document, 'hidden', {configurable:true, value:true}); document.dispatchEvent(new Event('visibilitychange'))")
            assert page.locator('#age').text_content() == ''
            page.evaluate("Object.defineProperty(document, 'hidden', {configurable:true, value:false}); document.dispatchEvent(new Event('visibilitychange'))")
            page.locator('#diagnostic').wait_for(state='visible')
            page.locator('#restart').click()
            page.get_by_role('button', name='Volver al resultado', exact=True).click()
            assert control.snapshot()['revision'] == 0
            assert page.locator('#diagnostic').is_visible()
            page.route('**/api/status', lambda route: route.abort())
            page.locator('#refresh').click()
            page.locator('#diagnostic').wait_for(state='hidden')
            assert page.locator('#age').inner_text() == ''
            assert page.locator('#restart').is_disabled()
            page.unroute('**/api/status')
            page.locator('#diagnostic').wait_for(state='visible')
            page.locator('#restart').click()
            page.get_by_role('button', name='Sí, reiniciar escaneo', exact=True).click()
            page.get_by_text('Escaneo reiniciado. Esperando una nueva lectura.').wait_for()
            assert page.locator('#diagnostic').is_hidden()
            assert page.locator('#age').inner_text() == ''
            assert control.snapshot()['revision'] == 1
            mode.update(state='ANALIZANDO')
            page.get_by_role('heading', name='Analizando lectura', exact=True).wait_for()
            assert page.locator('#restart').is_disabled()
            second = {'datos': {'sesion_id': 'synthetic-second', 'clinica': {}, 'prescripciones': [
                {'nombre_comun': '<img src=x onerror=alert(1)>', 'precauciones': '<script>bad()</script>'}]}}
            mode.update(state='DIAGNOSTICADO', result=second)
            page.locator('#diagnostic').wait_for(state='visible')
            assert page.locator('#age').inner_text() == 'No disponible'
            assert page.locator('#prescriptions img').count() == 0
            assert page.locator('#prescriptions script').count() == 0
            assert page.locator('#prescriptions h4').inner_text() == '<img src=x onerror=alert(1)>'
            for width in (320, 390):
                page.set_viewport_size({'width': width, 'height': 844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.locator('#logout').click()
            assert page.locator('#pairing').is_visible()
            assert page.locator('#age').inner_text() == ''
            assert page.locator('#prescriptions').inner_text() == ''
            assert page.evaluate('localStorage.length + sessionStorage.length') == 0
            assert not errors, errors
            browser.close()
        print('UI OK: conexión, lectura, precauciones, anchos 320–1280, cancelación, desconexión, reconexión, reinicio, análisis, datos faltantes, texto seguro y cierre.')
    finally:
        stop.set()
        server.should_exit = True
        thread.join(3)
        sock.close()


if __name__ == '__main__':
    main()
