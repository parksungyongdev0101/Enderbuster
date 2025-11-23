import json
from anytree import Node, RenderTree
import matplotlib.pyplot as plt
import networkx as nx


def load_recipes(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_recipe_dict(recipes):
    """Convert list of recipes into dict[target] = recipe."""
    return {r["target"]: r for r in recipes}


def build_tree(target: str, recipe_dict, parent=None):
    """Recursively build tree structure (allowing duplicates)."""
    recipe = recipe_dict.get(target)
    action = recipe.get("action", "unknown") if recipe else "unknown"
    node_label = f"{target}\n({action})"
    node = Node(node_label, parent=parent)

    if not recipe:
        return node

    for req in recipe.get("require", {}).keys():
        build_tree(req, recipe_dict, node)

    return node


def add_edges_from_anytree(node, G):
    """Recursively add edges from anytree Node to NetworkX graph."""
    for child in node.children:
        G.add_edge(node.name, child.name)
        add_edges_from_anytree(child, G)


def plot_tree(root_node, figsize=(16, 12), save_path=None):
    """Draw hierarchical tree using NetworkX with improved spacing."""
    G = nx.DiGraph()
    add_edges_from_anytree(root_node, G)

    # use hierarchy layout (top-down)
    pos = hierarchy_pos(G, root_node.name, width=3.0, vert_gap=0.5)

    plt.figure(figsize=figsize)
    nx.draw(
        G,
        pos,
        with_labels=True,
        node_size=2400,
        node_color="lightgreen",
        font_size=8,
        font_weight="bold",
        arrows=False,
        edge_color="gray",
        alpha=0.8,
    )
    plt.title("Recipe Tree (spaced layout, duplicated nodes allowed)", fontsize=14)
    plt.axis("off")

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Tree saved to {save_path}")
    else:
        plt.show()


def hierarchy_pos(
    G,
    root,
    width=1.0,
    vert_gap=0.2,
    vert_loc=0,
    xcenter=0.5,
    pos=None,
    parent=None,
):
    """Recursively compute positions for a hierarchical tree layout with adjustable spacing."""
    if pos is None:
        pos = {root: (xcenter, vert_loc)}
    else:
        pos[root] = (xcenter, vert_loc)

    children = list(G.successors(root))
    if not children:
        return pos

    # spacing between children (dx): wider for large width
    dx = width / max(len(children), 1)
    # optional: add small offset so leaves don't overlap vertically
    nextx = xcenter - width / 2 - dx / 2
    for child in children:
        nextx += dx
        pos = hierarchy_pos(
            G,
            child,
            width=dx * 1.7,  # slightly expand horizontal spacing downwards
            vert_gap=vert_gap * 1.1,  # increase vertical distance
            vert_loc=vert_loc - vert_gap,
            xcenter=nextx,
            pos=pos,
            parent=root,
        )
    return pos


def visualize_recipe_tree(json_path: str, root_target: str, save_path=None):
    recipes = load_recipes(json_path)
    recipe_dict = build_recipe_dict(recipes)
    root = build_tree(root_target, recipe_dict)

    # ASCII preview
    for pre, fill, node in RenderTree(root):
        print(f"{pre}{node.name}")

    plot_tree(root, save_path=save_path)


if __name__ == "__main__":
    visualize_recipe_tree("recipe_extended.json", "ender_eye")
