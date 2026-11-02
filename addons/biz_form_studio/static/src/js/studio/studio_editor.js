/** @odoo-module **/
/**
 * `biz_form_studio.studio` — the Studio editor for one screen.
 *
 * THREE COLUMNS. The palette on the left (new field types, and the custom
 * fields that exist but are not on the screen), the screen drawn as cards in
 * the middle, and the settings of whatever is selected on the right.
 *
 * THE CENTRE IS A SCHEMATIC, NOT THE LIVE FORM. It shows the screen's own
 * cards (grey, with their fields as locked chips, so an administrator sees
 * where things will land) and Studio's sections in between. Every move here
 * changes a JSON description, never the DOM of a real form; nothing changes
 * for anybody until Publish, which the server turns into one view.
 *
 * WHAT IS SAVED WHEN. A new field and a change to a field's settings are saved
 * at once (a field is a real column: it exists the moment it is made, and it
 * is only on the screen once the layout is published). Where fields sit is a
 * draft, saved quietly 800 ms after each change and kept per person, until
 * Publish or Discard.
 *
 * Drag and drop is HTML5 (as in the concept page); every move also has a
 * button in the right panel, so nothing needs a mouse.
 *
 * R1 — no `t-as` variable is named lt / gt / lte / gte / and / or / not / in.
 * R2 — every sentence is ONE expression.
 */
import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { rpcBus } from "@web/core/network/rpc";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { ic } from "@biz_kit/js/kit_icons";

const DRAFT_DELAY = 800;
let idCounter = 0;

function clone(value) {
    return JSON.parse(JSON.stringify(value === undefined ? null : value));
}

function newSectionId() {
    idCounter += 1;
    return ("s" + Date.now().toString(36) + idCounter.toString(36)).slice(0, 24);
}

function errorText(error, fallback) {
    const data = error && (error.data || (error.message && error.message.data));
    if (data && data.message) {
        return data.message;
    }
    return fallback;
}

/** The description reduced to what Publish compares: ids, titles, anchors,
 *  and field names in order. */
function shape(sections) {
    return (sections || []).map((sec) => ({
        id: sec.id,
        title: sec.title || "",
        title_vi: sec.title_vi || "",
        anchor: sec.anchor || { kind: "before_notebook" },
        fields: (sec.fields || [])
            .slice()
            .sort((a, b) => (a.order || 0) - (b.order || 0))
            .map((f) => f.name),
    }));
}

function sameShape(a, b) {
    return JSON.stringify(shape(a)) === JSON.stringify(shape(b));
}

export class FormStudioEditor extends Component {
    static template = "biz_form_studio.Studio";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.ic = ic;
        const params = (this.props.action && this.props.action.params) || {};
        this.model = params.model || false;
        this.viewId = params.view_id || false;
        this.resId = params.res_id || false;
        this.state = useState({
            loading: true,
            error: "",
            data: null,
            sections: [],
            published: [],
            sel: null,
            form: null,
            palTab: "new",
            sheet: "",
            busy: false,
            dragOver: "",
            refs: null,
            deleteText: "",
            rollbackTo: 0,
            phiNote: "",
            draft: null,
        });
        this._drag = null;
        this._draftTimer = null;
        onWillStart(async () => {
            await this.load();
        });
        onWillUnmount(() => {
            if (this._draftTimer) {
                clearTimeout(this._draftTimer);
                this._draftTimer = null;
                this.saveDraft();
            }
        });
    }

    // ================================================================ data
    async fetch() {
        return this.orm.call("fs.studio", "get_studio", [this.model, this.viewId]);
    }

    async load() {
        if (!this.model || !this.viewId) {
            this.state.loading = false;
            this.state.error = _t("Open a screen that supports Studio and press Studio.");
            return;
        }
        try {
            const data = await this.fetch();
            this.state.data = data;
            const published = clone(data.layout.sections || []);
            this.state.published = published;
            this.state.sections = clone(published);
            if (data.draft && !sameShape(data.draft, published)) {
                this.state.draft = clone(data.draft);
                this.state.sheet = "draft";
            }
            this.state.error = "";
        } catch (error) {
            this.state.error = errorText(error, _t("Studio could not open this screen."));
        }
        this.state.loading = false;
    }

    /** Fresh field list and history after a server change; the working
     *  layout stays as it is. */
    async refresh() {
        try {
            const data = await this.fetch();
            this.state.data = data;
            this.state.published = clone(data.layout.sections || []);
        } catch (error) {
            this.notify(errorText(error, _t("Studio could not open this screen.")), "danger");
        }
    }

    notify(message, type = "info") {
        this.notification.add(message, { type });
    }

    // ============================================================ getters
    get data() {
        return this.state.data;
    }

    get host() {
        return (this.data && this.data.host) || {};
    }

    get fields() {
        return (this.data && this.data.fields) || {};
    }

    get typeMap() {
        const out = {};
        for (const item of (this.data && this.data.types) || []) {
            out[item.key] = item;
        }
        return out;
    }

    get defaultAnchor() {
        return this.host.has_notebook ? "before_notebook" : "sheet_end";
    }

    /** Studio's own sections, in the place the writer will put them. */
    sectionsAt(where) {
        const notebook = this.host.has_notebook;
        return this.state.sections.filter((sec) => {
            const kind = (sec.anchor && sec.anchor.kind) || "before_notebook";
            if (kind === "card") {
                return false;
            }
            if (!notebook) {
                return where === "end";
            }
            return where === "before" ? kind === "before_notebook" : kind === "sheet_end";
        });
    }

    get cardsBefore() {
        const out = [];
        for (const card of (this.data && this.data.cards) || []) {
            if (card.kind === "notebook") {
                break;
            }
            out.push(card);
        }
        return out;
    }

    get cardsTabs() {
        const cards = (this.data && this.data.cards) || [];
        const at = cards.findIndex((card) => card.kind === "notebook");
        return at < 0 ? [] : cards.slice(at + 1);
    }

    cardSection(name) {
        return this.state.sections.find(
            (sec) => sec.anchor && sec.anchor.kind === "card" && sec.anchor.name === name
        );
    }

    fieldNames(sec) {
        if (!sec) {
            return [];
        }
        return (sec.fields || [])
            .slice()
            .sort((a, b) => (a.order || 0) - (b.order || 0))
            .map((f) => f.name)
            .filter((name) => this.fields[name]);
    }

    get placed() {
        const out = new Set();
        for (const sec of this.state.sections) {
            for (const f of sec.fields || []) {
                out.add(f.name);
            }
        }
        return out;
    }

    get notShown() {
        const placed = this.placed;
        return Object.keys(this.fields)
            .filter((name) => !this.fields[name].std && !placed.has(name))
            .sort((a, b) => this.fields[a].display.localeCompare(this.fields[b].display));
    }

    get selField() {
        const sel = this.state.sel;
        return sel && sel.kind === "field" ? this.fields[sel.name] : null;
    }

    get selSection() {
        const sel = this.state.sel;
        return sel && sel.kind === "section"
            ? this.state.sections.find((sec) => sec.id === sel.id)
            : null;
    }

    get isVi() {
        return ((this.data && this.data.lang) || "").startsWith("vi");
    }

    sectionTitle(sec) {
        if (this.isVi && sec.title_vi) {
            return sec.title_vi;
        }
        return sec.title || _t("New section");
    }

    typeIcon(type) {
        const item = this.typeMap[type];
        return ic(item ? item.icon : "circle", 14);
    }

    fieldIcon(name) {
        const info = this.fields[name];
        return ic((info && info.icon) || "circle", 14);
    }

    when(value) {
        if (!value) {
            return "";
        }
        try {
            return formatDateTime(deserializeDateTime(value));
        } catch {
            return value;
        }
    }

    visLabel(vis) {
        return { all: _t("Everyone"), staff: _t("Staff"), admin: _t("Admins") }[vis] || "";
    }

    get pwaLabel() {
        return this.host.pwa_label || _t("Mobile app");
    }

    // ============================================================ changes
    get changes() {
        const fields = this.fields;
        const label = (name) => (fields[name] ? fields[name].display : name);
        const before = shape(this.state.published);
        const after = shape(this.state.sections);
        const where = (sections) => {
            const out = {};
            for (const sec of sections) {
                sec.fields.forEach((name, i) => {
                    out[name] = `${sec.id}:${i}`;
                });
            }
            return out;
        };
        const a = where(before);
        const b = where(after);
        const out = [];
        for (const name of Object.keys(b)) {
            if (!(name in a)) {
                out.push({ kind: "add", icon: "plus", text: _t("Add %s", label(name)) });
            } else if (a[name] !== b[name]) {
                out.push({ kind: "move", icon: "arrowLeftRight", text: _t("Move %s", label(name)) });
            }
        }
        for (const name of Object.keys(a)) {
            if (!(name in b)) {
                out.push({ kind: "remove", icon: "minusCircle", text: _t("Take %s off the screen", label(name)) });
            }
        }
        const oldSecs = Object.fromEntries(before.map((sec) => [sec.id, sec]));
        const newIds = new Set(after.map((sec) => sec.id));
        for (const sec of after) {
            const old = oldSecs[sec.id];
            if (sec.anchor.kind === "card") {
                continue;
            }
            if (!old && sec.fields.length) {
                out.push({ kind: "section", icon: "layers", text: _t("New section: %s", sec.title || _t("New section")) });
            } else if (old && (old.title !== sec.title || old.title_vi !== sec.title_vi)) {
                out.push({ kind: "rename", icon: "pencil", text: _t("Rename section: %s", sec.title) });
            } else if (old && JSON.stringify(old.anchor) !== JSON.stringify(sec.anchor)) {
                out.push({ kind: "move", icon: "arrowLeftRight", text: _t("Move section: %s", sec.title) });
            }
        }
        for (const sec of before) {
            if (!newIds.has(sec.id) && sec.anchor.kind !== "card" && sec.fields.length) {
                out.push({ kind: "remove", icon: "minusCircle", text: _t("Remove section: %s", sec.title) });
            }
        }
        const orderBefore = before.map((sec) => sec.id).filter((id) => newIds.has(id));
        const orderAfter = after.map((sec) => sec.id).filter((id) => id in oldSecs);
        if (JSON.stringify(orderBefore) !== JSON.stringify(orderAfter)) {
            out.push({ kind: "move", icon: "arrowLeftRight", text: _t("New order of sections") });
        }
        return out;
    }

    get versionLabel() {
        const version = this.data ? this.data.layout.version : 0;
        return version ? _t("Version %s", version) : _t("Not published yet");
    }

    get changeCount() {
        const n = this.changes.length;
        if (!n) {
            return _t("No changes yet");
        }
        return n === 1 ? _t("1 change") : _t("%s changes", n);
    }

    get dirty() {
        return !sameShape(this.state.sections, this.state.published);
    }

    // ============================================================ layout ops
    touch() {
        for (const sec of this.state.sections) {
            (sec.fields || []).forEach((f, i) => {
                f.order = i;
            });
        }
        if (this._draftTimer) {
            clearTimeout(this._draftTimer);
        }
        this._draftTimer = setTimeout(() => {
            this._draftTimer = null;
            this.saveDraft();
        }, DRAFT_DELAY);
    }

    async saveDraft() {
        try {
            await this.orm.silent.call("fs.studio", "save_draft", [
                this.model,
                this.viewId,
                clone(this.state.sections),
            ]);
        } catch {
            // A draft is a convenience; the next change tries again.
        }
    }

    removeEverywhere(name) {
        for (const sec of this.state.sections) {
            sec.fields = (sec.fields || []).filter((f) => f.name !== name);
        }
    }

    sortedFields(sec) {
        sec.fields = (sec.fields || []).slice().sort((a, b) => (a.order || 0) - (b.order || 0));
        return sec.fields;
    }

    placeField(name, sectionId, index = -1) {
        this.removeEverywhere(name);
        const sec = this.state.sections.find((s) => s.id === sectionId);
        if (!sec) {
            return;
        }
        const list = this.sortedFields(sec);
        const at = index < 0 || index > list.length ? list.length : index;
        list.splice(at, 0, { name, order: at });
        this.touch();
    }

    addSection(fieldName = null, anchorKind = null) {
        const sec = {
            id: newSectionId(),
            title: _t("New section"),
            title_vi: "",
            anchor: { kind: anchorKind || this.defaultAnchor },
            fields: [],
        };
        this.state.sections.push(sec);
        if (fieldName) {
            this.placeField(fieldName, sec.id);
        } else {
            this.touch();
        }
        return sec;
    }

    ensureCardSection(name) {
        let sec = this.cardSection(name);
        if (!sec) {
            sec = { id: newSectionId(), title: "", title_vi: "", anchor: { kind: "card", name }, fields: [] };
            this.state.sections.push(sec);
        }
        return sec;
    }

    // ============================================================ selection
    selectField(name) {
        const info = this.fields[name];
        if (!info) {
            return;
        }
        this.state.sel = { kind: "field", name };
        this.state.form = info.std
            ? null
            : {
                  label: info.label,
                  help: info.help || "",
                  vis: info.vis || "all",
                  required: Boolean(info.required),
                  phi: Boolean(info.phi),
                  pwa: Boolean(info.pwa),
                  list_ok: Boolean(info.list_ok),
                  label_vi: info.label_vi || "",
                  help_vi: info.help_vi || "",
                  options: clone(info.options || []),
                  newOption: "",
              };
    }

    selectSection(id) {
        this.state.sel = { kind: "section", id };
        this.state.form = null;
    }

    clearSelection() {
        this.state.sel = null;
        this.state.form = null;
    }

    startNewField(type, target) {
        const item = this.typeMap[type];
        if (!item || item.disabled) {
            if (item && item.reason) {
                this.notify(item.reason, "warning");
            }
            return;
        }
        this.state.sel = { kind: "new", type, target: target || { newSection: true } };
        this.state.form = {
            label: "",
            help: "",
            vis: "all",
            required: false,
            phi: false,
            pwa: false,
            list_ok: true,
            label_vi: "",
            help_vi: "",
            options: type === "selection" ? [{ label: "" }] : [],
            newOption: "",
            comodel: "",
        };
    }

    /** A tile clicked rather than dragged: into the selected section, else
     *  into a new one. */
    onTileClick(type) {
        const sec = this.selSection;
        this.startNewField(type, sec ? { sectionId: sec.id } : { newSection: true });
    }

    get formDirty() {
        const form = this.state.form;
        const info = this.selField;
        if (!form || !info || info.std) {
            return false;
        }
        const keys = ["label", "help", "vis", "required", "phi", "pwa", "list_ok", "label_vi", "help_vi"];
        for (const key of keys) {
            const now = form[key];
            const was = info[key] === undefined ? (typeof now === "boolean" ? false : "") : info[key];
            if (now !== was) {
                return true;
            }
        }
        if (info.type === "selection") {
            return JSON.stringify(form.options) !== JSON.stringify(info.options || []) || Boolean(form.newOption.trim());
        }
        return false;
    }

    // ============================================================ form edits
    setForm(key, value) {
        if (!this.state.form) {
            return;
        }
        this.state.form[key] = value;
        if (key === "phi" && value) {
            this.state.form.list_ok = false;
        }
    }

    onInput(key, ev) {
        this.setForm(key, ev.target.value);
    }

    toggle(key) {
        if (!this.state.form) {
            return;
        }
        if (key === "list_ok" && this.state.form.phi) {
            return;
        }
        this.setForm(key, !this.state.form[key]);
    }

    setOptionLabel(index, ev) {
        this.state.form.options[index].label = ev.target.value;
    }

    toggleRetired(index) {
        const opt = this.state.form.options[index];
        opt.retired = !opt.retired;
    }

    removeNewOption(index) {
        const opt = this.state.form.options[index];
        if (!opt.value) {
            this.state.form.options.splice(index, 1);
        }
    }

    addOption() {
        const text = (this.state.form.newOption || "").trim();
        if (!text) {
            return;
        }
        this.state.form.options.push({ label: text });
        this.state.form.newOption = "";
    }

    onOptionKey(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.addOption();
        }
    }

    // ============================================================ server: fields
    async createField() {
        const sel = this.state.sel;
        const form = this.state.form;
        if (!sel || sel.kind !== "new" || !form || this.state.busy) {
            return;
        }
        if (form.newOption && form.newOption.trim()) {
            this.addOption();
        }
        const spec = {
            type: sel.type,
            label: form.label,
            help: form.help,
            vis: form.vis,
            required: form.required,
            phi: form.phi,
            pwa: form.pwa,
            list_ok: form.list_ok,
            label_vi: form.label_vi,
            help_vi: form.help_vi,
            options: form.options.map((o) => o.label).filter((t) => (t || "").trim()),
            comodel: form.comodel,
        };
        this.state.busy = true;
        try {
            const res = await this.orm.call("fs.studio", "create_field", [this.model, spec], {
                view_id: this.viewId,
            });
            await this.refresh();
            const target = sel.target || { newSection: true };
            if (target.sectionId && this.state.sections.find((s) => s.id === target.sectionId)) {
                this.placeField(res.name, target.sectionId, target.index === undefined ? -1 : target.index);
            } else if (target.card) {
                const sec = this.ensureCardSection(target.card);
                this.placeField(res.name, sec.id);
            } else {
                this.addSection(res.name);
            }
            this.selectField(res.name);
            this.state.phiNote = res.phi_warning ? res.name : "";
        } catch (error) {
            this.notify(errorText(error, _t("The field could not be added.")), "danger");
        }
        this.state.busy = false;
    }

    async saveField() {
        const sel = this.state.sel;
        const form = this.state.form;
        if (!sel || sel.kind !== "field" || !form || this.state.busy) {
            return;
        }
        const info = this.fields[sel.name];
        if (form.newOption && form.newOption.trim()) {
            this.addOption();
        }
        const spec = {
            label: form.label,
            help: form.help,
            vis: form.vis,
            required: form.required,
            phi: form.phi,
            pwa: form.pwa,
            list_ok: form.list_ok,
            label_vi: form.label_vi,
            help_vi: form.help_vi,
        };
        if (info.type === "selection") {
            spec.options = form.options;
        }
        this.state.busy = true;
        try {
            await this.orm.call("fs.studio", "update_field", [this.model, sel.name, spec]);
            await this.refresh();
            this.selectField(sel.name);
            this.notify(_t("Saved. The field's settings apply everywhere at once."), "success");
        } catch (error) {
            this.notify(errorText(error, _t("The field could not be saved.")), "danger");
        }
        this.state.busy = false;
    }

    async ackPhi() {
        const name = this.state.phiNote;
        this.state.phiNote = "";
        try {
            await this.orm.silent.call("fs.studio", "ack_phi_warning", [this.model, name]);
        } catch {
            // The note shows again next time; nothing else depends on it.
        }
    }

    // ============================================================ placement buttons
    sectionOf(name) {
        return this.state.sections.find((sec) => (sec.fields || []).some((f) => f.name === name));
    }

    moveField(name, delta) {
        const sec = this.sectionOf(name);
        if (!sec) {
            return;
        }
        const list = this.sortedFields(sec);
        const at = list.findIndex((f) => f.name === name);
        const to = at + delta;
        if (to < 0 || to >= list.length) {
            return;
        }
        const [item] = list.splice(at, 1);
        list.splice(to, 0, item);
        this.touch();
    }

    get moveTargets() {
        const out = [];
        for (const sec of this.state.sections) {
            if (sec.anchor.kind !== "card") {
                out.push({ key: `s:${sec.id}`, label: sec.title || _t("New section") });
            }
        }
        for (const card of this.host.sections || []) {
            out.push({ key: `c:${card.name}`, label: card.title || card.name });
        }
        out.push({ key: "new", label: _t("A new section") });
        return out;
    }

    currentTarget(name) {
        const sec = this.sectionOf(name);
        if (!sec) {
            return "";
        }
        return sec.anchor.kind === "card" ? `c:${sec.anchor.name}` : `s:${sec.id}`;
    }

    onMoveTo(name, ev) {
        const key = ev.target.value;
        if (!key || key === this.currentTarget(name)) {
            return;
        }
        if (key === "new") {
            this.removeEverywhere(name);
            this.addSection(name);
        } else if (key.startsWith("c:")) {
            const sec = this.ensureCardSection(key.slice(2));
            this.placeField(name, sec.id);
        } else {
            this.placeField(name, key.slice(2));
        }
    }

    takeOff(name) {
        this.removeEverywhere(name);
        this.touch();
    }

    // ============================================================ sections
    setSectionTitle(sec, ev) {
        sec.title = ev.target.value;
        this.touch();
    }

    setSectionTitleVi(sec, ev) {
        sec.title_vi = ev.target.value;
        this.touch();
    }

    setSectionAnchor(sec, kind) {
        sec.anchor = { kind };
        this.touch();
    }

    moveSection(sec, delta) {
        const list = this.state.sections;
        const kind = sec.anchor.kind;
        const peers = list.filter((s) => s.anchor.kind === kind);
        const at = peers.indexOf(sec);
        const other = peers[at + delta];
        if (!other) {
            return;
        }
        const i = list.indexOf(sec);
        const j = list.indexOf(other);
        list[i] = other;
        list[j] = sec;
        this.touch();
    }

    deleteSection(sec) {
        if ((sec.fields || []).length) {
            return;
        }
        this.state.sections = this.state.sections.filter((s) => s.id !== sec.id);
        this.clearSelection();
        this.touch();
    }

    // ============================================================ drag and drop
    onDragStart(ev, drag) {
        this._drag = drag;
        try {
            ev.dataTransfer.effectAllowed = "move";
            ev.dataTransfer.setData("text/plain", JSON.stringify(drag));
        } catch {
            // Some browsers refuse setData on a synthetic event; the
            // component keeps its own copy in `_drag`.
        }
    }

    onDragEnd() {
        this._drag = null;
        this.state.dragOver = "";
    }

    onDragOver(ev, key) {
        if (!this._drag) {
            return;
        }
        ev.preventDefault();
        if (this.state.dragOver !== key) {
            this.state.dragOver = key;
        }
    }

    onDragLeave(ev, key) {
        if (this.state.dragOver === key && !ev.currentTarget.contains(ev.relatedTarget)) {
            this.state.dragOver = "";
        }
    }

    /** `target`: {sectionId, index?} | {card} | {newSection: true} */
    onDrop(ev, target) {
        ev.preventDefault();
        ev.stopPropagation();
        const drag = this._drag;
        this._drag = null;
        this.state.dragOver = "";
        if (!drag) {
            return;
        }
        if (drag.kind === "type") {
            this.startNewField(drag.type, target);
            return;
        }
        if (drag.kind === "field") {
            if (target.newSection) {
                this.removeEverywhere(drag.name);
                this.addSection(drag.name);
            } else if (target.card) {
                const sec = this.ensureCardSection(target.card);
                this.placeField(drag.name, sec.id, target.index === undefined ? -1 : target.index);
            } else if (target.sectionId) {
                this.placeField(drag.name, target.sectionId, target.index === undefined ? -1 : target.index);
            }
            this.selectField(drag.name);
        }
    }

    // ============================================================ publish
    openPublish() {
        if (!this.changes.length) {
            this.notify(_t("There is nothing new to publish."));
            return;
        }
        this.state.sheet = "publish";
    }

    closeSheet() {
        this.state.sheet = "";
        this.state.refs = null;
        this.state.deleteText = "";
        this.state.rollbackTo = 0;
    }

    async publish() {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        if (this._draftTimer) {
            clearTimeout(this._draftTimer);
            this._draftTimer = null;
        }
        try {
            await this.orm.call("fs.studio", "publish", [this.model, this.viewId, clone(this.state.sections)], {
                base_version: this.data.layout.version,
            });
            this.state.sheet = "";
            this.notify(_t("Published. Everyone sees it on their next page load."), "success");
            this.state.busy = false;
            await this.goBack(true);
            return;
        } catch (error) {
            this.notify(errorText(error, _t("The layout could not be published.")), "danger");
        }
        this.state.busy = false;
    }

    async discard() {
        if (this._draftTimer) {
            clearTimeout(this._draftTimer);
            this._draftTimer = null;
        }
        this.state.sections = clone(this.state.published);
        this.clearSelection();
        try {
            await this.orm.call("fs.studio", "discard_draft", [this.model, this.viewId]);
        } catch (error) {
            this.notify(errorText(error, _t("The draft could not be discarded.")), "danger");
        }
    }

    continueDraft() {
        this.state.sections = clone(this.state.draft || []);
        this.state.draft = null;
        this.state.sheet = "";
    }

    async startFresh() {
        this.state.draft = null;
        this.state.sheet = "";
        await this.discard();
    }

    // ============================================================ history
    openHistory() {
        this.state.rollbackTo = 0;
        this.state.sheet = "history";
    }

    askRollback(version) {
        this.state.rollbackTo = version;
    }

    async rollback() {
        const version = this.state.rollbackTo;
        if (!version || this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            const res = await this.orm.call("fs.studio", "rollback", [this.data.layout.id, version]);
            this.closeSheet();
            const text = res.dropped
                ? _t("Back to version %(old)s, published as version %(new)s. Fields deleted since then were left out.", { old: version, new: res.version })
                : _t("Back to version %(old)s, published as version %(new)s.", { old: version, new: res.version });
            this.notify(text, "success");
            this.state.busy = false;
            await this.goBack(true);
            return;
        } catch (error) {
            this.notify(errorText(error, _t("That version could not be published.")), "danger");
        }
        this.state.busy = false;
    }

    // ============================================================ delete
    async openDelete() {
        const sel = this.state.sel;
        if (!sel || sel.kind !== "field") {
            return;
        }
        this.state.refs = null;
        this.state.deleteText = "";
        this.state.sheet = "delete";
        try {
            this.state.refs = await this.orm.call("fs.studio", "field_references", [this.model, sel.name]);
        } catch (error) {
            this.closeSheet();
            this.notify(errorText(error, _t("Studio could not check where this field is used.")), "danger");
        }
    }

    get valueCount() {
        const ref = (this.state.refs || []).find((r) => r.kind === "values");
        return ref ? ref.count : 0;
    }

    get valueSentence() {
        if (this.valueCount === 1) {
            return _t("This field has a value on 1 record.");
        }
        return _t("This field has values on %s records.", this.valueCount);
    }

    get deleteWarning() {
        return _t("Deleting it removes those values for good.");
    }

    goBackLabel(version) {
        return _t("Go back to version %s", version);
    }

    get blockers() {
        return (this.state.refs || []).filter((r) => r.blocker);
    }

    get canDelete() {
        return this.state.refs && !this.blockers.length && this.state.deleteText === "DELETE" && !this.state.busy;
    }

    onDeleteText(ev) {
        this.state.deleteText = ev.target.value;
    }

    async deleteField() {
        const sel = this.state.sel;
        if (!this.canDelete || !sel) {
            return;
        }
        this.state.busy = true;
        try {
            const res = await this.orm.call("fs.studio", "delete_field", [this.model, sel.name], {
                confirm: this.state.deleteText,
            });
            this.closeSheet();
            this.removeEverywhere(sel.name);
            this.clearSelection();
            await this.refresh();
            this.state.sections = this.state.sections.filter(
                (sec) => sec.anchor.kind !== "card" || (sec.fields || []).length
            );
            this.notify(
                res.count === 1
                    ? _t("Field deleted. 1 record had a value.")
                    : _t("Field deleted. %s records had a value.", res.count),
                "success"
            );
        } catch (error) {
            this.notify(errorText(error, _t("The field could not be deleted.")), "danger");
        }
        this.state.busy = false;
    }

    // ============================================================ leaving
    async goBack(published = false) {
        if (published) {
            rpcBus.trigger("CLEAR-CACHES", "get_views");
        } else if (this.dirty) {
            if (this._draftTimer) {
                clearTimeout(this._draftTimer);
                this._draftTimer = null;
            }
            await this.saveDraft();
            this.notify(_t("Your changes are kept as a draft until you publish them."));
        }
        try {
            await this.actionService.restore();
            return;
        } catch {
            // Opened directly: there is no screen behind this one.
        }
        if (this.resId) {
            await this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: this.model,
                res_id: this.resId,
                views: [[this.viewId, "form"]],
                target: "current",
            });
            return;
        }
        await this.actionService.doAction("biz_form_studio.action_fs_library");
    }

    openRequiredRules() {
        const xmlid = this.data && this.data.required_rules_action;
        if (xmlid) {
            this.actionService.doAction(xmlid);
        }
    }

    // ============================================================ chips
    chipClass(name) {
        const info = this.fields[name] || {};
        const sel = this.state.sel;
        const classes = ["fs-chip"];
        if (info.std) {
            classes.push("is-std");
        } else {
            classes.push("is-custom");
        }
        if (info.locked) {
            classes.push("is-locked");
        }
        if (sel && sel.kind === "field" && sel.name === name) {
            classes.push("is-sel");
        }
        if (this.state.dragOver === `f:${name}`) {
            classes.push("is-over");
        }
        return classes.join(" ");
    }

    zoneClass(key, base) {
        return this.state.dragOver === key ? `${base} is-over` : base;
    }
}

registry.category("actions").add("biz_form_studio.studio", FormStudioEditor);
