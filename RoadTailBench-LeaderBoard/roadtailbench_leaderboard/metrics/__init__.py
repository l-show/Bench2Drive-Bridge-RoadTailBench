from .ability_score import AbilityScoreMetric
from .collision_penalty import CollisionPenaltyMetric
from .comfort import ComfortMetric
from .composite_score import CompositeScoreMetric
from .control_stability import ControlStabilityMetric
from .drivable_area import DrivableAreaMetric
from .driving_efficiency import DrivingEfficiencyMetric
from .interaction_risk import OmnidirectionalInteractionRiskMetric
from .long_tail_hazard_response import LongTailHazardResponseMetric
from .road_engineering_hazard_adaptation import RoadEngineeringHazardAdaptationMetric
from .route_completion import RouteCompletionMetric
from .speed_appropriateness import SpeedAppropriatenessMetric


CORE_METRICS = [
    RouteCompletionMetric,
    CollisionPenaltyMetric,
    DrivingEfficiencyMetric,
    SpeedAppropriatenessMetric,
    DrivableAreaMetric,
    OmnidirectionalInteractionRiskMetric,
    RoadEngineeringHazardAdaptationMetric,
    ComfortMetric,
    ControlStabilityMetric,
    LongTailHazardResponseMetric,
]
