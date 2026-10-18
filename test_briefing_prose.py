from collections import Counter
import json
import pytest
import main
from offline_translation import reviewed_translation

OFFENSIVE='Be advised: Intelligence reports a large enemy offensive is in progress, probably with the intent to take target.'
POWER="Intelligence claims the Bir Gifgafa Power Plant is producing a substantial portion of the enemy's electrical power. We would like to put the facility out of commission."
TARGETS='Intelligence reports the highest impact targets are:'
OFFENSIVE_KR='주의: 정보당국에 따르면 현재 적군이 대규모 공세를 진행 중이며, 그 목적은 아마도 목표 지역을 점령하는 것으로 추정됩니다.'
POWER_KR='정보당국에 따르면 비르 기프가파(Bir Gifgafa) 발전소는 적군이 사용하는 전력의 상당 부분을 생산하고 있습니다. 따라서 우리는 이 발전소를 공격하여 가동 불능 상태로 만들고자 합니다.'
TARGETS_KR='정보당국이 보고한 가장 큰 타격 효과를 기대할 수 있는 주요 표적은 다음과 같습니다:'


def test_user_reference_paragraphs_apply_without_neural_inference(tmp_path,monkeypatch):
    engine=main.Engine(tmp_path/'app',opener=lambda _:None)
    engine.config.update(provider='ollama',model='unused')
    monkeypatch.setattr(main.httpx,'post',lambda *a,**k:(_ for _ in ()).throw(AssertionError('reviewed prose reached the model')))
    try:
        source='\t'+OFFENSIVE+'\n\n\t'+POWER+'\n\t'+TARGETS
        assert engine.translate(source)=='\t'+OFFENSIVE_KR+'\n\n\t'+POWER_KR+'\n\t'+TARGETS_KR
    finally:engine.close()


def test_variable_targets_and_wrapped_power_paragraph_keep_source_data():
    for name in ('Unknownfield','Site 42 EW'):
        source=POWER.replace('Bir Gifgafa',name).replace("enemy's",'enemy’s')
        result=reviewed_translation(source,main.TOKEN,{})
        assert name+' 발전소' in result
        assert '비르 기프가파' not in result
        assert Counter(main.TOKEN.findall(source))==Counter(main.TOKEN.findall(result))
    lines=POWER.split('. ')
    assert reviewed_translation(lines[0]+'.',main.TOKEN,{})==POWER_KR.split('. ')[0]+'.'
    assert '가동 불능' in reviewed_translation(lines[1],main.TOKEN,{})
    result=reviewed_translation(OFFENSIVE.replace('take target.','take Hatzor.'),main.TOKEN,{})
    assert 'Hatzor' in result and '추정' in result and '아마도' in result


def test_facility_orders_and_known_defenses_are_not_misinterpreted():
    cases={
        'Destroy Turbine Buildingat target site':'표적 지역의 터빈 건물 파괴',
        'Destroy Transformerat target site':'표적 지역의 변압기 파괴',
        'Strike Bir Gifgafa Power Plant':'비르 기프가파(Bir Gifgafa) 발전소 타격',
        '3841 (Airstrike)':'3841 (공중 타격)',
        'There are no known enemy air defense assets along your flight path.':'비행 경로상에서 확인된 적 방공 전력은 없습니다.',
    }
    for source,expected in cases.items():
        result=reviewed_translation(source,main.TOKEN,{})
        assert result==expected
        assert Counter(main.TOKEN.findall(source))==Counter(main.TOKEN.findall(result))


@pytest.mark.parametrize('model',['local-test','translategemma:4b'])
def test_unreviewed_model_prose_receives_military_style_rules(tmp_path,monkeypatch,model):
    engine=main.Engine(tmp_path/model.replace(':','-'),opener=lambda _:None)
    engine.config.update(provider='ollama',model=model)
    class Response:
        def raise_for_status(self):pass
        def json(self):
            return {'response':json.dumps({'id':'text','translation':'새로운 정보 보고입니다.'}),'message':{'content':'새로운 정보 보고입니다.'}}
    def post(url,**kwargs):
        payload=kwargs['json']
        prompt=payload.get('prompt') or payload['messages'][0]['content']
        assert main.BRIEFING_STYLE in prompt
        assert payload['options']['temperature']==0
        return Response()
    monkeypatch.setattr(main.httpx,'post',post)
    try:assert engine.translate('Unfamiliar intelligence briefing.')=='새로운 정보 보고입니다.'
    finally:engine.close()
