from pathlib import Path
import json

_DEFAULT_RECIPE_PATH = str(Path(__file__).resolve().parent / "craft_or_smelt/craft_or_smelt_recipes.json")

def search_craft_or_smelt_recipes(target: str, recipe_path: str = _DEFAULT_RECIPE_PATH) -> list[dict]:
    """
    Search for crafting or smelting recipes that produce the specified item.

    Args:
        target (str): The name of the item/structure to search for.
        recipe_path (str): The path to the JSON file containing the recipes.

    Returns:
        list[dict]: A list of recipes that produce the specified item.
    """
    with open(recipe_path, "r", encoding="utf-8") as file:
        recipes = json.load(file)

    matching_recipes = [
        recipe for recipe in recipes
        if recipe.get("target", "") == target
    ]

    return matching_recipes

if __name__ == '__main__':
    # Example usage
    item_to_search = "crafting_table"
    found_recipes = search_craft_or_smelt_recipes(item_to_search)
    print(f"Recipes that produce '{item_to_search}':")
    for recipe in found_recipes:
        print(json.dumps(recipe, indent=2))