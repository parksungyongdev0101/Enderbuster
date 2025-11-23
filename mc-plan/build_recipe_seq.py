import json
from recipe_to_list import bfs_to_sequence
from prop_need_amount import compute_need_amounts


def build_sequence_with_need(root_target: str, root_amount: int, json_path: str = "recipe_extended.json", save_path: str = "recipe_sequence.json"):
    """
    Combine BFS sequence and DFS-based need_amount propagation.
    Produces a list of recipes with each item's total need_amount filled in.
    """
    # Compute need_amounts from DFS propagation
    need_amounts, _ = compute_need_amounts(json_path, root_target, root_amount)

    # Build BFS sequence (deduped order)
    sequence = bfs_to_sequence(json_path, root_target)

    # Fill need_amounts into the sequence
    for entry in sequence:
        target = entry["target"]
        entry["need_amount"] = need_amounts.get(target, 0)

    # Save as JSON
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(sequence, f, indent=2, ensure_ascii=False)

    print(f"Sequence with need_amount saved to: {save_path}")
    print(f" - Total items: {len(sequence)}")

    return sequence


# Example usage
if __name__ == "__main__":
    path = "recipe_extended.json"
    root = "ender_eye"
    seq = build_sequence_with_need(root, 1, path)
    print("\n=== Preview ===")
    for s in seq[:10]:
        print(f"{s['target']:20s} | need_amount = {s['need_amount']}")
