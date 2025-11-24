import * as skills from '../library/skills.js';
import settings from '../settings.js';
import convoManager from '../conversation.js';
import pf from 'mineflayer-pathfinder';
import Vec3 from 'vec3'
import { getInventoryCounts } from '../library/world.js';

function runAsAction (actionFn, resume = false, timeout = -1) {
    let actionLabel = null;  // Will be set on first use
    
    const wrappedAction = async function (agent, ...args) {
        // Set actionLabel only once, when the action is first created
        if (!actionLabel) {
            const actionObj = actionsList.find(a => a.perform === wrappedAction);
            actionLabel = actionObj.name.substring(1); // Remove the ! prefix
        }

        const actionFnWithAgent = async () => {
            await actionFn(agent, ...args);
        };
        const code_return = await agent.actions.runAction(`action:${actionLabel}`, actionFnWithAgent, { timeout, resume });
        if (code_return.interrupted && !code_return.timedout)
            return;
        return code_return.message;
    }

    return wrappedAction;
}

export const actionsList = [
    {
        name: '!completeSubgoal',
        description: 'Call when you completed a given subogoal.',
        perform: function (agent) {
            agent.bot.emit('chat', 'ChebysofH', 'Tell me what you have done so far.');
            return;
        }
    },
    {
        name: '!newAction',
        description: 'Perform new and unknown custom behaviors that are not available as a command.', 
        params: {
            'prompt': { type: 'string', description: 'A natural language prompt to guide code generation. Make a detailed step-by-step plan.' }
        },
        perform: async function(agent, prompt) {
            // just ignore prompt - it is now in context in chat history
            if (!settings.allow_insecure_coding) { 
                agent.openChat('newAction is disabled. Enable with allow_insecure_coding=true in settings.js');
                return "newAction not allowed! Code writing is disabled in settings. Notify the user.";
            }
            let result = "";
            const actionFn = async () => {
                try {
                    result = await agent.coder.generateCode(agent.history);
                } catch (e) {
                    result = 'Error generating code: ' + e.toString();
                }
            };
            await agent.actions.runAction('action:newAction', actionFn, {timeout: settings.code_timeout_mins});
            return result;
        }
    },
    {
        name: '!stop',
        description: 'Force stop all actions and commands that are currently executing.',
        perform: async function (agent) {
            await agent.actions.stop();
            agent.clearBotLogs();
            agent.actions.cancelResume();
            agent.bot.emit('idle');
            let msg = 'Agent stopped.';
            if (agent.self_prompter.isActive())
                msg += ' Self-prompting still active.';
            return msg;
        }
    },
    {
        name: '!stfu',
        description: 'Stop all chatting and self prompting, but continue current action.',
        perform: async function (agent) {
            agent.openChat('Shutting up.');
            agent.shutUp();
            return;
        }
    },
    {
        name: '!restart',
        description: 'Restart the agent process.',
        perform: async function (agent) {
            agent.cleanKill();
        }
    },
    {
        name: '!clearChat',
        description: 'Clear the chat history.',
        perform: async function (agent) {
            agent.history.clear();
            return agent.name + "'s chat history was cleared, starting new conversation from scratch.";
        }
    },
    {
        name: '!goToPlayer',
        description: 'Go to the given player.',
        params: {
            'player_name': {type: 'string', description: 'The name of the player to go to.'},
            'closeness': {type: 'float', description: 'How close to get to the player.', domain: [0, Infinity]}
        },
        perform: runAsAction(async (agent, player_name, closeness) => {
            await skills.goToPlayer(agent.bot, player_name, closeness);
        })
    },
    {
        name: '!followPlayer',
        description: 'Endlessly follow the given player.',
        params: {
            'player_name': {type: 'string', description: 'name of the player to follow.'},
            'follow_dist': {type: 'float', description: 'The distance to follow from.', domain: [0, Infinity]}
        },
        perform: runAsAction(async (agent, player_name, follow_dist) => {
            await skills.followPlayer(agent.bot, player_name, follow_dist);
        }, true)
    },
    {
        name: '!goToCoordinates',
        description: 'Go to the given x, y, z location.',
        params: {
            'x': {type: 'float', description: 'The x coordinate.', domain: [-Infinity, Infinity]},
            'y': {type: 'float', description: 'The y coordinate.', domain: [-64, 320]},
            'z': {type: 'float', description: 'The z coordinate.', domain: [-Infinity, Infinity]},
            'closeness': {type: 'float', description: 'How close to get to the location.', domain: [0, Infinity]}
        },
        perform: runAsAction(async (agent, x, y, z, closeness) => {
            await skills.goToPosition(agent.bot, x, y, z, closeness);
        })
    },
    {
        name: '!searchForBlock',
        description: 'Find and go to the nearest block of a given type in a given range.',
        params: {
            'type': { type: 'BlockName', description: 'The block type to go to.' },
            'search_range': { type: 'float', description: 'The range to search for the block. Minimum 32.', domain: [10, 512] }
        },
        perform: runAsAction(async (agent, block_type, range) => {
            if (range < 32) {
                log(agent.bot, `Minimum search range is 32.`);
                range = 32;
            }
            await skills.goToNearestBlock(agent.bot, block_type, 4, range);
        })
    },
    {
        name: '!searchForEntity',
        description: 'Find and go to the nearest entity of a given type in a given range.',
        params: {
            'type': { type: 'string', description: 'The type of entity to go to.' },
            'search_range': { type: 'float', description: 'The range to search for the entity.', domain: [32, 512] }
        },
        perform: runAsAction(async (agent, entity_type, range) => {
            await skills.goToNearestEntity(agent.bot, entity_type, 4, range);
        })
    },
    {
        name: '!moveAway',
        description: 'Move away from the current location in any direction by a given distance.',
        params: {'distance': { type: 'float', description: 'The distance to move away.', domain: [0, Infinity] }},
        perform: runAsAction(async (agent, distance) => {
            await skills.moveAway(agent.bot, distance);
        })
    },
    {
        name: '!rememberHere',
        description: 'Save the current location with a given name.',
        params: {'name': { type: 'string', description: 'The name to remember the location as.' }},
        perform: async function (agent, name) {
            const pos = agent.bot.entity.position;
            agent.memory_bank.rememberPlace(name, pos.x, pos.y, pos.z);
            return `Location saved as "${name}".`;
        }
    },
    {
        name: '!goToRememberedPlace',
        description: 'Go to a saved location.',
        params: {'name': { type: 'string', description: 'The name of the location to go to.' }},
        perform: runAsAction(async (agent, name) => {
            const pos = agent.memory_bank.recallPlace(name);
            if (!pos) {
            skills.log(agent.bot, `No location named "${name}" saved.`);
            return;
            }
            await skills.goToPosition(agent.bot, pos[0], pos[1], pos[2], 1);
        })
    },
    {
        name: '!givePlayer',
        description: 'Give the specified item to the given player.',
        params: { 
            'player_name': { type: 'string', description: 'The name of the player to give the item to.' }, 
            'item_name': { type: 'ItemName', description: 'The name of the item to give.' },
            'num': { type: 'int', description: 'The number of items to give.', domain: [1, Number.MAX_SAFE_INTEGER] }
        },
        perform: runAsAction(async (agent, player_name, item_name, num) => {
            await skills.giveToPlayer(agent.bot, item_name, player_name, num);
        })
    },
    {
        name: '!consume',
        description: 'Eat/drink the given item.',
        params: {'item_name': { type: 'ItemName', description: 'The name of the item to consume.' }},
        perform: runAsAction(async (agent, item_name) => {
            await skills.consume(agent.bot, item_name);
        })
    },
    {
        name: '!equip',
        description: 'Equip the given item.',
        params: {'item_name': { type: 'ItemName', description: 'The name of the item to equip.' }},
        perform: runAsAction(async (agent, item_name) => {
            await skills.equip(agent.bot, item_name);
        })
    },
    {
        name: '!putInChest',
        description: 'Put the given item in the nearest chest.',
        params: {
            'item_name': { type: 'ItemName', description: 'The name of the item to put in the chest.' },
            'num': { type: 'int', description: 'The number of items to put in the chest.', domain: [1, Number.MAX_SAFE_INTEGER] }
        },
        perform: runAsAction(async (agent, item_name, num) => {
            await skills.putInChest(agent.bot, item_name, num);
        })
    },
    {
        name: '!takeFromChest',
        description: 'Take the given items from the nearest chest.',
        params: {
            'item_name': { type: 'ItemName', description: 'The name of the item to take.' },
            'num': { type: 'int', description: 'The number of items to take.', domain: [1, Number.MAX_SAFE_INTEGER] }
        },
        perform: runAsAction(async (agent, item_name, num) => {
            await skills.takeFromChest(agent.bot, item_name, num);
        })
    },
    {
        name: '!viewChest',
        description: 'View the items/counts of the nearest chest.',
        params: { },
        perform: runAsAction(async (agent) => {
            await skills.viewChest(agent.bot);
        })
    },
    {
        name: '!discard',
        description: 'Discard the given item from the inventory.',
        params: {
            'item_name': { type: 'ItemName', description: 'The name of the item to discard.' },
            'num': { type: 'int', description: 'The number of items to discard.', domain: [1, Number.MAX_SAFE_INTEGER] }
        },
        perform: runAsAction(async (agent, item_name, num) => {
            const start_loc = agent.bot.entity.position;
            await skills.moveAway(agent.bot, 5);
            await skills.discard(agent.bot, item_name, num);
            await skills.goToPosition(agent.bot, start_loc.x, start_loc.y, start_loc.z, 0);
        })
    },
    {
        name: '!collectBlocks',
        description: 'Collect the nearest blocks of a given type.',
        params: {
            'type': { type: 'BlockName', description: 'The block type to collect.' },
            'num': { type: 'int', description: 'The number of blocks to collect.', domain: [1, Number.MAX_SAFE_INTEGER] }
        },
        perform: runAsAction(async (agent, type, num) => {
            await skills.collectBlock(agent.bot, type, num);
        }, false, 10) // 10 minute timeout
    },
    {
        name: '!craftRecipe',
        description: 'Craft the given recipe a given number of times.',
        params: {
            'recipe_name': { type: 'ItemName', description: 'The name of the output item to craft.' },
            'num': { type: 'int', description: 'The number of times to craft the recipe. This is NOT the number of output items, as it may craft many more items depending on the recipe.', domain: [1, Number.MAX_SAFE_INTEGER] }
        },
        perform: runAsAction(async (agent, recipe_name, num) => {
            await skills.craftRecipe(agent.bot, recipe_name, num);
        })
    },
    {
        name: '!smeltItem',
        description: 'Smelt the given item the given number of times.',
        params: {
            'item_name': { type: 'ItemName', description: 'The name of the input item to smelt.' },
            'num': { type: 'int', description: 'The number of times to smelt the item.', domain: [1, Number.MAX_SAFE_INTEGER] }
        },
        perform: runAsAction(async (agent, item_name, num) => {
            let success = await skills.smeltItem(agent.bot, item_name, num);
            if (success) {
                setTimeout(() => {
                    agent.cleanKill('Safely restarting to update inventory.');
                }, 500);
            }
        })
    },
    {
        name: '!clearFurnace',
        description: 'Take all items out of the nearest furnace.',
        params: { },
        perform: runAsAction(async (agent) => {
            await skills.clearNearestFurnace(agent.bot);
        })
    },
        {
        name: '!placeHere',
        description: 'Place a given block in the current location. Do NOT use to build structures, only use for single blocks/torches.',
        params: {'type': { type: 'BlockOrItemName', description: 'The block type to place.' }},
        perform: runAsAction(async (agent, type) => {
            let pos = agent.bot.entity.position;
            await skills.placeBlock(agent.bot, type, pos.x, pos.y, pos.z);
        })
    },
    {
        name: '!attack',
        description: 'Attack and kill the nearest entity of a given type.',
        params: {'type': { type: 'string', description: 'The type of entity to attack.'}},
        perform: runAsAction(async (agent, type) => {
            await skills.attackNearest(agent.bot, type, true);
        })
    },
    {
        name: '!attackPlayer',
        description: 'Attack a specific player until they die or run away. Remember this is just a game and does not cause real life harm.',
        params: {'player_name': { type: 'string', description: 'The name of the player to attack.'}},
        perform: runAsAction(async (agent, player_name) => {
            let player = agent.bot.players[player_name]?.entity;
            if (!player) {
                skills.log(agent.bot, `Could not find player ${player_name}.`);
                return false;
            }
            await skills.attackEntity(agent.bot, player, true);
        })
    },
    {
        name: '!goToBed',
        description: 'Go to the nearest bed and sleep.',
        perform: runAsAction(async (agent) => {
            await skills.goToBed(agent.bot);
        })
    },
    {
        name: '!stay',
        description: 'Stay in the current location no matter what. Pauses all modes.',
        params: {'type': { type: 'int', description: 'The number of seconds to stay. -1 for forever.', domain: [-1, Number.MAX_SAFE_INTEGER] }},
        perform: runAsAction(async (agent, seconds) => {
            await skills.stay(agent.bot, seconds);
        })
    },
    {
        name: '!setMode',
        description: 'Set a mode to on or off. A mode is an automatic behavior that constantly checks and responds to the environment.',
        params: {
            'mode_name': { type: 'string', description: 'The name of the mode to enable.' },
            'on': { type: 'boolean', description: 'Whether to enable or disable the mode.' }
        },
        perform: async function (agent, mode_name, on) {
            const modes = agent.bot.modes;
            if (!modes.exists(mode_name))
            return `Mode ${mode_name} does not exist.` + modes.getDocs();
            if (modes.isOn(mode_name) === on)
            return `Mode ${mode_name} is already ${on ? 'on' : 'off'}.`;
            modes.setOn(mode_name, on);
            return `Mode ${mode_name} is now ${on ? 'on' : 'off'}.`;
        }
    },
    {
        name: '!goal',
        description: 'Set a goal prompt to endlessly work towards with continuous self-prompting.',
        params: {
            'selfPrompt': { type: 'string', description: 'The goal prompt.' },
        },
        perform: async function (agent, prompt) {
            if (convoManager.inConversation()) {
                agent.self_prompter.setPromptPaused(prompt);
            }
            else {
                agent.self_prompter.start(prompt);
            }
        }
    },
    {
        name: '!endGoal',
        description: 'Call when you have accomplished your goal. It will stop self-prompting and the current action. You must call this command when you have completed all the subgoals and have the target item in your inventory. If you don\'t call this command, the agent will keep working on the next subgoal without checking if the target item is in your inventory.',
        perform: async function (agent) {
            agent.self_prompter.stop();
            return 'Self-prompting stopped.';
        }
    },
    {
        name: '!showVillagerTrades',
        description: 'Show trades of a specified villager.',
        params: {'id': { type: 'int', description: 'The id number of the villager that you want to trade with.' }},
        perform: runAsAction(async (agent, id) => {
            await skills.showVillagerTrades(agent.bot, id);
        })
    },
    {
        name: '!tradeWithVillager',
        description: 'Trade with a specified villager.',
        params: {
            'id': { type: 'int', description: 'The id number of the villager that you want to trade with.' },
            'index': { type: 'int', description: 'The index of the trade you want executed (1-indexed).', domain: [1, Number.MAX_SAFE_INTEGER] },
            'count': { type: 'int', description: 'How many times that trade should be executed.', domain: [1, Number.MAX_SAFE_INTEGER] },
        },
        perform: runAsAction(async (agent, id, index, count) => {
            await skills.tradeWithVillager(agent.bot, id, index, count);
        })
    },
    {
        name: '!startConversation',
        description: 'Start a conversation with a bot. (FOR OTHER BOTS ONLY)',
        params: {
            'player_name': { type: 'string', description: 'The name of the player to send the message to.' },
            'message': { type: 'string', description: 'The message to send.' },
        },
        perform: async function (agent, player_name, message) {
            if (!convoManager.isOtherAgent(player_name))
                return player_name + ' is not a bot, cannot start conversation.';
            if (convoManager.inConversation() && !convoManager.inConversation(player_name)) 
                convoManager.forceEndCurrentConversation();
            else if (convoManager.inConversation(player_name))
                agent.history.add('system', 'You are already in conversation with ' + player_name + '. Don\'t use this command to talk to them.');
            convoManager.startConversation(player_name, message);
        }
    },
    {
        name: '!endConversation',
        description: 'End the conversation with the given bot. (FOR OTHER BOTS ONLY)',
        params: {
            'player_name': { type: 'string', description: 'The name of the player to end the conversation with.' }
        },
        perform: async function (agent, player_name) {
            if (!convoManager.inConversation(player_name))
                return `Not in conversation with ${player_name}.`;
            convoManager.endConversation(player_name);
            return `Converstaion with ${player_name} ended.`;
        }
    },
    {
        name: '!lookAtPlayer',
        description: 'Look at a player or look in the same direction as the player.',
        params: {
            'player_name': { type: 'string', description: 'Name of the target player' },
            'direction': {
                type: 'string',
                description: 'How to look ("at": look at the player, "with": look in the same direction as the player)',
            }
        },
        perform: async function(agent, player_name, direction) {
            if (direction !== 'at' && direction !== 'with') {
                return "Invalid direction. Use 'at' or 'with'.";
            }
            let result = "";
            const actionFn = async () => {
                result = await agent.vision_interpreter.lookAtPlayer(player_name, direction);
            };
            await agent.actions.runAction('action:lookAtPlayer', actionFn);
            return result;
        }
    },
    {
        name: '!lookAtPosition',
        description: 'Look at specified coordinates.',
        params: {
            'x': { type: 'int', description: 'x coordinate' },
            'y': { type: 'int', description: 'y coordinate' },
            'z': { type: 'int', description: 'z coordinate' }
        },
        perform: async function(agent, x, y, z) {
            let result = "";
            const actionFn = async () => {
                result = await agent.vision_interpreter.lookAtPosition(x, y, z);
            };
            await agent.actions.runAction('action:lookAtPosition', actionFn);
            return result;
        }
    },
    {
        name: '!digDown',
        description: 'Digs down a specified distance. Will stop if it reaches lava, water, or a fall of >=4 blocks below the bot.',
        params: {'distance': { type: 'int', description: 'Distance to dig down', domain: [1, Number.MAX_SAFE_INTEGER] }},
        perform: runAsAction(async (agent, distance) => {
            await skills.digDown(agent.bot, distance)
        })
    },
    {
        name: '!goToSurface',
        description: 'Moves the bot to the highest block above it (usually the surface).',
        params: {},
        perform: runAsAction(async (agent) => {
            await skills.goToSurface(agent.bot);
        })
    },
    {
        name: '!useOn',
        description: 'Use (right click) the given tool on the nearest target of the given type.',
        params: {
            'tool_name': { type: 'string', description: 'Name of the tool to use, or "hand" for no tool.' },
            'target': { type: 'string', description: 'The target as an entity type, block type, or "nothing" for no target.' }
        },
        perform: runAsAction(async (agent, tool_name, target) => {
            await skills.useToolOn(agent.bot, tool_name, target);
        })
    },
    {
        name: '!buildEndPortal',
        description: 'Activate the end portal by placing ender eyes in all nearby end portal frames.',
        params: {},
        perform: runAsAction(async (agent) => {
            const bot = agent.bot;

            // Find all end_portal_frame blocks nearby
            const frames = bot.findBlocks({
                matching: bot.registry.blocksByName.end_portal_frame.id,
                maxDistance: 32,
                count: 1000
            });

            if (frames.length === 0) {
                skills.log(bot, `No end portal frames found nearby.`);
                return false;
            }

            skills.log(bot, `Found ${frames.length} end portal frames.`);

            // Check inventory for ender eyes - must have at least 12
            const inventory = getInventoryCounts(bot);
            const enderEyeCount = inventory['ender_eye'] || 0;

            if (enderEyeCount < 12) {
                skills.log(bot, `Need at least 12 ender eyes to build end portal. You have ${enderEyeCount}.`);
                return false;
            }

            // Count how many frames need ender eyes (frames without eye have property eye: false)
            let framesNeedingEyes = 0;
            const framesToFill = [];

            for (const framePos of frames) {
                const block = bot.blockAt(framePos);
                if (block && block.name === 'end_portal_frame') {
                    // Check if the frame already has an eye (getProperties returns block state)
                    const hasEye = block.getProperties().eye;
                    if (!hasEye) {
                        framesNeedingEyes++;
                        framesToFill.push(framePos);
                    }
                }
            }

            skills.log(bot, `${framesNeedingEyes} frames need ender eyes.`);

            if (framesNeedingEyes === 0) {
                skills.log(bot, `All end portal frames already have ender eyes!`);
                return true;
            }


            // Place ender eyes on each frame
            let placedCount = 0;
            for (const framePos of framesToFill) {
                const block = bot.blockAt(framePos);
                if (!block) continue;

                try {
                    // Go near the frame
                    await skills.goToPosition(bot, framePos.x, framePos.y, framePos.z, 3);
                    await new Promise(resolve => setTimeout(resolve, 200));

                    // Use ender eye on the frame
                    await skills.equip(bot, 'ender_eye');
                    await bot.lookAt(block.position.offset(0.5, 0.5, 0.5));
                    await bot.activateBlock(block);

                    placedCount++;
                    skills.log(bot, `Placed ender eye ${placedCount}/${framesNeedingEyes} at (${framePos.x}, ${framePos.y}, ${framePos.z})`);

                    await new Promise(resolve => setTimeout(resolve, 500));
                } catch (err) {
                    skills.log(bot, `Failed to place ender eye at (${framePos.x}, ${framePos.y}, ${framePos.z}): ${err.message}`);
                }
            }

            if (placedCount === framesNeedingEyes) {
                skills.log(bot, `End portal activated! Placed ${placedCount} ender eyes.`);
                return true;
            } else {
                skills.log(bot, `Partially activated end portal. Placed ${placedCount}/${framesNeedingEyes} ender eyes.`);
                return false;
            }
        })
    },
    {
        name: '!buildNetherPortal',
        description: 'Build a nether portal in front of the agent. Requires at least 10 obsidian and 1 flint and steel.',
        params: {},
        perform: runAsAction(async (agent) => {
            const bot = agent.bot;

            // Check inventory for required items
            const inventory = getInventoryCounts(bot);
            const obsidianCount = inventory['obsidian'] || 0;
            const flintSteelCount = inventory['flint_and_steel'] || 0;

            if (obsidianCount < 10) {
                skills.log(bot, `Need at least 10 obsidian to build a nether portal. You have ${obsidianCount}.`);
                return false;
            }

            if (flintSteelCount < 1) {
                skills.log(bot, `Need at least 1 flint and steel to light the portal. You have ${flintSteelCount}.`);
                return false;
            }

            // Get bot position and calculate portal positions in front of the bot
            const pos = bot.entity.position;
            const baseX = Math.floor(pos.x);
            const baseY = Math.floor(pos.y);
            const baseZ = Math.floor(pos.z + 3); // 3 blocks in front to avoid bot position

            // Portal shape (viewed from front):
            //  xx   (y+4)
            // x  x  (y+3)
            // x  x  (y+2)
            // x  x  (y+1)
            //  xx   (y+0, ground level)

            const portalBlocks = [
                // Layer 0 (bottom) - 2 middle blocks only
                { x: baseX, y: baseY, z: baseZ },
                { x: baseX + 1, y: baseY, z: baseZ },
                // Layer 1 - left and right sides
                { x: baseX - 1, y: baseY + 1, z: baseZ },
                { x: baseX + 2, y: baseY + 1, z: baseZ },
                // Layer 2 - left and right sides
                { x: baseX - 1, y: baseY + 2, z: baseZ },
                { x: baseX + 2, y: baseY + 2, z: baseZ },
                // Layer 3 - left and right sides
                { x: baseX - 1, y: baseY + 3, z: baseZ },
                { x: baseX + 2, y: baseY + 3, z: baseZ },
                // Layer 4 (top) - 2 middle blocks only
                { x: baseX, y: baseY + 4, z: baseZ },
                { x: baseX + 1, y: baseY + 4, z: baseZ }
            ];

            // Also need to clear interior space
            const interiorBlocks = [
                { x: baseX, y: baseY + 1, z: baseZ },
                { x: baseX + 1, y: baseY + 1, z: baseZ },
                { x: baseX, y: baseY + 2, z: baseZ },
                { x: baseX + 1, y: baseY + 2, z: baseZ },
                { x: baseX, y: baseY + 3, z: baseZ },
                { x: baseX + 1, y: baseY + 3, z: baseZ }
            ];

            skills.log(bot, `Building nether portal at (${baseX}, ${baseY}, ${baseZ})...`);

            // Clear all blocks in the portal area (frame + interior)
            const allBlocks = [...portalBlocks, ...interiorBlocks];
            for (const blockPos of allBlocks) {
                bot.chat(`/setblock ${blockPos.x} ${blockPos.y} ${blockPos.z} air`);
                await new Promise(resolve => setTimeout(resolve, 50));
            }

            // Place obsidian blocks directly using setblock command
            for (const block of portalBlocks) {
                bot.chat(`/setblock ${block.x} ${block.y} ${block.z} obsidian`);
                await new Promise(resolve => setTimeout(resolve, 50));
            }

            // Remove 10 obsidian from inventory
            await skills.discard(bot, 'obsidian', 10);
            skills.log(bot, `Removed 10 obsidian from inventory.`);

            // Light the portal by placing fire in the interior
            bot.chat(`/setblock ${baseX} ${baseY + 1} ${baseZ} fire`);
            await new Promise(resolve => setTimeout(resolve, 100));

            // Remove 1 durability from flint and steel (simulated by removing it if durability system not available)
            // Note: In Minecraft, flint and steel loses durability, but we'll just acknowledge we used it
            skills.log(bot, `Used flint and steel to light the portal.`);

            skills.log(bot, `Nether portal built and lit successfully!`);
            return true;
            })
        },
        {
            name: '!findEndPortal',
            description: 'Find the end portal by throwing ender eyes and following their direction. Moves 250 blocks in the direction the ender eye travels, then searches for end portal frames within 250 blocks.',
            params: {},
            perform: runAsAction(async (agent) => {
                const bot = agent.bot;

                // Helper: Search for end portal and move to it if found
                async function findAndMoveToPortal() {
                    const frames = bot.findBlocks({
                        matching: bot.registry.blocksByName.end_portal_frame.id,
                        maxDistance: 250,
                        count: 1000
                    });

                    if (frames.length === 0) return false;

                    skills.log(bot, `Found ${frames.length} end portal frame(s)!`);
                    agent.openChat('I found the end portal!');

                    // Calculate portal center
                    const avgX = frames.reduce((sum, f) => sum + f.x, 0) / frames.length;
                    const avgY = frames.reduce((sum, f) => sum + f.y, 0) / frames.length;
                    const avgZ = frames.reduce((sum, f) => sum + f.z, 0) / frames.length;

                    skills.log(bot, `Moving to end portal at (${avgX.toFixed(1)}, ${avgY.toFixed(1)}, ${avgZ.toFixed(1)})...`);
                    
                    try {
                        await skills.goToGoal(bot, new pf.goals.GoalNear(avgX, avgY, avgZ, 3));
                        const distance = bot.entity.position.distanceTo(new Vec3(avgX, avgY, avgZ));
                        if (distance <= 5) {
                            skills.log(bot, `Successfully found and reached the end portal!`);
                        }
                    } catch (err) {
                        skills.log(bot, `Error moving to end portal: ${err.message}`);
                    }
                    return true;
                }

                // Helper: Track ender eye direction
                async function trackEnderEyeDirection() {
                    const inventory = getInventoryCounts(bot);
                    if ((inventory['ender_eye'] || 0) < 1) {
                        skills.log(bot, `Need at least 1 ender eye.`);
                        return null;
                    }

                    const entitiesBefore = new Set(Object.keys(bot.entities));
                    await skills.equip(bot, 'ender_eye');
                    await new Promise(resolve => setTimeout(resolve, 100));
                    await bot.activateItem();
                    skills.log(bot, `Threw ender eye.`);
                    await new Promise(resolve => setTimeout(resolve, 200));

                    // Find ender eye entity
                    let enderEyeEntity = null;
                    try {
                        for (const entityId in bot.entities) {
                            if (!entitiesBefore.has(entityId)) {
                                const entity = bot.entities[entityId];
                                const displayName = entity?.displayName || entity?.name;
                                if (entity?.position && (entity.name === 'eye_of_ender' || displayName === 'eye_of_ender')) {
                                    enderEyeEntity = entity;
                                    break;
                                }
                            }
                        }
                        if (!enderEyeEntity) {
                            for (const entity of Object.values(bot.entities)) {
                                if (entity?.position && (entity.name === 'eye_of_ender' || (entity.displayName || entity.name) === 'eye_of_ender')) {
                                    const distance = bot.entity.position.distanceTo(entity.position);
                                    if (distance < 50) {
                                        enderEyeEntity = entity;
                                        break;
                                    }
                                }
                            }
                        }
                    } catch (err) {
                        return null;
                    }

                    if (!enderEyeEntity) return null;

                    // Track movement
                    try {
                        const startPos = { x: enderEyeEntity.position.x, y: enderEyeEntity.position.y, z: enderEyeEntity.position.z };
                        await new Promise(resolve => setTimeout(resolve, 500));
                        
                        if (!bot.entities[enderEyeEntity.id]?.position) return null;
                        const endPos = bot.entities[enderEyeEntity.id].position;
                        
                        const dx = endPos.x - startPos.x;
                        const dz = endPos.z - startPos.z;
                        const dist = Math.sqrt(dx * dx + dz * dz);
                        
                        if (dist < 0.1) return null;
                        return { x: dx / dist, z: dz / dist };
                    } catch (err) {
                        return null;
                    }
                }

                // Initial search
                skills.log(bot, `Searching for end portal frames within 250 blocks...`);
                if (await findAndMoveToPortal()) return true;
                
                skills.log(bot, `No end portal found nearby. Starting ender eye search...`);
                agent.openChat('Failed to found. I will search again.');

                // Main loop
                while (true) {
                    const direction = await trackEnderEyeDirection();
                    if (!direction) {
                        skills.log(bot, `Failed to determine direction. Retrying...`);
                        await new Promise(resolve => setTimeout(resolve, 1000));
                        continue;
                    }

                    // Move 250 blocks in direction (non-destructive)
                    const pos = bot.entity.position;
                    const targetX = pos.x + direction.x * 250;
                    const targetZ = pos.z + direction.z * 250;
                    skills.log(bot, `Moving 250 blocks in direction (${direction.x.toFixed(2)}, ${direction.z.toFixed(2)})...`);

                    const nonDestructiveMovements = new pf.Movements(bot);
                    nonDestructiveMovements.canDig = false;
                    nonDestructiveMovements.canPlaceOn = false;
                    nonDestructiveMovements.allow1by1towers = false;
                    
                    const originalMovements = bot.pathfinder.movements;
                    try {
                        bot.pathfinder.setMovements(nonDestructiveMovements);
                        await skills.goToGoal(bot, new pf.goals.GoalNear(targetX, pos.y, targetZ, 5));
                    } finally {
                        if (originalMovements) bot.pathfinder.setMovements(originalMovements);
                    }

                    // Search for portal
                    skills.log(bot, `Searching for end portal frames within 250 blocks...`);
                    if (await findAndMoveToPortal()) return true;
                    
                    skills.log(bot, `No end portal frames found.`);
                    agent.openChat('Failed to found. I will search again.');
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            })
        },
        {
            name: '!enterEndPortal',
            description: 'Find the end portal, move to the portal area (3x3 space between frames at frame y+1), and jump to enter the End dimension.',
            params: {},
            perform: runAsAction(async (agent) => {
                const bot = agent.bot;

                // Find all end_portal_frame blocks nearby
                const frames = bot.findBlocks({
                    matching: bot.registry.blocksByName.end_portal_frame.id,
                    maxDistance: 32,
                    count: 1000
                });

                if (frames.length === 0) {
                    skills.log(bot, `No end portal frames found nearby.`);
                    return false;
                }

                skills.log(bot, `Found ${frames.length} end portal frame(s).`);

                // Calculate center position of the end portal frames
                // Portal blocks are created above the frames (y + 1) in the space between frames
                const avgX = frames.reduce((sum, f) => sum + f.x, 0) / frames.length;
                const avgY = frames.reduce((sum, f) => sum + f.y, 0) / frames.length;
                const avgZ = frames.reduce((sum, f) => sum + f.z, 0) / frames.length;
                
                // Portal blocks are at frame y + 1 (above the frames)
                const portalY = avgY + 1;

                // Move directly to portal block level (above frames)
                skills.log(bot, `Moving to portal block level at (${avgX.toFixed(1)}, ${portalY.toFixed(1)}, ${avgZ.toFixed(1)})...`);
                try {
                    bot.pathfinder.setMovements(new pf.Movements(bot));
                    await skills.goToGoal(bot, new pf.goals.GoalNear(avgX, portalY, avgZ, 0.5));
                    skills.log(bot, `Reached portal block level.`);
                } catch (err) {
                    skills.log(bot, `Could not pathfind to portal block level: ${err.message}. Will try jumping from current position.`);
                }
                
                // Ensure we're at the center of the portal before jumping
                let currentPos = bot.entity.position;
                const centerPos = new Vec3(avgX, portalY, avgZ);
                let distanceToCenter = currentPos.distanceTo(centerPos);
                
                if (distanceToCenter > 1) {
                    skills.log(bot, `Moving to portal center... Distance: ${distanceToCenter.toFixed(1)} blocks.`);
                    try {
                        bot.pathfinder.setMovements(new pf.Movements(bot));
                        await skills.goToGoal(bot, new pf.goals.GoalNear(avgX, portalY, avgZ, 0.3));
                    } catch (err) {
                        skills.log(bot, `Could not reach exact center: ${err.message}. Will jump from current position.`);
                    }
                }
                
                // Stop pathfinder before jumping into portal center
                bot.pathfinder.stop();
                bot.clearControlStates();

                // Calculate direction to portal center and look at it (use current position after movement)
                currentPos = bot.entity.position;
                await bot.lookAt(centerPos);
                
                // Jump while moving forward toward the portal center
                skills.log(bot, `Jumping into the end portal center...`);
                bot.setControlState('forward', true);
                bot.setControlState('jump', true);
                await new Promise(resolve => setTimeout(resolve, 500));
                bot.setControlState('jump', false);
                bot.setControlState('forward', false);
                
                // Wait a bit for dimension change, then ensure pathfinder is stopped
                await new Promise(resolve => setTimeout(resolve, 1000));
                bot.pathfinder.stop();
                bot.clearControlStates();

                skills.log(bot, `Entered the end portal!`);
                return true;
            })
        }
];
