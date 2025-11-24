import openai
import os
import yaml
import json
from pathlib import Path
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

OUTPUT_FILE_NAME = "item_plans.json"

# API 키 로드 (환경 변수 또는 keys.json 파일에서)
def get_api_key():
    """API 키를 환경 변수 또는 keys.json에서 가져옴"""
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        keys_path = Path(__file__).parent / "mindcraft" / "keys.json"
        if keys_path.exists():
            try:
                with open(keys_path, 'r') as f:
                    keys = json.load(f)
                    api_key = keys.get("OPENAI_API_KEY", "")
            except Exception as e:
                print(f"keys.json 읽기 오류: {e}")

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY를 찾을 수 없습니다. "
            "환경 변수 OPENAI_API_KEY를 설정하거나 "
            "mindcraft/keys.json 파일에 OPENAI_API_KEY를 추가하세요."
        )

    return api_key


# OpenAI 클라이언트 초기화
try:
    api_key = get_api_key()
    client = openai.OpenAI(api_key=api_key)
except ValueError as e:
    print(f"에러: {e}")
    raise


# YAML 파일에서 프롬프트 로드
def load_prompts(yaml_path="prompts.yaml"):
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# JSON 파일에서 recipe sequence 로드
def load_recipe_sequence(json_path="recipe_sequence.json"):
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# 프롬프트 로드
prompts_config = load_prompts()
settings = prompts_config.get('settings', {})
prompts = prompts_config.get('prompts', {})
atomic_actions = prompts_config.get('atomic_actions', '')

# 기본 모델 설정
default_model = settings.get('default_model', 'gpt-4o-mini')
default_temperature = settings.get('temperature', 0.7)
default_max_tokens = settings.get('max_tokens', 50000)

# temperature를 지원하지 않는 모델 목록
NO_TEMPERATURE_MODELS = ['gpt-5-nano', 'gpt-5-mini']



def generate_actions_for_item(item_entry, item_index_map=None, current_index=None, action_types_summary=""):
    """
    LLM을 사용하여 아이템 획득을 위한 atomic actions 생성

    Args:
        item_entry: recipe_sequence.json의 한 항목
        item_index_map: 아이템 이름 -> 인덱스 매핑 (선택적)
        current_index: 현재 아이템의 인덱스 (선택적, 이 인덱스보다 작은 아이템들은 이미 있다고 가정)
        action_types_summary: recipe_sequence.json에서 사용되는 action 종류 요약 (선택적)

    Returns:
        actions 리스트 (각 요소는 하나의 atomic action 문자열)
    """
    target = item_entry.get('target', '')
    recipe = item_entry.get('recipe')
    need_amount = item_entry.get('need_amount', 1)

    # 이전 아이템 목록 생성 (이미 있다고 가정)
    available_items = []
    available_items_text = ""
    if item_index_map is not None and current_index is not None:
        for item, idx in item_index_map.items():
            if idx < current_index:
                available_items.append(item)
        if available_items:
            available_items_text = f"\n\nIMPORTANT: The following items are already available in inventory (from previous steps): {', '.join(available_items)}\n"
            available_items_text += "Do NOT include actions to obtain these items. Only use them directly.\n"

    # 레시피 정보 구성 (모든 필드 포함)
    recipe_info = ""
    if recipe:
        action = recipe.get('action', '')
        require = recipe.get('require', {})
        result_amount = recipe.get('result_amount', 1)
        primary = recipe.get('primary', False)
        recipe_target = recipe.get('target', target)

        recipe_info = f"Recipe Target: {recipe_target}\n"
        recipe_info += f"Action: {action}\n"
        recipe_info += f"Required items: {json.dumps(require, ensure_ascii=False)}\n"
        recipe_info += f"Result amount: {result_amount}\n"
        recipe_info += f"Primary recipe: {primary}\n"
    else:
        recipe_info = "Recipe: null (direct collection, no recipe required)\n"
        action = "direct_collection"
        require = {}
        result_amount = 1
        primary = False

    # prompts.yaml의 system 프롬프트 가져오기
    base_system_prompt = prompts.get('planning', {}).get('system', '')

    # 프롬프트 구성 (base system prompt + 아이템별 정보)
    system_prompt = f"""{base_system_prompt}

---

### ACTION TYPES USED IN RECIPE SEQUENCE:
{action_types_summary}

---

### CURRENT TASK INFORMATION:
Target: {target}
Need amount: {need_amount}
{recipe_info}
{available_items_text}


Action type: {action}

### IMPORTANT CONTEXT:
- The following items are already available in inventory (from previous steps in recipe_sequence.json): {', '.join(available_items) if available_items else 'None'}
- Do NOT include steps to obtain items that are already available. Only use them directly.
- Assume that required items (from recipe.require) are already in the inventory. So you don't have to ensure and create them.
- Output actions in NATURAL LANGUAGE (not as commands like !actionName), but each action should correspond to one of the atomic actions listed above.
- IMPORTANT: If the target item is from mob, you have to find the unique habitat block (e.g., Nether Bricks for Nether Fortress mobs) and kill the mob to get the item.
- You can produce MORE than the need_amount. Do NOT repeat crafting actions multiple times. One crafting action can produce multiple items (e.g., crafting oak_planks once produces 4 planks from 1 log). Only craft once if it produces enough items.
- If you have to craft a item, just "Craft {need_amount} {target}." without any other text.
- If Action type is "mine:xxx", you don't have to use searchForBlock action.

### OUTPUT FORMAT:
Output the atomic action steps as multiple sentences in natural language, one per line. Each line should be a complete sentence ending with a period.

Example:
Target: {target}
Need amount: {need_amount}

Collect {need_amount} {target}.
------------
Example:
Target: oak_planks
Need amount: 20

Craft 20 oak_planks.
------------------
Example:
Target: stick
Need amount: 7

Craft 7 sticks.
------------------
Example:
Target: diamond_pickaxe
Need amount: 1

Craft 1 diamond_pickaxe.
------------------
Example:
Target: obsidian
Need amount: 10

Use water bucket on lava to create obsidian.
Collect 10 obsidian.
------------------
"""

    messages = [
        {"role": "system", "content": system_prompt},
    ]

    create_params = {
        "model": default_model,
        "messages": messages,
        "max_completion_tokens": 4000,
    }

    if default_model not in NO_TEMPERATURE_MODELS:
        create_params["temperature"] = default_temperature

    response = client.chat.completions.create(**create_params)

    actions_text = response.choices[0].message.content.strip()

    # 자연어 문장을 리스트로 분리
    actions = []
    lines = actions_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # "- " 또는 숫자로 시작하는 리스트 항목 제거
        if line.startswith('- '):
            line = line[2:].strip()
        elif line and line[0].isdigit() and ('. ' in line or ') ' in line):
            # "1. " 또는 "1) " 형식 제거
            import re
            line = re.sub(r'^\d+[\.\)]\s*', '', line).strip()

        # 마침표로 문장 분리
        if '.' in line:
            parts = line.split('.')
            for part in parts:
                part = part.strip()
                if part:
                    # 마지막에 마침표 추가
                    if not part.endswith('.'):
                        part += '.'
                    actions.append(part)
        else:
            # 마침표가 없으면 그대로 추가 (마침표 추가)
            if not line.endswith('.'):
                line += '.'
            actions.append(line)

    # 빈 문장 제거 및 정리
    actions = [a.strip() for a in actions if a.strip()]

    return actions


def get_action_types_from_recipe_sequence(recipe_sequence):
    """
    recipe_sequence.json에서 사용되는 action 종류 추출

    Args:
        recipe_sequence: recipe sequence 리스트

    Returns:
        dict: action 종류별 설명
    """
    action_types = set()
    for entry in recipe_sequence:
        recipe = entry.get('recipe')
        if recipe:
            action = recipe.get('action', '')
            if action:
                action_types.add(action)
        else:
            # recipe가 null인 경우는 직접 수집
            action_types.add('direct_collection')

    # action 종류별 설명
    action_descriptions = {
        'craft': 'Craft items using a crafting table with required materials',
        'mine:stone': 'Mine stone blocks to get cobblestone',
        'mine:coal_ore': 'Mine coal ore blocks to get coal',
        'mine:iron_ore': 'Mine iron ore blocks to get raw_iron',
        'mine:diamond_ore': 'Mine diamond ore blocks to get diamond',
        'mine:obsidian': 'Mine obsidian blocks (requires diamond pickaxe)',
        'smelt': 'Smelt items in a furnace using fuel (coal)',
        'pour:water': 'Use bucket to collect water from water source',
        'build:nether_portal': 'Build a nether portal frame with obsidian and light it with flint_and_steel',
        'kill:blaze': 'Kill blaze entities to get blaze_rod',
        'kill:enderman': 'Kill enderman entities to get ender_pearl',
        'direct_collection': 'Directly collect blocks or items from the world without crafting'
    }

    # 발견된 action 종류 설명
    found_actions = []
    for action in sorted(action_types):
        desc = action_descriptions.get(action, f'Action type: {action}')
        found_actions.append(f"- {action}: {desc}")

    return '\n'.join(found_actions) if found_actions else 'No actions found'


def plan_all_items(recipe_sequence_path="recipe_sequence.json"):
    """
    recipe_sequence.json의 모든 아이템에 대해 atomic actions 생성
    각 아이템을 계획할 때, 이전에 나온 아이템들은 이미 있다고 가정

    Args:
        recipe_sequence_path: recipe_sequence.json 파일 경로

    Returns:
        list: [{"item": "...", "actions": [...]}, ...]
    """
    # check output file existence
    output_path = Path(OUTPUT_FILE_NAME)
    if output_path.exists():
        print("Plan file already exists. Skipping planning process.")
        with open(output_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    # recipe_sequence 로드
    recipe_sequence = load_recipe_sequence(recipe_sequence_path)

    # recipe_sequence에서 사용되는 action 종류 추출
    action_types_summary = get_action_types_from_recipe_sequence(recipe_sequence)

    # 아이템 이름 -> 인덱스 매핑 생성 (순서 추적)
    item_index_map = {}
    for index, entry in enumerate(recipe_sequence):
        item_index_map[entry['target']] = index

    print(f"\n=== {len(recipe_sequence)}개 아이템에 대한 계획 생성 시작 ===\n")
    print("※ 각 아이템 계획 시, 이전 순서의 아이템들은 이미 있다고 가정합니다.\n")

    # recipe_sequence.json의 원본 데이터를 복사하고 actions 추가
    all_plans = []

    for i, item_entry in enumerate(recipe_sequence):
        target = item_entry['target']
        print(f"[{i + 1}/{len(recipe_sequence)}] Planning for: {target} (index: {i})")

        # Actions 생성
        print(f"  → Generating actions...")
        actions = generate_actions_for_item(item_entry, item_index_map, i)

        # 원본 item_entry를 복사하고 item과 actions 필드 추가
        plan_data = item_entry.copy()
        plan_data["item"] = target
        plan_data["actions"] = actions

        all_plans.append(plan_data)

        print(f"  ✓ Actions 생성 완료: {len(actions)} actions\n")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_plans, f, indent=2, ensure_ascii=False)

    print(f"\n전체 계획이 저장되었습니다: {output_path}")

    return all_plans


# 예시 사용
if __name__ == "__main__":
    # recipe_sequence.json의 모든 아이템에 대해 계획 생성
    all_plans = plan_all_items()

    print("\n=== 계획 생성 완료 ===")
    print(f"총 {len(all_plans)}개 아이템의 계획이 생성되었습니다.\n")
