from craft_or_smelt.extract_recipes import create_recipes
from build_extended_recipe import build_extended_recipe
from build_recipe_seq import build_sequence_with_need
from planner import plan_all_items

import argparse
from math import ceil

def argument_parser():
    # Create argument parser
    parser = argparse.ArgumentParser(
        description="Build extended recipe and need-amount sequence"
    )

    # Add target argument
    parser.add_argument(
        "--target",
        type=str,
        required=True,
        help="Target item to build recipe tree and sequence for"
    )
    parser.add_argument(
        "--need_amount",
        type=int,
        default=1,
        help="Amount of target item needed (default: 1)"
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="buffered",
        help="Mode of operation - buffered or exact (default: buffered)"
    )

    return parser


if __name__ == "__main__":
    parser = argument_parser()
    arg = parser.parse_args()

    root_amount = int(ceil(1.2 * arg.need_amount)) if arg.mode == "buffered" else arg.need_amount

    print("Creating recipes...")
    create_recipes()
    build_extended_recipe(target=arg.target)
    print("Building sequence...")
    build_sequence_with_need(root_target=arg.target, root_amount=root_amount)
    print("Planning all items...")
    plan_all_items()
    print("Done.")