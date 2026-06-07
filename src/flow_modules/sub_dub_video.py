"""
flow_modules/sub_dub_video.py
==============================
Flow 2: Tạo phụ đề & lồng tiếng cho video

Đơn vị xử lý : file audio (is_file)
Upload        : rclone sync qua staging dir tạm (1 file tại 1 thời điểm)
"""

import logging
from pathlib import Path

import kaggle_utils
from base_flow_module import FlowModule as _FlowModule

logger = logging.getLogger(__name__)


class Module(_FlowModule):
    item_label = "file"

    def collect_items(self, local_data_input: str) -> list[Path]:
        folder = Path(local_data_input)
        if not folder.exists():
            logger.warning(f"  ⚠️  Thư mục local_data_input không tồn tại: {folder}")
            return []

        files = sorted([f for f in folder.iterdir() if f.is_file()])
        logger.info(f"  📂 Tìm thấy {len(files)} file trong {folder}")
        return files

    def upload_item(self, item: Path, gdrive_folder_url: str, rclone_config_path: str) -> bool:
        return kaggle_utils.upload_file_to_gdrive(
            file_path=item,
            gdrive_folder_url=gdrive_folder_url,
            rclone_config_path=rclone_config_path,
            tmp_dir=self.tmp_dir,
        )
