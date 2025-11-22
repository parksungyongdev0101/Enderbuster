import openai
import os
import yaml
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from collections import defaultdict

# .env 파일에서 환경 변수 로드
load_dotenv()

# API 키 로드 (환경 변수 또는 keys.json 파일에서)
def get_api_key():
    """API 키를 환경 변수 또는 keys.json에서 가져옴"""
    # 먼저 환경 변수에서 확인 (.env 파일에서 로드됨)
    api_key = os.getenv("OPENAI_API_KEY")
    
    # 환경 변수에 없으면 keys.json에서 확인
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

# OpenAI 클라이언트 초기화 (최신 SDK 방식)
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

# 기본 모델 설정
default_model = settings.get('default_model', 'gpt-5-nano')
default_temperature = settings.get('temperature', 0.7)
default_max_tokens = settings.get('max_tokens', 50000)

# temperature를 지원하지 않는 모델 목록
NO_TEMPERATURE_MODELS = ['gpt-5-nano', 'gpt-5-mini']

# 프롬프트 저장 디렉토리
prompts_dir = Path(__file__).parent / "prompts_logs"
prompts_dir.mkdir(exist_ok=True)

# 계획 저장 디렉토리
plans_dir = Path(__file__).parent / "plans"
plans_dir.mkdir(exist_ok=True)

# 아이템별 계획 저장 디렉토리
item_plans_dir = Path(__file__).parent / "item_plans"
item_plans_dir.mkdir(exist_ok=True)

def save_prompt_to_file(messages, goal, prompt_type):
    """
    프롬프트를 .txt 파일로 저장
    
    Args:
        messages: LLM에 전송할 메시지 리스트
        goal: 목표 (파일명에 사용)
        prompt_type: 프롬프트 타입
    """
    # 타임스탬프 생성
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # 파일명 생성 (목표를 간단하게 정리)
    goal_safe = "".join(c for c in goal[:50] if c.isalnum() or c in (' ', '-', '_')).strip()
    goal_safe = goal_safe.replace(' ', '_')
    filename = f"{timestamp}_{prompt_type}_{goal_safe}.txt"
    filepath = prompts_dir / filename
    
    # 프롬프트 내용 작성
    content = f"=== 프롬프트 로그 ===\n"
    content += f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    content += f"프롬프트 타입: {prompt_type}\n"
    content += f"목표: {goal}\n"
    content += f"모델: {default_model}\n"
    content += f"Temperature: {default_temperature}\n"
    content += f"Max Tokens: {default_max_tokens}\n"
    content += f"\n{'='*50}\n\n"
    
    # 메시지 내용 추가
    for i, msg in enumerate(messages, 1):
        role = msg['role'].upper()
        content += f"[{role} MESSAGE {i}]\n"
        content += f"{'-'*50}\n"
        content += f"{msg['content']}\n"
        content += f"{'-'*50}\n\n"
    
    # 파일 저장
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"프롬프트가 저장되었습니다: {filepath}")

def save_item_plan(item_name, action_sequence, recipe_info=None):
    """
    아이템별 Action sequence를 저장
    
    Args:
        item_name: 아이템 이름
        action_sequence: 생성된 액션 시퀀스 (문자열)
        recipe_info: 레시피 정보 (선택적)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    item_safe = "".join(c for c in item_name if c.isalnum() or c in (' ', '-', '_')).strip()
    item_safe = item_safe.replace(' ', '_')
    filename = f"{timestamp}_{item_safe}.txt"
    filepath = item_plans_dir / filename
    
    content = f"=== 아이템: {item_name} ===\n"
    if recipe_info:
        content += f"레시피 정보: {json.dumps(recipe_info, indent=2, ensure_ascii=False)}\n"
    content += f"\n=== Action Sequence ===\n\n"
    content += action_sequence
    content += f"\n\n{'='*50}\n"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"아이템 계획이 저장되었습니다: {filepath}")
    return filepath

def plan_item(item_entry, recipe_sequence, item_map, item_index_map, current_index, use_llm=True):
    """
    단일 아이템에 대한 Action sequence 생성 (국소적 planner)
    
    Args:
        item_entry: recipe_sequence.json의 한 항목
        recipe_sequence: 전체 recipe sequence
        item_map: 아이템 이름 -> 항목 매핑
        item_index_map: 아이템 이름 -> 인덱스 매핑
        current_index: 현재 아이템의 인덱스 (이 인덱스보다 작은 아이템들은 이미 있다고 가정)
        use_llm: LLM 사용 여부
    
    Returns:
        Action sequence 문자열
    """
    target = item_entry['target']
    recipe = item_entry.get('recipe')
    need_amount = item_entry.get('need_amount', 1)
    
    # 이미 처리된 아이템은 스킵 (순환 참조 방지)
    if target in item_map and item_map[target].get('_processed'):
        return item_map[target].get('_action_sequence', '')
    
    # 처리 중 표시
    if target in item_map:
        item_map[target]['_processed'] = True
    
    action_sequence = []
    
    # recipe가 null인 경우: 직접 수집
    if recipe is None:
        # 블록 타입 추정 (일반적인 경우)
        block_type = target
        if target == 'flint':
            # flint는 gravel을 캐서 얻음
            action_sequence.append(f"!searchForBlock type:gravel search_range:128")
            action_sequence.append(f"!collectBlocks type:gravel num:{need_amount * 10}")  # flint는 드롭률이 낮음
        else:
            # 일반 블록 수집
            action_sequence.append(f"!searchForBlock type:{block_type} search_range:128")
            action_sequence.append(f"!collectBlocks type:{block_type} num:{need_amount}")
    else:
        # recipe가 있는 경우
        action = recipe.get('action', '')
        require = recipe.get('require', {})
        result_amount = recipe.get('result_amount', 1)
        
        # 1. 필요한 아이템들을 먼저 준비 (재귀적으로)
        # 단, 현재 인덱스보다 이전에 나온 아이템들은 이미 있다고 가정하고 스킵
        for req_item, req_amount in require.items():
            req_index = item_index_map.get(req_item, float('inf'))
            
            # 현재 인덱스보다 이전 아이템은 이미 있다고 가정
            if req_index < current_index:
                # 이미 있는 아이템이므로 스킵 (주석만 추가)
                action_sequence.append(f"# {req_item} is already available (from previous steps)")
                continue
            
            # 현재 인덱스 이후의 아이템만 계획에 포함
            if req_item in item_map:
                req_entry = item_map[req_item]
                # 필요한 수량 계산 (result_amount 고려)
                actual_need = max(1, int((need_amount * req_amount) / result_amount))
                req_entry['need_amount'] = max(req_entry.get('need_amount', 0), actual_need)
                req_sequence = plan_item(req_entry, recipe_sequence, item_map, item_index_map, current_index, use_llm)
                if req_sequence:
                    action_sequence.append(f"# Preparing {req_item} (need {actual_need})")
                    action_sequence.append(req_sequence)
        
        # 2. 현재 아이템을 얻기 위한 액션 생성
        if action == 'craft':
            # craft 횟수 계산
            craft_times = max(1, int((need_amount + result_amount - 1) / result_amount))
            action_sequence.append(f"!craftRecipe recipe_name:{target} num:{craft_times}")
        
        elif action.startswith('mine:'):
            # mine:block_type 형식
            block_type = action.split(':', 1)[1]
            action_sequence.append(f"!searchForBlock type:{block_type} search_range:128")
            action_sequence.append(f"!collectBlocks type:{block_type} num:{need_amount}")
        
        elif action == 'smelt':
            # smelt는 require의 첫 번째 아이템을 smelt
            input_item = list(require.keys())[0] if require else target.replace('_ingot', '')
            if input_item.endswith('_ore') or 'raw_' in input_item:
                smelt_times = max(1, int((need_amount + result_amount - 1) / result_amount))
                action_sequence.append(f"!smeltItem item_name:{input_item} num:{smelt_times}")
            else:
                # 일반적인 경우
                smelt_times = max(1, int((need_amount + result_amount - 1) / result_amount))
                action_sequence.append(f"!smeltItem item_name:{input_item} num:{smelt_times}")
        
        elif action.startswith('kill:'):
            # kill:entity_type 형식
            entity_type = action.split(':', 1)[1]
            action_sequence.append(f"!searchForEntity type:{entity_type} search_range:128")
            action_sequence.append(f"!attack type:{entity_type}")
        
        elif action == 'pour:water':
            # 물 양동이 만들기
            action_sequence.append(f"!searchForBlock type:water search_range:128")
            action_sequence.append(f"!useOn tool_name:bucket target:water")
        
        elif action == 'build:nether_portal':
            # 네더 포털 건설 (LLM 사용 또는 직접 처리)
            if use_llm:
                # LLM에게 맡기기
                llm_sequence = plan_item_with_llm(target, recipe, need_amount, item_index_map, current_index)
                if llm_sequence:
                    action_sequence.append(llm_sequence)
            else:
                # 직접 처리: obsidian 10개로 포털 건설
                action_sequence.append(f"# Build Nether Portal with obsidian and flint_and_steel")
                action_sequence.append(f"!newAction prompt:Build a nether portal frame with 10 obsidian blocks in a 4x5 rectangle, then use flint_and_steel to light it")
        
        else:
            # 알 수 없는 액션 타입
            action_sequence.append(f"# Unknown action type: {action}")
            if use_llm:
                llm_sequence = plan_item_with_llm(target, recipe, need_amount, item_index_map, current_index)
                if llm_sequence:
                    action_sequence.append(llm_sequence)
    
    result = '\n'.join(action_sequence)
    
    # 결과 저장
    if target in item_map:
        item_map[target]['_action_sequence'] = result
    
    return result

def plan_item_with_llm(item_name, recipe, need_amount, item_index_map=None, current_index=None):
    """
    LLM을 사용하여 아이템 획득 계획 생성
    
    Args:
        item_name: 아이템 이름
        recipe: 레시피 정보
        need_amount: 필요한 수량
        item_index_map: 아이템 이름 -> 인덱스 매핑 (선택적)
        current_index: 현재 아이템의 인덱스 (선택적)
    
    Returns:
        Action sequence 문자열
    """
    prompt_template = prompts.get('planning', {})
    system_prompt = prompt_template.get('system', '')
    
    if not system_prompt:
        return None
    
    # 레시피 정보를 텍스트로 변환
    recipe_text = f"Target: {item_name}\n"
    recipe_text += f"Need amount: {need_amount}\n"
    if recipe:
        recipe_text += f"Action: {recipe.get('action', '')}\n"
        recipe_text += f"Require: {json.dumps(recipe.get('require', {}), ensure_ascii=False)}\n"
        recipe_text += f"Result amount: {recipe.get('result_amount', 1)}\n"
    
    # 이전 아이템 정보 추가 (이미 있다고 가정)
    context_text = ""
    if item_index_map is not None and current_index is not None:
        available_items = []
        for item, idx in item_index_map.items():
            if idx < current_index:
                available_items.append(item)
        if available_items:
            context_text = f"\nIMPORTANT: The following items are already available in inventory (from previous steps): {', '.join(available_items)}\n"
            context_text += "Do NOT include actions to obtain these items. Only use them directly.\n"
    
    user_prompt = f"Generate the minimal atomic Action sequence to obtain {need_amount} {item_name}.{context_text}\n\nRecipe information:\n{recipe_text}\n\nOutput only the Action commands, one per line, no commentary."
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    try:
        # temperature를 지원하지 않는 모델은 temperature 파라미터 제외
        create_params = {
            "model": default_model,
            "messages": messages,
            "max_completion_tokens": 2000,  # 아이템별로는 작은 토큰 수면 충분
        }
        
        # temperature를 지원하는 모델만 temperature 파라미터 추가
        if default_model not in NO_TEMPERATURE_MODELS:
            create_params["temperature"] = default_temperature
        
        response = client.chat.completions.create(**create_params)
        
        result = response.choices[0].message.content.strip()
        save_prompt_to_file(messages, f"item_{item_name}", "item_planning")
        return result
    except Exception as e:
        print(f"LLM 호출 오류 ({item_name}): {e}")
        return None

def plan_all_items(recipe_sequence_path="recipe_sequence.json", use_llm_for_complex=True):
    """
    recipe_sequence.json의 모든 아이템에 대해 Action sequence 생성
    각 아이템을 계획할 때, 이전에 나온 아이템들은 이미 있다고 가정
    
    Args:
        recipe_sequence_path: recipe_sequence.json 파일 경로
        use_llm_for_complex: 복잡한 액션에 LLM 사용 여부
    
    Returns:
        dict: {item_name: action_sequence}
    """
    # recipe_sequence 로드
    recipe_sequence = load_recipe_sequence(recipe_sequence_path)
    
    # 아이템 이름 -> 항목 매핑 생성
    item_map = {}
    for entry in recipe_sequence:
        item_map[entry['target']] = entry
    
    # 아이템 이름 -> 인덱스 매핑 생성 (순서 추적)
    item_index_map = {}
    for index, entry in enumerate(recipe_sequence):
        item_index_map[entry['target']] = index
    
    # 각 아이템에 대해 계획 생성
    all_plans = {}
    
    print(f"\n=== {len(recipe_sequence)}개 아이템에 대한 계획 생성 시작 ===\n")
    print("※ 각 아이템 계획 시, 이전 순서의 아이템들은 이미 있다고 가정합니다.\n")
    
    for i, item_entry in enumerate(recipe_sequence):
        target = item_entry['target']
        print(f"[{i+1}/{len(recipe_sequence)}] Planning for: {target} (index: {i})")
        
        # item_map 초기화 (재사용을 위해)
        for entry in recipe_sequence:
            entry.pop('_processed', None)
            entry.pop('_action_sequence', None)
        
        # 현재 인덱스를 전달하여 이전 아이템들은 이미 있다고 가정
        action_sequence = plan_item(item_entry, recipe_sequence, item_map, item_index_map, i, use_llm_for_complex)
        all_plans[target] = action_sequence
        
        # 아이템별 계획 저장
        save_item_plan(target, action_sequence, item_entry.get('recipe'))
        
        print(f"  ✓ 완료: {len(action_sequence.split(chr(10)))} lines\n")
    
    # 전체 계획을 하나의 파일로 저장
    save_all_plans(all_plans, recipe_sequence)
    
    return all_plans

def save_all_plans(all_plans, recipe_sequence):
    """
    모든 아이템의 계획을 하나의 파일로 저장
    
    Args:
        all_plans: {item_name: action_sequence} 딕셔너리
        recipe_sequence: 원본 recipe sequence
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{timestamp}_all_item_plans.txt"
    filepath = plans_dir / filename
    
    content = f"=== 모든 아이템 Action Sequence ===\n"
    content += f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    content += f"총 {len(all_plans)}개 아이템\n"
    content += f"\n{'='*80}\n\n"
    
    for item_entry in recipe_sequence:
        target = item_entry['target']
        need_amount = item_entry.get('need_amount', 1)
        recipe = item_entry.get('recipe')
        
        content += f"\n{'='*80}\n"
        content += f"아이템: {target} (필요 수량: {need_amount})\n"
        if recipe:
            content += f"레시피: {recipe.get('action', 'N/A')}\n"
        content += f"{'-'*80}\n"
        content += f"{all_plans.get(target, 'N/A')}\n"
        content += f"\n"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n전체 계획이 저장되었습니다: {filepath}")

# 예시 사용
if __name__ == "__main__":
    # recipe_sequence.json의 모든 아이템에 대해 계획 생성
    all_plans = plan_all_items(use_llm_for_complex=True)
    
    print("\n=== 계획 생성 완료 ===")
    print(f"총 {len(all_plans)}개 아이템의 계획이 생성되었습니다.\n")
