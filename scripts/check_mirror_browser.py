"""Verifica el espejo con cámara sintética; requiere Playwright y Chromium."""
import argparse
import socket
import os
import tempfile
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import uvicorn
from playwright.sync_api import sync_playwright, expect
from src.mobile.server import ScanControl, create_mobile_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshot', default='/tmp/regen-mirror.png')
    args = parser.parse_args()
    test_storage = tempfile.TemporaryDirectory(prefix='regen-browser-recommendations-')
    previous_db = os.environ.get('DERMA_DB_PATH')
    previous_catalog = os.environ.get('DERMA_KNOWLEDGE_PATH')
    os.environ['DERMA_DB_PATH'] = str(Path(test_storage.name) / 'synthetic.db')
    os.environ['DERMA_KNOWLEDGE_PATH'] = str(Path(test_storage.name) / 'catalog.json')
    Path(os.environ['DERMA_KNOWLEDGE_PATH']).write_text('{"version":"synthetic-empty","rules":[]}')
    from src.db.database import get_db
    from src.db.repository import save_diagnostic_session, get_severity_by_spot_pct
    with get_db() as conn:
        severity = get_severity_by_spot_pct(conn, 1.25)
        save_diagnostic_session(conn, 'synthetic-mirror', severity['severidad_id'], 34, 1.25, 10, [])
    control = ScanControl()
    # Imagen de prueba sin fotografías personales ni datos de producción.
    y, x = np.mgrid[:720, :1280]
    frame = np.stack((45 + x // 32, 70 + y // 16, 90 + (x + y) // 24), axis=-1).astype(np.uint8)
    selector = SimpleNamespace(point=(560, 345), radius=24)
    result = {'datos': {'sesion_id': 'synthetic-mirror', 'clinica': {
        'edad_biologica_estimada': 34, 'porcentaje_hiperpigmentacion': 1.25,
        'porcentaje_hiperpigmentacion_zona': 2.5, 'fototipo_fitzpatrick': 3,
        'fototipo_label': 'Fototipo III', 'zona_seleccionada': {'x': .5, 'y': .5, 'radius': .1}},
        'capture_quality': {'status': 'ACEPTABLE', 'luminance': 128},
        'prescripciones': [{'nombre_comun': '<img src=x onerror=alert(1)>', 'precauciones': 'Texto sintético para comprobar presentación segura.'}]}}
    from src.inference.visual_appearance import analyze_visual_appearance
    appearance_rgb = np.full((512, 512, 3), [150, 110, 85], np.uint8)
    for sy in range(223, 290, 8):
        for sx in range(223, 290, 8):
            appearance_rgb[sy:sy+3, sx:sx+2] = [225, 222, 215]
    result['datos']['visual_appearance'] = analyze_visual_appearance(
        appearance_rgb, result['datos']['clinica']['zona_seleccionada'])
    mode = {'state': 'DIAGNOSTICADO', 'result': result, 'camera': True, 'session': 'synthetic-session'}
    stop = threading.Event()

    def capture():
        while not stop.wait(.05):
            control.apply_pending(lambda: mode.update(state='BUSCANDO', result=None),
                                  lambda: mode.update(state='BUSCANDO', result=None, session='synthetic-new'))
            control.publish(mode['state'], 1, mode['result'], mode['session'])
            if mode['result'] and control._analysis_preview is None:
                rgb = np.full((224, 224, 3), [150, 110, 85], np.uint8)
                mask = np.zeros((224, 224), bool)
                mask[108:114, 108:114] = True
                control.publish_analysis_preview(rgb, mask, result['datos']['clinica']['zona_seleccionada'], 'synthetic-mirror')
            control.publish_touch('COMPLETADO' if mode['result'] else 'ESPERANDO_ZONA',
                                  'Zona evaluada. Reinicia para señalar otra zona.' if mode['result'] else 'Señala una zona del rostro con el índice.', 1 if mode['result'] else 0)
            if mode['camera']:
                control.publish_preview(frame, selector if mode['result'] else None)
    threading.Thread(target=capture, daemon=True).start()
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    sock.listen(32)
    server = uvicorn.Server(uvicorn.Config(create_mobile_app(control, 'synthetic-token'), log_level='error'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1100, 'height': 1000}, reduced_motion='reduce')
            errors, violations = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('console', lambda msg: violations.append(msg.text) if msg.type == 'error' and 'Content Security Policy' in msg.text else None)
            page.goto(f'http://127.0.0.1:{sock.getsockname()[1]}/mirror')
            page.locator('#camera-empty').wait_for(state='hidden')
            page.locator('#closeup-empty').wait_for(state='hidden')
            expect(page.locator('#spots')).to_have_text('2.5 %')
            expect(page.locator('#metric-value-1')).to_have_text('2.5 %')
            expect(page.locator('#metric-value-2')).to_have_text('34 años')
            expect(page.locator('#metric-value-3')).to_have_text('III')
            expect(page.locator('.skin-closeup')).to_have_attribute('data-captured', 'true')
            expect(page.locator('#area-summary')).to_have_text('2.5 %')
            expect(page.locator('#rest-summary')).to_have_text('97.5 %')
            page.locator('#appearance-mode').click()
            assert page.locator('#appearance-mode').inner_text() == 'Análisis visual'
            assert page.locator('.measurement>div>span').all_text_contents() == ['Brillo visible', 'Textura visible', 'Señales de sequedad']
            expect(page.locator('#measurement-note')).to_contain_text('experimental')
            for i, key in enumerate(('shine', 'texture', 'dryness_cues'), 1):
                score = result['datos']['visual_appearance'][key]
                expect(page.locator(f'#metric-fill-{i}').locator('..')).to_have_attribute('aria-valuenow', str(score).removesuffix('.0'))
            page.screenshot(path=str(Path(args.screenshot).with_stem(Path(args.screenshot).stem + '-appearance')))
            old_appearance = result['datos']['visual_appearance']
            result['datos']['visual_appearance'] = {**old_appearance, 'status': 'SIN_DETALLE'}
            control._diagnostic_key = None
            expect(page.locator('#metric-value-1')).to_have_text('Sin detalle')
            expect(page.locator('#metric-fill-1').locator('..')).to_have_attribute('aria-valuenow', '0')
            result['datos']['visual_appearance'] = old_appearance
            control._diagnostic_key = None
            expect(page.locator('#metric-value-2')).to_have_text(f"{old_appearance['texture']:g} %")
            page.locator('#visual-mode').click()
            page.screenshot(path=args.screenshot)
            for width, height in ((320, 640), (390, 844), (1280, 720), (1280, 800), (1080, 1920)):
                page.set_viewport_size({'width': width, 'height': height})
                page.wait_for_function('() => document.getElementById("camera").width === Math.round(document.getElementById("camera").clientWidth)')
                dimensions = page.locator('.mirror').bounding_box()
                assert abs(dimensions['width'] - width) < 2
                assert dimensions['height'] >= height - 2
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                circle = page.locator('.camera-stage').bounding_box()
                assert abs(circle['width'] - circle['height']) < 2
                assert abs(circle['x'] + circle['width'] / 2 - width / 2) < 2
                for element_selector in ('.skin', '.measurements', '.product', '.scan-status', '.pages'):
                    box = page.locator(element_selector).bounding_box()
                    assert box['x'] >= 0 and box['y'] >= 0, (width, height, element_selector, box)
                    assert box['x'] + box['width'] <= width + 1, (width, height, element_selector, box)
                if width >= 1000:
                    assert page.evaluate("document.documentElement.scrollHeight <= innerHeight"), (width, height, "vertical overflow")
                    left = page.locator('.product').bounding_box()
                    right = page.locator('.left-panel').bounding_box()
                    assert left['x'] + left['width'] <= circle['x']
                    assert circle['x'] + circle['width'] <= right['x']
                    page.locator('#appearance-mode').click()
                    assert page.evaluate('document.documentElement.scrollHeight <= innerHeight'), (width, height, 'appearance overflow')
                    page.locator('#visual-mode').click()
                page.screenshot(path=str(Path(args.screenshot).with_stem(Path(args.screenshot).stem + f'-{width}x{height}')), full_page=True)
            page.set_viewport_size({'width': 1100, 'height': 1000})
            page.locator('#show-reading').click()
            assert page.locator('#reading-detail').is_visible()
            assert page.locator('#age').inner_text() == '34 años'
            expect(page.locator('#appearance-detail')).to_be_visible()
            expect(page.locator('#appearance-state')).to_contain_text('experimental')
            expect(page.locator('#appearance-detail')).to_contain_text('No se miden hidratación')
            page.keyboard.press('Escape')
            page.locator('#show-product').click()
            assert page.locator('#product-detail').is_visible()
            assert page.locator('#recommendations img').count() == 0
            assert page.locator('#recommendations h3').inner_text() == '<img src=x onerror=alert(1)>'
            page.locator('#open-questionnaire').click()
            page.locator('[name="sex"]').select_option('female')
            page.locator('[name="age"]').select_option('30')
            for name in ('sensitive_skin', 'salicylate_allergy', 'is_pregnant', 'is_lactating', 'has_open_wounds', 'has_cystic_acne', 'concerning_changes'):
                page.locator(f'[name="{name}"]').select_option('no')
            page.locator('[name="known_allergies_mode"]').select_option('none')
            page.locator('[name="current_treatments_mode"]').select_option('none')
            page.locator('[name="sensitive_skin"]').select_option('unknown')
            page.locator('#submit-questionnaire').click()
            expect(page.locator('#questionnaire-dialog')).not_to_be_visible()
            expect(page.locator('#product-state')).to_contain_text('Completa el cuestionario')
            page.locator('#open-questionnaire').click()
            assert page.locator('[name="age"]').input_value() == ''
            page.locator('[name="sex"]').select_option('male')
            expect(page.locator('[data-question="is_pregnant"]')).to_be_hidden()
            expect(page.locator('[name="is_pregnant"]')).to_be_disabled()
            expect(page.locator('[data-question="sensitive_skin"]')).to_contain_text('afeitarte')
            page.locator('[name="sex"]').select_option('female')
            expect(page.locator('[name="is_pregnant"]')).to_be_visible()
            expect(page.locator('[name="is_pregnant"]')).to_have_value('')
            page.locator('[name="age"]').select_option('30')
            for name in ('sensitive_skin', 'salicylate_allergy', 'is_pregnant', 'is_lactating', 'has_open_wounds', 'has_cystic_acne', 'concerning_changes'):
                page.locator(f'[name="{name}"]').select_option('no')
            page.locator('[name="known_allergies_mode"]').select_option('none')
            page.locator('[name="current_treatments_mode"]').select_option('none')
            page.locator('[name="sex"]').select_option('male')
            page.locator('[name="sensitive_skin"]').select_option('no')
            page.screenshot(path=str(Path(args.screenshot).with_stem(Path(args.screenshot).stem + '-questionnaire')))
            page.locator('#submit-questionnaire').click()
            expect(page.locator('#product-state')).to_contain_text('No hay recomendaciones revisadas')
            assert control.snapshot()['diagnostic']['orientation']['alcance'] == 'rostro_completo'
            assert not control.snapshot()['diagnostic']['prescriptions']
            expect(page.locator('#recommendation-context')).to_contain_text('El cuestionario se evaluó')
            page.screenshot(path=str(Path(args.screenshot).with_stem(Path(args.screenshot).stem + '-recommendations')))
            page.locator('#close-detail').click()
            page.locator('#new-person').click()
            page.get_by_role('button', name='Cancelar', exact=True).click()
            assert control.snapshot()['revision'] == 0
            page.locator('#restart').click()
            expect(page.locator('#spots')).to_have_text('—')
            page.locator('#closeup-empty').wait_for(state='visible')
            expect(page.locator('#restart')).to_be_enabled()
            assert control.snapshot()['revision'] == 1
            assert page.locator('[name="age"]').input_value() == ''
            page.locator('#appearance-mode').click()
            assert page.locator('.measurement output').all_text_contents() == ['—'] * 3
            page.locator('#visual-mode').click()
            expect(page.locator('#open-questionnaire')).to_be_disabled()
            page.locator('#new-person').click()
            page.locator('#new-person-confirm button[value="confirm"]').click()
            expect(page.locator('#restart')).to_be_disabled()
            expect(page.locator('#restart')).to_be_enabled()
            assert control.snapshot()['revision'] == 2 and mode['session'] == 'synthetic-new'
            page.route('**/mirror/api/status', lambda route: route.abort())
            expect(page.locator('#restart')).to_be_disabled()
            mode['camera'] = False
            page.locator('#camera-empty').wait_for(state='visible', timeout=8000)
            assert not errors, errors
            assert not violations, violations
            browser.close()
        print('Espejo OK: fotogramas, zona/ampliación, círculo centrado y paneles adaptables en cinco tamaños, análisis visual experimental, falta de detalle, detalles, cuestionario y recomendaciones, texto seguro, reinicio y desconexión; sin errores JS/CSP.')
        print(f'Captura sintética: {args.screenshot}')
    finally:
        stop.set()
        server.should_exit = True
        thread.join(3)
        sock.close()
        for name, value in [('DERMA_DB_PATH', previous_db), ('DERMA_KNOWLEDGE_PATH', previous_catalog)]:
            if value is None: os.environ.pop(name, None)
            else: os.environ[name] = value
        test_storage.cleanup()


if __name__ == '__main__':
    main()
