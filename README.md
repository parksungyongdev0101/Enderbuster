# Enderbuster 🐉

## Introduction

This project was conducted as part of a competition organized by the YAI Conference (October 2025 - December 2025).
This project extends the [Mindcraft](https://github.com/mindcraft-bots/mindcraft) framework to enable LLM-based agents to tackle complex long-horizon tasks in Minecraft through item-based planning.

### Goal

Apply LLM Agent reasoning capabilities to complex Minecraft tasks that require multi-step planning and execution. The primary challenge addressed is reaching the End dimension, which requires acquiring 29+ items with intricate dependency relationships.

### Challenge

Long-horizon tasks in Minecraft, such as reaching the End dimension, involve:
- **Complex dependencies**: Items require other items (e.g., Ender Eye requires Ender Pearl + Blaze Powder)
- **Multiple acquisition methods**: Crafting, mining, mob hunting, and exploration
- **Sequential requirements**: Tools must be crafted before resources can be gathered

For example, to reach the End dimension, an agent must:
1. Collect basic resources (oak_log, cobblestone)
2. Craft tools (wooden_pickaxe → stone_pickaxe → iron_pickaxe → diamond_pickaxe)
3. Gather advanced materials (diamond, obsidian)
4. Enter the Nether and obtain blaze_rod
5. Craft ender_eye and locate the End Portal

### Solution

We implement an **item-based planning system (mc-plan)** that:
- Generates complete item dependency trees from Minecraft recipe data
- Creates ordered execution sequences respecting dependencies
- Converts each item into a natural language subgoal for the LLM agent
- Executes plans sequentially using the `!executeItemPlan` command

## Project Overview

Built on the Mindcraft framework, this project adds a planning layer that breaks down complex goals into manageable item acquisition tasks. The mc-plan system analyzes Minecraft recipes to build dependency graphs and generate step-by-step execution plans.

### Key Features

- **Automatic Planning**: Generates complete item dependency trees for any target item
- **Sequential Execution**: Executes plans item-by-item, ensuring dependencies are met
- **Natural Language Actions**: Converts item requirements into actionable commands for LLM agents
- **Robust Dependency Resolution**: Handles crafting, mining, and mob-related item acquisition

## Architecture

### Mindcraft Framework

The base [Mindcraft](https://github.com/mindcraft-bots/mindcraft) framework provides:
- LLM-based agent that can converse, see, move, mine, build, and interact with the Minecraft world
- Command system for agent actions (`!collectBlocks`, `!craftRecipe`, etc.)
- Memory and conversation management
- Integration with various LLM APIs (OpenAI, Gemini, Anthropic, etc.)

### MC-Plan System

The mc-plan system consists of three main stages:

#### 1. Recipe Extraction
- Extracts Minecraft recipes from `mc-plan/craft_or_smelt/recipe/` (1,407 recipe JSON files)
- Parses crafting recipes, smelting recipes, and item acquisition methods
- Builds extended recipe tree with all dependencies (`recipe_extended.json`)

#### 2. Sequence Generation
- Analyzes dependency graph to determine execution order
- Generates ordered item sequence (`recipe_sequence.json`) with required amounts
- Ensures dependencies are resolved before dependent items

#### 3. Action Planning
- Converts each item in the sequence into natural language actions
- Generates `item_plans.json` with actionable commands for each item
- Handles different acquisition methods (craft, mine, hunt, etc.)

### Execution Flow

```
1. User/System sets target: "ender_eye"
   ↓
2. main.js calls: python mc-plan/main.py --target ender_eye --need_amount 1 --mode exact
   ↓
3. mc-plan generates:
   - recipe_extended.json (dependency tree)
   - recipe_sequence.json (ordered items)
   - item_plans.json (natural language actions)
   ↓
4. Agent receives: !executeItemPlan command
   ↓
5. Agent executes plan sequentially:
   - For each item in item_plans.json:
     a. Check if item already in inventory
     b. If not, set as subgoal
     c. Execute natural language action (e.g., "Collect 7 oak_log")
     d. Wait for subgoal completion
     e. Move to next item
   ↓
6. Final item (ender_eye) acquired → Goal achieved
```

## Data Structure

### Recipe Data
- **Location**: `mc-plan/craft_or_smelt/recipe/`
- **Content**: 1,407 raw Minecraft recipe JSON files
- **Purpose**: Source data for recipe extraction and dependency analysis

### Generated Files

#### `mc-plan/recipe_extended.json`
Extended recipe tree with all dependencies resolved. Contains:
- Item recipes with required ingredients
- Acquisition methods (craft, smelt, mine, hunt)
- Result amounts and dependency chains

#### `mc-plan/recipe_sequence.json`
Ordered list of items with execution order:
```json
[
  {
    "target": "oak_log",
    "recipe": null,
    "need_amount": 7
  },
  {
    "target": "oak_planks",
    "recipe": {
      "target": "oak_planks",
      "action": "craft",
      "require": {"oak_log": 1},
      "result_amount": 4
    },
    "need_amount": 12
  },
  ...
]
```

#### `mc-plan/item_plans.json`
Natural language action plans for each item:
```json
[
  {
    "target": "oak_log",
    "item": "oak_log",
    "need_amount": 7,
    "actions": ["Collect 7 oak_log."]
  },
  {
    "target": "oak_planks",
    "item": "oak_planks",
    "need_amount": 12,
    "actions": ["Craft 12 oak_planks."]
  },
  ...
]
```

## Installation & Setup

### Prerequisites

- **Node.js** (v18 or higher): [Download](https://nodejs.org/)
- **Python** 3.11: [Download](https://www.python.org/)
- **Conda** (recommended): [Download](https://docs.conda.io/en/latest/miniconda.html)
- **Minecraft Java Edition** (up to v1.21.6, recommend v1.21.1)
- **LLM API Key**: One of OpenAI, Gemini, Anthropic, etc.

### Installation Steps

1. **Clone the repository**:
```bash
git clone <repository-url>
cd Enderbuster_develop
```

2. **Install Node.js dependencies**:
```bash
npm install
```

3. **Set up Python environment**:
```bash
conda create --name mindcraft python=3.11
conda activate mindcraft
pip install -r requirements.txt
```

4. **Configure environment variables**:
   - Create `.env` file in project root:
   ```
   CONDA_PYTHON=C:\Users\YOUR_USERNAME\anaconda3\envs\mindcraft\python.exe
   OPENAI_API_KEY=YOUR_API_KEY
   ```
   - Or configure API keys in `keys.json` (copy from `keys.example.json` if exists)

5. **Configure bot profile**:
   - Edit `settings.js` to set your desired LLM model
   - Or modify `andy.json` for model configuration

## Execution

### Generate Plan

To generate an item plan for a target item:

```bash
python mc-plan/main.py --target ender_eye --need_amount 1 --mode exact
```

**Parameters**:
- `--target`: Target item name (e.g., "ender_eye", "diamond_pickaxe")
- `--need_amount`: Number of items needed (default: 1)
- `--mode`: `buffered` (adds 20% buffer) or `exact` (exact amount)

This generates:
- `mc-plan/recipe_extended.json`
- `mc-plan/recipe_sequence.json`
- `mc-plan/item_plans.json`

### Run Agent

1. **Start Minecraft world**:
   - Open Minecraft and create/load a world
   - Open to LAN on localhost port `55916` (default)

2. **Run the agent**:
```bash
node main.js
```

The agent will:
- Automatically generate plan for `ender_eye` (as configured in `main.js` line 123)
- Connect to Minecraft server
- Execute the plan using `!executeItemPlan` command

### Manual Plan Execution

If you want to execute a pre-generated plan:

1. Set environment variable:
```bash
export PLAN_FILE_NAME=mc-plan/item_plans.json
```

2. In Minecraft chat or agent interface, send:
```
!executeItemPlan
```

The agent will execute each item in the plan sequentially.

## Key Results

### Successfully Handled Tasks

- **Complex Dependency Resolution**: Generates complete dependency trees for 29+ items required for End dimension access
- **Multi-Method Acquisition**: Handles crafting, mining, smelting, and mob hunting
- **Sequential Execution**: Ensures proper order of operations (tools before resources)
- **Robust Planning**: Accounts for recipe outputs (e.g., 1 log → 4 planks) and calculates required amounts

### Example: End Dimension Access

The system successfully plans and executes the following sequence:
1. Basic resources: oak_log, cobblestone, coal
2. Tools progression: wooden_pickaxe → stone_pickaxe → iron_pickaxe → diamond_pickaxe
3. Advanced materials: diamond, obsidian, flint
4. Nether preparation: nether_portal, blaze_rod, blaze_powder
5. End preparation: ender_pearl, ender_eye, end_portal location

All 29+ items are acquired in the correct order, respecting all dependencies.

## Future Work

### Planned Improvements

1. **Ender Dragon Defeat**
   - Extend planning to include combat strategies
   - Plan for End dimension exploration and dragon battle

2. **Memory Persistence**
   - Implement memory saving on disconnect
   - Resume execution from last completed item on reconnection

3. **Reinforcement Learning with Open-Source Models**
   - Integrate RL training with open-source LLMs
   - Improve planning efficiency through learned strategies

4. **Parallel Item Processing**
   - Identify independent items that can be acquired simultaneously
   - Optimize execution time through parallel planning

## Project Structure

```
Enderbuster_develop/
├── main.js                 # Entry point, calls mc-plan and initializes agents
├── settings.js             # Agent configuration
├── send_subgoals.py        # Script to send subgoals to agent
├── mc-plan/                # Planning system
│   ├── main.py            # Main planner entry point
│   ├── planner.py         # Generates item_plans.json
│   ├── build_recipe_seq.py # Generates recipe_sequence.json
│   ├── item_plans.json    # Generated action plans
│   ├── recipe_sequence.json # Generated item sequence
│   └── craft_or_smelt/    # Recipe data (1,407 JSON files)
├── src/                    # Mindcraft framework
│   ├── agent/
│   │   └── commands/
│   │       └── actions.js # Contains !executeItemPlan command
│   └── ...
└── profiles/               # Bot profiles
```

## Credits

This project builds upon:
- **[Mindcraft](https://github.com/mindcraft-bots/mindcraft)**: LLM-based Minecraft agent framework
- **[Mineflayer](https://prismarinejs.github.io/mineflayer/)**: Minecraft bot API for Node.js
- **[PrismarineJS](https://prismarine.js.org/)**: Minecraft protocol implementation


## Team

- 박성용 (Team Leader)
- 김재후
- 김윤지
- 이현서
- 주현종
## License

See [LICENSE](LICENSE) file for details.
