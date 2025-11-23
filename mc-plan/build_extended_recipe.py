import json
import os
from search_craft_or_smelt_recipes import search_craft_or_smelt_recipes
from generate_llm_recipe import generate_llm_recipe  # LLM 기반 생성 함수 (외부 구현)
from typing import Dict, List, Any
from craft_or_smelt.search_tag import search_tag

EXTENDED_RECIPE_PATH = "./recipe_extended.json"

noop_tags = [
    "#minecraft:logs",
    "#minecraft:bamboo_blocks"
]
noop_ids = [
    "minecraft:bamboo",
]

for tag in noop_tags:
    noop_ids.extend(["minecraft:" + id for id in search_tag(tag.split(":")[1])])

def load_extended_recipes() -> List[Dict[str, Any]]:
    """Load existing extended recipe JSON file."""
    if not os.path.exists(EXTENDED_RECIPE_PATH):
        return []
    with open(EXTENDED_RECIPE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_extended_recipes(recipes: List[Dict[str, Any]]):
    """Save updated extended recipe list."""
    os.makedirs(os.path.dirname(EXTENDED_RECIPE_PATH), exist_ok=True)
    with open(EXTENDED_RECIPE_PATH, "w", encoding="utf-8") as f:
        json.dump(recipes, f, indent=4, ensure_ascii=False)


def find_existing_recipe(target: str, recipes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return all recipes matching a given target (could be multiple variants)."""
    return [r for r in recipes if r["target"] == target]


def parse_require_field(require_field: Dict[str, Any]) -> List[str]:
    """
    Extract base targets from the 'require' field.
    e.g. {"obsidian:10": ..., "flint_and_steel": ...} -> ["obsidian", "flint_and_steel"]
    """
    reqs = []
    for key in require_field:
        if ":" in key:
            reqs.append(key.split(":")[0])
        else:
            reqs.append(key)
    return reqs

def build_extended_recipe(target: str, visited=None):
    """
    Recursively build extended recipes for a target.
    - Step 1: check if recipe already exists
    - Step 2: check if craft/smelt recipe exists
    - Step 3: otherwise generate via LLM
    - Step 4: recursively process all 'require' dependencies
    """
    if visited is None:
        visited = set()

    # --- prevent infinite recursion ---
    if target in visited:
        return []
    visited.add(target)

    # --- noop check ---
    if f"minecraft:{target}" in noop_ids:
        return []

    # --- load current recipes ---
    recipes = load_extended_recipes()
    existing = find_existing_recipe(target, recipes)
    if existing:
        return existing

    # --- try craft/smelt recipe ---
    found = search_craft_or_smelt_recipes(target)
    if found and len(found) > 0:
        new_recipes = []
        for r in found:
            if r.get("primary", True):
                recipes.append(r)
                new_recipes.append(r)
        save_extended_recipes(recipes)
    else:
        # --- fallback: generate via LLM ---
        print(f"Building recipe for: {target}")
        generated = generate_llm_recipe(target)
        if generated is None:
            return []
        if not isinstance(generated, list):
            generated = [generated]
        for r in generated:
            recipes.append(r)
        save_extended_recipes(recipes)
        new_recipes = generated

    # --- recursively build require recipes ---
    for recipe in new_recipes:
        require_items = parse_require_field(recipe.get("require", {}))
        for req in require_items:
            if req not in visited:
                build_extended_recipe(req, visited)

    return new_recipes


if __name__ == "__main__":
    # 테스트 예시
    # print(noop_ids)
    result = build_extended_recipe("ender_eye")
    print(json.dumps(result, indent=4, ensure_ascii=False))
