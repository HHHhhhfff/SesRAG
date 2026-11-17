"""005入口中断/资源重入演练；不终止或重建应用。"""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers.lifecycle import Environment
from helpers.preflight import MODULE, MonitoringError, load
from live_validation import wait


def main():
    e = Environment("verify005")
    error = None
    try:
        e.reconcile()
        e.check_drift()
        e.stop()
        # 新进程真实Start，看到已建容器后硬杀主Python，下一次动作依账本和标签收束。
        process = subprocess.Popen(
            [
                sys.executable,
                "-X",
                "utf8",
                str(MODULE / "helpers/cli.py"),
                "Start",
                "--environment",
                "verify005",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            wait(e, "Start已进入创建阶段", lambda: len(e.inventory()["container"]) >= 3, 90, 1)
            process.kill()
            process.wait(timeout=10)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
        time.sleep(2)
        e.state = load(e.path / "ledger.json")
        e.stop()
        if e.inventory()["container"] or e.inventory()["network"]:
            raise MonitoringError("OBS005_HARD_KILL_REMAINS")
        e.check(
            "入口主进程硬杀后重入清理", "passed", "五卷保留；实际容器/临时工具/网络按完整标签清理"
        )
        # 在当前进程模拟控制台中断到达临时容器等待；临时容器的CID必须被finally回收。
        import threading

        before = {x["id"] for x in e.inventory()["container"]}

        def interrupt():
            time.sleep(2)
            import _thread

            _thread.interrupt_main()

        timer = threading.Thread(target=interrupt, daemon=True)
        timer.start()
        caught = False
        try:
            e.tool(["-c", "import time;time.sleep(60)"], network=False, timeout=20)
        except KeyboardInterrupt:
            caught = True
        except MonitoringError as exc:
            if exc.code != "OBS005_COMMAND_TIMEOUT":
                raise
            # Windows管道communicate可能到timeout边界才处理中断，不把超时计作Ctrl+C通过。
        if not caught:
            raise MonitoringError("OBS005_INTERRUPT_NOT_OBSERVED")
        if {x["id"] for x in e.inventory()["container"]} != before:
            raise MonitoringError("OBS005_INTERRUPT_REMAINS")
        e.check("Ctrl+C受控中断", "passed", "等待子进程时触发KeyboardInterrupt，CLI和CID容器均回收")
        e.start()
    except BaseException as exc:
        error = exc
        print(str(exc), flush=True)
    finally:
        e.finish(error)
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
