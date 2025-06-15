#!/usr/bin/env python3
"""
Workflow Manager for API Dictionary Optimization

This script serves as the main entry point to run the optimization workflow.
It supports both interactive and command-line execution for single or multiple
languages, creating a robust and developer-friendly process.

Author: github.com/rafactx
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional

# ===================================================================
# 1. SCRIPT CONFIGURATION
# ===================================================================

# --- 1.1. Module Imports ---
# Absolute imports work because the project is installed in editable mode.
from optimizer.api_dictionary_optimizer import APIDescriptionOptimizer
from optimizer.constants import StatKeys

# --- 1.2. Path Definitions ---
# All paths are relative to the project root for robustness.
# Assumes the script is run from the root of 'apps/openapi-tools'.
PROJECT_ROOT = Path.cwd()
INPUT_DIR = PROJECT_ROOT / "locales" / "original"
OUTPUT_ROOT = PROJECT_ROOT / "locales" / "optimized"
RULES_DIR = PROJECT_ROOT / "rules"  # Central location for all rule files

# --- 1.3. Language and Logging Setup ---
SUPPORTED_LANGUAGES = {
    "pt-BR": "🇧🇷", "en-US": "🇺🇸", "es-ES": "🇪🇸", "fr-FR": "🇫🇷",
}
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


# ===================================================================
# 2. CORE WORKFLOW LOGIC
# ===================================================================

def ask_for_language() -> str:
    """Prompts the user to interactively select a language."""
    logger.info("🌐 Please select a language to process:")
    lang_list = list(SUPPORTED_LANGUAGES.keys())
    for idx, lang in enumerate(lang_list, 1):
        flag = SUPPORTED_LANGUAGES[lang]
        print(f"  {idx}. {flag}  {lang}")

    while True:
        try:
            choice = input("Choose a language by name or number: ").strip()
            if choice in lang_list:
                return choice
            if choice.isdigit() and 1 <= int(choice) <= len(lang_list):
                return lang_list[int(choice) - 1]
            logger.warning("❌ Invalid input. Please try again.")
        except (KeyboardInterrupt, EOFError):
            logger.info("\nOperation cancelled by user.")
            sys.exit(0)


def process_language(language: str):
    """Runs the optimization process for a single language."""
    flag = SUPPORTED_LANGUAGES.get(language, "🏳️")
    logger.info(f"\n🚀 Starting process for language: {flag} {language}")

    output_dir = OUTPUT_ROOT / language
    output_dir.mkdir(parents=True, exist_ok=True)

    json_files = sorted([f for f in INPUT_DIR.glob("*.json") if f.is_file()])
    if not json_files:
        logger.error(f"❌ No JSON files found in the input directory: {INPUT_DIR}")
        return

    logger.info(f"🔎 Found {len(json_files)} file(s) to optimize.")

    # ### CORREÇÃO ###
    # Pass the RULES_DIR directly to the optimizer instance as required.
    optimizer = APIDescriptionOptimizer(language=language, rules_dir=RULES_DIR)

    total_stats = {key: 0 for key in StatKeys.__dict__ if not key.startswith('__')}

    for file_path in json_files:
        try:
            _, stats = optimizer.optimize_file(file_path, output_dir / file_path.name)
            for key, value in stats.items():
                if key in total_stats:
                    total_stats[key] += value

            optimized_count = stats.get(StatKeys.OPTIMIZED, 0)
            logger.info(f"  ✅ {file_path.name} processed ({optimized_count} changes).")

        except Exception as e:
            logger.error(f"  ❌ [FAIL] Could not process {file_path.name}. Reason: {e}")

    # --- Summary Report ---
    logger.info("\n📊" + ("-" * 20) + f" Summary for {flag} {language} " + ("-" * 20))
    total = total_stats.get(StatKeys.TOTAL, 0)
    optimized = total_stats.get(StatKeys.OPTIMIZED, 0)
    saved = total_stats.get(StatKeys.CHARS_SAVED, 0)

    logger.info(f" │ Files processed: {len(json_files)}")
    logger.info(f" │ Total descriptions: {total}")
    logger.info(f" │ Descriptions optimized: {optimized}")
    logger.info(f" │ Characters saved: {saved}")

    if total > 0:
        logger.info(f" │ Optimization rate: {(100 * optimized / total):.1f}%")
    if optimized > 0:
        logger.info(f" │ Avg. reduction: {saved / optimized:.1f} chars/description")

    logger.info("-" * (43 + len(language)))
    logger.info(f"📦 Optimized files available in: {output_dir.resolve()}")


# ===================================================================
# 3. COMMAND-LINE INTERFACE (CLI) ENTRY POINT
# ===================================================================

def main():
    """Defines and parses command-line arguments to run the script."""
    parser = argparse.ArgumentParser(
        description="Workflow Manager for API Dictionary Optimization.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    lang_flags = {lang.split('-')[0]: lang for lang in SUPPORTED_LANGUAGES}

    for short, long in lang_flags.items():
        parser.add_argument(f"--{short}", action="store_true", help=f"Run optimizer for {long}.")
    parser.add_argument("--all", action="store_true", help="Run optimizer for ALL supported languages.")

    args = parser.parse_args()

    # Determine which languages to run based on CLI flags or user interaction
    languages_to_run: List[str] = []
    if args.all:
        languages_to_run = list(SUPPORTED_LANGUAGES.keys())
    else:
        for short, long in lang_flags.items():
            if getattr(args, short):
                languages_to_run.append(long)

    if not languages_to_run:
        languages_to_run.append(ask_for_language())

    # Pre-flight check for required directories
    if not INPUT_DIR.exists():
        logger.error(f"❌ Input directory not found: {INPUT_DIR}")
        sys.exit(1)
    if not RULES_DIR.exists():
        logger.error(f"❌ Rules directory not found: {RULES_DIR}")
        sys.exit(1)

    # Run the main processing loop
    for lang in languages_to_run:
        process_language(lang)

    logger.info("\n✨ Workflow finished successfully! ✨")


if __name__ == "__main__":
    main()
