import argparse
import json
import subprocess
from pathlib import Path

from rox_dox.model import Page

DEFAULT_REPO = Path("/home/ubuntu/repos/rox-core")
argument_parser = argparse.ArgumentParser(
    description="Regenerate the cited Activity domain and feature pages."
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
    return {"text": text, "sources": list(sources)}


def D(text: str, *sources: dict[str, object]) -> dict[str, object]:
    if not 1 <= len(text) <= 90:
        raise SystemExit(f"detail too long ({len(text)}): {text}")
    return C(text, *sources)


def N(
    id: str,
    label: str,
    group: str,
    source: dict[str, object],
    details: list[dict[str, object]] | None = None,
    *,
    kind: str = "component",
    many: bool = False,
) -> dict[str, object]:
    return {
        "id": id,
        "label": label,
        "source": source,
        "kind": kind,
        "group": group,
        "many": many,
        "details": details or [],
    }


def E(
    src: str,
    dst: str,
    label: str,
    source: dict[str, object],
) -> dict[str, object]:
    return {"src": src, "dst": dst, "label": label, "source": source}


RN = "backend/src/rox_core/api/register_namespaces.py"
IEP = "backend/src/rox_core/api/integrations/endpoints.py"
IBUS = "backend/src/rox_core/api/integrations/business.py"
TIEP = "backend/src/rox_core/api/tasks/integrations/endpoints.py"
TSVC = "backend/src/rox_core/api/tasks/services.py"
WR = "backend/src/rox_core/api/webhook_integrations/webhook_router.py"
MSEP = "backend/src/rox_core/api/msteams_agent/endpoints.py"
MSBP = "backend/src/rox_core/api/msteams_agent/webhook_bp.py"
INIT = "backend/src/rox_core/__init__.py"
TYPES = "backend/src/tasks/types.py"
LU = "backend/src/util/listener_utils.py"
CIS = "backend/src/temporal/workflows/calendar_initial_sync.py"
OCB = "backend/src/temporal/workflows/orgwide_calendar_backfill.py"
CEX = "backend/src/tasks/executors/calendar_extract_and_persist_events.py"
EDS = "backend/src/ext_integrations/email_integration/email_data_store.py"
SCR = "backend/src/tasks/executors/sync_call_recorder_transcripts.py"
BGC = "backend/src/ext_integrations/calendar_integration/base_google_calendar.py"
BMC = "backend/src/ext_integrations/calendar_integration/base_microsoft_calendar.py"
AIF = "backend/src/ext_integrations/integration/admin_integration_fanout.py"
TEAMS_HANDLER = "backend/src/ext_integrations/ms_teams/event_handler.py"
CALENDAR_CHUNK = "backend/src/temporal/activities/calendar_sync/enqueue_chunk.py"
GOOGLE_CALENDAR = "backend/src/ext_integrations/calendar_integration/google_calendar.py"
INTEGRATION_MODEL = "backend/src/rox_core/models/integration.py"
CALENDAR_EVENT_MODEL = "backend/src/rox_core/models/public_calendar_event.py"
EMAIL_MESSAGE_MODEL = "backend/src/rox_core/models/public_email_message.py"
ADHOC_EVENT_MODEL = "backend/src/rox_core/models/public_adhoc_event.py"
NOTE_MODEL = "backend/src/rox_core/models/note.py"

s_web_list = S(IEP, '@integrations_ns.route("", endpoint="integration_list")')
s_web_create = S(IEP, "integration = create_integration(")
s_push_calendar = S(TIEP, 'channel_id = request.headers.get("X-Goog-Channel-ID")')
s_push_teams = S(MSEP, '@msteams_agent_ns.route("/events"')
s_push_webhook = S(WR, '@webhook_bp.route("/<endpoint_slug>", methods=["POST"])')
s_interaction = S(RN, 'api.add_namespace(integrations_ns, path="/integrations"')
s_calendar_namespace = S(
    RN, 'api.add_namespace(calendar_events_ns, path="/calendar_events"'
)
s_notify_calendar = S(TIEP, '"/notify_calendar_change",')
s_webhook = S(
    WR,
    'webhook_bp = Blueprint("webhook_receiver"',
    '@webhook_bp.route("/<endpoint_slug>", methods=["POST"])',
)
s_calendar_workflow = S(CIS, '@workflow.defn(name="CalendarInitialSyncWorkflow"')
s_orgwide_workflow = S(OCB, '@workflow.defn(name="OrgwideCalendarBackfillWorkflow"')
s_integration_queues = S(
    TYPES,
    "class IntegrationQueueType(TaskQueueType):",
    "EMAIL_SEND = QueueTypeInfo",
)
s_webhook_queue_type = S(TYPES, "WEBHOOK_COORDINATOR = QueueTypeInfo(", span=2)
s_calendar_worker = S(
    CEX, "class CalendarExtractionCoordinatorTaskExecutor(TaskExecutor):"
)
s_email_ingest = S(
    EDS,
    "def materialize_events(",
    '"""Upsert EmailMessage + recipients',
)
s_call_recorder = S(
    SCR,
    "from ext_integrations.call_recorders.attention.service import AttentionSyncService",
    "from ext_integrations.call_recorders.zoom.service import ZoomSyncService",
)
s_integration_model = S(INTEGRATION_MODEL, "class Integration(Base):")
s_integration_preferences = S(INTEGRATION_MODEL, "class IntegrationPreferences(Base):")
s_calendar_event_model = S(CALENDAR_EVENT_MODEL, "class PublicCalendarEvent(Base):")
s_email_message_model = S(
    EMAIL_MESSAGE_MODEL,
    "class PublicEmailMessage(EmailRecipientPropertiesMixin, Base):",
)
s_adhoc_event_model = S(ADHOC_EVENT_MODEL, "class PublicAdhocEvent(Base):")
s_note_model = S(NOTE_MODEL, "class Note(CompanyIdentifierBaseRoxModelWithUser):")
s_email_blob = S(EDS, "self.email_blob_store.upload_data(key, content)")
s_google_api = S(BGC, "from googleapiclient.errors import HttpError")
s_microsoft_graph = S(BMC, 'BASE_GRAPH_URL = "https://graph.microsoft.com/v1.0"')
s_integration_status_model = S(INTEGRATION_MODEL, "class IntegrationStatus(Base):")
s_external_mapping_model = S(
    INTEGRATION_MODEL, "class IntegrationExternalMapping(Base):"
)
s_email_mapping_model = S(INTEGRATION_MODEL, "class IntegrationEmailMapping(Base):")
s_linkedin_mapping_model = S(
    INTEGRATION_MODEL, "class IntegrationLinkedinMapping(Base):"
)
s_calendar_email_mapping_model = S(
    INTEGRATION_MODEL, "class IntegrationCalendarEmailMapping(Base):"
)

s_calendar_change = S(TIEP, "process_calendar_change(channel_id, token)")
s_register_push_blueprints = S(
    INIT,
    "app.register_blueprint(msteams_webhook_bp)",
    "app.register_blueprint(webhook_bp)",
)
s_save_integration = S(
    IBUS,
    "trx_mgr.session.add(integration)",
    after="def _create_integration(",
)
s_start_initial_sync = S(IBUS, "CalendarInitialSyncWorkflow.run,")
s_calendar_queue = S(
    TSVC,
    "queue_task(",
    after="def schedule_calendar_extraction_coordinator_task(",
)
s_raw_webhook_queue = S(WR, "queue_task(", after="def handle_webhook(")
s_calendar_chunk_queue = S(
    CALENDAR_CHUNK,
    "queue_task(",
    after="def enqueue_calendar_chunk_task(",
)
s_listener_poll = S(LU, '"INTEGRATION": ("integration", "IntegrationQueueType"),')
s_write_email_messages = S(EDS, '"""Upsert EmailMessage + recipients')
s_worker_upload = S(EDS, "self.email_blob_store.upload_data(key, content)")
s_teams_queue = S(
    TEAMS_HANDLER,
    "queue_task(",
    after="def handle_msteams_event(",
)

domain_groups = [
    {"id": "callers", "label": "Callers", "source": s_web_list},
    {"id": "services", "label": "HTTP services", "source": s_interaction},
    {"id": "workflows", "label": "Workflows", "source": s_calendar_workflow},
    {"id": "queues", "label": "Queues", "source": s_integration_queues},
    {
        "id": "background-workers",
        "label": "Background workers",
        "source": s_calendar_worker,
    },
    {"id": "stores", "label": "Stores", "source": s_integration_model},
    {
        "id": "provider-apis",
        "label": "Provider APIs",
        "source": s_microsoft_graph,
    },
]
domain_nodes = [
    N(
        "web",
        "web app",
        "callers",
        s_web_list,
        [D("Connect, list and configure integrations", s_web_list)],
    ),
    N(
        "push",
        "Provider push",
        "callers",
        s_push_calendar,
        [
            D("Google Calendar change notifications", s_push_calendar),
            D("Microsoft Teams bot events", s_push_teams),
            D("Customer webhooks (HMAC or API key)", s_push_webhook),
        ],
        kind="external",
    ),
    N(
        "interaction",
        "INTERACTION (Flask)",
        "services",
        s_interaction,
        [
            D(
                "/integrations: create, list, preferences",
                s_interaction,
            ),
            D(
                "/calendar_events, /email_integration",
                s_calendar_namespace,
            ),
            D("/tasks/integrations/notify_calendar_change", s_notify_calendar),
        ],
        many=True,
    ),
    N(
        "webhook",
        "WEBHOOK (Flask)",
        "services",
        s_webhook,
        [
            D(
                "/webhooks/msteams_agent/events",
                S(MSBP, 'api.add_namespace(msteams_agent_ns, path="/msteams_agent")'),
            ),
            D(
                "/webhooks/w/<slug> generic webhooks",
                s_webhook,
            ),
        ],
        many=True,
    ),
    N(
        "temporal",
        "Temporal sync workflows",
        "workflows",
        s_calendar_workflow,
        [
            D(
                "Per-user calendar and email initial sync",
                s_calendar_workflow,
            ),
            D(
                "Org-wide calendar and email backfill",
                s_orgwide_workflow,
            ),
        ],
        kind="queue",
    ),
    N(
        "sqs",
        "SQS queues",
        "queues",
        s_integration_queues,
        [
            D(
                "Calendar, email, LinkedIn extraction queues",
                s_integration_queues,
            ),
            D("WEBHOOK_COORDINATOR: inbound webhook fan-out", s_webhook_queue_type),
        ],
        kind="queue",
        many=True,
    ),
    N(
        "workers",
        "Integration workers",
        "background-workers",
        s_calendar_worker,
        [
            D(
                "Calendar extraction: fetch and persist events",
                s_calendar_worker,
            ),
            D("Email ingest: upsert messages and recipients", s_email_ingest),
            D("Call-recorder transcript sync", s_call_recorder),
        ],
        many=True,
    ),
    N(
        "postgres",
        "PostgreSQL",
        "stores",
        s_integration_model,
        [
            D(
                "integration, integration_preferences",
                s_integration_model,
                s_integration_preferences,
            ),
            D(
                "calendar_event, email_message, adhoc_event, note",
                s_calendar_event_model,
                s_email_message_model,
                s_adhoc_event_model,
                s_note_model,
            ),
        ],
        kind="store",
    ),
    N(
        "s3",
        "S3 email blobs",
        "stores",
        s_email_blob,
        [D("Email bodies and attachments", s_email_blob)],
        kind="store",
    ),
    N(
        "providers",
        "Provider APIs",
        "provider-apis",
        s_microsoft_graph,
        [
            D("Google Calendar and Gmail", s_google_api),
            D("Microsoft Graph", s_microsoft_graph),
            D("Zoom, Gong, Avoma, Attention, Granola", s_call_recorder),
        ],
        kind="external",
    ),
]
domain_edges = [
    E("web", "interaction", "connect / list", s_web_create),
    E("push", "interaction", "calendar changed", s_calendar_change),
    E("push", "webhook", "Teams events, webhooks", s_register_push_blueprints),
    E("interaction", "postgres", "save integration", s_save_integration),
    E("interaction", "temporal", "start initial sync", s_start_initial_sync),
    E("interaction", "sqs", "enqueue calendar refresh", s_calendar_queue),
    E("webhook", "sqs", "queue raw payload", s_raw_webhook_queue),
    E("webhook", "sqs", "queue Teams event", s_teams_queue),
    E("temporal", "sqs", "enqueue sync chunks", s_calendar_chunk_queue),
    E("sqs", "workers", "long-poll", s_listener_poll),
    E("workers", "postgres", "write events, messages", s_write_email_messages),
    E("workers", "s3", "upload email content", s_worker_upload),
    E("workers", "providers", "pull events, mail, transcripts", s_microsoft_graph),
]
domain_note = C(
    "Steps: 1 connect → 2 save + start sync → 3 workflows enqueue chunks → "
    "4 workers pull from providers → 5 write Postgres/S3; provider pushes enter "
    "via INTERACTION or WEBHOOK and join at the queue.",
    s_web_create,
    s_start_initial_sync,
    s_calendar_chunk_queue,
    s_microsoft_graph,
)
domain_page = {
    "id": "domain-activity",
    "title": "Activity integrations",
    "kind": "domain",
    "commit": COMMIT,
    "parent": "rox-core",
    "paths": ["backend/src/ext_integrations"],
    "tldr": {
        "summary": [domain_note],
        "key_points": [],
        "table": {
            "columns": ["component", "role"],
            "rows": [
                [
                    node["label"],
                    next(
                        group["label"]
                        for group in domain_groups
                        if group["id"] == node["group"]
                    ),
                ]
                for node in domain_nodes
            ],
            "sources": [node["source"] for node in domain_nodes],
        },
        "notes": [],
    },
    "block": {
        "groups": domain_groups,
        "nodes": domain_nodes,
        "edges": domain_edges,
        "notes": [domain_note],
    },
    "block_figures": [],
    "data": {
        "sql_tables": [],
        "nosql": [],
        "relations": [],
        "domains": [],
        "columns": [],
    },
    "sequences": [],
    "states": [],
    "related": [{"label": "rox-core", "page": "rox-core", "source": s_web_list}],
}

s_settings = S(
    IEP,
    '@integrations_ns.route("/preferences/<id>", endpoint="integration_preferences")',
)
s_oauth_callback = S(GOOGLE_CALENDAR, "/api/integrations/gcal/callback")
s_integration_route = S(
    IEP,
    '@integrations_ns.route("/<id>", endpoint="integration")',
    '@integrations_ns.route("/integration_status/<id>", endpoint="integration_status")',
)
s_integration_status_route = S(
    IEP,
    '@integrations_ns.route("/integration_status/<id>", endpoint="integration_status")',
)
s_fanout = S(AIF, "def fan_out_tasks_for_integrations(")
s_orgwide_start = S(AIF, "def try_start_orgwide_calendar_temporal_workflow(")
s_feature_queues = S(
    TYPES,
    "CALENDAR_EXTRACTION_COORDINATOR = QueueTypeInfo(",
    "EMAIL_INTEGRATION = QueueTypeInfo(",
)
s_integration_status_write = S(CEX, "stmt = pg_insert(IntegrationStatus).values(")
s_microsoft_graph = S(BMC, 'BASE_GRAPH_URL = "https://graph.microsoft.com/v1.0"')

feature_groups = [
    {"id": "callers", "label": "Callers", "source": s_settings},
    {"id": "services", "label": "HTTP services", "source": s_integration_route},
    {"id": "workflows", "label": "Workflows", "source": s_calendar_workflow},
    {"id": "queues", "label": "Queues", "source": s_feature_queues},
    {
        "id": "background-workers",
        "label": "Background workers",
        "source": s_calendar_worker,
    },
    {"id": "stores", "label": "Stores", "source": s_integration_model},
    {
        "id": "provider-apis",
        "label": "Provider APIs",
        "source": s_google_api,
    },
]
feature_nodes = [
    N(
        "web",
        "web app",
        "callers",
        s_settings,
        [D("Settings: connect, preferences, status", s_settings)],
    ),
    N(
        "oauth",
        "Google / Microsoft OAuth",
        "callers",
        s_oauth_callback,
        [D("Redirects back to /api/integrations/gcal/callback", s_oauth_callback)],
        kind="external",
    ),
    N(
        "interaction",
        "INTERACTION /integrations",
        "services",
        s_integration_route,
        [
            D(
                "create, get, update, delete integration",
                s_integration_route,
            ),
            D("preferences and integration_status", s_integration_status_route),
            D("admin connect fans out to every user", s_fanout),
        ],
        many=True,
    ),
    N(
        "temporal",
        "Temporal sync workflows",
        "workflows",
        s_calendar_workflow,
        [
            D("CalendarInitialSync, EmailInitialSync", s_calendar_workflow),
            D("Org-wide backfill for admin installs", s_orgwide_start),
        ],
        kind="queue",
    ),
    N(
        "sqs",
        "SQS integration queues",
        "queues",
        s_feature_queues,
        [
            D(
                "Calendar and email extraction coordinators",
                s_feature_queues,
            )
        ],
        kind="queue",
        many=True,
    ),
    N(
        "workers",
        "Integration workers",
        "background-workers",
        s_calendar_worker,
        [D("Calendar extraction coordinator", s_calendar_worker)],
        many=True,
    ),
    N(
        "postgres",
        "PostgreSQL",
        "stores",
        s_integration_model,
        [
            D(
                "integration, integration_preferences",
                s_integration_model,
                s_integration_preferences,
            ),
            D(
                "integration_*_mapping, integration_status",
                s_email_mapping_model,
                s_linkedin_mapping_model,
                s_calendar_email_mapping_model,
                s_external_mapping_model,
                s_integration_status_model,
            ),
        ],
        kind="store",
    ),
    N(
        "providers",
        "Google / Microsoft APIs",
        "provider-apis",
        s_google_api,
        [
            D("Google Calendar and Gmail", s_google_api),
            D("Microsoft Graph", s_microsoft_graph),
        ],
        kind="external",
    ),
]
feature_edges = [
    E("web", "interaction", "connect", s_web_create),
    E("oauth", "interaction", "OAuth callback", s_oauth_callback),
    E("interaction", "postgres", "save integration", s_save_integration),
    E("interaction", "temporal", "start initial sync", s_start_initial_sync),
    E("temporal", "sqs", "enqueue sync chunks", s_calendar_chunk_queue),
    E("sqs", "workers", "long-poll", s_listener_poll),
    E(
        "workers",
        "postgres",
        "update integration status",
        s_integration_status_write,
    ),
    E("workers", "providers", "fetch events", s_microsoft_graph),
]
feature_note = C(
    "1 connect → 2 save integration and start sync → 3 Temporal enqueues "
    "extraction chunks → 4 SQS workers update status and fetch provider events.",
    s_web_create,
    s_save_integration,
    s_start_initial_sync,
    s_calendar_chunk_queue,
    s_integration_status_write,
    s_microsoft_graph,
)
feature_page = {
    "id": "feature-activity-integration",
    "title": "Integration connections & sync",
    "kind": "feature",
    "commit": COMMIT,
    "parent": "domain-activity",
    "paths": ["backend/src/rox_core/api/integrations"],
    "tldr": {
        "summary": [feature_note],
        "key_points": [],
        "table": {
            "columns": ["component", "role"],
            "rows": [
                [
                    node["label"],
                    next(
                        group["label"]
                        for group in feature_groups
                        if group["id"] == node["group"]
                    ),
                ]
                for node in feature_nodes
            ],
            "sources": [node["source"] for node in feature_nodes],
        },
        "notes": [],
    },
    "block": {
        "groups": feature_groups,
        "nodes": feature_nodes,
        "edges": feature_edges,
    },
    "block_figures": [],
    "data": {
        "sql_tables": [],
        "nosql": [],
        "relations": [],
        "domains": [],
        "columns": [],
    },
    "sequences": [],
    "states": [],
    "related": [
        {
            "label": "Activity integrations",
            "page": "domain-activity",
            "source": s_interaction,
        }
    ],
}


def write_page(page: dict[str, object], filename: str) -> None:
    Page.model_validate(page)
    output = Path(__file__).resolve().parents[1] / filename
    output.write_text(json.dumps(page, indent=2, ensure_ascii=False) + "\n")
    block = page["block"]
    print(
        "wrote",
        output,
        len(block["nodes"]),
        "nodes",
        len(block["edges"]),
        "edges",
    )


write_page(domain_page, "domain-activity.json")
write_page(feature_page, "feature-activity-integration.json")
