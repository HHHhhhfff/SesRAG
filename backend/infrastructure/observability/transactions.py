"""把提交结果通知到观测旁路；回调永不执行数据库或网络操作。"""

from contextlib import suppress

from sqlalchemy import event

_KEY = "sesrag_observation_callbacks"
_INSTALLED = "sesrag_observation_listeners"


def after_transaction(session, committed, rolled_back) -> None:
    sync = session.sync_session
    if not sync.in_transaction():
        raise ValueError("observation callback requires a transaction")
    if sync.in_nested_transaction():
        raise ValueError("nested transactions are not supported")
    callbacks = sync.info.setdefault(_KEY, [])
    if len(callbacks) >= 16:
        raise ValueError("too many observation callbacks")
    callbacks.append((committed, rolled_back))
    if sync.info.get(_INSTALLED):
        return
    sync.info[_INSTALLED] = True

    def finish(target, index):
        if target.in_nested_transaction():
            return
        for item in target.info.pop(_KEY, []):
            with suppress(Exception):
                item[index]()

    event.listen(sync, "after_commit", lambda target: finish(target, 0))
    event.listen(sync, "after_rollback", lambda target: finish(target, 1))
    event.listen(sync, "after_soft_rollback", lambda target, previous: finish(target, 1))
    event.listen(
        sync,
        "after_transaction_end",
        lambda target, transaction: finish(target, 1) if transaction.parent is None else None,
    )
