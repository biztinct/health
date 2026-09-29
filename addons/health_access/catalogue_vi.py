# -*- coding: utf-8 -*-
"""The clinic's roles and abilities in Vietnamese (ACCESS AR-3, item C).

THE WORDS ARE STORED, SO A `.po` CANNOT REACH THEM. A role's and an ability's
`name` and `description` are `translate=True` fields on `biz.access.role` and
`biz.access.ability`: each row keeps a jsonb of `{lang: text}`, filled when the
row is created from the plain Python in `hooks.py` (`ABILITIES`, `ROLE_NOTES`),
which nothing extracts. So every seeded row carried `en_US` only, and a
Vietnamese reader of the Access home saw English role names on a Vietnamese
screen.

`apply_catalogue_vi` writes the `vi_VN` value for every seeded row, keyed by
the row's ENGLISH text exactly as `hooks.py` writes it. Idempotent, and it
never overwrites somebody's own words:

  * a row whose English is not one of these sentences (renamed by an
    administrator, or a role somebody made by hand) is left alone;
  * a row that already carries a Vietnamese value different from its English
    (somebody translated it themselves) is left alone;
  * a database where Vietnamese is not active is left alone.

Called from the catalogue seed (`hooks._seed`, a fresh database) and from the
19.0.1.7.0 migration (the rows already there). Shape cloned from Payobook's
`pb_vendor_access/catalogue_vi.py`; the words are this clinic's, in the terms
`health_base/i18n/vi_VN.po` already fixed (Chủ sở hữu, Bác sĩ, Y tá, Kế toán,
Quản lý vận hành, Quản trị viên, vai trò, bàn giao quyền, menu bên trái).
"""
import logging

_logger = logging.getLogger(__name__)

LANG = 'vi_VN'

#: English (exactly as `hooks.py` writes it) -> Vietnamese.
VI = {
    # ================================================================ roles
    "Owner": "Chủ sở hữu",
    "Runs the clinic and answers for its records. Opens every part of the "
    "system this clinic uses, including permanently removing a record — but "
    "never the system administrator permission for the box itself.":
        "Điều hành phòng khám và chịu trách nhiệm về hồ sơ của phòng khám. Mở "
        "mọi phần của hệ thống mà phòng khám dùng, kể cả xóa vĩnh viễn một hồ "
        "sơ — nhưng không bao giờ có quyền quản trị hệ thống của chính máy chủ.",
    "Operations Manager": "Quản lý vận hành",
    "Runs the day: the roster, the visits, the people and the money that "
    "follows them. Everything an owner can reach except the last word on "
    "removing records.":
        "Điều hành công việc hằng ngày: lịch phân ca, các lượt thăm khám, con "
        "người và tiền bạc đi kèm. Mọi thứ chủ sở hữu tiếp cận được, trừ quyết "
        "định cuối cùng về việc xóa hồ sơ.",
    "Branch Manager": "Quản lý chi nhánh",
    "Coaches and reviews one branch's team. It opens the performance screens "
    "and nothing clinical or financial.":
        "Huấn luyện và đánh giá đội ngũ của một chi nhánh. Vai trò này mở các "
        "màn hình hiệu suất, không mở gì về lâm sàng hay tài chính.",
    "Banker": "Nhân viên ngân hàng",
    "Kept from an earlier setup and held by nobody. It carries nothing beyond "
    "signing in, which is why it is put away rather than left on the board.":
        "Còn lại từ một thiết lập trước đây và không ai giữ. Vai trò này không "
        "có gì ngoài việc đăng nhập, vì vậy nó được cất đi thay vì để trên bảng.",
    "Nurse": "Y tá",
    "Gives care and records it: visits, observations, medicines and notes, "
    "plus the billing that goes with a visit. It does not run the roster.":
        "Chăm sóc và ghi lại việc chăm sóc: lượt thăm khám, quan sát, thuốc và "
        "ghi chép, cùng phần thu tiền đi kèm một lượt thăm. Vai trò này không "
        "điều hành lịch phân ca.",
    "Doctor": "Bác sĩ",
    "Diagnoses, prescribes and signs off clinical records. It opens the "
    "clinical screens and nothing else.":
        "Chẩn đoán, kê đơn và ký duyệt hồ sơ lâm sàng. Vai trò này mở các màn "
        "hình lâm sàng và không mở gì khác.",
    "Accountant": "Kế toán",
    "Owns the money: invoices, claims, tax, red invoices and the accounting "
    "sync. It opens no clinical record.":
        "Phụ trách tiền bạc: hóa đơn, hồ sơ bảo hiểm, thuế, hóa đơn đỏ và đồng "
        "bộ kế toán. Vai trò này không mở hồ sơ lâm sàng nào.",
    "Admin": "Quản trị viên",
    "Adds colleagues, switches them off and says which role each of them "
    "holds. It carries no clinical or financial access of its own, and never "
    "the system administrator permission.":
        "Thêm đồng nghiệp, tắt tài khoản của họ và quyết định mỗi người giữ vai "
        "trò nào. Vai trò này tự nó không có quyền lâm sàng hay tài chính, và "
        "không bao giờ có quyền quản trị hệ thống.",
    "CRM": "CRM",
    "Works the front desk and the enquiry pipeline from first contact to a "
    "booked visit. It opens no clinical record.":
        "Làm việc ở quầy lễ tân và theo dõi yêu cầu từ lần liên hệ đầu tiên đến "
        "khi đặt được lượt thăm khám. Vai trò này không mở hồ sơ lâm sàng nào.",

    # ============================================================ abilities
    "Sign in and use the basics": "Đăng nhập và dùng các chức năng cơ bản",
    "Open the system, see the home screen and their own details. On its own "
    "it opens no patient record and no money.":
        "Mở hệ thống, xem màn hình chính và thông tin của chính mình. Tự nó "
        "không mở hồ sơ bệnh nhân nào và không mở gì về tiền.",
    "See the clinic's patients and visits": "Xem bệnh nhân và lượt thăm khám của phòng khám",
    "Look up a patient and read the visits arranged for them. It does not by "
    "itself allow writing clinical notes or changing a booking.":
        "Tra cứu một bệnh nhân và xem các lượt thăm khám đã sắp xếp cho họ. Tự "
        "nó không cho phép viết ghi chép lâm sàng hay thay đổi lịch hẹn.",
    "Work the front desk": "Làm việc ở quầy lễ tân",
    "Book, move and check in visits, and keep patient contact details right. "
    "It does not include clinical records or invoicing.":
        "Đặt, dời và tiếp nhận lượt thăm khám, và giữ thông tin liên hệ của "
        "bệnh nhân chính xác. Không bao gồm hồ sơ lâm sàng hay xuất hóa đơn.",
    "Give nursing care": "Chăm sóc điều dưỡng",
    "Run a visit, record observations and medicines given, and write the "
    "notes for it. It does not include leading the nursing team.":
        "Thực hiện một lượt thăm khám, ghi lại quan sát và thuốc đã dùng, và "
        "viết ghi chép cho lượt đó. Không bao gồm việc dẫn dắt đội điều dưỡng.",
    "Lead the nursing team": "Dẫn dắt đội điều dưỡng",
    "Everything nursing care involves, plus checking and signing off what the "
    "team has recorded. It does not make somebody a doctor.":
        "Mọi việc của chăm sóc điều dưỡng, cộng thêm kiểm tra và ký duyệt những "
        "gì đội đã ghi lại. Không biến một người thành bác sĩ.",
    "Practise as a doctor": "Hành nghề bác sĩ",
    "Diagnose, prescribe and sign off clinical records. It does not include "
    "running the roster or the money side of a visit.":
        "Chẩn đoán, kê đơn và ký duyệt hồ sơ lâm sàng. Không bao gồm điều hành "
        "lịch phân ca hay phần tiền bạc của một lượt thăm.",
    "Sell services and follow up leads": "Bán dịch vụ và theo đuổi khách tiềm năng",
    "Quote for care packages, follow up enquiries and close them. It opens no "
    "clinical record.":
        "Báo giá các gói chăm sóc, theo dõi yêu cầu và chốt chúng. Không mở hồ "
        "sơ lâm sàng nào.",
    "Run daily operations": "Điều hành công việc hằng ngày",
    "Plan the day's visits, staff them and deal with what goes wrong. It does "
    "not include hiring, pay or the accounts.":
        "Lên kế hoạch các lượt thăm khám trong ngày, phân công người và xử lý "
        "những gì trục trặc. Không bao gồm tuyển dụng, lương hay sổ sách kế toán.",
    "Work the clinic's finances": "Làm việc với tài chính của phòng khám",
    "Read and work with what has been billed, collected and written off. It "
    "is not the accounting ledger itself.":
        "Xem và làm việc với những gì đã xuất hóa đơn, đã thu và đã xóa nợ. "
        "Không phải chính sổ cái kế toán.",
    "Manage the care team": "Quản lý đội chăm sóc",
    "Oversee the clinical team and the work they are given, across the whole "
    "clinic. It does not by itself open the finances.":
        "Giám sát đội lâm sàng và công việc được giao cho họ, trên toàn phòng "
        "khám. Tự nó không mở phần tài chính.",
    "Administer the clinic's records": "Quản trị danh mục của phòng khám",
    "Keep the reference lists behind every screen right — services, "
    "facilities, areas, price lists. It changes settings, not patients.":
        "Giữ đúng các danh mục phía sau mọi màn hình — dịch vụ, cơ sở, khu vực, "
        "bảng giá. Thay đổi thiết lập, không thay đổi bệnh nhân.",
    "Archive and restore records": "Lưu trữ và khôi phục hồ sơ",
    "Put a record beyond everyday reach and bring it back if it was a "
    "mistake. It never destroys anything.":
        "Đưa một hồ sơ ra khỏi tầm sử dụng hằng ngày và đưa nó trở lại nếu đó "
        "là nhầm lẫn. Không bao giờ phá hủy thứ gì.",
    "Own the clinic's data": "Làm chủ dữ liệu của phòng khám",
    "The last word on what happens to a record, including permanently "
    "removing one. It is not the system administrator permission and never "
    "carries it.":
        "Quyết định cuối cùng về số phận một hồ sơ, kể cả xóa vĩnh viễn. Đây "
        "không phải quyền quản trị hệ thống và không bao giờ bao gồm quyền đó.",
    "Use the patient portal": "Dùng cổng bệnh nhân",
    "Reach the pages a patient and their family are shown. It grants nothing "
    "inside the clinic itself.":
        "Truy cập các trang mà bệnh nhân và người nhà được xem. Không cấp quyền "
        "gì bên trong phòng khám.",
    "Work enquiries and bookings": "Xử lý yêu cầu và lịch hẹn",
    "Take an enquiry from first contact to a booked visit, and keep the "
    "follow-ups moving. It does not include changing how the pipeline works.":
        "Đưa một yêu cầu từ lần liên hệ đầu tiên đến khi đặt được lượt thăm "
        "khám, và giữ cho việc theo dõi luôn tiến triển. Không bao gồm thay "
        "đổi cách quy trình vận hành.",
    "Manage enquiries and bookings": "Quản lý yêu cầu và lịch hẹn",
    "Everything working enquiries involves, plus setting up the stages, the "
    "reasons and who picks work up.":
        "Mọi việc của xử lý yêu cầu, cộng thêm thiết lập các giai đoạn, các lý "
        "do và ai nhận việc.",
    "Raise and send invoices": "Lập và gửi hóa đơn",
    "Bill a visit or a package and send it out. It does not include changing "
    "prices or approving a write-off.":
        "Xuất hóa đơn cho một lượt thăm hoặc một gói và gửi đi. Không bao gồm "
        "thay đổi giá hay duyệt xóa nợ.",
    "Manage invoicing": "Quản lý hóa đơn",
    "Everything raising invoices involves, plus corrections, credit notes and "
    "how billing is set up.":
        "Mọi việc của lập hóa đơn, cộng thêm điều chỉnh, giấy báo có và cách "
        "thiết lập việc thu tiền.",
    "Process insurance claims": "Xử lý hồ sơ bảo hiểm",
    "Prepare, send and chase claims for the care given. It does not change "
    "the clinical record the claim is about.":
        "Chuẩn bị, gửi và theo dõi hồ sơ yêu cầu thanh toán cho việc chăm sóc "
        "đã thực hiện. Không thay đổi hồ sơ lâm sàng mà hồ sơ đó nói đến.",
    "Run the accounting sync": "Chạy đồng bộ kế toán",
    "Send billing across to the connected accounting system and see what came "
    "back. It does not write in that system by hand.":
        "Gửi dữ liệu hóa đơn sang hệ thống kế toán được kết nối và xem kết quả "
        "trả về. Không tự tay ghi vào hệ thống đó.",
    "Keep tax records compliant": "Giữ hồ sơ thuế đúng quy định",
    "Maintain the tax details and the returns that go with billing. It does "
    "not issue the official invoices themselves.":
        "Duy trì thông tin thuế và các tờ khai đi kèm việc thu tiền. Không tự "
        "phát hành hóa đơn chính thức.",
    "Issue red invoices": "Phát hành hóa đơn đỏ",
    "Issue and cancel the official tax invoices for care given. It is the "
    "last step of billing, not the first.":
        "Phát hành và hủy hóa đơn thuế chính thức cho việc chăm sóc đã thực "
        "hiện. Đây là bước cuối của việc thu tiền, không phải bước đầu.",
    "Work in the accounting ledger": "Làm việc trong sổ kế toán",
    "Open and work with customer and supplier invoices in the accounts. It is "
    "not the whole of accounting.":
        "Mở và làm việc với hóa đơn khách hàng và nhà cung cấp trong sổ sách. "
        "Không phải toàn bộ công việc kế toán.",
    "Manage staff records": "Quản lý hồ sơ nhân viên",
    "Keep the people records right — who works here, where and on what terms. "
    "It does not include pay.":
        "Giữ hồ sơ nhân sự chính xác — ai làm việc ở đây, ở đâu và theo điều "
        "kiện nào. Không bao gồm lương.",
    "See every lead": "Xem mọi khách tiềm năng",
    "See the whole pipeline rather than only their own enquiries. It changes "
    "what is visible, not what can be done.":
        "Xem toàn bộ danh sách khách tiềm năng thay vì chỉ các yêu cầu của "
        "mình. Thay đổi những gì nhìn thấy, không thay đổi những gì làm được.",
    "Manage the sales team": "Quản lý đội bán hàng",
    "Everything selling involves, plus the teams, the targets and who owns "
    "which enquiry.":
        "Mọi việc của bán hàng, cộng thêm các nhóm, chỉ tiêu và ai phụ trách "
        "yêu cầu nào.",
    "Coach as a branch manager": "Huấn luyện với tư cách quản lý chi nhánh",
    "See and work the coaching and performance screens for one branch. It "
    "opens no clinical record and no money.":
        "Xem và làm việc với các màn hình huấn luyện và hiệu suất của một chi "
        "nhánh. Không mở hồ sơ lâm sàng nào và không mở gì về tiền.",
    "Add people and give out roles": "Thêm người và cấp vai trò",
    "Add a colleague, switch one off and say which role each of them holds. "
    "It never includes the system administrator permission for the box.":
        "Thêm một đồng nghiệp, tắt tài khoản của một người và quyết định mỗi "
        "người giữ vai trò nào. Không bao giờ bao gồm quyền quản trị hệ thống "
        "của máy chủ.",
    "Read the reports": "Xem báo cáo",
    "Open the dashboards and reports somebody has already built, and filter "
    "them. It does not include building a new one.":
        "Mở các bảng số liệu và báo cáo đã có người xây dựng, và lọc chúng. "
        "Không bao gồm việc xây dựng báo cáo mới.",
    "Build reports": "Xây dựng báo cáo",
    "Everything reading reports involves, plus building new charts, lists and "
    "dashboards from the data this clinic already has. It changes no record "
    "it reports on.":
        "Mọi việc của xem báo cáo, cộng thêm xây dựng biểu đồ, danh sách và "
        "bảng số liệu mới từ dữ liệu phòng khám đã có. Không thay đổi hồ sơ nào "
        "mà nó báo cáo.",
    "Work the Zalo channel": "Làm việc với kênh Zalo",
    "Read and answer the conversations and messages that arrive through Zalo. "
    "It does not include setting the channel up.":
        "Đọc và trả lời các hội thoại và tin nhắn đến qua Zalo. Không bao gồm "
        "việc thiết lập kênh.",
    "Set up the Zalo channel": "Thiết lập kênh Zalo",
    "Everything working the Zalo channel involves, plus the Zalo settings — "
    "the account it is connected to and how messages are handled.":
        "Mọi việc của làm việc với kênh Zalo, cộng thêm các thiết lập Zalo — "
        "tài khoản được kết nối và cách xử lý tin nhắn.",
    "Handle calls": "Xử lý cuộc gọi",
    "See every call, every missed call and the list of call recordings. It "
    "does not include setting the phone system up.":
        "Xem mọi cuộc gọi, mọi cuộc gọi nhỡ và danh sách bản ghi âm cuộc gọi. "
        "Không bao gồm việc thiết lập tổng đài điện thoại.",
    "Set up the phone system": "Thiết lập tổng đài điện thoại",
    "Everything handling calls involves, plus the extensions, bringing the "
    "call history across from the phone provider, and the voice settings.":
        "Mọi việc của xử lý cuộc gọi, cộng thêm các máy nhánh, việc lấy lịch "
        "sử cuộc gọi từ nhà cung cấp điện thoại, và các thiết lập thoại.",
    "Set up reporting": "Thiết lập báo cáo",
    "Everything building reports involves, plus importing data, the reporting "
    "settings, who sees which numbers, and the AI providers the reports use. "
    "It changes no record it reports on.":
        "Mọi việc của xây dựng báo cáo, cộng thêm nhập dữ liệu, các thiết lập "
        "báo cáo, ai xem số liệu nào, và các nhà cung cấp AI mà báo cáo dùng. "
        "Không thay đổi hồ sơ nào mà nó báo cáo.",
}


def _lang_active(env):
    return bool(env['res.lang'].sudo().search_count(
        [('code', '=', LANG), ('active', '=', True)]))


def apply_catalogue_vi(env):
    """Write the Vietnamese name and description of every seeded role and
    ability. Returns the number of rows written."""
    if not _lang_active(env):
        _logger.info('health_access: %s is not active here; the roles keep '
                     'their English words only', LANG)
        return 0
    written = 0
    for model in ('biz.access.role', 'biz.access.ability'):
        Model = env[model].sudo().with_context(active_test=False)
        for rec in Model.search([]):
            en = rec.with_context(lang='en_US')
            vi = rec.with_context(lang=LANG)
            vals = {}
            for field in ('name', 'description'):
                source = (en[field] or '').strip()
                target = VI.get(source)
                if not target:
                    continue                       # not our sentence
                current = (vi[field] or '').strip()
                if current == target:
                    continue                       # already done
                if current and current != source:
                    continue                       # somebody's own words
                vals[field] = target
            if vals:
                vi.write(vals)
                written += 1
    _logger.info('health_access: %s role/ability row(s) given their Vietnamese '
                 'words', written)
    return written
