from collections import defaultdict
from recipe_to_tree import build_recipe_tree, RecipeNode
from math import ceil

reusable_item_dict = {
    "diamond_sword": False,
    "diamond_helmet": False,
    "diamond_chestplate": False,
    "diamond_leggings": False,
    "diamond_boots": False,
    "iron_pickaxe": False,
    "diamond_pickaxe": False,
    "wooden_shovel": False,
    "stone_pickaxe": False,
    "wooden_pickaxe": False,
    "crafting_table": False,
    "furnace": False,
    "bucket": False,
    "water_bucket": False,
    "flint_and_steel": False
}

def propagate_need_amount_dfs(root: RecipeNode):
    """
    DFS traversal to propagate need_amount values down the recipe tree.
    Each node starts with its own need_amount (root should be set to 1).
    """
    if not root.recipe:
        return
    if reusable_item_dict.get(root.target, False):
        return

    if root.target in reusable_item_dict:
        reusable_item_dict[root.target] = True
        root.need_amount = 1

    for child in root.children:
        require_amount = root.recipe.get("require", {}).get(child.target, 0)
        if child.target not in reusable_item_dict:
            child.need_amount += ceil(root.need_amount * require_amount / root.recipe.get("result_amount", 1))
        propagate_need_amount_dfs(child)


def compute_need_amounts(json_path: str, root_target: str, root_amount: int = 1):
    """
    Build recipe tree and propagate need amounts from root downward.
    Returns dictionary {target: total_need}.
    """
    root, nodes = build_recipe_tree(json_path, root_target)

    # Initialize root need_amount
    root.need_amount = root_amount

    # DFS propagation
    propagate_need_amount_dfs(root)

    # Aggregate totals per target (since duplicates are allowed)
    totals = defaultdict(int)
    for node in nodes:
        totals[node.target] += node.need_amount

    return totals, nodes


if __name__ == "__main__":
    path = "recipe_extended.json"
    root_target = "ender_eye"

    totals, nodes = compute_need_amounts(path, root_target)

    print("=== Need Amount Results ===")
    for k, v in sorted(totals.items()):
        print(f"{k}: {v}")

    print("\n=== Example Tree Preview ===")
    for node in nodes[:10]:
        print(f"{node.id:2d} | {node.target:20s} | need={node.need_amount:.2f}")
