from prompts.generate_llm_recipe_prompt import GENERATE_LLM_RECIPE_PROMPT
from utils.model import LLMFactory
from utils.json_parser import safe_json_parse

def generate_llm_recipe(target: str):
    client = LLMFactory.create("openai", model_name="gpt-5-nano", temperature=1.0)
    prompt = GENERATE_LLM_RECIPE_PROMPT.replace("$TARGET$", target)
    response = client.generate(prompt)
    if "noop" in response.text.lower():
        return None
    recipe = safe_json_parse(response.text)
    if "kill" in recipe.get("action", "").lower():
        recipe["result_amount"] = 1

    return recipe

if __name__ == '__main__':
    target = "water_bucket"
    print(generate_llm_recipe(target))