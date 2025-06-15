#!/usr/bin/env python3
"""
OpenAPI Fixer and Translator - Enhanced Version

This script reads a base OpenAPI file with translation keys,
and uses the optimized dictionaries to generate fully-translated
and corrected OpenAPI specifications for multiple languages.
"""
import yaml
import json
import re
import argparse
from pathlib import Path
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import copy
from collections import defaultdict

# ===================================================================
# 1. SCRIPT CONFIGURATION
# ===================================================================
# Global constants defining default paths and behavior.
# These can be overridden by command-line arguments.

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_INPUT_OPENAPI_PATH = BASE_DIR / "openapi.yaml"
DEFAULT_DICTIONARY_DIR = BASE_DIR / "locales" / "optimized"
DEFAULT_OUTPUT_DIR = BASE_DIR / "dist"

# Default 'info' object structure to ensure the OpenAPI file is valid.
# The values are translation keys to be resolved by the dictionaries.
DEFAULT_INFO_OBJECT = {
    "title": "api.doc.general.title",
    "description": "api.doc.general.description",
    "version": "1.0.0",
    "contact": {
        "name": "api.doc.general.contact.name",
        "email": "api.doc.general.contact.email"
    },
    "license": {
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html"
    }
}

# Defines which fields across the OpenAPI spec should be targeted for translation.
TRANSLATABLE_FIELDS = {'description', 'summary', 'title', 'name'}

# Configure a global logger for consistent output.
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# ===================================================================
# 2. HELPER CLASSES
# ===================================================================

class TranslationStats:
    """A simple class to track statistics during the translation process."""
    def __init__(self):
        self.total_keys = 0
        self.translated_keys = 0
        self.missing_keys: set[str] = set()
        self.errors: list[str] = []

    def add_translation(self, key: str, found: bool):
        """Records a translation attempt."""
        self.total_keys += 1
        if found:
            self.translated_keys += 1
        else:
            self.missing_keys.add(key)

    def add_error(self, error: str):
        """Records a processing error."""
        self.errors.append(error)

    def get_summary(self) -> Dict[str, Any]:
        """Returns a dictionary summary of the translation statistics."""
        return {
            'total_keys': self.total_keys,
            'translated_keys': self.translated_keys,
            'missing_keys_count': len(self.missing_keys),
            'translation_rate': f"{(self.translated_keys/self.total_keys*100):.1f}%" if self.total_keys > 0 else "0%",
            'errors': len(self.errors)
        }


# ===================================================================
# 3. CORE LOGIC CLASS
# ===================================================================

class OpenApiFixer:
    """
    Orchestrates the entire process of loading, fixing, translating,
    and saving the OpenAPI specification.
    """

    def __init__(self, language: str, dictionary: Dict[str, str], openapi_path: Path, output_dir: Path):
        """
        Initializes the fixer for a specific language.

        Args:
            language: The target language code (e.g., 'pt-BR').
            dictionary: The loaded dictionary with translations for the language.
            openapi_path: Path to the base OpenAPI file.
            output_dir: Path to the directory where results will be saved.
        """
        self.language = language
        self.dictionary = dictionary
        self.openapi_path = openapi_path
        self.output_dir = output_dir
        self.backup_dir = self.output_dir / "backup"
        self.stats = TranslationStats()
        self.openapi_data: Optional[Dict[str, Any]] = None
        self.original_data: Optional[Dict[str, Any]] = None

    def load_openapi(self) -> bool:
        """Loads and parses the base OpenAPI YAML file, handling potential errors."""
        try:
            logger.info(f"Loading base OpenAPI file from: {self.openapi_path}")
            with open(self.openapi_path, 'r', encoding='utf-8') as f:
                self.openapi_data = yaml.safe_load(f)
                self.original_data = copy.deepcopy(self.openapi_data)
            return True
        except FileNotFoundError:
            self.stats.add_error(f"File not found: {self.openapi_path}")
            return False
        except yaml.YAMLError as e:
            self.stats.add_error(f"YAML parsing error: {e}")
            return False
        return False

    def get_translation(self, key: str, context: Optional[str] = None) -> str:
        """
        Retrieves a translation for a given key from the dictionary.
        If the key is not found, it logs a warning and returns the key itself.
        """
        if key in self.dictionary:
            self.stats.add_translation(key, True)
            return self.dictionary[key]

        self.stats.add_translation(key, False)
        logger.warning(f"Missing translation for key: '{key}'" + (f" (context: {context})" if context else ""))
        return key

    def _recursive_translate(self, data: Any):
        """Recursively traverses the OpenAPI data structure to find and translate keys."""
        if isinstance(data, dict):
            for key, value in data.items():
                # If the key is a known translatable field and the value is a key...
                if key in TRANSLATABLE_FIELDS and isinstance(value, str) and value.startswith("api.doc."):
                    data[key] = self.get_translation(value, key)
                # Otherwise, continue traversing deeper into the structure.
                else:
                    self._recursive_translate(value)
        elif isinstance(data, list):
            for item in data:
                self._recursive_translate(item)

    def fix_and_translate(self) -> bool:
        """Runs the main pipeline of fixes and translations on the loaded data."""
        logger.info(f"Applying fixes and translating to {self.language.upper()}...")
        if not self.load_openapi():
            return False

        # This guard clause ensures self.openapi_data is not None from this point forward,
        # satisfying the type checker and preventing potential runtime errors.
        if self.openapi_data is None:
            self.stats.add_error("Internal failure: OpenAPI data is None after a seemingly successful load.")
            logger.error("Could not proceed because OpenAPI data is None.")
            return False

        try:
            # 1. Ensure 'info' object exists and is populated/translated
            if "info" not in self.openapi_data:
                self.openapi_data["info"] = {}
            info = self.openapi_data["info"]
            for key, default_value in DEFAULT_INFO_OBJECT.items():
                if key not in info:
                    info[key] = default_value
            self._recursive_translate(info)

            # 2. Translate tags
            if "tags" in self.openapi_data:
                for tag in self.openapi_data["tags"]:
                    if "name" in tag and isinstance(tag["name"], str) and tag["name"].startswith("api.doc."):
                         # Use the same key for both name and description for simplicity
                         translated_name = self.get_translation(tag["name"], "tag.name")
                         tag["name"] = translated_name
                         tag["description"] = translated_name

            # 3. Recursively translate the rest of the document
            self._recursive_translate(self.openapi_data)
            return True
        except Exception as e:
            self.stats.add_error(f"Processing error: {e}")
            logger.error(f"An unexpected error occurred during processing: {e}")
            return False

    def save_output(self, create_backup: bool = True):
        """Saves the processed OpenAPI file and a summary report."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            if create_backup:
                self._create_backup()

            output_path = self.output_dir / f"openapi_{self.language}.yaml"
            logger.info(f"Saving translated OpenAPI to: {output_path}")
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.openapi_data, f, allow_unicode=True, sort_keys=False, width=1000)

            self._save_translation_report()
            logger.info("✓ File and report saved successfully.")
        except Exception as e:
            self.stats.add_error(f"Save error: {e}")
            logger.error(f"Error saving output: {e}")

    def _create_backup(self):
        """Creates a timestamped backup of the original OpenAPI file."""
        if not self.original_data: return
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"openapi_original_{timestamp}.yaml"
        with open(backup_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.original_data, f, allow_unicode=True, sort_keys=False)
        logger.info(f"Backup of original file saved to: {backup_path}")

    def _save_translation_report(self):
        """Saves a JSON report detailing the translation process results."""
        report_path = self.output_dir / f"translation_report_{self.language}.json"
        report = {
            "language": self.language,
            "timestamp": datetime.now().isoformat(),
            "statistics": self.stats.get_summary(),
            "missing_keys": sorted(list(self.stats.missing_keys)),
            "errors": self.stats.errors
        }
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)


# ===================================================================
# 4. WORKFLOW ORCHESTRATION
# ===================================================================

def process_all_languages(languages_to_process: Optional[List[str]], input_path: Path, dict_dir: Path, output_dir: Path, no_backup: bool):
    """Processes the OpenAPI file for all specified or available languages."""
    if not dict_dir.exists():
        logger.error(f"Dictionary directory not found: {dict_dir}")
        return

    available_languages = [f.stem for f in dict_dir.glob("*.json")]
    if not languages_to_process:
        languages_to_process = available_languages

    results = {}
    for lang in languages_to_process:
        if lang not in available_languages:
            logger.warning(f"No dictionary found for language '{lang}', skipping.")
            continue

        logger.info(f"\n{'='*25} Processing language: {lang.upper()} {'='*25}")
        dict_file = dict_dir / f"{lang}.json"
        with open(dict_file, 'r', encoding='utf-8') as f:
            dictionary = json.load(f)

        fixer = OpenApiFixer(lang, dictionary, input_path, output_dir)
        if fixer.fix_and_translate():
            fixer.save_output(create_backup=not no_backup)

        results[lang] = fixer.stats.get_summary()

    # Final Summary Report
    logger.info(f"\n{'='*28} FINAL SUMMARY {'='*29}")
    successful = sum(1 for r in results.values() if not r['errors'])
    logger.info(f"Successfully processed {successful}/{len(results)} languages.")
    for lang, summary in results.items():
        logger.info(f"-> {lang}: {summary['translation_rate']} translated, {summary['missing_keys_count']} missing keys, {summary['errors']} errors.")


# ===================================================================
# 5. COMMAND-LINE INTERFACE (CLI) ENTRY POINT
# ===================================================================

def main():
    """Defines and parses command-line arguments to run the script."""
    parser = argparse.ArgumentParser(description="Fix and translate OpenAPI specifications.")
    parser.add_argument('-l', '--languages', nargs='+', help='Specific languages to process (e.g., pt-BR en-US).')
    parser.add_argument('-i', '--input', type=Path, default=DEFAULT_INPUT_OPENAPI_PATH, help='Custom input OpenAPI file path.')
    parser.add_argument('-d', '--dictionaries', type=Path, default=DEFAULT_DICTIONARY_DIR, help='Custom dictionaries directory path.')
    parser.add_argument('-o', '--output', type=Path, default=DEFAULT_OUTPUT_DIR, help='Custom output directory path.')
    parser.add_argument('--no-backup', action='store_true', help='Skip creating a backup of the original OpenAPI file.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose (DEBUG) logging.')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    process_all_languages(args.languages, args.input, args.dictionaries, args.output, args.no_backup)


if __name__ == "__main__":
    main()
