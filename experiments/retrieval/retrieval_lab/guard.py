"""Conservative experiment guard. Reads questions/facts, never oracle answers."""
from dataclasses import dataclass
import re


def matches(pattern, text):
    return bool(re.search(pattern, text, re.I))


@dataclass(frozen=True)
class Scope:
    query: str
    targets: tuple = ()
    fallback: str = ''
    abstain: bool = False


UNSUPPORTED = r'날씨|기온|강수|비가|운영시간|영업시간|개장|폐장|weather|opening|hours|교통|버스|지하철|차량|차로|transport|subway|\bbus\b'
OVERRIDE = r'규칙.{0,10}무시|정책.{0,10}무시|ignore.{0,15}(rule|policy)|혼잡도.{0,10}0이라고'
REFERENCE = r'그날|거기|그곳|그건|그것|그럼|\b(that|there)\b'
TOPIC = r'혼잡|백분위|집중률|대안|방문|순서|데이터|기준|crowd|alternative|order|policy|출처|지역|source|region'
GENERIC = {'혼잡도 등급의 기준은 무엇인가요?', '대안 점수는 어떻게 계산하나요?', '방문 순서는 어떤 규칙으로 정하나요?'}


def resolve(question, history, facts):
    def fallback(reason, context=question, abstain=False):
        return Scope(context, fallback=reason, abstain=abstain)
    if not question.strip():
        return fallback('FALLBACK_UNKNOWN_INTENT')
    if matches(OVERRIDE, question):
        return fallback('FALLBACK_RULE_OVERRIDE', abstain=True)
    if matches(UNSUPPORTED, question):
        return fallback('FALLBACK_UNSUPPORTED_TOPIC', abstain=True)
    items = facts.get('items', [])
    places = {i.get('name', '') for i in items if i.get('name')}
    def names(text):
        found = {p for p in places if p in text}
        if matches(r'경복궁|\bGyeongbokgung\b', text):
            found.add('경복궁')
        return found
    context, targets = question, names(question)
    position = re.search(r'(첫|두 번째|first|second)\s*(방문지|장소|stop)', question, re.I)
    if position and not targets:
        order = 1 if position[1].lower() in {'첫', 'first'} else 2
        selected = [i for i in items if i.get('visitOrder') == order]
        if len(selected) != 1:
            return fallback('FALLBACK_UNRESOLVED_REFERENCE')
        targets = {selected[0]['name']}
    if not targets and matches(REFERENCE, question):
        for turn in reversed(history):
            prior = turn['question']
            context += '\n' + prior
            found = names(prior)
            if len(found) > 1:
                return fallback('FALLBACK_AMBIGUOUS_REFERENCE', context)
            if found:
                targets = found
                break
            if not matches(REFERENCE, prior):
                break
        if not targets:
            return fallback('FALLBACK_UNRESOLVED_REFERENCE', context)
    if matches(UNSUPPORTED, context):
        return fallback('FALLBACK_UNSUPPORTED_TOPIC', context, True)
    if matches(OVERRIDE, context):
        return fallback('FALLBACK_RULE_OVERRIDE', context, True)
    if not targets and question.strip() not in GENERIC:
        return fallback('FALLBACK_UNKNOWN_INTENT', context)
    if not matches(TOPIC, context):
        return fallback('FALLBACK_UNKNOWN_INTENT', context)
    return Scope(context + '\n' + '\n'.join(sorted(targets)), tuple(sorted(targets)))


def facts_for(agent, suite, case):
    import json
    path = agent / case.get('factsFixture', suite['baseFactsFixture'])
    raw = json.loads(path.read_text())
    return raw['backendResponses']['GET /api/v1/courses/{uuid}']['data']
