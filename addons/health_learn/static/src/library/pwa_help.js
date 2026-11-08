/* Mobile help is outside the Vue work tree: opening it cannot unmount a draft. */
(function () {
    'use strict';
    const root = document.getElementById('carejiyo-mobile-learning');
    if (!root) return;
    const find = (id) => document.getElementById(id);
    const open = find('cj-mobile-help-open');
    const panel = find('cj-mobile-help-panel');
    const frame = find('cj-mobile-help-frame');
    const choice = find('cj-mobile-topic');
    const offline = find('cj-mobile-offline');
    const topics = [
        ['mobile.find-your-assigned-visits', 'Find your assigned visits', 'Tìm lịch hẹn được phân công'],
        ['mobile.review-a-visit-before-attending', 'Review a visit', 'Kiểm tra thông tin buổi chăm sóc'],
        ['operations.accept-an-assignment', 'Accept an assignment', 'Chấp nhận phân công'],
        ['mobile.start-a-visit', 'Start a visit', 'Bắt đầu dịch vụ'],
        ['mobile.write-and-save-a-clinical-note', 'Write and save a note', 'Nhập và lưu ghi chú'],
        ['mobile.answer-the-visit-closing-questions', 'Answer closing questions', 'Trả lời câu hỏi kết thúc'],
        ['mobile.finish-a-visit-and-confirm-completion', 'Finish a visit', 'Hoàn tất buổi chăm sóc'],
        ['mobile.check-the-invoice-created-at-completion', 'Check the invoice', 'Kiểm tra hóa đơn'],
    ];
    function language() {
        try { return localStorage.getItem('pwa_preferred_language') || 'vi'; }
        catch { return 'vi'; }
    }
    function labels() {
        const vi = language() === 'vi';
        const current = choice.value;
        choice.replaceChildren();
        for (const [key, en, vn] of topics) {
            const option = document.createElement('option');
            option.value = key; option.textContent = vi ? vn : en; choice.append(option);
        }
        if (current) choice.value = current;
        open.textContent = vi ? 'Hướng dẫn' : 'Help';
        find('cj-mobile-help-close').setAttribute('aria-label', vi ? 'Đóng' : 'Close');
        find('cj-mobile-topic-label').textContent = vi ? 'Chọn công việc' : 'Choose a task';
        find('cj-mobile-library').textContent = vi ? 'Tất cả hướng dẫn và lộ trình học' : 'All guides and learning paths';
        offline.textContent = vi ? 'Kết nối mạng để mở hướng dẫn và video.' : 'Connect to open the instructions and videos.';
    }
    function load() {
        offline.hidden = navigator.onLine;
        frame.hidden = !navigator.onLine;
        if (navigator.onLine) frame.src = '/carejiyo/learn/manual?key=' + encodeURIComponent(choice.value);
        else frame.removeAttribute('src');
    }
    function close() {
        panel.hidden = true; open.setAttribute('aria-expanded', 'false');
        frame.removeAttribute('src'); open.focus();
    }
    open.addEventListener('click', () => {
        labels();
        if (!panel.hidden) { close(); return; }
        panel.hidden = false; open.setAttribute('aria-expanded', 'true'); load(); choice.focus();
    });
    find('cj-mobile-help-close').addEventListener('click', close);
    choice.addEventListener('change', load);
    root.addEventListener('keydown', (ev) => {
        if (ev.key === 'Escape' && !panel.hidden) { ev.stopPropagation(); close(); }
    });
    window.addEventListener('online', () => { if (!panel.hidden) load(); });
    window.addEventListener('offline', () => { if (!panel.hidden) load(); });
    labels();
})();
