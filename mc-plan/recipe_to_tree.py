import json
from collections import deque


# --- Global ID counter ---
class IDGenerator:
    _counter = 0

    @classmethod
    def next(cls):
        cls._counter += 1
        return cls._counter


class RecipeNode:
    """Tree node for recipe DAG expansion."""

    def __init__(self, target, recipe=None, parent=None):
        self.id = IDGenerator.next()
        self.target = target
        self.recipe = recipe
        self.parent = parent  # reference to parent node (or None)
        self.children = []    # list of RecipeNode objects
        self.need_amount = 0
        self.visited = False

    def add_child(self, child_node):
        """Link a child node."""
        self.children.append(child_node)

    def __repr__(self):
        parent_id = self.parent.id if self.parent else None
        return f"<Node id={self.id}, target='{self.target}', parent={parent_id}, children={len(self.children)}>"

    def to_dict(self):
        """Convert node to serializable dict (for JSON export)."""
        return {
            "id": self.id,
            "target": self.target,
            "recipe": self.recipe,
            "parent": self.parent.id if self.parent else None,
            "children": [c.id for c in self.children],
            "need_amount": self.need_amount,
            "visited": self.visited
        }


# --- Build function ---
def load_recipes(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_recipe_dict(recipes):
    return {r["target"]: r for r in recipes}


def build_recipe_tree(json_path: str, root_target: str):
    """
    Build full recipe tree from recipe_extended.json.
    Returns root node (RecipeNode) and list of all nodes.
    """
    # Reset counter each time we build
    IDGenerator._counter = 0

    recipes = load_recipes(json_path)
    recipe_dict = build_recipe_dict(recipes)

    # BFS
    root_recipe = recipe_dict.get(root_target)
    root = RecipeNode(root_target, root_recipe)
    all_nodes = [root]
    queue = deque([root])

    while queue:
        current = queue.popleft()
        recipe = current.recipe
        if not recipe:
            continue

        for req_target in recipe.get("require", {}).keys():
            req_recipe = recipe_dict.get(req_target)
            child = RecipeNode(req_target, req_recipe, parent=current)
            current.add_child(child)
            all_nodes.append(child)
            queue.append(child)

    return root, all_nodes


# --- Example run ---
if __name__ == "__main__":
    path = "recipe_extended.json"
    root_target = "ender_eye"

    root, nodes = build_recipe_tree(path, root_target)
    print(f"Built tree with {len(nodes)} nodes. Root: {root.target}")

    # Example preview
    for node in nodes:
        print(node)