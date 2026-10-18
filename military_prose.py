"""Reviewed translations of recurring BMS PRINT sentences, with variable data retained."""
import re

PLACE_NAMES={'Bir Gifgafa':'비르 기프가파'}
FACILITIES={'Turbine Building':'터빈 건물','Control Center':'제어 센터','Transformer':'변압기'}


def power_plant(name):
    # Only reviewed names receive a Korean reading; unknown names stay identifiable.
    place=PLACE_NAMES.get(name)
    return (f'{place}({name})' if place else name)+' 발전소'

def location(text):
    m=re.fullmatch(r'(.+?\s+(?:nm|km|NM))\s+(northwest|northeast|southwest|southeast|north|south|west|east) of (.+)',text)
    if not m:return text
    direction={'northwest':'북서쪽','northeast':'북동쪽','southwest':'남서쪽','southeast':'남동쪽','north':'북쪽','south':'남쪽','west':'서쪽','east':'동쪽'}[m[2]]
    return f'{m[3]} {direction} {m[1]}'

FIXED={
'Strike':'타격','-- Radar EW Dome':'-- EW 레이더 돔',
'OCA STRIKE':'공세 제공 타격(OCA STRIKE)',
'STRIKE':'타격(STRIKE)','SWEEP':'전투기 소탕(SWEEP)','ESCORT':'호위(ESCORT)',
'No enemy air response is anticipated.':'적기의 대응은 예상되지 않습니다.',
'Clear sweep area of hostile aircraft':'소탕 구역 내 적기를 제거',
'Box':'상자 대형','Fair':'대체로 맑음','Attack target':'표적 공격',
'No support flights available.':'가용 지원 편대가 없습니다.',
'Intelligence reports the highest impact targets are':'정보당국이 보고한 가장 큰 타격 효과를 기대할 수 있는 주요 표적은 다음과 같습니다',
'We would like to put the facility out of commission.':'따라서 우리는 이 시설을 공격하여 가동 불능 상태로 만들고자 합니다.',
'There are no known enemy air defense assets along your flight path.':'비행 경로상에서 확인된 적 방공 전력은 없습니다.',
'Destroy or other facilities at target site':'표적 지역의 기타 시설을 파괴',
'-- Small Desert Bunker':'-- 소형 사막 벙커',
'Enemy CAP aircraft are likely to be operating within operation area.':'작전 구역 내에서 적 전투초계(CAP) 항공기가 활동할 가능성이 있습니다.',
'Protect package elements from enemy aircraft':'적기로부터 패키지 소속 편대를 보호',
'Pre IP':'IP 이전 지점','Turn Pt':'선회 지점',
'Ladder':'계단 대형','ArrowHead':'화살촉 대형','Arrowhead':'화살촉 대형',
'Line Abreast':'횡대 대형','Trail':'종대 대형',
'Rot/day':'일일 코드 변경 횟수',
'x  = Primary Flight':'x = 주 임무 편대',
'Visually ID unknown aircraft before engaging, unless authorized by AWACS.':'AWACS의 허가가 없는 경우, 미식별 항공기는 교전 전에 육안으로 식별(ID)해야 합니다.',
'Note: Friendly aircraft may be operating in the area.':'주의: 해당 구역에서 아군 항공기가 활동할 수 있습니다.',
'For aircrew in a hostile area, prior to ejection, transmit on the working frequency: “MAYDAY” (three times); call-sign; and position in relation to BULLSEYE.':'적 지역에서 비상탈출하기 전, 사용 중인 주파수로 “MAYDAY”를 세 번 송신하고 호출부호와 BULLSEYE 기준 위치를 보고하십시오.',
'Sanitise yourself and review your evasion plan of action.':'노출될 수 있는 개인·작전 정보를 정리하고 탈출 및 회피 행동계획을 재확인하십시오.',
'Global Check-In':'전체 구역 최초 교신','Package Comms':'패키지 통신','Primary Flight':'주 임무 편대','Tank':'연료탱크','base':'기준 고도',
}

def reviewed(text):
    if text in FIXED:return FIXED[text]
    if text.endswith(':') and text[:-1] in FIXED:return FIXED[text[:-1]]+':'
    if text in FACILITIES:return FACILITIES[text]
    if text.startswith('-- ') and text[3:] in FACILITIES:return '-- '+FACILITIES[text[3:]]
    m=re.fullmatch(r'Be advised: Intelligence reports a large enemy offensive is in progress, probably with the intent to take (.+?)\.',text)
    if m:
        objective='목표 지역을 점령하는 것' if m[1] in ('target','the target') else m[1]+' 점령인 것'
        return '주의: 정보당국에 따르면 현재 적군이 대규모 공세를 진행 중이며, 그 목적은 아마도 '+objective+'으로 추정됩니다.'
    m=re.fullmatch(r"Intelligence claims the (.+?) Power Plant is producing a substantial portion of the enemy['’]s electrical power\.(\s+We would like to put the facility out of commission\.)?",text)
    if m:
        result='정보당국에 따르면 '+power_plant(m[1])+'는 적군이 사용하는 전력의 상당 부분을 생산하고 있습니다.'
        if m[2]:result+=' 따라서 우리는 이 발전소를 공격하여 가동 불능 상태로 만들고자 합니다.'
        return result
    m=re.fullmatch(r'Strike (.+?) Power Plant',text)
    if m:return power_plant(m[1])+' 타격'
    m=re.fullmatch(r'([A-Za-z][A-Za-z0-9]+) \((OCA STRIKE|STRIKE|SWEEP|ESCORT)\)',text)
    if m:return m[1]+' ('+FIXED[m[2]]+')'
    m=re.fullmatch(r'(\d+)%operational',text)
    if m:return m[1]+'% 가동 중'
    m=re.fullmatch(r"([A-Z][A-Za-z0-9'(). -]*?) (Ground|Tower|Approach|Departure|ATIS)",text)
    if m:
        base={'Osan':'오산','Pyeongtaek':'평택','Kunsan':'군산'}.get(m[1],m[1])
        service={'Ground':'지상관제','Tower':'관제탑','Approach':'접근관제','Departure':'출항관제','ATIS':'ATIS'}[m[2]]
        return base+' '+service
    m=re.fullmatch(r'(.+? Airbase), (\d+(?:\.\d+)?\s+(?:nm|km|NM) (?:northwest|northeast|southwest|southeast|north|south|west|east) of .+)',text)
    if m:return m[1]+', '+location(m[2])
    m=re.fullmatch(r'-- (.+?)anti-aircraft guns over (.+)',text)
    if m:return '-- '+m[1]+' 대공포 · '+m[2]+' 일대'
    m=re.fullmatch(r'Destroy (.+?)or other facilities at target site',text)
    if m:return m[1].strip()+' 또는 표적 지역의 기타 시설을 파괴'
    m=re.fullmatch(r'Destroy (.+?)at target site',text)
    if m:return '표적 지역의 '+FACILITIES.get(m[1].strip(),m[1].strip())+' 파괴'
    m=re.fullmatch(r'Strike (.+)',text)
    if m:return m[1]+' 타격'
    m=re.fullmatch(r'(-?\d+(?:\.\d+)?deg\s+C\.?)',text)
    if m:return m[1]+' (섭씨)'
    m=re.fullmatch(r'Key ([AB]):\s*(.+)',text)
    if m:return f'암호키 {m[1]}: {m[2]}'
    m=re.fullmatch(r'(.+? \([A-Z0-9]{4}\)), (\d+(?:\.\d+)?\s+(?:nm|km|NM) (?:northwest|northeast|southwest|southeast|north|south|west|east) of .+)',text)
    if m:return m[1]+', '+location(m[2])
    m=re.fullmatch(r'BRIEFING RECORD generated at (.+)\.',text)
    if m:return '브리핑 생성 기록(BRIEFING RECORD) · '+m[1]+'.'
    m=re.fullmatch(r'In an effort to obtain air superiority, air command has initiated an Offensive Counter Air operation targeted at the area around (.+?)\. If everything goes as planned, earlier DEAD raids and fighter sweeps will have suppressed or cleared most of the air defenses in the region allowing us to strike several airbases, search radars and command facilities including your target, (.+)\.',text)
    if m:return f'제공권 확보를 위해 항공 지휘부는 {m[1]} 주변 지역에 대한 공세 제공 작전을 개시했습니다. 계획대로 진행된다면 선행 적 방공망 파괴(DEAD) 공격과 전투기 소탕 작전으로 이 지역 방공망 대부분이 제압되거나 제거될 것입니다. 이에 따라 비행장·탐색 레이더·지휘 시설을 타격할 수 있으며, 귀 편대의 표적은 {m[2]}입니다.'
    m=re.fullmatch(r'Be advised: Starting at (.+?), our ground forces will be making a major push towards (.+)\.',text)
    if m:return f'상황 전파: {m[1]}부터 아군 지상군이 {m[2]} 방면으로 대규모 진격을 실시할 예정입니다.'
    m=re.fullmatch(r'In an effort to obtain air superiority, air command has initiated an Offensive Counter Air operation targeted at the area around (.+?)\. As part of this effort, air command needs you to destroy or suppress the enemy\'s air defenses in an attempt to clear the way for additional strikes\. Your target is the (.+?), located (.+?), which consists of (.+)\.',text)
    if m:
        target=m[2].replace('Battalion','대대');weapons=m[4].replace('several ','').replace(' guns',' 대공포')
        return f'제공권 확보를 위해 항공 지휘부는 {m[1]} 주변 지역에 대한 공세 제공 작전을 개시했습니다. 후속 타격 부대의 진입로를 확보하기 위해 적 방공 전력을 파괴하거나 제압하십시오. 표적은 {location(m[3])}에 위치한 {target}이며, {weapons} 여러 문으로 구성되어 있습니다.'
    m=re.fullmatch(r'--\s*(.+?)missile launchers (.+)',text)
    if m:return '-- '+m[1]+' 미사일 발사대 · '+location(m[2])
    m=re.fullmatch(r'Friendly (AWACS|JSTAR) aircraft will be operating (.+?)\. Available for (.+)\.',text)
    if m:
        role={'air detection and warning':'공중 표적 탐지 및 경보 지원 가능','ground movement queries':'지상 이동 표적 정보 요청 가능'}.get(m[3],m[3])
        return f'아군 {m[1]} 항공기는 {location(m[2])}에서 작전할 예정입니다. {role}.'
    m=re.fullmatch(r'Friendly tankers will be operating (.+?)\. Available for mid-air refueling\. \(TCN: (.+?)\)',text)
    if m:return f'아군 공중급유기는 {location(m[1])}에서 작전할 예정입니다. 공중급유 지원 가능. (TCN: {m[2]})'
    m=re.fullmatch(r'SAR helos are available within (.+?) of FLOT\. In case of shoot-down, mark closest coordinates of the survivor[’\']s position and report the incident to the CSAR assets\. Establish radio communication with survivor and execute the On Scene Commander procedures\.?',text)
    if m:return f'FLOT로부터 {m[1]} 이내에서 SAR 헬기 지원이 가능합니다. 격추 시 생존자 위치에 가장 가까운 좌표를 표시하고 CSAR 전력에 상황을 보고하십시오. 생존자와 무선 교신을 수립하고 현장지휘관 절차를 수행하십시오.'
    if re.fullmatch(r'\d+(?:\.\d+)?\s+(?:nm|km|NM) (?:northwest|northeast|southwest|southeast|north|south|west|east) of .+\.',text):return location(text[:-1])+'.'
    return None
