import json
from collections import deque


single_keywords = [
    "sword", "pickaxe", "axe", "shovel", "hoe",
    "helmet", "chestplate", "leggings", "boots",
    "crafting_table", "furnace",
    "bucket", "flint_and_steel"
]


def is_singleton_item(name: str) -> bool:
    return any(k in name for k in single_keywords)


def load_recipes(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_recipe_dict(recipes):
    return {r["target"]: r for r in recipes}


def extract_dag_subset(root: str, recipe_dict: dict):
    """Return all recipes reachable from the root target."""
    queue = deque([(root, 0)])  # (target, depth)
    visited = {}
    sub_recipes = {}

    while queue:
        target, depth = queue.popleft()
        if target not in recipe_dict:
            continue

        # depth 기록 (싱글턴 선택을 위해)
        if visited.get(target, -1) < depth:
            visited[target] = depth
        recipe = recipe_dict[target]
        sub_recipes[target] = recipe

        # enqueue children
        for req in recipe.get("require", {}).keys():
            queue.append((req, depth + 1))

    return sub_recipes, visited


def prune_singletons(sub_recipes, depths):
    """Keep only the deepest occurrence of singleton items."""
    singleton_depth = {}
    # 1️⃣ 각 singleton의 가장 깊은 depth 기록
    for name, depth in depths.items():
        if is_singleton_item(name):
            if name not in singleton_depth or depth > singleton_depth[name]:
                singleton_depth[name] = depth

    # 2️⃣ 각 recipe의 require에서 불필요한 singleton 제거
    for recipe in sub_recipes.values():
        req = recipe.get("require", {})
        to_remove = []
        for item in req.keys():
            if is_singleton_item(item):
                # 현재 recipe 깊이가 singleton의 가장 깊은 depth보다 얕으면 제거
                if depths.get(recipe["target"], -2) + 1 < singleton_depth.get(item, 0):
                    to_remove.append(item)
        for item in to_remove:
            del req[item]

    return sub_recipes


def extract_and_prune(path: str, root_target: str):
    recipes = load_recipes(path)
    recipe_dict = build_recipe_dict(recipes)
    sub_recipes, depths = extract_dag_subset(root_target, recipe_dict)
    pruned = prune_singletons(sub_recipes, depths)
    return list(pruned.values())


if __name__ == "__main__":
    path = "recipe_extended.json"
    root = "ender_eye"
    pruned_recipes = extract_and_prune(path, root)

    with open("recipe_pruned.json", "w", encoding="utf-8") as f:
        json.dump(pruned_recipes, f, indent=2, ensure_ascii=False)

    print(f"Extracted DAG for '{root}' with singleton pruning: {len(pruned_recipes)} recipes")
