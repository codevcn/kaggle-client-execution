"""
flow_modules/align_music_lyrics.py
====================================
Flow 4: Align lyrics khớp với bài hát

Đơn vị xử lý : subfolder / work dir (is_dir)
                mỗi subfolder chứa: <tên bài>.wav + <tên bài>.txt
Upload        : rclone sync toàn bộ thư mục lên GDrive (không cần staging)
"""

import logging
from pathlib import Path

import kaggle_utils
from base_flow_module import FlowModule as _FlowModule

logger = logging.getLogger(__name__)


class Module(_FlowModule):
    item_label = "work"

    def collect_items(self, local_data_input: str) -> list[Path]:
        folder = Path(local_data_input)
        if not folder.exists():
            logger.warning(f"  ⚠️  Thư mục local_data_input không tồn tại: {folder}")
            return []

        works = sorted([d for d in folder.iterdir() if d.is_dir()])
        logger.info(f"  📂 Tìm thấy {len(works)} work (sub-dir) trong {folder}")
        return works

    def upload_item(self, item: Path, gdrive_folder_url: str, rclone_config_path: str) -> bool:
        return kaggle_utils.upload_dir_to_gdrive(
            dir_path=item,
            gdrive_folder_url=gdrive_folder_url,
            rclone_config_path=rclone_config_path,
        )
