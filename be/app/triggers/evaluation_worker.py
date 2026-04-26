import asyncio
from datetime import datetime, timezone, timedelta
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.db import get_table
from app.keys import project_pk, PROJECT_SK, gsi4_score_sk, GSI4_PK, GSI4_SK
from app.models.evaluation import EvaluationResult, EvaluationRecord
from app.config import settings

SYSTEM_PROMPT = """You are an expert startup evaluator with deep knowledge of the Greek and European tech ecosystem.
You evaluate early-stage projects and startups for potential, originality, and acquisition readiness.
Return a structured JSON evaluation — no extra text."""

_agent: Agent[None, EvaluationResult] | None = None


def _get_agent() -> Agent[None, EvaluationResult]:
    global _agent
    if _agent is None:
        model = OpenAIModel(settings.openai_model, provider=OpenAIProvider(api_key=settings.openai_api_key))
        _agent = Agent(model, output_type=EvaluationResult, system_prompt=SYSTEM_PROMPT)
    return _agent


def _build_prompt(project: dict) -> str:
    return f"""Evaluate this project submission. Score each dimension 0–100.

Name: {project['name']}
Tagline: {project['tagline']}
Description: {project['description']}
Vision: {project['vision']}
Features: {', '.join(project.get('features', []))}
Website: {project.get('websiteUrl') or 'Not provided'}
GitHub: {project.get('githubUrl') or 'Not provided'}
GitHub Stars: {project.get('githubStars', 'N/A')}
Monthly Revenue: {project.get('monthlyRevenue') or 'Not disclosed'} (€)
Monthly Users: {project.get('monthlyUsers') or 'Not disclosed'}
Category: {project['category']}

DIMENSIONS:
1. problemClarity (20%) — is the problem real and clearly articulated? Is the target user obvious?
2. originality (20%) — what is the differentiator? Consider Greek/EU market context.
3. completenessDeployment (25%) — is there a live product? Score on whether something is built and deployed, not on whether the repo is public or private. A closed-source product with a live site scores the same as an open-source one.
4. commercialViability (20%) — is there a plausible path to revenue? B2B preferred. If monthlyRevenue is provided treat it as a strong positive signal but NEVER penalise for low or undisclosed revenue — early-stage projects are not expected to have revenue yet. Use monthlyUsers only to validate traction claims if provided.
5. presentationQuality (15%) — well-written, credible submission.

totalScore = weighted average, rounded to nearest int.
readinessLabel: "idea" (<30), "prototype" (30–54), "launched" (55–74, live product exists), "scalable" (≥75, clear traction or strong commercial signal)

biggestGap: identify the single most important improvement across problemClarity, originality, and commercialViability only. Do NOT mention GitHub, repo visibility, revenue size, or user count as gaps — those are not weaknesses for an early-stage project."""


def handle(event: dict, context) -> None:
    project_id = event["projectId"]
    now = datetime.now(timezone.utc).isoformat()
    table = get_table()

    try:
        project = table.get_item(
            Key={"PK": project_pk(project_id), "SK": PROJECT_SK}
        ).get("Item")
        if not project:
            raise ValueError(f"Project {project_id} not found")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_get_agent().run(_build_prompt(project)))
        evaluation_result: EvaluationResult = result.output

        record = EvaluationRecord(
            **evaluation_result.model_dump(),
            requestedAt=project["updatedAt"],
            completedAt=now,
        )

        locked_until = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

        table.update_item(
            Key={"PK": project_pk(project_id), "SK": PROJECT_SK},
            UpdateExpression=(
                "SET evaluationStatus = :s, evaluation = :e, updatedAt = :now,"
                " #gsi4pk = :g4pk, #gsi4sk = :g4sk, evaluationLockedUntil = :lock"
            ),
            ExpressionAttributeNames={"#gsi4pk": GSI4_PK, "#gsi4sk": GSI4_SK},
            ExpressionAttributeValues={
                ":s": "complete",
                ":e": record.model_dump(),
                ":now": now,
                ":g4pk": "PROJECT",
                ":g4sk": gsi4_score_sk(evaluation_result.totalScore),
                ":lock": locked_until,
            },
        )
    except Exception as e:
        print(f"Evaluation worker failed for {project_id}: {e}")
        table.update_item(
            Key={"PK": project_pk(project_id), "SK": PROJECT_SK},
            UpdateExpression="SET evaluationStatus = :f, updatedAt = :now",
            ExpressionAttributeValues={":f": "failed", ":now": now},
        )
