#!/usr/bin/env python3
"""Review a Google health translation draft before it reaches PO catalogs.

The Google endpoint is useful for prose but frequently chooses the wrong sense
for short software and clinical labels.  This pass applies a small, explicit
glossary, fixes only well-understood mistranslations, and quarantines output
whose placeholders, markup, identifiers, or language still look unsafe.
"""

import argparse
import json
import pathlib
import re

from po_catalog import PLACEHOLDER_RE, markup_signature


VIETNAMESE_RE = re.compile(
    r"[ăâđêôơưĂÂĐÊÔƠƯáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệ"
    r"íìỉĩịóòỏõọốồỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]"
)
ENGLISH_RESIDUE_RE = re.compile(
    r"\b(?:the|this|that|these|those|with|from|for|and|into|only|never|"
    r"client|patient|provider|booking|activity|service|search|staff|reason|"
    r"status|wizard|cancel|referral|existing|selected|relationship|calendar|"
    r"meeting|follow-up|create|save|failed|error|please|cannot|should|would|"
    r"must|will|has|have|was|were|are|is)\b",
    re.IGNORECASE,
)
BAD_OUTPUT_RE = re.compile(
    r"nốt nhạc|tàn tật|kiên nhẫn|nhà soạn nhạc|trận đấu|độ cứng|"
    r"cơ quan giao hàng|API\s+Phím|FHIR\s+Học viên|MedicineRequest|"
    r"sức khỏe\s*19|v\.v\.\.|\)\)",
    re.IGNORECASE,
)
IDENTIFIER_RE = re.compile(
    r"\b(?:Health19|MedicationRequest|ServiceRequest|DocumentReference|"
    r"AdverseEvent|CodeSystem|client_id|note_id|json\.dumps)\b|"
    r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b"
)


EXACT_OVERRIDES = {
    "API Key": "Khóa API",
    "API Keys": "Các khóa API",
    "Application": "Ứng dụng",
    "API Gateway OAuth2 Client": "Ứng dụng khách OAuth2 của Cổng API",
    "BHYT Card": "Thẻ BHYT",
    "Body": "Nội dung",
    "Client secret generated": "Đã tạo bí mật ứng dụng khách",
    "Count": "Số lượng",
    "Current": "Hiện tại",
    "Dead": "Không thể gửi",
    "Dest Lat": "Vĩ độ đích",
    "Disabled": "Đã tắt",
    "EMR Export (VN)": "Xuất EMR (VN)",
    "Form Instance": "Phiên biểu mẫu",
    "Frequency Interval": "Khoảng thời gian lặp lại",
    "Internal Extension": "Số máy nhánh nội bộ",
    "Key": "Khóa",
    "Match Confidence": "Độ tin cậy khớp",
    "Missing": "Thiếu",
    "No forms apply to this visit": "Không có biểu mẫu nào áp dụng cho lượt thăm này",
    "Note": "Ghi chú",
    "OA ID": "ID OA",
    "Pass": "Đạt",
    "Preset Key": "Khóa cài đặt sẵn",
    "Record Lifecycle Action": "Hành động vòng đời bản ghi",
    "Sent At": "Thời điểm gửi",
    "Staleness": "Độ cũ của dữ liệu",
    "Staleness Points": "Điểm độ cũ của dữ liệu",
    "Submission Reference": "Mã tham chiếu gửi",
    "TAMPER DETECTED at seq": "PHÁT HIỆN GIẢ MẠO tại số thứ tự",
    "Traffic": "Lưu lượng",
    "Travel buffer (minutes)": "Thời gian đệm di chuyển (phút)",
    "Withdrawal Date": "Ngày thu hồi",
    "Withdrawal Reason": "Lý do thu hồi",
    "Withdrawal reason": "Lý do thu hồi",
}


def identifier_signature(value):
    return sorted(IDENTIFIER_RE.findall(value))


def correct_known_senses(msgid, msgstr):
    if msgid in EXACT_OVERRIDES:
        return EXACT_OVERRIDES[msgid]
    fixes = []
    if re.search(r"\bkeys?\b", msgid, re.IGNORECASE):
        fixes.extend((("Phím", "Khóa"), ("phím", "khóa")))
    if re.search(r"\bnotes?\b", msgid, re.IGNORECASE):
        fixes.extend((("nốt nhạc", "ghi chú"), ("Nốt nhạc", "Ghi chú")))
    if re.search(r"\bpatient\b", msgid, re.IGNORECASE):
        fixes.extend((("Kiên nhẫn", "Bệnh nhân"), ("kiên nhẫn", "bệnh nhân")))
    if re.search(r"\bmatch(?:es|ed|ing)?\b", msgid, re.IGNORECASE):
        fixes.extend((("Trận đấu", "Kết quả khớp"), ("trận đấu", "kết quả khớp")))
    if re.search(r"\bline\b", msgid, re.IGNORECASE):
        fixes.extend((("dây chuyền", "dòng"), ("Dây chuyền", "Dòng")))
    if re.search(r"\bcomposer\b", msgid, re.IGNORECASE):
        fixes.extend((("nhà soạn nhạc", "trình soạn thảo"), ("Nhà soạn nhạc", "Trình soạn thảo")))
    if re.search(r"\blog(?:ged|ging)?\b", msgid, re.IGNORECASE):
        fixes.extend((("đăng nhập", "ghi nhật ký"), ("Đăng nhập", "Ghi nhật ký")))
    if re.search(r"\bforms?\b", msgid, re.IGNORECASE):
        fixes.extend((("hình thức", "biểu mẫu"), ("Hình thức", "Biểu mẫu")))
    if re.search(r"\bidempotenc", msgid, re.IGNORECASE):
        fixes.extend((("khóa bình thường", "khóa đảm bảo tính lũy đẳng"),))
    if re.search(r"\blead(?:s)?\b", msgid, re.IGNORECASE):
        fixes.extend((("Dẫn đầu", "Khách hàng tiềm năng"), ("dẫn đầu", "khách hàng tiềm năng")))
    if re.search(r"\btravel\b", msgid, re.IGNORECASE):
        fixes.extend((("du lịch", "di chuyển"), ("Du lịch", "Di chuyển")))
    if "Zalo OA" in msgid:
        fixes.extend((("Zalo viêm khớp", "Zalo OA"),))
    if re.search(r"\bOA\b", msgid):
        fixes.extend((("viêm khớp", "OA"), ("Viêm khớp", "OA")))
    if re.search(r"\bclaims?\b", msgid, re.IGNORECASE):
        fixes.extend((("khẳng định", "yêu cầu"), ("Khẳng định", "Yêu cầu")))
    if "active care plan" in msgid.casefold():
        fixes.extend((("kế hoạch chăm sóc tích cực", "kế hoạch chăm sóc đang hoạt động"),))
    for old, new in fixes:
        msgstr = msgstr.replace(old, new)
    return msgstr


def rejection_reason(msgid, msgstr):
    if not msgstr or msgid.strip().casefold() == msgstr.strip().casefold():
        return "unchanged"
    if sorted(PLACEHOLDER_RE.findall(msgid)) != sorted(PLACEHOLDER_RE.findall(msgstr)):
        return "placeholder_mismatch"
    if markup_signature(msgid) != markup_signature(msgstr):
        return "markup_mismatch"
    if identifier_signature(msgid) != identifier_signature(msgstr):
        return "identifier_changed"
    if ENGLISH_RESIDUE_RE.search(msgstr):
        return "english_residue"
    if BAD_OUTPUT_RE.search(msgstr):
        return "suspicious_word_sense"
    if len(msgid) > 12 and not 0.35 <= len(msgstr) / len(msgid) <= 2.7:
        return "length_ratio"
    # ASCII-only output is acceptable for preserved identifiers, numbers, and
    # well-known product names, but not as a purported translation of prose.
    if not VIETNAMESE_RE.search(msgstr) and re.search(r"[A-Za-z]{4}", msgid):
        return "no_vietnamese"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=pathlib.Path)
    parser.add_argument("--approved", required=True, type=pathlib.Path)
    parser.add_argument("--rejected", required=True, type=pathlib.Path)
    args = parser.parse_args()

    draft = json.loads(args.draft.read_text(encoding="utf-8"))
    approved = {}
    rejected = {}
    for msgid, original in draft.items():
        candidate = correct_known_senses(msgid, original)
        reason = rejection_reason(msgid, candidate)
        if reason:
            rejected[msgid] = {
                "draft": original,
                "corrected": candidate,
                "reason": reason,
            }
        else:
            approved[msgid] = candidate

    for path, value in ((args.approved, approved), (args.rejected, rejected)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"Approved after structural and terminology checks: {len(approved)}")
    print(f"Quarantined for review: {len(rejected)}")


if __name__ == "__main__":
    main()
