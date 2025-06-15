import pytest
from scripts.api_dictionary_optimizer import APIDescriptionOptimizer

# A pytest fixture creates a reusable object for tests, avoiding repetitive setup.
@pytest.fixture
def optimizer_pt():
    """Returns a default optimizer instance for pt-BR."""
    return APIDescriptionOptimizer(language="pt-BR")

# --- Tests for Helper Methods ---

def test_detect_field_type(optimizer_pt):
    """Tests if field types are correctly detected from keys."""
    assert optimizer_pt._detect_field_type("api.v1.user.id.description") == "id"
    assert optimizer_pt._detect_field_type("api.v1.user.status.description") == "status"
    assert optimizer_pt._detect_field_type("api.v1.user.name.description") == "name"
    assert optimizer_pt._detect_field_type("api.v1.user.some_other_field.description") is None

def test_extract_entity_name(optimizer_pt):
    """Tests if the entity name is correctly extracted."""
    key = "api.doc.v1.user_profile.field.description"
    assert optimizer_pt._extract_entity_name(key) == "user profile"

def test_finalize_description(optimizer_pt):
    """Tests the final formatting steps like capitalization and punctuation."""
    assert optimizer_pt._finalize_description("test message") == "Test message."
    assert optimizer_pt._finalize_description("Test message with period.") == "Test message with period."
    assert optimizer_pt._finalize_description("") == ""

# --- Tests for Strategy Methods ---

@pytest.mark.parametrize("original, expected", [
    # It should preserve an already good description
    ("ID da visita", "ID da visita"),
    # It should apply the generic pattern to a vague description
    ("Identificador da visita", "ID único do(a) visita"),
])
def test_strategy_optimize_id(optimizer_pt, original, expected):
    """Tests the intelligent ID optimization strategy."""
    # Mock field_patterns for consistent testing
    optimizer_pt.field_patterns['id'] = "ID único do(a) {entity}"
    assert optimizer_pt._optimize_id_description(original, "visita") == expected

def test_strategy_optimize_status(optimizer_pt):
    """Tests the parsing of complex status descriptions."""
    original = "Status da Justificativa. Valores retornados: 0 (Pendente), 1 (Aprovada) e 2 (Reprovada)."
    expected = "Status da Justificativa: 0 = Pendente, 1 = Aprovada, 2 = Reprovada"
    assert optimizer_pt._optimize_status_description(original, "justificativa") == expected

def test_strategy_optimize_list(optimizer_pt):
    """Tests the simplification of list descriptions."""
    original = "Retorna uma lista paginada de usuários"
    expected = "Lista de usuários"
    assert optimizer_pt._optimize_list_description(original, "usuários") == expected
