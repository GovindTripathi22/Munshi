"""Evaluation package initialization."""

from munshi.evaluation.synthetic_data import generate_synthetic_dataset
from munshi.evaluation.benchmark import run_benchmark

__all__ = ["generate_synthetic_dataset", "run_benchmark"]
