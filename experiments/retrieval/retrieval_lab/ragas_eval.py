"""Actual RAGAS 0.3.9 ID metrics. No default LLM/embedding factories."""
import os
os.environ['RAGAS_DO_NOT_TRACK'] = 'true'
os.environ['LANGSMITH_TRACING'] = 'false'
import math
from importlib.metadata import version
from ragas.dataset_schema import SingleTurnSample, EvaluationDataset
from ragas.metrics import IDBasedContextPrecision, IDBasedContextRecall
from .corpus import require


async def id_scores(sample):
    require(version('ragas') == '0.3.9', 'use the tested RAGAS release')
    sample = SingleTurnSample(**sample)
    precision = float(await IDBasedContextPrecision().single_turn_ascore(sample))
    recall = float(await IDBasedContextRecall().single_turn_ascore(sample))
    return dict(precision=precision if math.isfinite(precision) else None,
                recall=recall if math.isfinite(recall) else None,
                precisionStatus='measured' if math.isfinite(precision) else 'undefined_empty_retrieval',
                recallStatus='measured' if math.isfinite(recall) else 'undefined_empty_reference')


def native_dataset(samples):
    return EvaluationDataset.from_list(samples)


async def judge_scores(sample, *, enabled=False, llm=None, embeddings=None):
    """Prepared opt-in adapter. Caller supplies authorized real clients; none are constructed here."""
    require(enabled, 'LLM judge disabled; explicit opt-in required')
    require(llm is not None and embeddings is not None, 'explicit real judge/embedding adapters required')
    from ragas.metrics import Faithfulness, ResponseRelevancy
    row = SingleTurnSample(**sample)
    return dict(faithfulness=float(await Faithfulness(llm=llm).single_turn_ascore(row)),
                responseRelevancy=float(await ResponseRelevancy(llm=llm, embeddings=embeddings).single_turn_ascore(row)),
                status='actual_judge_executed')
