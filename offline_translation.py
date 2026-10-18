"""CPU-only English to Korean inference using an Argos CTranslate2 model.
No network access at inference time. Numeric/operational spans never enter the model.
"""
import re
from pathlib import Path
from military_prose import reviewed
from military_terms import spans, replace_known, loadout

class NeedsInference(Exception):pass

def reviewed_translation(text,token_pattern,glossary):
    """Use the same reviewed cells for every provider without loading a model."""
    translator=OfflineTranslator.__new__(OfflineTranslator)
    translator.cache={};translator.dictionary_only=True
    try:return translator.translate(text,token_pattern,glossary)
    except NeedsInference:return None

LABELS = {
'Airstrike':'공중 타격',
'GENERAL':'일반 설정(GENERAL)','TIME EVENTS':'시각별 변경(TIME EVENTS)','POS EVENTS':'위치별 변경(POS EVENTS)','FILE A':'설정 파일(FILE A)','FILE B':'설정 파일(FILE B)','END_OF_BRIEFING':'브리핑 끝(END_OF_BRIEFING)','Mission Overview':'임무 개요','Situation':'전장 상황','Pilot Roster':'조종사 편성','Package Elements':'패키지 편성','Threat Analysis':'위협 분석','Steerpoints':'비행계획 / 스티어포인트','Comm Ladder':'통신 계획','Iff':'피아식별 (Iff)','Link 16':'데이터링크 Link 16','Ordnance':'무장 구성','Weather':'기상','Support':'지원 전력','Rules of Engagement':'교전 수칙','Emergency Procedures':'비상 절차',
'Callsign':'호출부호','Flt Lead':'편대장','Wing Two':'윙맨','Elem Lead':'분대장','Elem Two':'분대 윙맨','Flt #':'편대 번호','Role':'임무 역할','Aircraft':'항공기','Task':'세부 임무','Package #':'패키지 번호','Pkg-Mission':'패키지 임무','Target Area':'표적 지역','Time on Target':'표적 도착시각','Sunrise':'일출','Sunset':'일몰',
'Air-to-Air Threats':'공대공 위협','Surface-To-Air Threats':'지대공 위협','Desc':'설명','Time':'시각','Dist':'거리','Head':'방위','Cas':'보정대기속도','Alt':'고도','Action':'행동','Form':'대형','Comments':'비고','Agency':'통신 대상','Uhf [Chnl]':'Uhf [채널]','Vhf [Chnl]':'Vhf [채널]','Notes':'비고',
'Takeoff':'이륙','Take Off':'이륙','Land':'착륙','Refuel':'공중급유','Holding Pt':'대기 지점','Push':'공격 진입','Split':'패키지 이탈','Wedge':'쐐기 대형','Spread':'산개 대형','Climb immediate':'즉시 상승','Climb delayed':'지연 상승','Descend immediate':'즉시 강하','Descend delayed':'지연 강하','Rendezvous with package':'패키지와 합류','Engage enemy air defenses':'적 방공 전력 교전','Depart from package':'패키지에서 이탈','Tanker station area':'공중급유기 대기 구역','Land (Alternate)':'대체 비행장 착륙',
'Strike enemy air defense assets':'적 방공 전력 타격','Destroy enemy air defense assets':'적 방공 전력 파괴','Protect package from enemy air defenses':'적 방공 위협으로부터 패키지 보호','Suppression of Enemy Air Defenses':'적 방공망 제압','Enemy CAP aircraft are likely to be operating within operation area.':'작전 구역 내에서 적 전투초계(CAP) 항공기가 활동할 가능성이 있습니다.',
'Known or suspected enemy air defenses along your flight path include':'비행 경로를 따라 확인되었거나 추정되는 적 방공 전력',
'Intra-Flight':'편대 내부','Guard':'비상 주파수','Common':'공통 주파수','Base Ops':'기지 작전','Check-In':'최초 교신','Tactical':'전술 통신','Tanker / Aar':'공중급유','Dep Atis':'출발 비행장 Atis','Dep Ground':'출발 지상관제','Dep Tower':'출발 관제탑','Dep Departure':'출발 출항관제','Arr Atis':'복귀 비행장 Atis','Arr Approach':'복귀 접근관제','Arr Tower':'복귀 관제탑','Arr Ground':'복귀 지상관제','Alt Atis':'대체 비행장 Atis','Alt Approach':'대체 접근관제','Alt Tower':'대체 관제탑','Alt Ground':'대체 지상관제',
'Flight Management Comms':'편대 운용 통신','Distress / Emergency':'조난 / 비상','Advisory / UNICOM':'비행정보 / UNICOM','Homeplate Operations':'모기지 작전','Departure Airbase':'출발 비행장','Recovery Airbase':'복귀 비행장','Alternate Airbase':'대체 비행장','Boom Operator':'급유 붐 조작원','Station Area':'작전 구역','Conditions@':'기상 조건','Landing':'착륙','Sunny':'맑음','Wind':'바람','Visibility':'시정','Temp':'기온','Cloud Base':'운저 고도','Con Layer':'비행운 형성층','None':'없음','Yes':'예','No':'아니요','Good Luck!':'무운을 빕니다!',
'Distress call':'조난 통신','Combat Search and Rescue':'전투 탐색구조','Alternate airfield':'대체 비행장','Initial STAT Settings':'초기 STAT 설정','Modes Active':'활성 모드','Codes':'코드','IFF Policy':'IFF 운용 방침','Code Change Setting':'코드 변경 설정','M4 Validity Time (Until)':'M4 유효 시한','per team':'팀별','per aircraft':'항공기별','Ingress':'진입','Egress':'이탈','Ext. Time Ref.':'외부 시간 기준','Number':'번호','Channels':'채널','Donor':'정보 제공기','Team':'팀','Flight':'편대','Mission':'임무','Fighter':'전투기','Special':'특수','Departure':'출발','Hold':'대기','Tank':'연료탱크','T/O':'이륙(T/O)','Tgt':'표적','Hold  (Departure':'대기 (출발','Global Check-In':'전체 구역 최초 교신','Package Comms':'패키지 통신','AN':'AN'
}

class OfflineTranslator:
    def __init__(self, root=None):
        import ctranslate2
        import sentencepiece
        root = Path(root or Path(__file__).parent/'models'/'en_ko')
        if not (root/'model'/'model.bin').exists():
            raise RuntimeError('영어→한국어 모델이 없습니다. setup.ps1을 실행하세요.')
        self.tokenizer=sentencepiece.SentencePieceProcessor(model_file=str(root/'sentencepiece.model'))
        self.model=ctranslate2.Translator(str(root/'model'),device='cpu',compute_type='int8',inter_threads=1,intra_threads=2)
        self.cache={}

    def fragment(self, text):
        if text in self.cache:return self.cache[text]
        if text in ('A','B','C') or re.fullmatch(r'\(?\s*x\s*\)?',text):return text
        for label in sorted(LABELS,key=len,reverse=True):
            if text.startswith(label+':'):
                tail=text[len(label)+1:]
                space=tail[:len(tail)-len(tail.lstrip())]
                return LABELS[label]+':'+space+(self.fragment(tail.strip()) if tail.strip() else '')
        inner=text.strip(' ()[]:.,')
        if inner in LABELS and inner!=text:
            return text.replace(inner,LABELS[inner],1)
        # Short BMS labels use reviewed military terminology; prose uses the neural model.
        if text in LABELS:return LABELS[text]
        known=reviewed(text)
        if known is not None:return known
        if getattr(self,'dictionary_only',False):raise NeedsInference()
        pieces=re.split(r'(?<=[.!?])\s+(?=[A-Z])',text)
        output=[]
        for piece in pieces:
            tokens=self.tokenizer.encode(piece,out_type=str)
            if len(tokens)>200:
                # Bound inference size without truncating input.
                chunks=[tokens[i:i+160] for i in range(0,len(tokens),160)]
            else:chunks=[tokens]
            results=self.model.translate_batch(chunks,beam_size=4,replace_unknowns=True,max_decoding_length=512)
            output.append(' '.join(self.tokenizer.decode(r.hypotheses[0]) for r in results))
        result=' '.join(output);self.cache[text]=result
        return result

    def translate(self,text,token_pattern,glossary):
        # Preserve tabs and whitespace so the text PRINT tables can be reconstructed.
        pieces=re.split(r'(\t+|\r?\n)',text)
        result=[]
        for piece in pieces:
            if not piece or not re.search('[A-Za-z]',piece):result.append(piece);continue
            leading=piece[:len(piece)-len(piece.lstrip())];trailing=piece[len(piece.rstrip()):]
            stripped=piece.strip();suffix=''
            equipment=loadout(stripped)
            if equipment is not None:
                result.append(leading+equipment+trailing);continue
            core=stripped
            if core.endswith(':'):core=core[:-1].rstrip();suffix=':'
            if core in LABELS:
                result.append(leading+LABELS[core]+suffix+trailing);continue
            known=reviewed(stripped)
            if known is not None:
                result.append(leading+replace_known(known)+trailing);continue
            translated=[]
            for protected,value in spans(stripped,token_pattern,glossary):
                if protected:translated.append(glossary.get(value,value));continue
                if not re.search('[A-Za-z]',value):translated.append(value);continue
                left=value[:len(value)-len(value.lstrip())];right=value[len(value.rstrip()):]
                content=value.strip()
                translated.append(left+self.fragment(content)+right if content else value)
            result.append(leading+''.join(translated)+trailing)
        return ''.join(result)
