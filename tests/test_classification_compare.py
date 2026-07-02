"""Comparação canônica Purity × LLM (EVOLUTION_PLAN.md, VAL-1 e VAL-9).

Regressão do defeito VAL-1: o analisador comparava a classificação do LLM
(PURE/FLOSS) com os literais 'TRUE'/'FALSE' do Purity Checker, de modo que
NENHUM par jamais contava como concordância — a métrica-alvo da pesquisa
reportava 0 agree em toda sessão. A fonte única `compare_purity_llm` aplica
o mapeamento semântico TRUE↔PURE / FALSE↔FLOSS (o mesmo da view SQL
`model_metrics`) e trata vereditos ausentes como NOT_COMPARABLE.
"""

import pytest

from src.utils.classification import (
    AGREE,
    DISAGREE,
    NOT_COMPARABLE,
    compare_purity_llm,
    summarize_convergence,
)


class TestComparePurityLlm:
    @pytest.mark.parametrize(
        ("purity", "llm", "expected"),
        [
            # Núcleo semântico: TRUE↔PURE, FALSE↔FLOSS
            ("TRUE", "PURE", AGREE),
            ("TRUE", "FLOSS", DISAGREE),
            ("FALSE", "FLOSS", AGREE),
            ("FALSE", "PURE", DISAGREE),
            # Regressão VAL-1: os pares que o código antigo marcava como
            # 'agree' eram impossíveis (llm nunca vale 'TRUE'/'FALSE')
            ("TRUE", "TRUE", NOT_COMPARABLE),
            ("FALSE", "FALSE", NOT_COMPARABLE),
            # Purity sem veredito nunca conta como (dis)cordância
            ("None", "PURE", NOT_COMPARABLE),
            ("NONE", "FLOSS", NOT_COMPARABLE),
            (None, "PURE", NOT_COMPARABLE),
            ("", "FLOSS", NOT_COMPARABLE),
            ("not_in_purity", "PURE", NOT_COMPARABLE),
            # LLM sem veredito idem
            ("TRUE", "FAILED", NOT_COMPARABLE),
            ("FALSE", "ERROR", NOT_COMPARABLE),
            ("TRUE", "DRY_RUN", NOT_COMPARABLE),
            ("FALSE", "not_analyzed", NOT_COMPARABLE),
            ("TRUE", None, NOT_COMPARABLE),
            ("TRUE", "", NOT_COMPARABLE),
        ],
    )
    def test_matrix(self, purity, llm, expected):
        assert compare_purity_llm(purity, llm) == expected

    @pytest.mark.parametrize(
        ("purity", "llm", "expected"),
        [
            # Case-insensitive nos dois lados
            ("true", "pure", AGREE),
            ("False", "floss", AGREE),
            ("TRUE", "pure", AGREE),
            # Vocabulário de handler: purity já expressa como pure/floss
            ("floss", "floss", AGREE),
            ("pure", "floss", DISAGREE),
            # Booleans (o purity_handler opera com bool/numpy.bool_ do pandas;
            # str(numpy.bool_(True)) == 'True', mesmo caminho de normalização)
            (True, "pure", AGREE),
            (False, "floss", AGREE),
            (True, "floss", DISAGREE),
            # NaN do pandas vira 'nan' -> sem veredito
            (float("nan"), "pure", NOT_COMPARABLE),
        ],
    )
    def test_vocabularies_and_types(self, purity, llm, expected):
        assert compare_purity_llm(purity, llm) == expected


class TestSummarizeConvergence:
    def test_counts_all_three_buckets(self):
        pairs = [
            ("TRUE", "PURE"),      # agree
            ("FALSE", "FLOSS"),    # agree
            ("TRUE", "FLOSS"),     # disagree
            ("None", "PURE"),      # not_comparable
            ("FALSE", "FAILED"),   # not_comparable
        ]
        assert summarize_convergence(pairs) == {
            AGREE: 2,
            DISAGREE: 1,
            NOT_COMPARABLE: 2,
        }

    def test_empty_input(self):
        assert summarize_convergence([]) == {AGREE: 0, DISAGREE: 0, NOT_COMPARABLE: 0}

    def test_regression_val1_realistic_session(self):
        """Uma sessão realista NÃO pode reportar zero agree (defeito VAL-1)."""
        session = [
            ("FALSE", "FLOSS"),
            ("FALSE", "FLOSS"),
            ("TRUE", "PURE"),
            ("FALSE", "PURE"),
        ]
        counts = summarize_convergence(session)
        assert counts[AGREE] == 3
        assert counts[DISAGREE] == 1
        assert counts[NOT_COMPARABLE] == 0
