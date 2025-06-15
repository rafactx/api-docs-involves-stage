#!/usr/bin/env python3
"""
API Dictionary Optimizer - Turns verbose API descriptions into dev-friendly texts.
Enterprise-grade, extensible, multi-language and strategy-based.

Author: github.com/rafactx
"""
import json
import re
import logging
from typing import Dict, Optional, Callable, Tuple
from pathlib import Path
from collections import defaultdict

# Absolute import from within the package
from .constants import StatKeys

# ===================================================================
# 1. CORE LOGIC CLASS
# ===================================================================

class APIDescriptionOptimizer:
    """
    Main optimizer class. It orchestrates the loading of language-specific rules
    and applies a pipeline of optimizations to text descriptions.
    """

    # --- 1.1. Initialization & Setup ---

    def __init__(self, language: str, rules_dir: Path, verbose: bool = False):
        """
        Initializes the optimizer for a specific language.

        Args:
            language: The target language for the rules (e.g., 'pt-BR').
            rules_dir: The absolute path to the directory containing rule files.
            verbose: Enables detailed logging if True.
        """
        self.language = language
        self.rules_dir = rules_dir
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)

        # Load, compile, and register all rules and strategies upon instantiation.
        self.rules = self._load_rules()
        self._compile_patterns()
        self._setup_field_optimizers()

    def _load_rules(self) -> Dict:
        """Loads language-specific rules from the configured rules directory."""
        rules_path = self.rules_dir / f"{self.language}.json"
        if not rules_path.exists():
            self.logger.warning(f"Rules file for '{self.language}' not found at {rules_path}. Using empty rules.")
            return {}
        with open(rules_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _compile_patterns(self):
        """Pre-compiles regex patterns from the loaded rules for high performance."""
        self.redundant_phrases = [(re.compile(p, re.IGNORECASE), r) for p, r in self.rules.get("redundant_phrases", [])]
        self.formatting_patterns = [(re.compile(p), r) for p, r in self.rules.get("formatting_patterns", [])]
        self.term_mappings = self.rules.get("term_mappings", {})
        self.field_patterns = self.rules.get("field_patterns", {})
        self.contractions = [(re.compile(p), r) for p, r in self.rules.get("contractions", [])]
        self.success_patterns = self.rules.get("success_message_patterns", {})

    # --- 1.2. Optimization Strategies (Strategy Pattern) ---
    # Each method handles a specific 'field_type' for targeted optimization.
    # They are registered in the dispatcher below.

    def _optimize_id_description(self, value: str, entity_info: Tuple[str, str]) -> str:
        """Intelligently optimizes 'id' fields by preserving already good descriptions."""
        _, entity_display_name = entity_info
        if 'ID' in value:
            return value
        # Fallback to the generic pattern from the rules file
        if 'id' in self.field_patterns:
            return self.field_patterns['id'].format(entity=entity_display_name)
        return value

    def _optimize_name_description(self, value: str, entity_info: Tuple[str, str]) -> str:
        """Intelligently optimizes 'name' fields, handling grammatical articles for pt-BR."""
        raw_entity_key, entity_display_name = entity_info
        entity_rules = self.rules.get("entity_optimizations", {}).get(raw_entity_key, {})
        article = entity_rules.get("article")

        # Only applies this special logic if an article is defined in the rules for pt-BR
        if article and self.language == 'pt-BR':
            contraction = "do" if article == "o" else "da"
            return f"Nome {contraction} {entity_display_name}"

        # Fallback to the generic pattern for other cases
        generic_pattern = self.field_patterns.get('name', "Name of {entity}")
        return generic_pattern.format(entity=entity_display_name)

    def _optimize_ok_message(self, value: str, entity_info: Tuple[str, str]) -> str:
        """Simplifies success messages with proper grammatical agreement for gender and number."""
        raw_entity_key, _ = entity_info
        value_lower = value.lower()

        action_map = {
            "retrieved": ["retornado com sucesso", "retornada com sucesso"],
            "created": ["salvo com sucesso", "salva com sucesso"],
            "updated": ["editado com sucesso", "editada com sucesso"],
            "removed": ["excluído com sucesso", "excluída com sucesso"],
        }
        current_action = next((action for action, triggers in action_map.items() if any(trigger in value_lower for trigger in triggers)), None)

        if not current_action:
            return value

        # For simple actions, we can just return the pattern from the rules file
        if current_action != "retrieved":
            return self.success_patterns.get(current_action, value)

        # For 'retrieved', apply the complex grammar logic
        subject_match = re.search(r'^(.+?)\s+(?:retornad)[oa]', value, re.IGNORECASE)
        subject = subject_match.group(1).strip() if subject_match and subject_match.group(1) else ""

        if not subject:
            return value

        entity_rules = self.rules.get("entity_optimizations", {}).get(raw_entity_key, {})
        gender = entity_rules.get("gender", "m") # Default to masculine
        is_plural = subject.lower().endswith('s')

        # Start with the base adjective (masculine singular)
        adjective = "recuperado"

        # 1. Adjust for feminine gender
        if gender == 'f':
            adjective = adjective[:-1] + 'a'

        # 2. Adjust for plural
        if is_plural:
            adjective += 's'

        return f"{subject.capitalize()} {adjective} com sucesso"

    def _setup_field_optimizers(self):
        """Sets up the dispatcher to register all optimization strategies."""
        self.field_optimizers: Dict[str, Callable[[str, Tuple[str, str]], str]] = {
            'id': self._optimize_id_description,
            'name': self._optimize_name_description,
            'ok': self._optimize_ok_message,
        }

    # --- 1.3. Main Optimization Pipeline & Helpers ---

    def optimize_description(self, key: str, value: str) -> str:
        """
        Orchestrates the optimization of a single description string.
        This is the main public method for a single-item optimization.
        """
        if not value or not isinstance(value, str):
            return value

        field_type = self._detect_field_type(key)
        raw_entity_key, entity_display_name = self._extract_entity_name(key)

        # 1. Apply advanced strategy via dispatcher if available
        if field_type and field_type in self.field_optimizers:
            value = self.field_optimizers[field_type](value, (raw_entity_key, entity_display_name))
        # 2. Apply simple pattern-based optimization as a fallback
        elif field_type and field_type in self.field_patterns:
            value = self.field_patterns[field_type].format(entity=entity_display_name)

        # 3. Apply generic pipeline of optimizations
        value = self._apply_generic_optimizations(value)
        return value

    def _apply_generic_optimizations(self, value: str) -> str:
        """Applies a sequence of general-purpose text optimizations."""
        for pattern, repl in self.redundant_phrases:
            value = pattern.sub(repl, value)
        for verbose, concise in self.term_mappings.items():
            value = value.replace(verbose, concise)
        for pattern, repl in self.formatting_patterns:
            value = pattern.sub(repl, value)
        value = self._apply_contractions(value)
        value = self._clean_description(value)
        value = self._finalize_description(value)
        return value

    def _detect_field_type(self, key: str) -> Optional[str]:
        """Detects field type from the key string based on naming conventions."""
        key_lower = key.lower()
        patterns = {
            'id': r'\.id\.description$',
            'name': r'\.name\.description$',
            'ok': r'-ok\.description$',
        }
        for field_type, pattern in patterns.items():
            if re.search(pattern, key_lower):
                return field_type
        return None

    def _extract_entity_name(self, key: str) -> Tuple[str, str]:
        """
        Extracts the raw entity key and a formatted, human-readable name.
        Returns: A tuple of (raw_entity_key, display_name).
        """
        parts = key.split('.')
        if len(parts) < 4:
            return "", ""

        raw_entity = parts[3]
        entity_optimizations = self.rules.get("entity_optimizations", {})
        if raw_entity in entity_optimizations:
            display_name = entity_optimizations[raw_entity].get("name", raw_entity)
            return raw_entity, display_name

        # Fallback: convert camelCase/PascalCase to separate words
        human_readable_entity = re.sub(r'(?<!^)(?=[A-Z])', ' ', raw_entity).lower()
        return raw_entity, human_readable_entity.replace('_', ' ').replace('-', ' ')

    def _extract_entity_from_success_message(self, msg: str) -> str:
        """Extracts the subject from a Portuguese success message."""
        match = re.search(r'^(.+?)\s+(?:retornad|salv|editad|excluíd)[oa]', msg, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _apply_contractions(self, value: str) -> str:
        """Applies language-specific contractions from the rules file."""
        for pattern, repl in self.contractions:
            value = pattern.sub(repl, value)
        return value

    def _clean_description(self, value: str) -> str:
        """Removes extra whitespace and fixes common punctuation issues."""
        value = re.sub(r'\s+', ' ', value).strip()
        value = re.sub(r'\s+([,.!?:;])', r'\1', value)
        value = re.sub(r'\.+', '.', value)
        return value

    def _finalize_description(self, value: str) -> str:
        """Ensures proper capitalization and a final punctuation mark."""
        if not value:
            return value
        value = value[0].upper() + value[1:]
        if value and value[-1] not in '.!?:':
            value += '.'
        return value

    # --- 1.4. File Processing ---

    def optimize_file(self, input_path: Path, output_path: Optional[Path] = None) -> Tuple[Dict, Dict[str, int]]:
        """
        Optimizes a full JSON file and returns the optimized data and stats.
        This method is stateless and driven by the orchestrator.
        """
        self.logger.info(f"Processing file: {input_path}")
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        optimized_content = {}
        stats = defaultdict(int)

        # The input data is always in Portuguese
        for key, value in data.items():
            original_value = str(value) # Ensure value is a string
            optimized_value = self.optimize_description(key, original_value)
            optimized_content[key] = optimized_value

            if optimized_value != original_value:
                stats[StatKeys.OPTIMIZED] += 1
                stats[StatKeys.CHARS_SAVED] += len(original_value) - len(optimized_value)

        stats[StatKeys.TOTAL] = len(data)

        output_path = output_path or (input_path.parent / f"{input_path.stem}.optimized.json")

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(optimized_content, f, ensure_ascii=False, indent=2)

        self.logger.info(f"Optimized file written to: {output_path}")
        return optimized_content, stats
