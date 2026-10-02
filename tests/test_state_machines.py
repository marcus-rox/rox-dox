from rox_dox.state_machines import page_state_machines
from rox_dox.states import (
    Member,
    StateColumn,
    StateEnum,
    StateSet,
    StatesReport,
    Transition,
)


def _report() -> StatesReport:
    persisted = StateEnum(
        "TaskState",
        "backend/src/models/task.py",
        10,
        [Member("QUEUED", 11), Member("RUNNING", 12), Member("DONE", 13)],
        columns=[
            StateColumn("task_run", "current_state", "backend/src/models/task.py", 30)
        ],
        transitions=[
            Transition("QUEUED", "RUNNING", "backend/src/tasks/handler.py", 50),
            Transition("RUNNING", "DONE", "backend/src/tasks/handler.py", 70),
        ],
    )
    assigned = StateEnum(
        "SyncStatus",
        "backend/src/sync/status.py",
        5,
        [Member("IDLE", 6), Member("SYNCING", 7)],
        sets=[StateSet("SYNCING", "backend/src/sync/runner.py", 40)],
    )
    dto_only = StateEnum(
        "TicketState",
        "backend/src/sync/dto.py",
        3,
        [Member("OPEN", 4), Member("CLOSED", 5)],
    )
    return StatesReport("abc123", [persisted, assigned, dto_only], [])


def test_persisted_enum_is_selected_by_table_and_cites_members_and_transitions() -> (
    None
):
    machines = page_state_machines(_report(), paths=(), tables=["task_run"])

    assert [machine.title for machine in machines] == ["TaskState lifecycle"]
    (machine,) = machines
    assert machine.entity == "task_run.current_state"
    assert [(state.id, state.source.lines) for state in machine.states] == [
        ("QUEUED", (11, 11)),
        ("RUNNING", (12, 12)),
        ("DONE", (13, 13)),
    ]
    assert [(t.src, t.dst, t.event) for t in machine.transitions] == [
        ("QUEUED", "RUNNING", "handler.py:50"),
        ("RUNNING", "DONE", "handler.py:70"),
    ]


def test_assignment_site_in_page_files_selects_enum_but_dto_only_enum_is_skipped() -> (
    None
):
    machines = page_state_machines(
        _report(),
        paths=["backend/src/sync/runner.py", "backend/src/sync/dto.py"],
        tables=[],
    )

    assert [machine.title for machine in machines] == ["SyncStatus lifecycle"]
    assert machines[0].entity == "SyncStatus"
    assert machines[0].transitions == []


def test_missing_report_yields_no_state_machines() -> None:
    assert page_state_machines(None, paths=["x.py"], tables=["t"]) == []
