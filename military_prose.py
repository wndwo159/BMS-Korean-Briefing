"""Reviewed translations of recurring BMS PRINT sentences, with variable data retained."""
import re

def location(text):
    m=re.fullmatch(r'(.+?\s+(?:nm|km|NM))\s+(northwest|northeast|southwest|southeast|north|south|west|east) of (.+)',text)
    if not m:return text
    direction={'northwest':'북서쪽','northeast':'북동쪽','southwest':'남서쪽','southeast':'남동쪽','north':'북쪽','south':'남쪽','west':'서쪽','east':'동쪽'}[m[2]]
    return f'{m[3]} {direction} {m[1]}'

FIXED={
'No enemy air response is anticipated.':'적기의 대응은 예상되지 않습니다.',
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
    m=re.fullmatch(r'(Osan|Pyeongtaek|Kunsan) (Ground|Tower|Approach|Departure|ATIS)',text)
    if m:
        base={'Osan':'오산','Pyeongtaek':'평택','Kunsan':'군산'}[m[1]]
        service={'Ground':'지상관제','Tower':'관제탑','Approach':'접근관제','Departure':'출항관제','ATIS':'ATIS'}[m[2]]
        return base+' '+service
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
    m=re.fullmatch(r'SAR helos are available within (.+?) of FLOT\. In case of shoot-down, mark closest coordinates of the survivor[’\']s position and report the incident to the CSAR assets\. Establish radio communication with survivor and execute the On Scene Commander procedures\.',text)
    if m:return f'FLOT로부터 {m[1]} 이내에서 SAR 헬기 지원이 가능합니다. 격추 시 생존자 위치에 가장 가까운 좌표를 표시하고 CSAR 전력에 상황을 보고하십시오. 생존자와 무선 교신을 수립하고 현장지휘관 절차를 수행하십시오.'
    if re.fullmatch(r'\d+(?:\.\d+)?\s+(?:nm|km|NM) (?:northwest|northeast|southwest|southeast|north|south|west|east) of .+\.',text):return location(text[:-1])+'.'
    return None
