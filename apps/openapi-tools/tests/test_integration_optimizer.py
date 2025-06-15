import pytest
import json
from scripts.api_dictionary_optimizer import APIDescriptionOptimizer

@pytest.fixture
def optimizer_pt():
    """Returns a default optimizer instance for pt-BR."""
    # For integration tests, it's good to provide a mock rule set
    # to avoid dependency on the actual file system.
    optimizer = APIDescriptionOptimizer(language="pt-BR")
    optimizer.rules = {
        "redundant_phrases": [["^Retorna uma lista de ", ""]],
        "field_patterns": {"id": "ID genérico de {entity}"}
    }
    optimizer._compile_patterns() # Re-compile mock rules
    return optimizer

def test_full_pipeline_produces_correct_final_string(optimizer_pt):
    """
    Tests the main public method 'optimize_description' to ensure the full
    pipeline (strategy + generic cleanups) works together.
    """
    key = "api.v1.users.list.description"
    original_value = "Retorna uma lista de usuários"

    # Expected value after prefix removal, capitalization, and period addition.
    expected_final_value = "Usuários."

    assert optimizer_pt.optimize_description(key, original_value) == expected_final_value

def test_full_pipeline_preserves_specific_id(optimizer_pt):
    """
    Tests that the 'id' strategy correctly preserves a good value
    even when run through the full pipeline.
    """
    key = "api.v1.visit.id.description"
    original_value = "ID da visita"

    # The finalizer will capitalize and add a period, but the core text is preserved.
    expected_final_value = "ID da visita."

    assert optimizer_pt.optimize_description(key, original_value) == expected_final_value

def test_optimizer_loads_and_uses_real_json_rule(tmp_path):
    """
    Tests that the optimizer correctly loads a rule from a specified
    JSON file and uses it.
    """
    # pytest's tmp_path fixture provides a temporary directory for tests
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    rule_file = rules_dir / "xx-TEST.json"

    # Create a dummy rule file
    test_rules = {
        "term_mappings": {"specific test word": "optimized word"}
    }
    rule_file.write_text(json.dumps(test_rules))

    # Initialize optimizer with our temporary rules
    optimizer = APIDescriptionOptimizer(language="xx-TEST", rules_dir=rules_dir)

    original = "this is a specific test word"
    expected = "This is a optimized word." # Note capitalization and period

    assert optimizer.optimize_description("some.key", original) == expected
