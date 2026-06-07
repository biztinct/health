#!/usr/bin/env python3
"""Apply reviewed healthcare CRM terminology outside markup and placeholders."""

import argparse
import ast
import json
import pathlib
import re


TAG_RE = re.compile(r"(<[^>]+>)")
PROTECTED_RE = re.compile(
    r"\{\{.*?\}\}|\{%.*?%\}|"
    r"%(?:\([^)]+\))?[#0 +\-]?\d*(?:\.\d+)?[a-zA-Z](?!\w)"
    r"|\{\w+\}"
    r"|&[a-zA-Z0-9#]+;"
    r"|(?:[a-zA-Z_][a-zA-Z0-9_]*\.)+[a-zA-Z_][a-zA-Z0-9_]*"
    r"|⚠️|✔|👤|🔍|←|→|•|·|●"
, re.DOTALL)

REPLACEMENTS = [
    ("Đăng sách bị mất", "MẤT LỊCH HẸN"),
    ("đặt sách", "lịch hẹn"),
    ("Đặt sách", "Lịch hẹn"),
    ("sổ sách", "lịch hẹn"),
    ("Sổ sách", "Lịch hẹn"),
    ("đặt phòng", "lịch hẹn"),
    ("Đặt phòng", "Lịch hẹn"),
    ("đặt chỗ", "lịch hẹn"),
    ("Đặt chỗ", "Lịch hẹn"),
    ("đặt trước", "lịch hẹn"),
    ("Đặt trước", "Lịch hẹn"),
    ("những người dẫn đầu", "khách hàng tiềm năng"),
    ("Những người dẫn đầu", "Khách hàng tiềm năng"),
    ("người dẫn đầu", "khách hàng tiềm năng"),
    ("Người dẫn đầu", "Khách hàng tiềm năng"),
    ("các dẫn đầu", "các khách hàng tiềm năng"),
    ("Các dẫn đầu", "Các khách hàng tiềm năng"),
    ("dẫn đầu", "khách hàng tiềm năng"),
    ("Dẫn đầu", "Khách hàng tiềm năng"),
    ("Thông tin dẫn", "Thông tin khách hàng tiềm năng"),
    ("lead", "khách hàng tiềm năng"),
    ("Lead", "Khách hàng tiềm năng"),
    ("LEAD", "KHÁCH HÀNG TIỀM NĂNG"),
    ("wizard", "trình hướng dẫn"),
    ("Wizard", "Trình hướng dẫn"),
    ("SPAM CALLER", "NGƯỜI GỌI THƯ RÁC"),
    ("Spam Caller", "Người gọi thư rác"),
    ("spam caller", "người gọi thư rác"),
    ("SPAM", "THƯ RÁC"),
    ("Spam", "Thư rác"),
    ("spam", "thư rác"),
    ("Contact", "Liên hệ"),
    ("contact", "liên hệ"),
    ("Client", "Khách hàng"),
    ("client", "khách hàng"),
    ("Booking", "Lịch hẹn"),
    ("booking", "lịch hẹn"),
    ("Staff", "Nhân viên"),
    ("staff", "nhân viên"),
    ("Activity", "Hoạt động"),
    ("activity", "hoạt động"),
    ("Meeting", "Cuộc họp"),
    ("meeting", "cuộc họp"),
    ("Source", "Nguồn"),
    ("source", "nguồn"),
    ("Search", "Tìm kiếm"),
    ("search", "tìm kiếm"),
    ("Mark Junk", "Đánh dấu là rác"),
    ("Mark Thư rác", "Đánh dấu là thư rác"),
    ("Use Existing Liên hệ", "Sử dụng liên hệ hiện có"),
    ("Call/Email/To-Do/Cuộc họp", "Gọi/Email/Việc cần làm/Cuộc họp"),
    ("rác/thư rác", "rác hoặc thư rác"),
    ("Đánh dấu là spam", "Đánh dấu là thư rác"),
    ("Log New", "Ghi nhận mới"),
    ("Log ", "Ghi nhận "),
    ("Skip", "Bỏ qua"),
    ("View", "Chế độ xem"),
    ("New/Active", "Mới/Đang hoạt động"),
    ("New", "Mới"),
    ("Create", "Tạo"),
    ("Save", "Lưu"),
    ("Hình danh", "ID"),
    ("Dễ hoạt", "Đang hoạt động"),
    ("Tốc độ", "Mức độ khẩn cấp"),
    ("tăng lên", "chuyển cấp"),
    ("Tăng lên", "Chuyển cấp"),
    ("tăng cường", "chuyển cấp"),
    ("Tăng cường", "Chuyển cấp"),
    ("leo thang", "chuyển cấp"),
    ("Leo thang", "Chuyển cấp"),
    ("Ủy ban", "hoa hồng"),
    ("Tiếp tục quá thời gian", "Theo dõi quá hạn"),
    ("Hãng đường ống tiếp xúc", "Quy trình liên hệ"),
    ("Tags liên lạc", "Thẻ liên hệ"),
    ("Tags liên hệ", "Thẻ liên hệ"),
    ("\n                            Sáng\n", "\n                            Khách hàng tiềm năng\n"),
    ("Thư rác Call", "Cuộc gọi thư rác"),
    ("Lịch hẹn bị mất", "Mất lịch hẹn"),
    ("Phụ phần trăm của hoa hồng", "Tỷ lệ hoa hồng"),
    ("Đường ống", "Quy trình"),
    ("Tiềm năng", "Khách hàng tiềm năng"),
    ("NGƯỜI GỌI THƯ RÁC được phát hiện", "ĐÃ PHÁT HIỆN NGƯỜI GỌI THƯ RÁC"),
    ("Người gọi thư rác được phát hiện", "Đã phát hiện người gọi thư rác"),
]

OVERRIDES = {
    "%(type)s: %(contact)s": "%(type)s: %(contact)s",
    "Active": "Đang hoạt động",
    "Active Pipeline": "Quy trình đang hoạt động",
    "Apply to All Bookings": "Áp dụng cho tất cả lịch hẹn",
    "Booking Lost": "Mất lịch hẹn",
    "Booking Lost Reason": "Lý do mất lịch hẹn",
    "Booking Creation Wizard": "Trình hướng dẫn tạo lịch hẹn",
    "Booking Lost Reason Wizard": "Trình hướng dẫn lý do mất lịch hẹn",
    "Bookings": "Các lịch hẹn",
    "Cancelling booking for:": "Đang hủy lịch hẹn cho:",
    "Contact Action Selector": "Bộ chọn hành động liên hệ",
    "Contact Escalation/Consultation Wizard": "Trình hướng dẫn chuyển cấp/tham vấn liên hệ",
    "Contact Pipeline": "Quy trình liên hệ",
    "Contact Status": "Trạng thái liên hệ",
    "Commission %": "Tỷ lệ hoa hồng (%)",
    "Escalate": "Chuyển cấp",
    "Escalated": "Đã chuyển cấp",
    "Explain why this contact needs to be escalated...": "Hãy giải thích lý do cần chuyển cấp liên hệ này...",
    "Family Registration Book (Sổ hộ khẩu)": "Sổ hộ khẩu",
    "Follow-ups": "Theo dõi",
    "From Excel: Lead Status field": "Từ Excel: Trường trạng thái khách hàng tiềm năng",
    "Lead": "Khách hàng tiềm năng",
    "Lead Status": "Trạng thái khách hàng tiềm năng",
    "Log New Lead": "Ghi nhận khách hàng tiềm năng mới",
    "Mark Junk": "Đánh dấu là rác",
    "Mark Spam": "Đánh dấu là thư rác",
    "Overdue Follow-ups": "Theo dõi quá hạn",
    "Source Wizard": "Trình hướng dẫn nguồn",
    "Spam": "Thư rác",
    "Spam Caller": "Người gọi thư rác",
    "SPAM CALLER DETECTED": "ĐÃ PHÁT HIỆN NGƯỜI GỌI THƯ RÁC",
    "Urgency": "Mức độ khẩn cấp",
}


def decode_po_string(line):
    value = line.strip()
    if value.startswith(("msgid ", "msgstr ")):
        value = value.split(" ", 1)[1]
    return ast.literal_eval(value)


def load_mapping(path):
    if path.suffix != ".po":
        return json.loads(path.read_text(encoding="utf-8"))

    lines = path.read_text(encoding="utf-8").splitlines()
    mapping = {}
    index = 0
    while index < len(lines):
        if not lines[index].startswith("msgid "):
            index += 1
            continue
        msgid = decode_po_string(lines[index])
        index += 1
        while index < len(lines) and lines[index].startswith('"'):
            msgid += decode_po_string(lines[index])
            index += 1
        if index >= len(lines) or not lines[index].startswith("msgstr "):
            continue
        msgstr = decode_po_string(lines[index])
        index += 1
        while index < len(lines) and lines[index].startswith('"'):
            msgstr += decode_po_string(lines[index])
            index += 1
        if msgid:
            mapping[msgid] = msgstr
    return mapping


def replace_text(text):
    parts = []
    position = 0
    for match in PROTECTED_RE.finditer(text):
        segment = text[position : match.start()]
        for old, new in REPLACEMENTS:
            segment = segment.replace(old, new)
        parts.extend((segment, match.group(0)))
        position = match.end()
    segment = text[position:]
    for old, new in REPLACEMENTS:
        segment = segment.replace(old, new)
    parts.append(segment)
    return "".join(parts)


def review_translation(text):
    parts = TAG_RE.split(text)
    for index, part in enumerate(parts):
        if not TAG_RE.fullmatch(part or ""):
            parts[index] = replace_text(part)
    return "".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapping", type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args()

    mapping = load_mapping(args.mapping)
    reviewed = {
        msgid: OVERRIDES.get(msgid, review_translation(msgstr))
        for msgid, msgstr in mapping.items()
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(reviewed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Reviewed {len(reviewed)} translations in {args.output}")


if __name__ == "__main__":
    main()
