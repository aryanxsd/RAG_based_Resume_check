ROLE_OPTIONS = [
    {
        "id": "ai_ml_engineer",
        "label": "AI/ML Engineer",
        "description": "Modeling fundamentals, learning theory, feature engineering, evaluation, and deployment tradeoffs.",
    },
    {
        "id": "data_science_applied_ml",
        "label": "Data Science / Applied ML",
        "description": "Data preparation, model selection, validation, explainability, and applied business reasoning.",
    },
    {
        "id": "backend_engineer",
        "label": "Backend Engineer for AI Systems",
        "description": "API design, persistence, retrieval services, orchestration, reliability, and AI product backend flow.",
    },
    {
        "id": "advanced_theoretical_ml",
        "label": "Advanced / Theoretical ML",
        "description": "Probabilistic models, generalization, inference, optimization, and theory-aware system decisions.",
    },
]


ROLE_LABELS = {role["id"]: role["label"] for role in ROLE_OPTIONS}


ROLE_QUERY_HINTS = {
    "ai_ml_engineer": [
        "supervised learning bias variance regularization model evaluation",
        "feature engineering decision trees neural networks nearest neighbors",
        "training data validation generalization overfitting practical deployment",
    ],
    "data_science_applied_ml": [
        "data preprocessing exploratory analysis train test split metrics",
        "classification regression model interpretation business constraints",
        "applied machine learning pipelines validation leakage feature selection",
    ],
    "backend_engineer": [
        "retrieval augmented generation backend architecture API sessions persistence",
        "vector search embeddings database orchestration error handling",
        "scalable service design asynchronous processing observability validation",
    ],
    "advanced_theoretical_ml": [
        "probabilistic models Bayesian inference graphical models kernel methods",
        "generalization regularization maximum likelihood expectation maximization",
        "pattern recognition decision theory optimization latent variables",
    ],
}


ROLE_TO_SOURCE_TAGS = {
    "ai_ml_engineer": ["ai_ml", "ml_basics"],
    "data_science_applied_ml": ["data_science", "ml_basics"],
    "backend_engineer": ["backend_ai_systems", "ai_ml"],
    "advanced_theoretical_ml": ["advanced_ml", "ai_ml"],
}
