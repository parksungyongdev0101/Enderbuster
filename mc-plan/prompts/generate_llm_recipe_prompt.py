GENERATE_LLM_RECIPE_PROMPT = """
You are a Minecraft recipe generator.

Your task:
Generate a structured JSON recipe that describes **how a player can obtain** `$TARGET$`.
This target does **not** have an existing vanilla crafting or smelting recipe.
Assume survival mode with standard Minecraft mechanics.

---

### Rules
1. **Output format**
   - Always return **pure JSON** only, with **no explanations or markdown**.
   - If multiple methods exist, return only a SINGLE primary method.
   - The recipe must follow this schema:
     ```json
     {
       "target": "<target_name>",
       "action": "<action>",
       "require": { "<subitem>": <quantity>, ... },
       "result_amount": <integer>
     }
     ```

2. **Field details**
   - `target`: the exact item or structure name.
   - `action`: the primary way to obtain it.  
     Choose one of the following forms:
     - `"mine:<object>"` — mined from a block (e.g. `"mine:diamond_ore"`)
     - `"kill:<mob>"` — dropped from a mob (e.g. `"kill:blaze"`)
     - `"build:<structure>"` — manually constructed (e.g. `"build:nether_portal"`)
     - `"pour:<liquid>"` — poured into a bucket (e.g. `"pour:water"`)
   - `require`:  
     - A dictionary of items or structures **needed to achieve the action**.  
     - Every key must be an **item or structure name**. **Never use entities** like `"pig"`, `"zombie"`, `"villager"`, etc.
   - `result_amount`: integer, typically `1`.
   
2-1. **Additional rules for each action:**
     **(1) mine:**  
     - The `require` field must include:
       - The **minimum tool** necessary to break the block and obtain the drop.  
         (e.g., `"diamond_pickaxe"` for obsidian, `"iron_pickaxe"` for diamond_ore, `"stone_pickaxe"` for iron_ore, etc.)
       - If the block requires a **special enabling item or structure**, include it as well.  
         Examples:
         - obsidian → `"diamond_pickaxe": 1`, `"water_bucket": 1`
         - glowstone → `"iron_pickaxe": 1`, `"nether_portal": 1` (to enter Nether)
     - Never include the block itself in `require`.

     **(2) kill:**  
     - The `require` field can include up to two categories:
       1. **Equipment:** weapon and armor based on mob difficulty.
          - Passive mobs (pig, cow, sheep, ...): `"stone_sword": 1`
          - Common hostile mobs (zombie, skeleton, spider, ...): `"iron_sword": 1`, `"iron_helmet": 1`, `"iron_chestplate": 1`, `"iron_leggings": 1`, `"iron_boots": 1`
          - Dangerous or boss mobs (enderman, blaze, guardian, wither, ender_dragon, ...): `"diamond_sword": 1`, `"diamond_helmet": 1`, `"diamond_chestplate": 1`, `"diamond_leggings": 1`, `"diamond_boots": 1`
       2. **Portal:**  
          - If the mob ONLY spawns in the **Nether**, add `"nether_portal": 1`.  
          - If the mob ONLY spawns in the **End**, add `"ender_portal": 1`.  
          - If it CAN spawn in **Overworld**, the portal is not required.
     - The `result_amount` always set to `1`, regardless of actual drop rates.

     **(3) build:**  
     - The `require` field must list all materials needed to construct the structure, and any tools required for placement or activation.  
       Examples:
       - `"build:nether_portal"` → `{"obsidian": 10, "flint_and_steel": 1}`
       - `"build:ender_portal"` → `{"ender_eye": 12}`

3. **Special case – NOOP rule**
   - If the target can be obtained **naturally with bare hands** (no tools or equipments required)
   - If the target cannot be obtained through above actions (mine, kill, build, pour)
   - Then, use the following NOOP recipe format:
     ```json
     {"target": "$TARGET$", "action": "NOOP", "require": {}, "result_amount": 1}
     ```
     Example NOOP targets: dirt, sand, log, etc.

---

### Examples

Example 1:
Input target: blaze_rod
Output:
```json
{
  "target": "blaze_rod",
  "action": "kill:blaze",
  "require": {
    "nether_portal": 1,
    "diamond_sword": 1,
    "diamond_helmet": 1,
    "diamond_chestplate": 1,
    "diamond_leggings": 1,
    "diamond_boots": 1
  },
  "result_amount": 1
}

Example 2:
Input target: raw_iron
Output:
```json
{
  "target": "raw_iron",
  "action": "mine:iron_ore",
  "require": {
    "stone_pickaxe": 1
  },
  "result_amount": 1
}
```

Example 3:
Input target: nether_portal
Output:
```json
{
  "target": "nether_portal",
  "action": "build:nether_portal",
  "require": {
    "obsidian": 10,
    "flint_and_steel": 1
  },
  "result_amount": 1
}

Example 4:
Input target: oak_logs
Output:
```json
{
  "target": "oak_logs",
  "action": "NOOP",
  "require": {},
  "result_amount": 1
}
```

Example 5:
Input target: water_bucket
Output:
```json
{
  "target": "water_bucket",
  "action": "pour:water",
  "require": {
    "bucket": 1
  },
  "result_amount": 1
}
```

---

Your turn:
Input target: $TARGET$
Output:
"""