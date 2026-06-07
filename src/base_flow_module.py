"""
base_flow_module.py
===================
Abstract base class cho tất cả FlowModule.

Mỗi FlowModule cụ thể chỉ cần implement 2 method:
  - collect_items()  : xác định danh sách item cần xử lý
  - upload_item()    : upload 1 item lên GDrive

Toàn bộ orchestration (validate, load accounts, loop, log) được xử lý
bởi run() — không cần override.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path

import kaggle_utils

logger = logging.getLogger(__name__)


class FlowModule(ABC):
    """
    Base class cho mọi FlowModule.

    Subclass khai báo:
      - item_label (str)  : nhãn hiển thị trong log, vd "file" hoặc "work"
      - collect_items()   : trả về list[Path] các item cần xử lý
      - upload_item()     : upload 1 item, trả True/False
    """

    item_label: str = "item"  # subclass override để log đẹp hơn

    def __init__(self, flow: dict, flow_idx: int, total_flows: int, tmp_dir: Path):
        self.flow = flow
        self.flow_idx = flow_idx
        self.total_flows = total_flows
        self.tmp_dir = tmp_dir

    # ── Abstract interface ──────────────────────────────────────

    @abstractmethod
    def collect_items(self, local_data_input: str) -> list[Path]:
        """
        Xác định danh sách item cần xử lý từ thư mục đầu vào.
        Ví dụ: scan file (is_file) hoặc scan subfolder (is_dir).
        """
        ...

    @abstractmethod
    def upload_item(
        self,
        item: Path,
        gdrive_folder_url: str,
        rclone_config_path: str,
    ) -> bool:
        """Upload 1 item lên GDrive. Trả True nếu thành công."""
        ...

    # ── Template method — KHÔNG override ───────────────────────

    def run(self) -> None:
        """
        Orchestrate toàn bộ flow:
        validate config → load accounts → collect items → upload + trigger Kaggle.
        """
        flow = self.flow
        flow_idx = self.flow_idx

        # ── Đọc config ──────────────────────────────────────────
        local_data_input: str = flow.get("local_data_input", "")

        gdrive_cfg: dict = flow.get("gdrive", {})
        gdrive_folder_url: str = gdrive_cfg.get("upload_gdrive_folder_url", "")
        rclone_config_path: str = gdrive_cfg.get("rclone_config_path", "")

        kaggle_cfg: dict = flow.get("kaggle", {})
        notebooks: list = kaggle_cfg.get("notbooks", [])

        # ── Tìm notebook active (to_execute = true) ─────────────
        active_notebook: dict | None = next(
            (nb for nb in notebooks if nb.get("to_execute") is True), None
        )
        if active_notebook is None:
            logger.error(
                f"  ❌ Flow {flow_idx}: Không tìm thấy notebook nào có 'to_execute: true' "
                f"trong kaggle.notbooks — bỏ qua flow này."
            )
            return

        notebook_to_execute: str = active_notebook.get("notebook_to_execute", "")
        credentials_path: str = active_notebook.get("credentials_path", "")
        edit_vars: dict = active_notebook.get("edit_vars", {})

        # ── Log thông tin flow ───────────────────────────────────
        logger.info(f"   local_data_input   : {local_data_input}")
        logger.info(f"   gdrive_folder_url  : {gdrive_folder_url}")
        logger.info(f"   rclone_config_path : {rclone_config_path}")
        logger.info(f"   notebook_to_execute: {notebook_to_execute}  [to_execute=true]")
        logger.info(f"   credentials_path   : {credentials_path}")
        logger.info(f"   Tổng notebooks trong flow: {len(notebooks)} (chỉ 1 được chạy)")
        logger.info(f"{'═'*60}")

        # ── Validate các field bắt buộc ──────────────────────────
        missing = []
        if not local_data_input:
            missing.append("local_data_input")
        if not gdrive_folder_url:
            missing.append("gdrive.upload_gdrive_folder_url")
        if not rclone_config_path:
            missing.append("gdrive.rclone_config_path")
        if not notebook_to_execute:
            missing.append("kaggle.notbooks[to_execute].notebook_to_execute")
        if not credentials_path:
            missing.append("kaggle.notbooks[to_execute].credentials_path")

        if missing:
            logger.error(f"  ❌ Flow {flow_idx}: Thiếu các trường bắt buộc: {missing} — bỏ qua flow này.")
            return

        # ── Load Kaggle accounts ─────────────────────────────────
        try:
            kaggle_accounts = kaggle_utils.load_kaggle_accounts(credentials_path)
        except (FileNotFoundError, KeyError, ValueError) as e:
            logger.error(f"  ❌ Flow {flow_idx}: Không load được Kaggle credentials: {e} — bỏ qua flow này.")
            return

        # ── Collect items ────────────────────────────────────────
        items = self.collect_items(local_data_input)
        if not items:
            logger.warning(
                f"  ⚠️  Flow {flow_idx}: Không tìm thấy {self.item_label} nào "
                f"trong '{local_data_input}' — kết thúc flow."
            )
            return

        total = len(items)
        success = 0
        failed = 0

        # ── Loop từng item: upload → trigger Kaggle ──────────────
        for idx, item in enumerate(items, start=1):
            logger.info(f"\n  ── {self.item_label.capitalize()} {idx}/{total}: {item.name} ──")

            upload_ok = self.upload_item(item, gdrive_folder_url, rclone_config_path)
            if not upload_ok:
                logger.error(f"  ❌ Upload thất bại cho {item.name} — bỏ qua trigger Kaggle.")
                failed += 1
                continue

            kaggle_ok = kaggle_utils.trigger_kaggle_notebook(
                notebook_ref=notebook_to_execute,
                kaggle_accounts=kaggle_accounts,
                tmp_dir=self.tmp_dir,
                edit_vars=edit_vars if edit_vars else None,
            )
            if kaggle_ok:
                success += 1
                logger.info(f"  ✅ Hoàn tất {self.item_label} {idx}/{total}: {item.name}")
            else:
                failed += 1
                logger.error(f"  ❌ Trigger Kaggle thất bại cho {item.name}")

        # ── Summary ──────────────────────────────────────────────
        logger.info(f"\n  📊 Flow {flow_idx} hoàn tất — kết quả xử lý {total} {self.item_label}:")
        logger.info(f"     ✅ Thành công : {success}/{total}")
        logger.info(f"     ❌ Thất bại   : {failed}/{total}")
