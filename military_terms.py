"""Deterministic proper names shared by every translation provider."""
import re

REVISION = 'military-terms-v6'
TERMS = {
    'Pyeongtaek AAF': '평택 육군비행장(AAF)',
    'Pyeongtaek': '평택', 'Osan': '오산', 'Kunsan': '군산',
    'Maverick': '매버릭', 'Sidewinder': '사이드와인더',
    'Sparrow': '스패로', 'Raptor': '랩터', 'Harpoon': '하푼',
    'Phoenix': '피닉스', 'Hellfire': '헬파이어',
    'Paveway': '페이브웨이', 'Durandal': '듀랑달',
    'Offensive Counter Air': '공세 제공 작전',
    'Defensive Counter Air': '방어 제공 작전',
    'Enemy Air': '적기', 'enemy aircraft':'적기',
    'enemy air defenses':'적 방공망',
}
KNOWN = re.compile(r'\b(?:' + '|'.join(re.escape(t) for t in sorted(TERMS, key=len, reverse=True)) + r')\b', re.I | re.ASCII)
# Unknown airfields remain English instead of guessing their Korean names.
AIRFIELD = r"\b(?:Camp[ \t]+)?[A-Z][A-Za-z'-]*[ \t]+(?:AAF|AFB|AB)\b"
EQUIPMENT = r'\b\d+x +(?:AIM-|AGM-|GBU-|CBU-|Mk-|AN/|Tank\b|Python-|Spice\b|\d+mm\b)[^\t\r\n]+'
LOOKUP = {k.lower(): v for k, v in TERMS.items()}


def replace_known(text):
    return KNOWN.sub(lambda m: LOOKUP[m[0].lower()], text)


def spans(text, token_pattern, glossary):
    pattern = re.compile('(?i:' + EQUIPMENT + '|' + KNOWN.pattern + ')|' + AIRFIELD + '|' + token_pattern.pattern, re.ASCII)
    cursor = 0
    for m in pattern.finditer(text):
        if m.start() > cursor:
            yield False, text[cursor:m.start()]
        value = m[0]
        equipment = loadout(value.strip())
        replacement = equipment + value[len(value.rstrip()):] if equipment is not None else LOOKUP.get(value.lower(), glossary.get(value, value))
        yield True, replacement
        cursor = m.end()
    if cursor < len(text):
        yield False, text[cursor:]


def loadout(text):
    # Equipment rows are data, not prose. Keep unrecognized names intact.
    if re.fullmatch(r'\d+x\s+(?:AIM-|AGM-|GBU-|CBU-|Mk-|AN/|Tank\b|Python-|Spice\b|\d+mm\b).+', text, re.I):
        return replace_known(text).replace('Tank ', '연료탱크 ')
    return None
