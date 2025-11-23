import * as Mindcraft from './src/mindcraft/mindcraft.js';
import settings from './settings.js';
import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';
import { readFileSync } from 'fs';
import { spawn } from 'child_process';
import path from 'path';

/**
 * Run mc-plan main.py to generate crafting recipes and sequences
 * @param {string} target - Target item to build recipe tree and sequence for
 * @param {number} needAmount - Amount of target item needed (default: 1)
 * @param {string} mode - Mode of operation - 'buffered' or 'exact' (default: 'buffered')
 * @returns {Promise<{success: boolean, output: string, error?: string}>}
 */
function runMcPlan(target, needAmount = 1, mode = 'buffered') {
    return new Promise((resolve, reject) => {
        const mcPlanDir = path.join(process.cwd(), 'mc-plan');
        const pythonScript = path.join(mcPlanDir, 'main.py');

        const args = [
            pythonScript,
            '--target', target,
            '--need_amount', needAmount.toString(),
            '--mode', mode
        ];

        console.log(`Running mc-plan for target: ${target}, need_amount: ${needAmount}, mode: ${mode}`);

        const pythonProcess = spawn('python', args, {
            cwd: mcPlanDir,
            stdio: ['ignore', 'pipe', 'pipe']
        });

        let output = '';
        let errorOutput = '';

        pythonProcess.stdout.on('data', (data) => {
            const message = data.toString();
            output += message;
            console.log(`[mc-plan]: ${message.trim()}`);
        });

        pythonProcess.stderr.on('data', (data) => {
            const message = data.toString();
            errorOutput += message;
            console.error(`[mc-plan error]: ${message.trim()}`);
        });

        pythonProcess.on('close', (code) => {
            if (code === 0) {
                console.log('mc-plan completed successfully');
                resolve({
                    success: true,
                    output: output
                });
            } else {
                console.error(`mc-plan exited with code ${code}`);
                resolve({
                    success: false,
                    output: output,
                    error: errorOutput || `Process exited with code ${code}`
                });
            }
        });

        pythonProcess.on('error', (err) => {
            console.error('Failed to start mc-plan:', err);
            reject({
                success: false,
                error: err.message
            });
        });
    });
}

function parseArguments() {
    return yargs(hideBin(process.argv))
        .option('profiles', {
            type: 'array',
            describe: 'List of agent profile paths',
        })
        .option('task_path', {
            type: 'string',
            describe: 'Path to task file to execute'
        })
        .option('task_id', {
            type: 'string',
            describe: 'Task ID to execute'
        })
        .help()
        .alias('help', 'h')
        .parse();
}

const args = parseArguments();
if (args.profiles) {
    settings.profiles = args.profiles;
}
if (args.task_path) {
    let tasks = JSON.parse(readFileSync(args.task_path, 'utf8'));
    if (args.task_id) {
        settings.task = tasks[args.task_id];
        settings.task.task_id = args.task_id;
    }
    else {
        throw new Error('task_id is required when task_path is provided');
    }
}

await runMcPlan("ender_eye", 1, "exact");

// these environment variables override certain settings
if (process.env.MINECRAFT_PORT) {
    settings.port = process.env.MINECRAFT_PORT;
}
if (process.env.MINDSERVER_PORT) {
    settings.mindserver_port = process.env.MINDSERVER_PORT;
}
if (process.env.PROFILES && JSON.parse(process.env.PROFILES).length > 0) {
    settings.profiles = JSON.parse(process.env.PROFILES);
}
if (process.env.INSECURE_CODING) {
    settings.allow_insecure_coding = true;
}
if (process.env.BLOCKED_ACTIONS) {
    settings.blocked_actions = JSON.parse(process.env.BLOCKED_ACTIONS);
}
if (process.env.MAX_MESSAGES) {
    settings.max_messages = process.env.MAX_MESSAGES;
}
if (process.env.NUM_EXAMPLES) {
    settings.num_examples = process.env.NUM_EXAMPLES;
}
if (process.env.LOG_ALL) {
    settings.log_all_prompts = process.env.LOG_ALL;
}

Mindcraft.init(false, settings.mindserver_port, settings.auto_open_ui);

for (let profile of settings.profiles) {
    const profile_json = JSON.parse(readFileSync(profile, 'utf8'));
    settings.profile = profile_json;
    Mindcraft.createAgent(settings);
}

// Export the function for use in other modules
export { runMcPlan };
