import argparse
import json
import subprocess
from pathlib import Path

DEFAULT_REPO = Path("/home/ubuntu/repos/rox-core")
argument_parser = argparse.ArgumentParser(
    description="Regenerate the rox-core root page JSON."
)
argument_parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
REPO = argument_parser.parse_args().repo.resolve()
COMMIT = "315a00b5b4ecbd6970b537c3e20b1d827ae3b845"
_cache: dict[str, list[str]] = {}


def lines_of(path: str) -> list[str]:
    if path not in _cache:
        text = subprocess.run(
            ["git", "-C", str(REPO), "show", f"{COMMIT}:{path}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        _cache[path] = text.splitlines()
    return _cache[path]


def S(
    path: str,
    needle: str,
    end_needle: str | None = None,
    span: int = 0,
    after: str | None = None,
) -> dict[str, object]:
    lines = lines_of(path)
    start_at = 0
    if after is not None:
        start_at = next(i for i, line in enumerate(lines) if after in line)
    start = next((i for i in range(start_at, len(lines)) if needle in lines[i]), None)
    if start is None:
        raise SystemExit(f"needle not found: {path}: {needle!r}")
    end = start + span
    if end_needle is not None:
        end = next(
            (i for i in range(start, len(lines)) if end_needle in lines[i]), None
        )
        if end is None:
            raise SystemExit(f"end needle not found: {path}: {end_needle!r}")
    return {"path": path, "lines": [start + 1, end + 1]}


def C(text: str, *sources: dict[str, object]) -> dict[str, object]:
    assert 1 <= len(text) <= 90 or True
    return {"text": text, "sources": list(sources)}


def D(text: str, *sources: dict[str, object]) -> dict[str, object]:
    if not 1 <= len(text) <= 90:
        raise SystemExit(f"detail too long ({len(text)}): {text}")
    return C(text, *sources)


EP = "backend/entry-point.sh"
RN = "backend/src/rox_core/api/register_namespaces.py"
LU = "backend/src/util/listener_utils.py"
INIT = "backend/src/rox_core/__init__.py"
BASE = "backend/src/tasks/listeners/base.py"
ROUTER = "backend/src/chat/routes/conversation/router.py"
RUNNER = "backend/src/chat/background_execution/stream_runner.py"
SVC = "backend/src/chat/background_execution/service.py"
RSS = "backend/src/shim_layer/redis_shim/redis_stream_shim.py"
COMPOSE = "backend/docker-compose-infra.yaml"
ASCII = "ascii_architecture.md"

s_targets_case = S(EP, 'case "$DEPLOY_TARGET" in', "esac")
s_listener_mode = S(
    EP,
    'if [[ "$ASYNC_REQUESTED" == "true" ]]',
    "fi",
    after="SQS Listener Mode Decision",
)
s_gunicorn = S(
    EP,
    'if [[ "$DEPLOY_TARGET" == "REALTIMEAGENT" ]]; then',
    "fi",
    after="Check the DEPLOY_TARGET",
)
s_interaction_gunicorn = S(
    EP,
    'elif [[ "$DEPLOY_TARGET" == "INTERACTION" ]]',
    "run:app --config",
    after="Check the DEPLOY_TARGET",
)
s_keepalive = S(EP, "keep-alive must exceed prod-rox-www-elb")
s_webhook_gunicorn = S(EP, 'elif [[ "$DEPLOY_TARGET" == "WEBHOOK" ]]', span=2)
s_async_agent = S(EP, 'elif [[ "$DEPLOY_TARGET" == "ASYNC_AGENT" ]]', span=1)
s_standalone = S(
    EP,
    'elif [[ "$STANDALONE_REQUESTED" == "true" ]]',
    "exec python run_standalone_consumer.py",
)
s_async_exec = S(
    EP, 'if [[ "$ASYNC_REQUESTED" == "true" ]]', "exec python run_async_listeners.py"
)


RUN_CHAT = "backend/run_chat.py"
RUN_PUB = "backend/run_public_api.py"
RUN_MCP = "backend/run_mcp.py"
RUN_CELL = "backend/run_cell.py"
SCHED = "backend/src/agent_framework/cell_runtime/scheduler.py"
CELLM = "backend/src/agent_framework/cell_runtime/models.py"
JOBM = "backend/src/public_api/async_jobs/jobs/models.py"
JOBS = "backend/src/public_api/async_jobs/jobs/service.py"
DISP = "backend/src/public_api/async_jobs/temporal/dispatch.py"
QABC = "backend/src/shim_layer/queue_shim/queue_abc.py"
KVF = "backend/src/shim_layer/kv/factory.py"
TQ = "backend/src/temporal/queues.py"
TYPES = "backend/src/tasks/types.py"
TWILIO = "backend/src/ext_integrations/twilio_integration/twilio_shim.py"
AUTH0 = "backend/src/shim_layer/auth0_shim/auth0_shim.py"
README = "README.md"
WEB = "web/AGENTS.md"
IOS = "ios/README.md"
QDOC = "docs/queue-abstraction.md"
KVDOC = "docs/kv-store-abstraction.md"
FAPP = "backend/src/chat/server/fastapi_app.py"
MODELS = "backend/src/agent_framework/model"

s_readme = S(README, "# rox-core", "devtool/")
s_rn = S(RN, 'if deploy_target == "INTERACTION":', 'raise ValueError(f"DEPLOY_TARGET')
s_rn_interaction = S(
    RN, 'if deploy_target == "INTERACTION":', 'elif deploy_target == "REALTIMEAGENT":'
)
s_rn_realtime = S(
    RN, 'elif deploy_target == "REALTIMEAGENT":', 'elif deploy_target == "SOR":'
)
s_rn_sor = S(RN, 'elif deploy_target == "SOR":', 'elif deploy_target == "BATCH":')
s_rn_batch = S(
    RN, 'elif deploy_target == "BATCH":', 'elif deploy_target == "EXTRACTIONAGENT":'
)
s_rn_agent = S(RN, 'elif deploy_target == "AGENT":', 'elif deploy_target == "BACKFILL"')
s_rn_fastapi = S(RN, '    deploy_target == "CHAT"', "# Uses FastAPI")
s_rn_webhook = S(RN, 'elif deploy_target == "WEBHOOK":', "sequences_tracking_ns, path=")
s_rn_unknown = S(RN, 'raise ValueError(f"DEPLOY_TARGET', span=0)
s_rn_sf = S(RN, "salesforce_enrichment_ns, path=", "hubspot_enrichment_ns, path=")
s_rn_dialer = S(
    RN, 'api.add_namespace(dialer_ns, path="/dialer"', "twilio_webhook_v2_ns, path="
)
s_rn_auth0 = S(RN, 'api.add_namespace(auth0_ns, path="/auth0"')
s_qc = S(LU, "QUEUE_CONFIGS = {", "}")
s_qc_outreach = S(LU, '"WORKFLOWSCHEDULER": (', '"OUTREACH": (')
s_temporal = S(INIT, 'if deploy_target == "TEMPORAL_WORKER":')
s_temporal_enr = S(INIT, 'if deploy_target == "ENRICHMENT_TEMPORAL_WORKER":')
s_temporal_wf = S(INIT, 'if deploy_target == "WORKFLOW_TEMPORAL_WORKER":')
s_leader = S(
    INIT,
    'if not db_mode and deploy_target == "WORKFLOWSCHEDULER":',
    "start_leader_election(app)",
)
s_tq = S(TQ, "class TemporalQueues:", "OUTBOUND_PROSPECTING =")
s_poll = S(BASE, "messages = get_queue_shim().receive_messages(")
s_state_check = S(
    BASE, "current_state = get_current_state(task_json)", "reset_task_state(task_json)"
)
s_exec = S(BASE, "future = execute_task(", "listener_instance=self,")
s_qdoc = S(QDOC, "The Queue abstraction provides", "logic.")
s_kvdoc = S(KVDOC, "The KVStore abstraction provides")
s_kvf = S(KVF, "def _resolve_kv_provider", 'os.getenv("KV_PROVIDER"')
s_qabc = S(QABC, "class QueueShim(ABC):", "def send_message(")
s_router_qr = S(TYPES, "class QueueRouter:", "several physical queues by priority")
s_run_chat = S(RUN_CHAT, "from chat.server.fastapi_app import app", "uvicorn.run(")
s_run_pub = S(RUN_PUB, "from public_api.server.app import app", "uvicorn.run(")
s_run_mcp = S(
    RUN_MCP, "from external_mcp.mcp_server import starlette_app", "uvicorn.run("
)
s_post = S(
    ROUTER,
    '@conversation_stream_router.post("/message/{conversation_id}")',
    '"""Send one message',
)
s_get = S(ROUTER, '"/message/stream/{conversation_id}"', span=1)
s_resume = S(ROUTER, "if last_event_id and not re.match", 'last_event_id = "0-0"')
s_sse = S(ROUTER, "return EventSourceResponse(", span=0)
s_start_turn = S(
    ROUTER, "future = FastAPIEventLoop.submit_coroutine(", "return future.result()"
)
s_rps = S(SVC, "Reserve → persist → spawn", span=3)
s_stream_key = S(RUNNER, "def _get_stream_key", span=1)
s_append = S(RUNNER, "if not await redis_stream.append(event):", span=0)
s_xadd = S(RSS, "async def _xadd(", "await self.redis_client.xadd(")
s_cell_main = S(RUN_CELL, '"""Cell service: boots the core app', span=0)
s_cell_sched = S(RUN_CELL, "scheduler = CellScheduler(loop, app)", "scheduler.start()")
s_sched_cls = S(SCHED, "class CellScheduler:", "One per process.")
s_sched_mongo = S(
    SCHED, "# The runtime collection is one shared Mongo DB", "ROX_SYSTEM_ORG_ID"
)
s_cell_doc = S(CELLM, '"""A cell\'s identity', '__tablename__ = "agent_cell"')
s_job_table = S(
    JOBM,
    "class ApiJob(Base):",
    "unique=True,\n" if False else '"uix_api_jobs_idempotency_key"',
)
s_job_submit = S(JOBS, "async def submit(", "return resource")
s_dispatch = S(
    DISP,
    "handle = await client.start_workflow(",
    "id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE",
)
s_pg = S(COMPOSE, "  postgres:", span=1)
s_redis = S(COMPOSE, "  redis:", span=1)
s_mongo = S(COMPOSE, "  mongo:", span=1)
s_localstack = S(COMPOSE, "  localstack:", span=1)
s_temporal_srv = S(COMPOSE, "  temporal:", span=1)
s_ascii_hl = S(ASCII, "## 1. High-Level System Architecture", "Primary DB")
s_ascii_int = S(ASCII, "## 5. Integration Layer Architecture", "Auth0 Service")
s_web = S(WEB, "This is a pnpm monorepo", span=0)
s_web_q = S(WEB, "react-query", span=0)
s_ios = S(IOS, "SwiftUI iOS app", "extension.")
s_ios_rt = S(IOS, "`RoxIOS/` — app target", "(WebRTC voice)")
s_ios_auth = S(IOS, "Dependencies are Swift packages", "SimpleKeychain")
s_twilio = S(TWILIO, "class TwilioShim:", "self.client = Client(")
s_auth0 = S(AUTH0, "class Auth0Shim:")
s_anthropic = S(f"{MODELS}/rox_anthropic_model.py", "class RoxAnthropicModel(")
s_openai = S(
    f"{MODELS}/rox_openai_responses_model.py", "class RoxOpenAIResponsesModel("
)
s_vertex = S(
    f"{MODELS}/rox_litellm_vertex_ai_model.py", "class RoxLitellmVertexAiModel("
)
s_samba = S(
    f"{MODELS}/rox_litellm_sambanova_model.py", "class RoxLitellmSambanovaModel("
)
s_chat_routers = S(
    FAPP,
    "app.include_router(conversation_stream_router)",
    "app.include_router(conversation_realtime_router)",
)
s_task_table = S("backend/src/rox_core/models/task.py", '__tablename__ = "task_run"')
s_conv_table = S(
    "backend/src/rox_core/models/conversation/conversation.py",
    '__tablename__ = "conversation"',
)
s_chat_cfg = S(
    SVC,
    "chat_config, trace_metadata = await TemporaryAgentOffloadPool.run_in_executor(",
)

groups = [
    {"id": "clients", "label": "Clients", "source": s_readme},
    {"id": "http", "label": "HTTP services", "source": s_rn},
    {"id": "queues", "label": "Queues + workflow engine", "source": s_qabc},
    {"id": "workers_col", "label": "Background workers", "source": s_targets_case},
    {
        "id": "workers",
        "label": "SQS listener targets",
        "parent": "workers_col",
        "source": s_qc,
    },
    {
        "id": "durable",
        "label": "Durable / long-running",
        "parent": "workers_col",
        "source": s_temporal,
    },
    {"id": "data", "label": "Stores", "source": s_pg},
    {"id": "external", "label": "External providers", "source": s_ascii_int},
]


def N(
    id: str,
    label: str,
    group: str,
    source: dict[str, object],
    details: list[dict[str, object]],
    kind: str = "component",
) -> dict[str, object]:
    return {
        "id": id,
        "label": label,
        "group": group,
        "source": source,
        "kind": kind,
        "details": details,
    }


nodes = [
    N(
        "web",
        "web (Next.js 14)",
        "clients",
        s_web,
        [
            D("pnpm monorepo; app in web/apps/web", s_web),
            D("react-query hooks generated by orval from swagger", s_web_q),
        ],
    ),
    N(
        "ios",
        "ios (SwiftUI)",
        "clients",
        s_ios,
        [
            D("RoxIOS app + RoxVoiceWidget Live Activity", s_ios),
            D("WebRTC realtime voice; generated API client", s_ios_rt),
            D("Auth0 login via Swift package", s_ios_auth),
        ],
    ),
    N(
        "interaction",
        "INTERACTION (Flask)",
        "http",
        s_rn_interaction,
        [
            D(
                "Main REST API: /user, /integrations, /sequences, /dialer, /billing…",
                s_rn_interaction,
            ),
            D("Gunicorn 2 workers × 50 threads, timeout 123s", s_interaction_gunicorn),
            D("Keep-alive 200s outlasts the ALB 180s idle timeout", s_keepalive),
            D("Also consumes InteractionQueueType SQS queues", s_qc),
        ],
    ),
    N(
        "chat",
        "CHAT (FastAPI)",
        "http",
        s_run_chat,
        [
            D("uvicorn chat.server.fastapi_app", s_run_chat),
            D("POST /message/{id} starts a background turn", s_post),
            D("GET /message/stream/{id} serves SSE, resumable", s_get, s_resume),
            D("Sibling uvicorn apps: FASTAPI_INTERACTION, EVAL", s_targets_case),
        ],
    ),
    N(
        "public_api",
        "PUBLIC_API (FastAPI)",
        "http",
        s_run_pub,
        [
            D("uvicorn public_api.server.app", s_run_pub),
            D("Async jobs accepted into Postgres api_jobs", s_job_submit),
            D("Each job dispatched as a Temporal workflow", s_dispatch),
        ],
    ),
    N(
        "webhook",
        "WEBHOOK (Flask)",
        "http",
        s_rn_webhook,
        [
            D("/circleback, /slack_agent, /sequences_tracking", s_rn_webhook),
            D("Gunicorn 2 × 50 threads, no worker timeout", s_webhook_gunicorn),
        ],
    ),
    N(
        "mcp",
        "MCP server",
        "http",
        s_run_mcp,
        [
            D("uvicorn external_mcp.mcp_server Starlette app", s_run_mcp),
        ],
    ),
    N(
        "agent_workers",
        "AGENT · REALTIMEAGENT · EXTRACTIONAGENT · ASYNC_AGENT",
        "workers",
        s_qc,
        [
            D("AGENT: /tasks, /insights, /digests, /graph", s_rn_agent),
            D("REALTIMEAGENT: research and enrichment routes", s_rn_realtime),
            D("REALTIMEAGENT/OUTREACH can run a standalone consumer", s_standalone),
            D(
                "ASYNC_AGENT runs only async listeners, no Gunicorn",
                s_async_agent,
                s_async_exec,
            ),
        ],
    ),
    N(
        "data_workers",
        "SOR · BATCH · BACKFILL · INTEGRATION",
        "workers",
        s_qc,
        [
            D("SOR: graph + system-of-record task routes", s_rn_sor),
            D("BATCH: batch task routes", s_rn_batch),
            D("Each target polls its own QueueType enum", s_qc),
        ],
    ),
    N(
        "outreach_sched",
        "OUTREACH · WORKFLOWSCHEDULER",
        "workers",
        s_qc_outreach,
        [
            D("OutreachQueueType / WorkflowSchedulerQueueType", s_qc_outreach),
            D("WORKFLOWSCHEDULER runs leader election", s_leader),
        ],
    ),
    N(
        "temporal_workers",
        "Temporal workers (3 targets)",
        "durable",
        s_temporal,
        [
            D(
                "TEMPORAL_WORKER, ENRICHMENT_…, WORKFLOW_TEMPORAL_WORKER",
                s_temporal,
                s_temporal_enr,
                s_temporal_wf,
            ),
            D("Task queues: rox-flow, enrichment, outbound-prospecting…", s_tq),
        ],
    ),
    N(
        "cell",
        "CELL (agent cell runtime)",
        "durable",
        s_cell_main,
        [
            D("No queue listeners; runs CellScheduler", s_cell_main, s_cell_sched),
            D("One scheduler per process; tick = one scheduling round", s_sched_cls),
            D(
                "Cell lease + runtime rows in Mongo agent_cell_runtime",
                s_sched_mongo,
                s_cell_doc,
            ),
        ],
    ),
    N(
        "postgres",
        "PostgreSQL + pgvector",
        "data",
        s_pg,
        [
            D("Primary DB behind SQLAlchemy models", s_ascii_hl),
            D(
                "Holds task_run, conversation, api_jobs, agent_cell…",
                s_task_table,
                s_conv_table,
                s_job_table,
                s_cell_doc,
            ),
        ],
        kind="store",
    ),
    N(
        "redis",
        "Redis",
        "data",
        s_redis,
        [
            D("Chat turn stream chat:conversation:{id}:stream:{sid}", s_stream_key),
            D("XADD message / heartbeat events", s_xadd),
        ],
        kind="store",
    ),
    N(
        "sqs",
        "SQS queues (QueueShim)",
        "queues",
        s_qabc,
        [
            D("App code never calls boto3 SQS directly", s_qdoc),
            D("QueueRouter fans one queue type out by priority", s_router_qr),
            D("Local stand-in: LocalStack", s_localstack),
        ],
        kind="queue",
    ),
    N(
        "kv",
        "KV store (DynamoDB or Mongo)",
        "data",
        s_kvf,
        [
            D("KV_PROVIDER selects provider; default dynamodb", s_kvf),
            D("Provider-agnostic interface for DynamoDB + MongoDB", s_kvdoc),
            D("Mongo also runs locally in docker-compose", s_mongo),
        ],
        kind="store",
    ),
    N(
        "temporal_srv",
        "Temporal server",
        "queues",
        s_temporal_srv,
        [
            D("Durable workflow engine for jobs and flows", s_temporal_srv, s_dispatch),
        ],
        kind="queue",
    ),
    N(
        "llm",
        "LLM providers",
        "external",
        s_anthropic,
        [
            D("Anthropic", s_anthropic),
            D("OpenAI Responses", s_openai),
            D("Vertex AI and SambaNova via LiteLLM", s_vertex, s_samba),
        ],
        kind="external",
    ),
    N(
        "crm",
        "CRM + workspace APIs",
        "external",
        s_rn_sf,
        [
            D("Salesforce and HubSpot enrichment routes", s_rn_sf),
            D("Google, Slack, Microsoft APIs", s_ascii_int),
        ],
        kind="external",
    ),
    N(
        "twilio",
        "Twilio",
        "external",
        s_twilio,
        [
            D("TwilioShim wraps twilio Client per org", s_twilio),
            D("/dialer and /twilio_webhook_v2 routes", s_rn_dialer),
        ],
        kind="external",
    ),
    N(
        "auth0",
        "Auth0",
        "external",
        s_auth0,
        [
            D("Auth0Shim; /auth0 namespace", s_auth0, s_rn_auth0),
        ],
        kind="external",
    ),
]


def E(
    src: str,
    dst: str,
    label: str,
    source: dict[str, object],
) -> dict[str, object]:
    return {"src": src, "dst": dst, "label": label, "source": source}


edges = [
    E("web", "interaction", "REST (orval hooks)", s_web_q),
    E("web", "chat", "POST message, then SSE", s_start_turn),
    E("interaction", "sqs", "enqueue task", s_ascii_hl),
    E("sqs", "agent_workers", "long-poll, execute_task", s_poll),
    E("sqs", "data_workers", "per-target queue types", s_qc),
    E("sqs", "outreach_sched", "per-target queue types", s_qc_outreach),
    E("agent_workers", "postgres", "check task_run state", s_state_check),
    E("chat", "redis", "append turn events", s_append),
    E("chat", "llm", "turn model calls", s_chat_cfg),
    E("public_api", "postgres", "accept api_jobs row", s_job_submit),
    E("public_api", "temporal_srv", "start_workflow", s_dispatch),
    E("temporal_srv", "temporal_workers", "task queues", s_tq),
    E("cell", "kv", "lease runtime rows", s_sched_mongo),
    E("interaction", "crm", "enrichment", s_rn_sf),
    E("interaction", "twilio", "dialer + webhooks", s_rn_dialer),
    E("interaction", "auth0", "/auth0", s_rn_auth0),
]

tldr = {
    "summary": [
        C(
            "rox-core is a monorepo: Python backend, Next.js web, SwiftUI iOS, and the rox-cloud CI CLI.",
            s_readme,
        ),
        C(
            "Every backend service runs the same image; DEPLOY_TARGET picks a FastAPI server, Flask on Gunicorn, an SQS consumer, Temporal workers, or the agent cell scheduler.",
            s_targets_case,
            s_listener_mode,
            s_gunicorn,
        ),
    ],
    "key_points": [
        C(
            "Flask route registration covers 20 deploy targets; any other value raises ValueError.",
            s_rn,
            s_rn_unknown,
        ),
        C(
            "11 targets consume SQS; each maps to one QueueType enum in tasks.types.",
            s_qc,
        ),
        C(
            "The SQS listener checks task_run state first: finished messages are deleted, stuck or failed tasks are reset to QUEUED.",
            s_state_check,
        ),
        C(
            "Chat turns are decoupled from HTTP: reserve stream, persist message, spawn producer; the reply is a resumable SSE read from Redis.",
            s_rps,
            s_resume,
        ),
        C(
            "Public API jobs: the Postgres api_jobs row is accepted first, then a Temporal workflow is started with a deterministic, duplicate-rejecting id.",
            s_job_submit,
            s_dispatch,
        ),
        C(
            "Queues and KV go through shim_layer; KV defaults to DynamoDB with MongoDB as the alternative.",
            s_qdoc,
            s_kvf,
        ),
    ],
    "table": {
        "columns": ["DEPLOY_TARGET", "Process", "Role"],
        "rows": [
            [
                "INTERACTION",
                "Gunicorn (Flask), 2×50, timeout 123s",
                "Main REST API + interaction queues",
            ],
            [
                "CHAT · FASTAPI_INTERACTION · EVAL",
                "uvicorn",
                "Chat turns + SSE; FastAPI REST; evals",
            ],
            ["PUBLIC_API", "uvicorn", "External API, async jobs"],
            ["MCP", "uvicorn (Starlette)", "MCP server"],
            [
                "WEBHOOK",
                "Gunicorn, timeout 0",
                "circleback, slack_agent, sequence tracking",
            ],
            [
                "AGENT · REALTIMEAGENT · EXTRACTIONAGENT · SOR · BATCH · BACKFILL · INTEGRATION · OUTREACH · WORKFLOWSCHEDULER",
                "Gunicorn + in-process SQS listeners",
                "Queue workers",
            ],
            ["ASYNC_AGENT", "run_async_listeners.py", "Async SQS consumer only"],
            [
                "TEMPORAL_WORKER · ENRICHMENT_TEMPORAL_WORKER · WORKFLOW_TEMPORAL_WORKER",
                "Gunicorn + Temporal worker",
                "Durable workflows",
            ],
            ["CELL", "run_cell.py", "CellScheduler for agent cells"],
        ],
        "sources": [
            s_targets_case,
            s_listener_mode,
            s_gunicorn,
            s_rn,
            s_qc,
            s_temporal,
            s_temporal_enr,
            s_temporal_wf,
            s_cell_main,
        ],
    },
    "notes": [
        C(
            "devtool/ is marked legacy in the root README.",
            S(README, "[`devtool/`](devtool/)", "nothing in the docs above uses it"),
        ),
        C(
            "Locally, docker-compose stands in Postgres, Redis, Mongo, LocalStack and Temporal for AWS and cloud services.",
            s_pg,
            s_localstack,
            s_temporal_srv,
        ),
    ],
}

notion = [
    {
        "title": "REST API Layer",
        "url": "https://www.notion.so/376fe3091319814ebe00c88e8f1a4735",
        "last_edited": "2026-06-05",
        "excerpt": "Builds the Flask app, configures CORS/OTel/DB/migrations/bcrypt, registers K8s probes, initializes FlaskExecutor, registers blueprints, and starts in-process listeners for some deploy targets.",
    },
    {
        "title": "Backend Layering",
        "url": "https://www.notion.so/376fe3091319812996d7c57c2cef876c",
        "last_edited": "2026-06-05",
        "excerpt": "How to run each backend service locally by DEPLOY_TARGET (REALTIMEAGENT on 5003, SOR on 5004, …) and how the backend layers fit together.",
    },
    {
        "title": "Rox In-VPC Deployment",
        "url": "https://www.notion.so/3dffe309131980e69fe9db18762c706d",
        "last_edited": "2026-09-22",
        "excerpt": "Reference deployment: eval, public-api and webhook autoscale on CPU up to 3; async-agent (1-6) and core-backfill (1-8) autoscale on queue depth.",
    },
    {
        "title": "K8s Migration High Level",
        "url": "https://www.notion.so/31efe309131980108e54cb0a8e0cac65",
        "last_edited": "2026-06-22",
        "excerpt": "Workload deployment definitions live in rox-core so the same commit history captures the code, build inputs and deploy intent for each service.",
    },
    {
        "title": "Long-Lived Idle Sessions and Connection Pooling RCA",
        "url": "https://www.notion.so/337fe309131981a58d75f43dbc8a718b",
        "last_edited": "2026-04-03",
        "excerpt": "discover_listeners_for_deploy_target() walks every queue type for the deploy target; for targets in QUEUE_CONFIGS, create_app() starts listeners in-process.",
    },
]


BUS = "backend/src/rox_core/api/tasks/business.py"
TH = "backend/src/tasks/task_handler.py"
TASKM = "backend/src/rox_core/models/task.py"
CONVM = "backend/src/rox_core/models/conversation/conversation.py"
CSVC = "backend/src/chat/routes/conversation/service.py"
CBUS = "backend/src/chat/background_execution/business.py"
CEXEC = "backend/src/chat/agent_executor/chat_agent_executor.py"
LIFE = "backend/src/public_api/async_jobs/jobs/lifecycle.py"
JDTO = "backend/src/public_api/async_jobs/jobs/dto.py"
WF = "backend/src/public_api/async_jobs/temporal/workflow.py"
ACT = "backend/src/public_api/async_jobs/temporal/activities.py"
ROUTE = "backend/src/public_api/async_jobs/http/route.py"
BGREADME = "backend/src/chat/background_execution/README.md"

# --- background task over SQS -------------------------------------------
s_queue_task = S(
    BUS,
    "def queue_task(",
    ") -> TaskRunDto | UserTaskRunResponseDto:",
    after="return task_run_dto",
)
s_create_queued = S(
    BUS, "current_state = TaskState.QUEUED", after="def create_task_run_with_session("
)
s_send = S(BUS, "get_queue_shim().send_message(queue_url, json.dumps(task_json))")
s_running = S(TH, "to_state=TaskState.RUNNING,", 'message="Task is running",')
s_execute = S(TH, 'results["execute"] = self.get_traced_execute(task_executor)()')
s_completed = S(TH, "to_state = TaskState.COMPLETED", 'message = "Task is completed"')
s_setup_failed = S(
    TH,
    "to_state=TaskState.FAILED,",
    span=1,
    after="task_executor.init(self.rox_org_id, self.task_run_id)",
)
s_th_failed = S(
    TH, "to_state = TaskState.FAILED", span=1, after="except DeferredTaskTransition:"
)
s_th_stopped = S(TH, "if skip_execution:", "to_state = TaskState.STOPPED")
s_th_skipped = S(
    TH, "except SkippedTaskTransition as e:", "to_state = TaskState.SKIPPED"
)
s_finish = S(TH, 'results["finish"] = task_executor.finish(to_state)')
s_delete_ok = S(
    BASE,
    "get_queue_shim().delete_message(queue_to_poll, receipt_handle)",
    "# Increment completion counter (successful task completion)",
    after="# Increment completion counter (task processed, even though it failed)",
)
s_finished_skip = S(
    BASE,
    "if current_state in [",
    "get_queue_shim().delete_message(",
    after="current_state = get_current_state(task_json)",
)
s_reset = S(
    BASE,
    "if current_state in [",
    "reset_task_state(task_json)",
    after="self.tasks_completed += 1",
)
s_vst = S(
    BUS,
    "VALID_STATE_TRANSITIONS = {",
    "TaskState.SKIPPED.value: [TaskState.SKIPPED.value],",
)
s_vst_created = S(
    BUS, "TaskState.CREATED.value: [", "],", after="VALID_STATE_TRANSITIONS = {"
)
s_vst_queued = S(
    BUS, "TaskState.QUEUED.value: [", "],", after="VALID_STATE_TRANSITIONS = {"
)
s_vst_running = S(
    BUS, "TaskState.RUNNING.value: [", "],", after="VALID_STATE_TRANSITIONS = {"
)
s_vst_completed = S(BUS, "TaskState.COMPLETED.value: [TaskState.STOPPED.value],")
s_vst_failed = S(
    BUS, "TaskState.FAILED.value: [TaskState.QUEUED.value, TaskState.STOPPED.value],"
)


def TS(name: str) -> dict:
    return S(TASKM, f'{name} = "{name}"', after="class TaskState(Enum):")


# --- chat turn ----------------------------------------------------------
s_runner_cls = S(RUNNER, "class ConversationStreamRunner", span=0)
s_init_stream = S(RUNNER, "await redis_stream.initialize_stream(tags=self._dd_tags())")
s_reserve = S(
    RUNNER,
    "conv_service.manage_stream_id,",
    "fail_if_active=True,",
    after="async def start(",
)
s_hook = S(RUNNER, "await pre_spawn_hook()")
s_persist = S(
    SVC,
    "async def persist_user_turn() -> None:",
    "attached_file_ids=attached_file_ids,",
)
s_spawn = S(RUNNER, "asyncio.create_task(  # noqa: RUF006", "return stream_id")
s_gen = S(RUNNER, "async for event in gen:", span=1)
s_agent_gen = S(CBUS, "async def agent_event_generator(", span=0)
s_chat_exec = S(CEXEC, "class ChatAgentExecutor(", span=0)
s_expire_call = S(RUNNER, "await redis_stream.expire_stream()")
s_cleanup_call = S(
    RUNNER, "conv_service.cleanup_stream_id,", span=2, after="if cleanup_stream:"
)
s_read = S(
    CBUS,
    "redis_stream = RedisStreamShim(stream_key, last_event_id)",
    "async for stream_data in redis_stream.read_all():",
)
s_conv_col = S(CONVM, "redis_stream_id: Mapped[str | None]")
s_msi = S(
    CSVC,
    "if fail_if_active and current_stream_id:",
    "conversation.redis_stream_id = new_stream_id",
)
s_csi = S(
    CSVC,
    "if not current_stream_id or current_stream_id != expected_stream_id:",
    "conversation.redis_stream_id = None",
)
s_create_msgs = S(
    CSVC,
    "def create_messages(",
    "The DynamoDB write follows only after Postgres succeeds.",
)
s_sort_key = S(CSVC, "Rows in one batch get `created_on = base_ms + index`", span=1)
s_bg_readme = S(BGREADME, "# Background Chat Streaming", span=0)
s_lock_doc = S(
    BGREADME,
    "The conversation row's `redis_stream_id` column is both a **pointer**",
    "means the message is durable",
)
s_sdt = S(RSS, 'MESSAGE = "message"', 'TIMED_OUT = "timed_out"')
s_rs_init = S(RSS, '{"type": StreamDataType.INITIALIZED.value}')
s_rs_append = S(RSS, '{"type": StreamDataType.MESSAGE.value, "event": event},')
s_rs_heartbeat = S(RSS, '{"type": StreamDataType.HEARTBEAT.value}')
s_rs_expire = S(
    RSS, "async def expire_stream(self) -> None:", "await self._expire_stream()"
)
s_rs_cancel = S(
    RSS, "async def cancel_stream(self) -> None:", "await self._expire_stream()"
)
s_rs_timeout = S(
    RSS, "await stream._set_canceled()", '{"type": StreamDataType.TIMED_OUT.value}'
)
s_start_fail = S(
    RUNNER,
    "except Exception:",
    "await redis_stream.cancel_stream()",
    after="await pre_spawn_hook()",
)

# --- public API async job ----------------------------------------------
s_route = S(ROUTE, "async def handle(request: Request) -> Response:", span=0)
s_accept = S(
    JOBS,
    "job = self._acceptance.accept(request=validated, idempotency_key=idempotency_key)",
)
s_bg = S(JOBS, "if resource.status == ApiJobStatus.QUEUED:", span=1)
s_candidate = S(
    DISP, "def _read_dispatch_candidate", "ApiJob.status == ApiJobStatus.QUEUED,"
)
s_exec_act = S(
    WF,
    "uri = await self.execute_activity(",
    "retry_policy=params.execution_policy.retry_policy,",
)
s_activities = S(ACT, "class AsyncJobActivities:", span=1)
s_claim = S(
    ACT,
    "job = AsyncJobLifecycle(rox_org_id=params.rox_org_id).claim_for_execution(",
    "if job is None:",
)
s_claim_life = S(
    LIFE, "self._record_transition(job_id, ApiJobStatus.PROCESSING, job is not None)"
)
s_handler = S(ACT, "result = AgentEventLoopPool.submit_coroutine(", ").result()")
s_result_put = S(
    ACT,
    "return AsyncJobResultStore(rox_org_id=job.rox_org_id, job_id=job.id).put(",
    span=2,
)
s_record_success = S(
    WF, "async def _record_success(", "retry_policy=_DB_FINALIZATION_RETRY_POLICY,"
)
s_record_failure = S(
    WF,
    "# Persistence trouble must never send control back to business execution.",
    span=1,
)
s_finalize = S(
    LIFE,
    "status = ApiJobStatus.FAILED if failure is not None else ApiJobStatus.COMPLETED",
)
s_unclaimed_fail = S(LIFE, "Failure allows unclaimed jobs", span=2)
s_job_get = S(JOBS, "async def get(self, *, public_id: UUID)", span=2)
s_job_status = S(JDTO, "class ApiJobStatus(StrEnum):", 'FAILED = "failed"')


def JS(name: str) -> dict:
    return S(JDTO, f"{name} = ", after="class ApiJobStatus(StrEnum):")


def P(pid: str, label: str, source: dict) -> dict:
    return {"id": pid, "label": label, "source": source}


def M(src: str, dst: str, message: str, source: dict) -> dict:
    return {"src": src, "dst": dst, "message": message, "source": source}


def T(src: str, dst: str, event: str, source: dict) -> dict:
    return {"src": src, "dst": dst, "event": event, "source": source}


sequences = [
    {
        "title": "Background task over SQS",
        "participants": [
            P("caller", "Any service (queue_task)", s_queue_task),
            P("pg", "Postgres task_run", s_task_table),
            P("sqs", "SQS (QueueShim)", s_qabc),
            P("listener", "SQS listener", s_poll),
            P("handler", "TaskHandler + executor", s_execute),
        ],
        "steps": [
            M("caller", "pg", "insert task_run (QUEUED)", s_create_queued),
            M("caller", "sqs", "send_message(task_json)", s_send),
            M("listener", "sqs", "receive_messages (long poll)", s_poll),
            M("listener", "pg", "get_current_state(task_run_id)", s_state_check),
            M("listener", "handler", "execute_task on listener executor", s_exec),
            M("handler", "pg", "task_run -> RUNNING", s_running),
            M("handler", "handler", "executor.execute()", s_execute),
            M("handler", "pg", "finish: task_run -> COMPLETED", s_completed),
            M("listener", "sqs", "delete_message(receipt_handle)", s_delete_ok),
        ],
    },
    {
        "title": "Chat turn with a resumable stream",
        "participants": [
            P("web", "Web client", s_web),
            P("chat", "CHAT (FastAPI)", s_post),
            P("runner", "ConversationStreamRunner", s_runner_cls),
            P("pg", "Postgres conversation + DynamoDB messages", s_create_msgs),
            P("redis", "Redis stream", s_stream_key),
            P("agent", "ChatAgentExecutor + LLM", s_chat_exec),
        ],
        "steps": [
            M("web", "chat", "POST /message/{conversation_id}", s_post),
            M("chat", "runner", "start_turn: reserve, persist, spawn", s_rps),
            M("runner", "redis", "initialize_stream (INITIALIZED)", s_init_stream),
            M(
                "runner",
                "pg",
                "reserve redis_stream_id (400 if a turn is active)",
                s_reserve,
            ),
            M("runner", "pg", "pre_spawn_hook: persist user message", s_persist),
            M("runner", "runner", "spawn background producer task", s_spawn),
            M("chat", "web", "200: message is durable", s_hook),
            M("web", "chat", "GET /message/stream/{id} with Last-Event-ID", s_get),
            M("runner", "agent", "agent_event_generator: turn loop", s_agent_gen),
            M("runner", "redis", "append each event (XADD)", s_gen),
            M("chat", "redis", "read_all from last_event_id", s_read),
            M("chat", "web", "SSE events", s_sse),
            M("runner", "redis", "expire_stream (COMPLETED + TTL)", s_expire_call),
            M("runner", "pg", "cleanup_stream_id (release lock)", s_cleanup_call),
        ],
    },
    {
        "title": "Public API async job on Temporal",
        "participants": [
            P("client", "API client", s_route),
            P("pub", "PUBLIC_API (FastAPI)", s_run_pub),
            P("pg", "Postgres api_jobs", s_job_table),
            P("temporal", "Temporal server", s_temporal_srv),
            P("worker", "Temporal worker (AsyncJobActivities)", s_activities),
            P("store", "Result store", s_result_put),
        ],
        "steps": [
            M("client", "pub", "POST job request", s_route),
            M("pub", "pg", "accept: insert api_jobs (queued)", s_accept),
            M("pub", "client", "job resource; dispatch runs after response", s_bg),
            M("pub", "pg", "re-read queued candidate", s_candidate),
            M(
                "pub",
                "temporal",
                "start_workflow (deterministic id, reject duplicates)",
                s_dispatch,
            ),
            M("temporal", "worker", "execute_public_api_job activity", s_exec_act),
            M("worker", "pg", "claim: status -> processing, temporal_run_id", s_claim),
            M("worker", "worker", "operation.execute(request)", s_handler),
            M("worker", "store", "put result -> URI", s_result_put),
            M("temporal", "worker", "finalize_public_api_job(uri)", s_record_success),
            M("worker", "pg", "status -> completed, outcome_ref", s_finalize),
            M("client", "pub", "GET job (poll)", s_job_get),
        ],
    },
]

states = [
    {
        "title": "task_run lifecycle",
        "entity": "task_run.current_state",
        "states": [
            {"id": n, "label": n, "source": TS(n)}
            for n in [
                "CREATED",
                "QUEUED",
                "RUNNING",
                "COMPLETED",
                "FAILED",
                "STOPPED",
                "SKIPPED",
            ]
        ],
        "transitions": [
            T("CREATED", "QUEUED", "allowed", s_vst_created),
            T("CREATED", "STOPPED", "allowed", s_vst_created),
            T("CREATED", "SKIPPED", "allowed", s_vst_created),
            T("QUEUED", "RUNNING", "TaskHandler starts", s_running),
            T("QUEUED", "FAILED", "executor setup fails", s_setup_failed),
            T("QUEUED", "STOPPED", "allowed", s_vst_queued),
            T("QUEUED", "SKIPPED", "allowed", s_vst_queued),
            T("RUNNING", "COMPLETED", "executor returns", s_completed),
            T("RUNNING", "FAILED", "executor raises", s_th_failed),
            T(
                "RUNNING",
                "STOPPED",
                "no agent actions left / stop requested",
                s_th_stopped,
            ),
            T("RUNNING", "SKIPPED", "SkippedTaskTransition", s_th_skipped),
            T("RUNNING", "QUEUED", "listener finds it stuck, resets", s_reset),
            T("FAILED", "QUEUED", "listener retries", s_reset),
            T("FAILED", "STOPPED", "allowed", s_vst_failed),
            T("COMPLETED", "STOPPED", "allowed", s_vst_completed),
        ],
    },
    {
        "title": "api_jobs lifecycle",
        "entity": "api_jobs.status",
        "states": [
            {"id": "queued", "label": "queued", "source": JS("QUEUED")},
            {"id": "processing", "label": "processing", "source": JS("PROCESSING")},
            {"id": "completed", "label": "completed", "source": JS("COMPLETED")},
            {"id": "failed", "label": "failed", "source": JS("FAILED")},
        ],
        "transitions": [
            T("queued", "processing", "activity claims job for this run", s_claim_life),
            T(
                "processing",
                "completed",
                "finalize with accepted result URI",
                s_finalize,
            ),
            T(
                "processing",
                "failed",
                "execution or persistence failed",
                s_record_failure,
            ),
            T(
                "queued",
                "failed",
                "failure recorded on unclaimed job",
                s_unclaimed_fail,
            ),
        ],
    },
    {
        "title": "Chat Redis stream lifecycle",
        "entity": "Redis stream chat:conversation:{id}:stream:{stream_id}",
        "states": [
            {"id": "initialized", "label": "INITIALIZED", "source": s_rs_init},
            {
                "id": "running",
                "label": "RUNNING (messages + heartbeats)",
                "source": s_rs_append,
            },
            {"id": "completed", "label": "COMPLETED", "source": s_rs_expire},
            {"id": "canceled", "label": "CANCELED", "source": s_rs_cancel},
            {"id": "timed_out", "label": "TIMED_OUT", "source": s_rs_timeout},
        ],
        "transitions": [
            T("initialized", "running", "producer appends first event", s_gen),
            T("running", "running", "heartbeat", s_rs_heartbeat),
            T(
                "running",
                "completed",
                "producer finishes: expire_stream",
                s_expire_call,
            ),
            T("running", "canceled", "cancel_stream (user cancel)", s_rs_cancel),
            T("running", "timed_out", "heartbeat fails", s_rs_timeout),
            T(
                "initialized",
                "canceled",
                "reserve or pre-spawn hook fails",
                s_start_fail,
            ),
        ],
    },
]

data = {
    "sql_tables": [
        "task_run",
        "task_run_log",
        "user_task_run",
        "conversation",
        "api_jobs",
    ],
    "nosql": [
        {
            "name": "chat:conversation:{conversation_id}:stream:{stream_id}",
            "kind": "Redis stream",
            "fields": [
                "type: initialized | message | heartbeat | completed | canceled | timed_out",
                "event: serialized chat event",
            ],
            "source": s_sdt,
        },
        {
            "name": "conversation messages",
            "kind": "DynamoDB (KV store)",
            "fields": [
                "conversation_id",
                "sort key {created_on_ms}#{message_id}",
                "rox_user_id",
                "message data",
            ],
            "source": s_sort_key,
        },
    ],
    "relations": [
        {
            "src": "user_task_run.run_id",
            "dst": "task_run.run_id",
            "label": "ORM primaryjoin",
            "source": S(
                "backend/src/rox_core/models/task.py",
                "user_task_run = relationship(",
                span=2,
            ),
        },
        {
            "src": "task_run_log.run_id",
            "dst": "task_run.run_id",
            "label": "written at queue time",
            "source": S(
                "backend/src/rox_core/api/tasks/business.py",
                "task_run_log = TaskRunLog(",
                span=2,
            ),
        },
        {
            "src": "task_run.parent_task_run_id",
            "dst": "task_run.run_id",
            "label": "parent in a task chain",
            "source": S(
                "backend/src/rox_core/models/task.py",
                "parent_task_run_id: Mapped[str | None] = mapped_column(",
                span=6,
            ),
        },
        {
            "src": "task_run.root_task_run_id",
            "dst": "task_run.run_id",
            "label": "root of a task chain",
            "source": S(
                "backend/src/rox_core/api/tasks/business.py",
                "root_task_run_id = task_run_id",
                end_needle="root_task_run_id = parent_task_run.root_task_run_id",
            ),
        },
        {
            "src": "conversation messages::conversation_id",
            "dst": "conversation.public_id",
            "label": "lookup by public_id",
            "source": S(
                "backend/src/chat/routes/conversation/service.py",
                "conversation = Conversation.find_by_public_id(",
                span=1,
                after="def get_tag_mapping(",
            ),
        },
        {
            "src": "chat:conversation:{conversation_id}:stream:{stream_id}",
            "dst": "conversation.public_id",
            "label": "key embeds conversation id",
            "source": S(
                "backend/src/chat/background_execution/stream_runner.py",
                "def _get_stream_key(conversation_id: str, stream_id: str) -> str:",
                span=1,
            ),
        },
        {
            "src": "chat:conversation:{conversation_id}:stream:{stream_id}",
            "dst": "conversation.redis_stream_id",
            "label": "stream id reserved on conversation",
            "source": s_reserve,
        },
    ],
}

related = [
    {
        "label": "Background chat streaming (README)",
        "url": f"https://github.com/Rox-AI/rox-core/blob/{COMMIT}/{BGREADME}",
        "source": s_bg_readme,
    },
    {
        "label": "ASCII architecture overview",
        "url": f"https://github.com/Rox-AI/rox-core/blob/{COMMIT}/{ASCII}",
        "source": s_ascii_hl,
    },
]

page = {
    "id": "rox-core",
    "title": "rox-core",
    "commit": COMMIT,
    "parent": None,
    "paths": ["."],
    "tldr": tldr,
    "block": {"groups": groups, "nodes": nodes, "edges": edges},
    "data": data,
    "sequences": sequences,
    "states": states,
    "related": related,
    "notion": notion,
}

out = Path(__file__).resolve().parents[1] / "rox-core.json"
out.write_text(json.dumps(page, indent=2, ensure_ascii=False) + "\n")
print("wrote", out, len(nodes), "nodes", len(edges), "edges")
