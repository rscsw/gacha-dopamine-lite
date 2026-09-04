import json
import random
import time
import msvcrt
from pathlib import Path

SAVE_FILE = Path(__file__).with_name("gacha_save.json")

# 시작 코인 / 1회 뽑기 가격 / 10연차 가격 / 천장 한도
START_COINS = 10_000_000
SINGLE_COST = 100
TEN_COST = 1_000
PITY_LIMIT = 1_000

BLACK  = "\033[30m"
RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
BLUE   = "\033[34m"
PURPLE = "\033[35m"
CYAN   = "\033[36m"
WHITE  = "\033[37m"

BRIGHT_BLACK   = "\033[90m"
BRIGHT_RED     = "\033[91m"
BRIGHT_GREEN   = "\033[92m"
BRIGHT_YELLOW  = "\033[93m"
BRIGHT_BLUE    = "\033[94m"
BRIGHT_MAGENTA = "\033[95m"
BRIGHT_CYAN    = "\033[96m"
BRIGHT_WHITE   = "\033[97m"

RESET = "\033[0m"

# 이름, 확률, 중복 시 환급 코인, 색상, 심볼을 자유롭게 수정할 수 있습니다.
# 형식: (레어리티 이름, 확률(%), 중복 환급 코인, 색상(ANSI), 심볼)
RARITIES = [
    ("LEGEND", 0.1, 100, BRIGHT_RED, "☆"),
    ("SSR", 0.5, 50, YELLOW, "★★★"),
    ("SR", 2, 10, BRIGHT_BLUE, "★★"),
    ("R", 10, 5, BRIGHT_CYAN, "★"),
    ("N", 87.4, 1, WHITE, ""),
]

# ── RARITIES 캐시 (가독성을 해치지 않는 선에서 반복 연산 절감) ──
# 모듈 로드 시 1회 계산, 이후 조회는 O(1). 런타임에 RARITIES를 수정하면 _refresh_rarity_cache()로 갱신.
_RARITY_NAMES = [r[0] for r in RARITIES]
_RARITY_WEIGHTS = [r[1] for r in RARITIES]
_RARITY_REFUND_MAP = {r[0]: (r[2] if len(r) > 2 else 0) for r in RARITIES}
_RARITY_COLOR_MAP = {r[0]: (r[3] if len(r) > 3 else None) for r in RARITIES}
_RARITY_SYMBOL_MAP = {r[0]: (r[4] if len(r) > 4 else None) for r in RARITIES}
_RARITY_ORDER = list(_RARITY_NAMES)
# 천장 대상은 SSR 우선, LEGEND 제외
_PITY_RARITY_CACHE = next(
    (r[0] for r in RARITIES if r[0] == "SSR"),
    next((r[0] for r in RARITIES if r[0] != "LEGEND"), RARITIES[0][0] if RARITIES else "SSR"),
)


def _refresh_rarity_cache():
    global _RARITY_NAMES, _RARITY_WEIGHTS, _RARITY_REFUND_MAP, _RARITY_COLOR_MAP, _RARITY_SYMBOL_MAP, _RARITY_ORDER, _PITY_RARITY_CACHE
    _RARITY_NAMES = [r[0] for r in RARITIES]
    _RARITY_WEIGHTS = [r[1] for r in RARITIES]
    _RARITY_REFUND_MAP = {r[0]: (r[2] if len(r) > 2 else 0) for r in RARITIES}
    _RARITY_COLOR_MAP = {r[0]: (r[3] if len(r) > 3 else None) for r in RARITIES}
    _RARITY_SYMBOL_MAP = {r[0]: (r[4] if len(r) > 4 else None) for r in RARITIES}
    _RARITY_ORDER = list(_RARITY_NAMES)
    _PITY_RARITY_CACHE = next(
        (r[0] for r in RARITIES if r[0] == "SSR"),
        next((r[0] for r in RARITIES if r[0] != "LEGEND"), RARITIES[0][0] if RARITIES else "SSR"),
    )


def _ensure_rarity_cache():
    # RARITIES가 런타임에 수정된 경우(추가/삭제) 캐시 갱신 — 가벼운 길이/첫원소 비교
    if len(_RARITY_NAMES) != len(RARITIES) or (RARITIES and _RARITY_NAMES and _RARITY_NAMES[0] != RARITIES[0][0]):
        _refresh_rarity_cache()
    elif _RARITY_REFUND_MAP.get(_RARITY_NAMES[0] if _RARITY_NAMES else None) is None and RARITIES:
        # 내용이 바뀐 경우 방어적 갱신
        if set(_RARITY_NAMES) != {r[0] for r in RARITIES}:
            _refresh_rarity_cache()

# ── 가챠 종류 정의 ──
# 레어리티(확률/환급/색상/심볼), 가격, 천장 한도는 전역 상수(RARITIES/SINGLE_COST/TEN_COST/PITY_LIMIT)로 통일됩니다.
# 가챠별로 items(보상 목록)와 천장 도달율(진행도)만 따로 관리됩니다.
# 아이템 정의는 외부 JSON(gacha_items.json)에서 로드하여 코드 수정 없이 아이템을 관리할 수 있습니다.
GACHA_ITEMS_FILE = Path(__file__).with_name("gacha_items.json")

_DEFAULT_GACHAS = {
    "별빛 가챠": {
        "items": {
            "LEGEND": ["별의 수호자", "빛의 정령"],
            "SSR": ["전설의 황금 고양이", "우주를 삼킨 슬라임", "시간을 거스르는 토끼", "신비한 검은 별"],
            "SR": ["반짝이는 여우", "달빛 마법서", "행운의 부적", "구름 위의 집", "푸른 불꽃"],
            "R": ["맛있는 쿠키", "작은 화분", "낡은 게임기", "고양이 스티커", "반짝이는 돌"],
            "N": ["돌멩이", "나뭇가지", "빈 상자", "구겨진 영수증", "평범한 양말"],
        },
        "desc": "아름다운 별빛을 모아보세요!",
    },
    "심해 가챠": {
        "items": {
            "LEGEND": ["심해의 크라켄", "심연의 진주"],
            "SSR": ["공기방울 트랩", "아쿠아마린 열쇠", "고대 해룡", "깊은 밤 등대"],
            "SR": ["발광 해파리", "산호 마법사", "조개 보물상자", "파도 정령", "인어의 노래"],
            "R": ["반짝이는 조약돌", "소라 껍데기", "작은 거북이", "물고기 떼", "해초 다발"],
            "N": ["젖은 모래", "빈 병", "낡은 밧줄", "물방울", "조그만 돌"],
        },
        "desc": "깊은 심해를 탐험해 보세요!",
    },
    "도심 가챠": {
        "items": {
            "LEGEND": ["낡은 플로피 디스크", "네온사인 유령"],
            "SSR": ["네온 황제 고양이", "야경의 지배자", "전설의 택시 기사", "옥상 위의 달"],
            "SR": ["반짝이는 간판", "심야 라면", "행운의 동전", "빗속 우산", "도시의 바람"],
            "R": ["종이컵", "전단지", "낡은 이어폰", "버스 티켓", "작은 화분"],
            "N": ["구겨진 영수증", "빈 캔", "돌멩이", "나뭇잎", "플라스틱 조각"],
        },
        "desc": "도심 속 숨겨진 보물을 찾아보세요!",
    },
}


def _load_gachas():
    """gacha_items.json에서 가챠 아이템 정의를 로드. 실패 시 기본값 반환."""
    if not GACHA_ITEMS_FILE.exists():
        return _DEFAULT_GACHAS
    try:
        with GACHA_ITEMS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # 기본 검증: dict 형태이고 각 가챠에 items/desc가 있는지 확인
        if not isinstance(data, dict) or not data:
            print(f"경고: {GACHA_ITEMS_FILE.name} 형식이 올바르지 않아 기본 아이템을 사용합니다.")
            return _DEFAULT_GACHAS
        # 최소 검증 — items가 없는 가챠는 기본값으로 대체하지 않고 경고만
        for name, gacha in list(data.items()):
            if not isinstance(gacha, dict) or "items" not in gacha:
                print(f"경고: 가챠 '{name}' 정의가 올바르지 않아 제외됩니다.")
                data.pop(name, None)
        if not data:
            return _DEFAULT_GACHAS
        return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"경고: {GACHA_ITEMS_FILE.name} 로드 실패({e}) — 기본 아이템을 사용합니다.")
        return _DEFAULT_GACHAS


GACHAS = _load_gachas()


def resolve_gacha(gacha_name=None, gacha=None):
    # 가챠 해석 헬퍼 — 3중 분기 중복 제거 (가독성 ↑)
    if gacha is None and gacha_name is None:
        gacha_name = next(iter(GACHAS))
        return gacha_name, GACHAS[gacha_name]
    if gacha is not None and gacha_name is None:
        for n, v in GACHAS.items():
            if v is gacha:
                return n, v
        gacha_name = next(iter(GACHAS))
        return gacha_name, GACHAS[gacha_name]
    if gacha is None and gacha_name is not None:
        return gacha_name, GACHAS.get(gacha_name, GACHAS[next(iter(GACHAS))])
    return gacha_name, gacha


# ── 가챠별 남은 아이템 증분 캐시 (4-2) ──
# 전체 스캔 대신 신규 획득 시 1씩 감소, 조회는 O(1)
_GACHA_ALL_KEYS = {name: {f"{r}:{item}" for r, lst in g["items"].items() for item in lst} for name, g in GACHAS.items()}
_GACHA_NON_LEGEND_KEYS = {name: {f"{r}:{item}" for r, lst in g["items"].items() if r != "LEGEND" for item in lst} for name, g in GACHAS.items()}
_GACHA_REMAINING_TOTAL = {name: len(keys) for name, keys in _GACHA_ALL_KEYS.items()}
_GACHA_REMAINING_NON_LEGEND = {name: len(keys) for name, keys in _GACHA_NON_LEGEND_KEYS.items()}

# ── 표시 정렬 캐시 (4-3) ──
# GACHAS 정의가 불변이므로 정렬 결과를 1회 캐시, show_collection에서 반복 정렬 제거
_GACHAS_SORTED = {name: {rarity: sorted(lst) for rarity, lst in g["items"].items()} for name, g in GACHAS.items()}


def _refresh_gacha_remaining_cache(data=None):
    global _GACHA_ALL_KEYS, _GACHA_NON_LEGEND_KEYS, _GACHA_REMAINING_TOTAL, _GACHA_REMAINING_NON_LEGEND, _GACHAS_SORTED
    _GACHA_ALL_KEYS = {name: {f"{r}:{item}" for r, lst in g["items"].items() for item in lst} for name, g in GACHAS.items()}
    _GACHA_NON_LEGEND_KEYS = {name: {f"{r}:{item}" for r, lst in g["items"].items() if r != "LEGEND" for item in lst} for name, g in GACHAS.items()}
    _GACHAS_SORTED = {name: {rarity: sorted(lst) for rarity, lst in g["items"].items()} for name, g in GACHAS.items()}
    if data is None:
        _GACHA_REMAINING_TOTAL.update({name: len(keys) for name, keys in _GACHA_ALL_KEYS.items() if name not in _GACHA_REMAINING_TOTAL})
        _GACHA_REMAINING_NON_LEGEND.update({name: len(keys) for name, keys in _GACHA_NON_LEGEND_KEYS.items() if name not in _GACHA_REMAINING_NON_LEGEND})
        # 삭제된 가챠 정리
        for name in list(_GACHA_REMAINING_TOTAL.keys()):
            if name not in GACHAS:
                _GACHA_REMAINING_TOTAL.pop(name, None)
                _GACHA_REMAINING_NON_LEGEND.pop(name, None)
                _GACHA_ALL_KEYS.pop(name, None)
                _GACHA_NON_LEGEND_KEYS.pop(name, None)
    else:
        coll = set(data.get("collection", {}).keys())
        for name in GACHAS:
            all_keys = _GACHA_ALL_KEYS[name]
            non_keys = _GACHA_NON_LEGEND_KEYS[name]
            _GACHA_REMAINING_TOTAL[name] = len(all_keys - coll)
            _GACHA_REMAINING_NON_LEGEND[name] = len(non_keys - coll)
        # 삭제된 가챠 정리 (data가 있는 경우에도)
        for name in list(_GACHA_REMAINING_TOTAL.keys()):
            if name not in GACHAS:
                _GACHA_REMAINING_TOTAL.pop(name, None)
                _GACHA_REMAINING_NON_LEGEND.pop(name, None)


def _on_new_item_acquired(data, gacha_name, rarity, item):
    # 신규 아이템 획득 시 증분 갱신 — O(1)
    key = f"{rarity}:{item}"
    # 해당 가챠의 키셋에 포함된 경우에만 감소 (중복이 아닌 경우에만 호출됨)
    if key in _GACHA_ALL_KEYS.get(gacha_name, set()):
        if _GACHA_REMAINING_TOTAL[gacha_name] > 0:
            _GACHA_REMAINING_TOTAL[gacha_name] -= 1
    if rarity != "LEGEND" and key in _GACHA_NON_LEGEND_KEYS.get(gacha_name, set()):
        if _GACHA_REMAINING_NON_LEGEND[gacha_name] > 0:
            _GACHA_REMAINING_NON_LEGEND[gacha_name] -= 1
    # 동일 아이템이 여러 가챠에 존재할 수 있으므로, 다른 가챠도 갱신 (드문 경우지만 정확성 보장)
    for other_name, keys in _GACHA_ALL_KEYS.items():
        if other_name == gacha_name:
            continue
        if key in keys and _GACHA_REMAINING_TOTAL[other_name] > 0:
            # 다른 가챠에도 동일 키가 존재하면 해당 가챠도 진행도 감소 (공유 아이템)
            # 단, collection은 전역이므로 실제로는 해당 가챠의 남은 개수도 감소해야 함
            # 이를 위해 전체 재계산 대신 해당 키만 체크
            if key not in data.get("collection", {}) or data["collection"].get(key, 0) == 1:
                # 방금 첫 획득인 경우에만 감소 (중복 호출 방지)
                _GACHA_REMAINING_TOTAL[other_name] = max(0, _GACHA_REMAINING_TOTAL[other_name] - 1)
                if rarity != "LEGEND" and key in _GACHA_NON_LEGEND_KEYS.get(other_name, set()):
                    _GACHA_REMAINING_NON_LEGEND[other_name] = max(0, _GACHA_REMAINING_NON_LEGEND[other_name] - 1)


def _is_all_cleared(data, gacha_name):
    # 증분 캐시 기반 O(1) — 전체 스캔 제거
    if gacha_name not in _GACHA_REMAINING_TOTAL:
        _refresh_gacha_remaining_cache(data)
    # GACHAS가 늘어난 경우 방어적 갱신
    if gacha_name not in _GACHA_REMAINING_TOTAL:
        return False
    return _GACHA_REMAINING_TOTAL.get(gacha_name, 0) == 0


def _update_clear_flags(data):
    # 클리어 조건 빠른 확인용 캐시 — 세이브 파일에 저장됨
    # legend_unlocked: SSR~N 수집으로 LEGEND 해금 여부
    # fully_cleared: 전체 아이템 클리어 여부
    data["legend_unlocked"] = {name: _is_legend_unlocked(data, name) for name in GACHAS}
    data["fully_cleared"] = {name: _is_all_cleared(data, name) for name in GACHAS}
    # 구 버전 호환: cleared_legend_o/x 제거 — 존재하면 삭제
    data.pop("cleared_legend_o", None)
    data.pop("cleared_legend_x", None)
    data.pop("cleared_legend", None)
    return data


def default_save():
    base = {
        "coins": START_COINS,
        "pity": {name: 0 for name in GACHAS},
        "total_pulls": 0,
        "collection": {},
    }
    # 증분 캐시 초기화 + 클리어 플래그 초기화
    _refresh_gacha_remaining_cache(base)
    _update_clear_flags(base)
    return base


def _migrate_pity(pity_value):
    # 과거 저장(정수형 pity) → 가챠별 딕셔너리로 마이그레이션
    # 가격/천장 한도는 통일되었으므로, 기존 pity를 모든 가챠에 동일 적용
    if isinstance(pity_value, dict):
        # 누락된 가챠는 0으로 보정, 삭제된 가챠 키는 유지하되 정수화
        migrated = {name: int(pity_value.get(name, 0)) for name in GACHAS}
        # 기존 저장에 있던 알 수 없는 가챠 키도 보존 (혹시 모를 호환성)
        for k, v in pity_value.items():
            if k not in migrated:
                try:
                    migrated[k] = int(v)
                except (ValueError, TypeError):
                    migrated[k] = 0
        return migrated
    elif isinstance(pity_value, int):
        return {name: int(pity_value) for name in GACHAS}
    else:
        return {name: 0 for name in GACHAS}


def _get_pity(data, gacha_name):
    # load_save에서 마이그레이션이 완료되므로 정상 경로는 항상 dict
    return int(data["pity"].get(gacha_name, 0))


def _set_pity(data, gacha_name, value):
    # 단순 대입 — 누락 키는 자동으로 생성, 신규 가챠도 0으로 시작 후 갱신
    data["pity"][gacha_name] = int(value)


def load_save():
    if not SAVE_FILE.exists():
        return default_save()

    try:
        with SAVE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

        base = default_save()
        base.update(data)
        # pity 마이그레이션
        base["pity"] = _migrate_pity(base.get("pity", 0))
        # collection 등 기본 키 보정
        if "coins" not in base:
            base["coins"] = START_COINS
        if "total_pulls" not in base:
            base["total_pulls"] = 0
        if "collection" not in base:
            base["collection"] = {}
        # 증분 캐시 재계산 + 클리어 플래그 재계산 (기존 세이브 호환)
        _refresh_gacha_remaining_cache(base)
        _update_clear_flags(base)
        return base
    except (json.JSONDecodeError, OSError):
        print("저장 파일을 읽을 수 없어 새 게임으로 시작합니다.")
        return default_save()


def save_game(data):
    try:
        # 저장 전 클리어 플래그 갱신으로 빠른 확인 가능
        _update_clear_flags(data)
        with SAVE_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"저장 실패: {e}")


def weighted_rarity():
    _ensure_rarity_cache()
    return random.choices(_RARITY_NAMES, weights=_RARITY_WEIGHTS, k=1)[0]


def get_duplicate_refund(rarity):
    _ensure_rarity_cache()
    return _RARITY_REFUND_MAP.get(rarity, 0)


def _is_legend_unlocked(data, gacha_name):
    # 증분 캐시 기반 O(1) — SSR~N 전체 스캔 제거
    if gacha_name not in _GACHA_REMAINING_NON_LEGEND:
        _refresh_gacha_remaining_cache(data)
    if gacha_name not in _GACHA_REMAINING_NON_LEGEND:
        return False
    # LEGEND가 없는 가챠는 항상 해금 (남은 개수가 0인 경우도 포함)
    gacha = GACHAS.get(gacha_name)
    if gacha and "LEGEND" not in gacha["items"]:
        return True
    return _GACHA_REMAINING_NON_LEGEND.get(gacha_name, 0) == 0


def _get_pity_rarity():
    # 천장은 LEGEND가 아닌 SSR에 적용 — 캐시 활용
    _ensure_rarity_cache()
    return _PITY_RARITY_CACHE


def pull_one(data, gacha_name=None, gacha=None):
    # 가격(PITY_LIMIT/SINGLE_COST)은 전역으로 통일, 진행도(pity)는 가챠별
    gacha_name, gacha = resolve_gacha(gacha_name, gacha)

    items = gacha["items"]
    pity = _get_pity(data, gacha_name)
    pity_rarity = _get_pity_rarity()

    # 천장일 때 무조건 SSR (LEGEND 아님)
    if pity + 1 >= PITY_LIMIT:
        rarity = pity_rarity
    else:
        rarity = weighted_rarity()
        # 선택된 레어리티에 아이템이 없으면(잘못된 설정) 재추첨
        if rarity not in items or not items[rarity]:
            # 가용 레어리티 중 재추첨 — 캐시 활용
            _ensure_rarity_cache()
            available = [r for r in _RARITY_ORDER if r in items and items[r]]
            if available:
                # 가중치 유지하며 재추첨
                filtered = [(n, w) for n, w, *_ in RARITIES if n in available]
                if filtered:
                    names = [n for n, _ in filtered]
                    weights = [w for _, w in filtered]
                    rarity = random.choices(names, weights=weights, k=1)[0]
                else:
                    rarity = available[0]
            else:
                rarity = pity_rarity
        # LEGEND 등급은 SSR~N을 모두 모은 뒤에만 등장, 그 전까지는 SSR로 치환
        if rarity == "LEGEND" and not _is_legend_unlocked(data, gacha_name):
            # 미해금 상태에서 LEGEND가 추첨되면 SSR 아이템으로 대체
            if pity_rarity in items and items[pity_rarity]:
                rarity = pity_rarity
            else:
                # SSR 아이템이 없는 예외적 설정 방어: 다른 가용 등급 중 가장 희귀한 것으로 대체
                _ensure_rarity_cache()
                available = [r for r in _RARITY_ORDER if r != "LEGEND" and r in items and items[r]]
                rarity = available[0] if available else pity_rarity

    # 방어: 아이템이 없으면 더미 아이템 생성
    if rarity not in items or not items[rarity]:
        item = f"({rarity} 아이템 없음)"
    else:
        item = random.choice(items[rarity])

    data["coins"] -= SINGLE_COST
    data["total_pulls"] += 1

    if rarity == pity_rarity:
        _set_pity(data, gacha_name, 0)
    else:
        _set_pity(data, gacha_name, pity + 1)

    key = f"{rarity}:{item}"
    is_duplicate = key in data["collection"]
    refund = get_duplicate_refund(rarity) if is_duplicate else 0
    if refund:
        data["coins"] += refund
    data["collection"][key] = data["collection"].get(key, 0) + 1
    if not is_duplicate:
        _on_new_item_acquired(data, gacha_name, rarity, item)

    return rarity, item, refund


def rarity_symbol(rarity):
    # RARITIES에 정의된 색상/심볼을 우선 사용 — 캐시 O(1) 조회
    _ensure_rarity_cache()
    if rarity in _RARITY_SYMBOL_MAP and _RARITY_SYMBOL_MAP[rarity] is not None:
        color = _RARITY_COLOR_MAP.get(rarity) or ""
        symbol = _RARITY_SYMBOL_MAP[rarity] or ""
        return f"{color}{symbol} "
    if rarity in _RARITY_COLOR_MAP and _RARITY_COLOR_MAP[rarity]:
        return f"{_RARITY_COLOR_MAP[rarity]} "


def show_result(rarity, item, refund=0):
    if refund:
        print(f"  {rarity_symbol(rarity)}{item} {BRIGHT_BLACK}[+{refund}P]{RESET}")
    else:
        print(f"  {rarity_symbol(rarity)}{item} {BRIGHT_GREEN}[NEW!]{RESET}")


def pull_animation(count):
    frames = ["", "=", "===", "=====", "=======", "==========", "=============", "==============="]
    print()
    print("  가챠를 돌리는 중...", end="", flush=True)

    for frame in frames:
        print("\r  가챠를 돌리는 중... " + frame, end="", flush=True)
        time.sleep(0.08)

    print("\n  결과가 나왔습니다!")
    # wait_for_keypress("> 확인하기")


def single_pull(data, gacha_name=None, gacha=None):
    gacha_name, gacha = resolve_gacha(gacha_name, gacha)

    if data["coins"] < SINGLE_COST:
        print("\n코인이 부족합니다.")
        wait_for_keypress("> 돌아가기")
        return

    pull_animation(1)
    rarity, item, refund = pull_one(data, gacha_name, gacha)

    pity = _get_pity(data, gacha_name)
    pity_rarity = _get_pity_rarity()
    print(f"\n  [{gacha_name}]")
    show_result(rarity, item, refund)
    if refund:
        print(f"  → 중복 보상으로 {refund}P가 환급되었습니다!")
    print(f"\n  남은 코인: {data['coins']:,}P")
    print(f"  {pity_rarity} 천장까지: {PITY_LIMIT - pity}회")

    save_game(data)
    wait_for_keypress("> 돌아가기")


def ten_pull(data, gacha_name=None, gacha=None):
    gacha_name, gacha = resolve_gacha(gacha_name, gacha)

    if data["coins"] < TEN_COST:
        print("\n코인이 부족합니다.")
        wait_for_keypress("> 확인 완료")
        return

    pull_animation(10)

    results = [pull_one(data, gacha_name, gacha) for _ in range(10)]

    print(f"\n  ───────── [{gacha_name}] 10연차 결과 ─────────")
    for rarity, item, refund in results:
        show_result(rarity, item, refund)
    print("  ───────────────────────────────")

    total_refund = sum(refund for _, _, refund in results)
    dup_count = sum(1 for _, _, refund in results if refund > 0)

    pity = _get_pity(data, gacha_name)
    pity_rarity = _get_pity_rarity()
    if dup_count:
        print(f"  중복: {dup_count}개 → 총 {total_refund:,}P 환급!")
    print(f"  남은 코인: {data['coins']:,}P")
    print(f"  {pity_rarity} 천장까지: {PITY_LIMIT - pity}회")

    save_game(data)
    wait_for_keypress("> 확인 완료")


def _show_single_gacha_collection(data, gacha_name):
    # 단일 가챠의 획득 현황 상세 출력 — 캐시 활용
    _ensure_rarity_cache()
    rarity_order = list(_RARITY_ORDER)
    gacha = GACHAS.get(gacha_name)
    if not gacha:
        print(f"\n존재하지 않는 가챠: {gacha_name}")
        return
    items_by_rarity = gacha["items"]
    total = sum(len(v) for v in items_by_rarity.values())
    remaining = _GACHA_REMAINING_TOTAL.get(gacha_name)
    if remaining is None:
        _refresh_gacha_remaining_cache(data)
        remaining = _GACHA_REMAINING_TOTAL.get(gacha_name, total)
    collected = total - remaining
    is_clear = collected == total and total > 0
    clear_tag = f" {BRIGHT_GREEN}Clear!{RESET}" if is_clear else ""
    unlocked = _is_legend_unlocked(data, gacha_name)
    lock_tag = "" if unlocked else f" {BRIGHT_BLACK}[LEGEND 잠김]{RESET}"
    print(f"\n[{gacha_name}]{clear_tag}{lock_tag} ({collected}/{total})")
    for rarity in rarity_order:
        sorted_list = _GACHAS_SORTED.get(gacha_name, {}).get(rarity)
        if sorted_list is None:
            item_list = items_by_rarity.get(rarity, [])
            if not item_list:
                continue
            sorted_list = sorted(item_list)
        elif not sorted_list:
            continue
        print(f"  [{rarity}] {rarity_symbol(rarity).strip()}")
        for item in sorted_list:
            key = f"{rarity}:{item}"
            count = data["collection"].get(key, 0)
            if count > 0:
                print(f"    {rarity_symbol(rarity)}{item} × {count}{RESET}")
            else:
                print(f"    {BRIGHT_BLACK}{item} (미획득){RESET}")
    wait_for_keypress("> 확인 완료")


def show_collection(data):
    # 획득한 아이템이 없으면 선택 옵션 없이 바로 복귀
    if not data["collection"]:
        print("\n========== 획득 기록 ==========")
        print("아직 획득한 아이템이 없습니다.")
        wait_for_keypress("> 확인 완료")
        return
    # 가챠 종류 선택 후 해당 가챠의 획득 기록만 확인
    while True:
        print("\n========== 획득 기록 ==========")
        _ensure_rarity_cache()
        if set(_GACHAS_SORTED.keys()) != set(GACHAS.keys()):
            _refresh_gacha_remaining_cache(data)
        gacha_names = list(GACHAS.keys())
        for idx, name in enumerate(gacha_names, 1):
            total = sum(len(v) for v in GACHAS[name]["items"].values())
            remaining = _GACHA_REMAINING_TOTAL.get(name)
            if remaining is None:
                _refresh_gacha_remaining_cache(data)
                remaining = _GACHA_REMAINING_TOTAL.get(name, total)
            collected = total - remaining
            is_clear = collected == total and total > 0
            clear_tag = f" {BRIGHT_GREEN}Clear!{RESET}" if is_clear else ""
            print(f"  {idx}. [{name}]{clear_tag} ({collected}/{total})")
        print("  A. 전체 보기")
        print("  0. 뒤로가기")
        choice = input("\n  가챠 선택 > ").strip().lower()
        if choice == "0":
            return
        if choice in ("a", "ㅁ"):
            # 전체 보기 — 기존처럼 전체 순회하되 한 번에
            for name in gacha_names:
                _show_single_gacha_collection(data, name)
            continue
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(gacha_names):
                _show_single_gacha_collection(data, gacha_names[idx])
            else:
                print("\n올바른 번호를 입력해주세요.")
        except ValueError:
            print("\n올바른 번호를 입력해주세요.")


def reset_game(data):
    print("\n정말 처음부터 다시 시작하시겠습니까? (y/n)")
    answer = input("  입력: ").strip().lower()

    if answer in ("y", "ㅛ"):
        new_data = default_save()
        save_game(new_data)
        print("\n게임 데이터를 초기화했습니다.")
        return new_data

    print("초기화를 취소했습니다.")
    return data


def show_status(data):
    print("\n========== 상태 ==========")
    print(f"  보유 : {data['coins']:,}P")
    print(f"  총 뽑기 : {data['total_pulls']:,}회")
    print(f"  천장 : {PITY_LIMIT}회")
    print(f"  1회 가격 : {SINGLE_COST:,}P / 10연차: {TEN_COST:,}P")
    # for name in GACHAS:
    #     pity = _get_pity(data, name)
    #     remain = PITY_LIMIT - pity
    #     if remain < 0:
    #         remain = 0
    #     print(f"    - {name}: {pity}/{PITY_LIMIT}")
    print(f"  가챠 종류 : {len(GACHAS)}종")
    for name in GACHAS:
        print(f"    - {name}")


def wait_for_keypress(comment=None):
    if comment:
        print(f"\n{comment}", end=" ", flush=True)
    else:
        # comment가 없어도 커서가 보이도록 공백 없이 대기
        print("", end="", flush=True)
    msvcrt.getch()
    print()


def gacha_menu(data):
    while True:
        print("\n========== 가챠 선택 ==========")
        # 레어리티/가격/천장 한도는 공통, 진행도만 가챠별 — RARITIES를 그대로 표시
        print(f"  공통: 1회 {SINGLE_COST:,}P / 10연차 {TEN_COST:,}P | {_get_pity_rarity()} 천장 {PITY_LIMIT}")
        rarity_info = " | ".join(f"{name}: {prob}%" for name, prob, *_ in RARITIES)
        print(f"  {rarity_info}\n")
        gacha_names = list(GACHAS.keys())
        for idx, name in enumerate(gacha_names, 1):
            g = GACHAS[name]
            pity = _get_pity(data, name)
            remain = PITY_LIMIT - pity
            if remain < 0:
                remain = 0
            print(f"  {idx}. {name}")
        print("  0. 뒤로가기")

        choice = input("\n  가챠 선택 > ").strip()
        if choice == "0":
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(gacha_names):
                name = gacha_names[idx]
                gacha = GACHAS[name]
                gacha_pull_menu(data, name, gacha)
            else:
                print("\n올바른 번호를 입력해주세요.")
        except ValueError:
            print("\n올바른 번호를 입력해주세요.")


def gacha_pull_menu(data, gacha_name, gacha):
    while True:
        pity = _get_pity(data, gacha_name)
        remain = PITY_LIMIT - pity
        if remain < 0:
            remain = 0
        print("\n")
        print(f"  ★ {gacha_name} ★")
        print(f"  {gacha['desc']}\n")
        
        print(f"  보유 : {data['coins']:,}P")
        print(f"  천장 : {pity}/{PITY_LIMIT}\n")
        
        print(f"  1. 1회 뽑기 ({SINGLE_COST:,}P)")
        print(f"  2. 10연차 ({TEN_COST:,}P)")
        print("  0. 뒤로가기")
        
        choice = input("\n  선택 > ").strip()
        if choice == "1":
            single_pull(data, gacha_name, gacha)
        elif choice == "2":
            ten_pull(data, gacha_name, gacha)
        elif choice == "0":
            return
        else:
            print("\n올바른 번호를 입력해주세요.")


def show_game_instructions():
    print("\n========== 게임 방법 ==========")
    print("  가챠를 뽑아 다양한 아이템을 획득하세요.")
    print("  중복된 아이템은 코인으로 환급됩니다.")
    print("  LEGEND 등급은 SSR~N 아이템을 모두 모은 후에만 등장합니다.")
    print("  LEGEND 등급에는 천장이 없습니다.")
    wait_for_keypress("> 확인 완료")

def main():
    data = load_save()

    while True:
        print("\n")
        print("  ★ 무한 가챠 ★\n")
        
        print(f"  보유 : {data['coins']:,}P")
        print(f"  가격 : {SINGLE_COST}P/회 | 천장: {PITY_LIMIT}\n")
        
        print("  1. 가챠 뽑기")
        print("  2. 획득 기록")
        print("  3. 상태 보기")
        print("  4. 게임 방법")
        print("  5. 데이터 초기화")
        print("  0. 종료")
        # print(f"  * {len(GACHAS)}종의 가챠가 준비되어 있습니다.")
        # # 가챠별 천장 요약
        # for name in GACHAS:
        #     pity = _get_pity(data, name)
        #     remain = PITY_LIMIT - pity
        #     print(f"    - {name}: {pity}/{PITY_LIMIT} (남은 {remain}회)")

        choice = input("\n  선택 > ").strip()

        if choice == "1":
            gacha_menu(data)
        elif choice == "2":
            show_collection(data)
        elif choice == "3":
            show_status(data)
            wait_for_keypress("> 확인 완료")
        elif choice == "4":
            show_game_instructions()
        elif choice == "5":
            data = reset_game(data)
        elif choice == "0":
            save_game(data)
            print("\n게임을 종료합니다. 다음에 또 뽑아주세요.")
            break
        else:
            print("\n올바른 번호를 입력해주세요.")


if __name__ == "__main__":
    main()