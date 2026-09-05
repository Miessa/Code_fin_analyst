"""Deterministic feature engineering and comparable-project analytics."""

from .features import ProjectFeatures, QualityIssue, build_project_features
from .comparability import ComparableCandidate, ProjectProfile, rank_comparables
from .statistics import BenchmarkStatistic, calculate_benchmark_statistics
from .profile import ProfileBuildResult, build_project_profile, load_project_profile
from .review import ComparableDecision, review_candidates

__all__ = [
    "BenchmarkStatistic", "ComparableCandidate", "ProjectFeatures", "ProjectProfile",
    "QualityIssue", "build_project_features", "calculate_benchmark_statistics",
    "rank_comparables", "ComparableDecision", "ProfileBuildResult",
    "build_project_profile", "load_project_profile", "review_candidates",
]
