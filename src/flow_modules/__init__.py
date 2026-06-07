# flow_modules/__init__.py
# Mỗi FlowModule trong package này phải:
#   1. Extend FlowModule từ base_flow_module.py
#   2. Implement collect_items() và upload_item()
#   3. Đặt tên class là `Module` (convention để main.py dispatch động)
