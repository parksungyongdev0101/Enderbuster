import json
from collections import defaultdict
from craft_or_smelt.search_tag import search_tag  # 태그 검색기 사용
from itertools import product
from pathlib import Path


_DEFAULT_RECIPE_DIR = Path(__file__).resolve().parent / "recipe"
_RESULT_FILE = Path(__file__).resolve().parent / "craft_or_smelt_recipes.json"

def parse_craft_shapeless_recipe(recipe_json: dict):
    """
    Parse a 'minecraft:crafting_shapeless' recipe into extended recipe format.
    Supports tag expansion (#minecraft:...), list-based choices, and generates multiple variants.
    """

    # --- Step 1. target/result ---
    result_data = recipe_json.get("result", {})
    target = result_data.get("id", "").replace("minecraft:", "")
    result_amount = result_data.get("count", 1)

    # --- Step 2. ingredients list ---
    ingredients = recipe_json.get("ingredients", [])
    choices = []  # 각 요소는 [variant1, variant2, ...]

    for ing in ingredients:
        variants = []

        # Case 1: 단일 문자열 ("minecraft:stick")
        if isinstance(ing, str):
            variants = [ing]

        # Case 2: 여러 선택지 (["minecraft:coal", "minecraft:charcoal"])
        elif isinstance(ing, list):
            variants = ing

        else:
            raise ValueError(f"Unknown ingredient format: {ing}")

        # --- tag 확장 ---
        expanded = []
        for v in variants:
            if v.startswith("#minecraft:") or v.startswith("#"):
                tag_name = v.split(":", 1)[1] if ":" in v else v[1:]
                items = search_tag(tag_name)
                expanded.extend(items if items else [tag_name])
            else:
                expanded.append(v)
        choices.append(expanded)

    # --- Step 3. variant 조합 생성 ---
    variants = list(product(*choices))  # 모든 조합 전개
    recipes = []

    primary = True
    for combo in variants:
        req_counter = defaultdict(int)
        for item in combo:
            item = item.replace("minecraft:", "")
            req_counter[item] += 1

        # --- Step 4. crafting table 여부 ---
        if len(ingredients) > 4:
            req_counter["crafting_table"] += 1

        recipes.append({
            "target": target,
            "action": "craft",
            "require": dict(req_counter),
            "result_amount": result_amount,
            "primary": primary
        })
        primary = False  # 첫 번째만 primary 표시

    return recipes

def parse_craft_recipe(recipe_json: dict):
    """
    Convert Minecraft vanilla crafting_shaped recipe JSON into extended recipe format.
    Supports tag expansion (#minecraft:...) and list-based key variants.
    Returns a list of recipe variants.
    """

    # --- Step 1. result ---
    result_data = recipe_json.get("result", {})
    target = result_data.get("id", "").replace("minecraft:", "")
    result_amount = result_data.get("count", 1)

    # --- Step 2. pattern/key extraction ---
    pattern = recipe_json.get("pattern", [])
    key_map = recipe_json.get("key", {})
    counts = defaultdict(int)

    for row in pattern:
        for ch in row:
            if ch == " " or ch not in key_map:
                continue
            counts[ch] += 1  # 문자 빈도

    # --- Step 3. 각 key에 대한 가능한 재료 후보 확장 ---
    expanded_keys = {}  # ch → [possible_items]
    for ch, key_val in key_map.items():
        variants = []
        # value가 리스트일 수도, 문자열일 수도 있음
        key_values = key_val if isinstance(key_val, list) else [key_val]

        for raw in key_values:
            if raw.startswith("#minecraft:"):
                tag_name = raw.split(":", 1)[1]
                tag_items = search_tag(tag_name)
                variants.extend(tag_items if tag_items else [tag_name])
            elif raw.startswith("minecraft:"):
                variants.append(raw.replace("minecraft:", ""))
            else:
                variants.append(raw)

        # 중복 제거
        expanded_keys[ch] = list(dict.fromkeys(variants))

    # --- Step 4. pattern에 실제 등장하는 문자만 남기기 ---
    # (혹시 key_map에 정의만 있고 실제 사용 안된 경우 제거)
    expanded_keys = {ch: expanded_keys[ch] for ch in counts.keys() if ch in expanded_keys}

    # --- Step 5. crafting table 필요 여부 ---
    pattern_width = max((len(r) for r in pattern), default=0)
    pattern_height = len(pattern)
    needs_table = pattern_width > 2 or pattern_height > 2

    # --- Step 6. 모든 조합 전개 ---
    # 예: {'#': ['diamond'], 'C': ['copper_block','waxed_copper_block'], 'S': ['bolt_armor_trim_smithing_template']}
    key_names = list(expanded_keys.keys())
    variant_lists = list(expanded_keys.values())
    variant_combinations = list(product(*variant_lists))

    recipes = []
    primary = True
    for combo in variant_combinations:
        req_counter = defaultdict(int)
        for key_char, item in zip(key_names, combo):
            count = counts.get(key_char, 0)
            req_counter[item] += count

        if needs_table:
            req_counter["crafting_table"] += 1

        recipes.append({
            "target": target,
            "action": "craft",
            "require": dict(req_counter),
            "result_amount": result_amount,
            "primary": primary
        })
        primary = False

    return recipes

def parse_smelting_recipe(recipe_json: dict):
    """
    Parse vanilla smelting-type recipe JSON into extended recipe format.
    (Each ore variant has its own JSON file, so no tag expansion needed.)
    """
    # --- Step 1. target/result ---
    result_data = recipe_json.get("result", {})
    target = result_data.get("id", "").replace("minecraft:", "")
    result_amount = result_data.get("count", 1)

    # --- Step 2. ingredient ---
    ingredient = recipe_json.get("ingredient")

    ing_name = ingredient.replace("minecraft:", "")

    # --- Step 3. 기본 재료 구성 ---
    require = {
        ing_name: 1,
        "furnace": 1,
        "coal": 0.125,
    }

    # --- Step 4. 결과 구성 ---
    recipe = {
        "target": target,
        "action": "smelt",
        "require": require,
        "result_amount": result_amount
    }

    return [recipe]

def is_recipe_useful(recipe_json: dict) -> bool:
    """
    Determine if a recipe is useful based on its type and result.
    """
    recipe_type = recipe_json.get("type", "")
    id = recipe_json.get("result", {}).get("id", "")

    crafting_id_banlist = [
        "minecraft:copper_ingot",
        "minecraft:iron_ingot",
        "minecraft:gold_ingot",
        "minecraft:diamond",
        "minecraft:emerald",
        "minecraft:raw_copper",
        "minecraft:raw_iron",
        "minecraft:raw_gold",
        "minecraft:coal",
    ]
    smelting_id_banlist = [
        "minecraft:gold_nugget",
        "minecraft:iron_nugget",
        "minecraft:diamond",
        "minecraft:emerald",
        "minecraft:coal",
    ]

    if "crafting" in recipe_type:
        if id in crafting_id_banlist:
            return False
        return True

    if "smelt" in recipe_type:
        if id in smelting_id_banlist:
            return False
        if "ingot" in id and "raw" not in recipe_json["ingredient"]:
            return False
        return True

    return False

def create_recipes():
    recipe_dir = _DEFAULT_RECIPE_DIR
    all_recipes = []

    if _RESULT_FILE.exists():
        print("Recipe file already exists. Skipping creation.")
        return

    for recipe_file in recipe_dir.glob("*.json"):
        if "from_bamboo" in recipe_file.name:
            continue
        with open(recipe_file, 'r', encoding='utf-8') as f:
            recipe_json = json.load(f)

        recipe_type = recipe_json.get("type", "")

        if not is_recipe_useful(recipe_json):
            continue
        if "crafting" in recipe_type:
            if "shapeless" in recipe_type:
                parsed_recipes = parse_craft_shapeless_recipe(recipe_json)
            elif "shaped" in recipe_type:
                parsed_recipes = parse_craft_recipe(recipe_json)
            else:
                continue
        elif "smelt" in recipe_type:
            parsed_recipes = parse_smelting_recipe(recipe_json)
        else:
            continue

        all_recipes.extend(parsed_recipes)

    with open(_RESULT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_recipes, f, indent=4, ensure_ascii=False)

if __name__ == '__main__':
    create_recipes()