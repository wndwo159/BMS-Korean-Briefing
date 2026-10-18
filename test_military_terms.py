from collections import Counter
import main
from offline_translation import OfflineTranslator
from military_terms import spans


def test_equipment_and_airfield_never_enter_neural_model():
    translator = OfflineTranslator.__new__(OfflineTranslator)
    translator.fragment = lambda text: (_ for _ in ()).throw(AssertionError(text))
    cases = {
        'Pyeongtaek AAF': '평택 육군비행장(AAF)',
        '6x AGM-65D Maverick': '6x AGM-65D 매버릭',
        '2x AIM-9M Sidewinder': '2x AIM-9M 사이드와인더',
        '2x AGM-65D UnknownWeapon': '2x AGM-65D UnknownWeapon',
        'Unknownfield AAF': 'Unknownfield AAF',
    }
    for text, expected in cases.items():
        output = translator.translate(text, main.TOKEN, {})
        assert output == expected
        assert Counter(main.TOKEN.findall(text)) == Counter(main.TOKEN.findall(output))


def test_shared_protection_keeps_duplicates_units_and_unknown_names():
    text = 'Sidewinder / Sidewinder 305.000 MHz Pyeongtaek AAF Unknownfield AAF'
    parts = list(spans(text, main.TOKEN, {}))
    values = [value for keep, value in parts if keep]
    assert values == ['사이드와인더', '사이드와인더', '305.000 MHz', '평택 육군비행장(AAF)', 'Unknownfield AAF']


def test_pilot_name_does_not_consume_next_table_cell():
    assert main.TOKEN.findall('2Lt. JoongJae Pilot\tUnassigned') == ['2Lt. JoongJae Pilot']


def test_remote_provider_also_protects_entire_unknown_loadout():
    assert list(spans('6x AGM-65D UnknownWeapon\t2x AIM-9M Sidewinder', main.TOKEN, {})) == [
        (True, '6x AGM-65D UnknownWeapon'), (False, '\t'), (True, '2x AIM-9M 사이드와인더')]


def test_dictionary_upgrade_reprocesses_same_source(tmp_path):
    engine=main.Engine(tmp_path/'data',opener=lambda url:None)
    engine.config.update(provider='test',output_dir=str(tmp_path/'out'),watch_dir=str(tmp_path/'in'),auto_open=False)
    source=tmp_path/'in'/'mission.html';source.parent.mkdir();source.write_text('<p>Maverick</p>','utf-8')
    engine.stable_read=lambda p:p.read_bytes()
    translated=[]
    engine.translate=lambda text:translated.append(text) or '매버릭'
    try:
        engine.process(source);count=len(translated)
        engine.process(source);assert len(translated)==count
        engine.db.execute("UPDATE translation_versions SET version='previous-dictionary'");engine.db.commit()
        engine.process(source);assert len(translated)>count
    finally:engine.close()


def test_inline_bms_label_uses_reviewed_dictionary():
    translator=OfflineTranslator.__new__(OfflineTranslator);translator.cache={}
    assert translator.fragment('Ext. Time Ref.: No')=='외부 시간 기준: 아니요'
    assert translator.fragment('Flt Lead: Yes')=='편대장: 예'
