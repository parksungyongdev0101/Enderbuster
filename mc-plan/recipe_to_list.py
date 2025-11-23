import json
from collections import deque


def load_recipes(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_recipe_dict(recipes):
    """Convert list of recipes into dict[target] = recipe."""
    return {r["target"]: r for r in recipes}


def bfs_to_sequence(json_path: str, root_target: str):
    """
    Traverse recipe DAG with BFS, collect sequence (with duplicates),
    then reverse and deduplicate so each target appears once,
    keeping the last (deepest) occurrence.
    """
    # Load recipe data
    recipes = load_recipes(json_path)
    recipe_dict = build_recipe_dict(recipes)

    # --- Step 1. BFS traversal (duplicates allowed)
    sequence = []
    queue = deque([root_target])

    while queue:
        target = queue.popleft()
        recipe = recipe_dict.get(target)
        if not recipe:
            sequence.append({
                "target": target,
                "recipe": None,
                "need_amount": 0
            })
            continue

        sequence.append({
            "target": target,
            "recipe": recipe,
            "need_amount": 0
        })

        for req in recipe.get("require", {}).keys():
            queue.append(req)

    # --- Step 2. Reverse list (deepest first)
    sequence.reverse()

    # --- Step 3. Deduplicate (keep last occurrence only)
    seen = set()
    de_duped = []
    for item in sequence:
        target = item["target"]
        if target not in seen:
            seen.add(target)
            de_duped.append(item)

    return de_duped


if __name__ == "__main__":
    path = "recipe_extended.json"
    root = "ender_eye"
    seq = bfs_to_sequence(path, root)
    for item in seq:
        print(f"- {item['target']}")

    with open("recipe_bfs_sequence.json", "w", encoding="utf-8") as f:
        json.dump(seq, f, indent=2, ensure_ascii=False)

    print(f"BFS sequence generated for '{root}' ({len(seq)} unique recipes)")
