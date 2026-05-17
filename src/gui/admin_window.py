"""Admin Window — GUI quản lý GV/SV/Lớp/TKB (E8-S1)."""

import logging
import os
import re
from tkinter import filedialog
import customtkinter as ctk

logger = logging.getLogger(__name__)

DAY_MAP = {
    0: "Thứ 2", 1: "Thứ 3", 2: "Thứ 4",
    3: "Thứ 5", 4: "Thứ 6", 5: "Thứ 7", 6: "Chủ nhật",
}
DAY_REVERSE = {v: k for k, v in DAY_MAP.items()}

# [F1-fix] Regex for HH:MM validation
_TIME_RE = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
# [F4-fix] Module-level date regex (avoid recompilation on every filter call)
_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


class AdminWindow(ctk.CTkToplevel):
    def __init__(self, parent, class_mgr, student_mgr, db, initial_tab=None):
        super().__init__(parent)
        self.class_mgr = class_mgr
        self.student_mgr = student_mgr
        self.db = db

        self.title("⚙️ Quản lý hệ thống")
        self.geometry("1000x600")
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(expand=True, fill="both", padx=10, pady=10)

        for name in ["Giảng viên", "Sinh viên", "Lớp học", "Thời khóa biểu", "📋 Lịch sử"]:
            self.tabview.add(name)

        self._teacher_widgets = []
        self._student_widgets = []
        self._class_widgets = []
        self._tt_widgets = []
        self._history_widgets = []

        self._build_teacher_tab()
        self._build_student_tab()
        self._build_class_tab()
        self._build_timetable_tab()
        self._build_history_tab()

        # [E9-S3] Set active tab nếu specified
        if initial_tab:
            try:
                self.tabview.set(initial_tab)
            except ValueError:
                pass  # Tab name không tồn tại — ignore

    def _on_close(self):
        """[CR-9] Defensive grab_release — Tk may raise if nested dialog holds grab."""
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    # ── HELPERS ──

    def _make_list_frame(self, tab):
        sf = ctk.CTkScrollableFrame(tab)
        sf.pack(expand=True, fill="both", padx=5, pady=5)
        return sf

    def _make_button_bar(self, tab, add_text, add_cmd):
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", padx=5, pady=5)
        ctk.CTkButton(bar, text=add_text, command=add_cmd).pack(side="left", padx=5)
        return bar

    def _confirm_delete(self, name, on_confirm):
        """[F2/F12-fix] Exception-safe confirm dialog."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("⚠️ Xác nhận xóa")
        dlg.geometry("350x160")
        dlg.transient(self)
        dlg.grab_set()
        ctk.CTkLabel(dlg, text=f"Xóa {name}?", font=ctk.CTkFont(size=16)).pack(pady=(20, 5))
        ctk.CTkLabel(dlg, text="Không thể hoàn tác.", text_color="gray").pack(pady=(0, 15))
        bf = ctk.CTkFrame(dlg, fg_color="transparent")
        bf.pack()

        def _do_delete():
            try:
                on_confirm()
            except Exception as e:
                logger.error(f"Delete failed: {e}")
            finally:
                # [CR-6] Release grab before destroy to prevent Tk errors
                try:
                    dlg.grab_release()
                except Exception:
                    pass
                dlg.destroy()

        def _cancel():
            try:
                dlg.grab_release()
            except Exception:
                pass
            dlg.destroy()

        ctk.CTkButton(bf, text="Xóa", fg_color="#DC3545", hover_color="#C82333",
                       command=_do_delete).pack(side="left", padx=10)
        ctk.CTkButton(bf, text="Hủy", command=_cancel).pack(side="right", padx=10)

    def _clear_widgets(self, widgets_list):
        for w in widgets_list:
            try:
                w.destroy()
            except Exception:
                pass
        widgets_list.clear()

    def _safe_close_dialog(self, dlg):
        """[CR-Q1] Defensive grab_release + destroy for any dialog."""
        try:
            dlg.grab_release()
        except Exception:
            pass
        dlg.destroy()

    def _show_empty_label(self, parent, widgets_list, text="(Chưa có dữ liệu)"):
        """[F9-fix] Show placeholder when list is empty."""
        lbl = ctk.CTkLabel(parent, text=text, text_color="gray",
                           font=ctk.CTkFont(size=13))
        lbl.pack(pady=20)
        widgets_list.append(lbl)

    def _pick_image(self, dlg, img_dict, path_lbl):
        """[F4/F5-fix] Shared image picker with safe grab management."""
        dlg.grab_release()
        p = filedialog.askopenfilename(filetypes=[("Ảnh", "*.jpg *.jpeg *.png")])
        if dlg.winfo_exists():
            dlg.grab_set()
        else:
            # [F4-fix] Dialog closed while filedialog open → restore AdminWindow grab
            if self.winfo_exists():
                self.grab_set()
            return
        if p:
            img_dict["path"] = p
            path_lbl.configure(text=f"📷 {os.path.basename(p)}", text_color="white")

    # ══════════════════════════════════════════
    # TAB 1: GIẢNG VIÊN
    # ══════════════════════════════════════════

    def _build_teacher_tab(self):
        tab = self.tabview.tab("Giảng viên")
        self._teacher_scroll = self._make_list_frame(tab)
        self._make_button_bar(tab, "➕ Thêm GV", self._show_add_teacher_dialog)
        self._refresh_teacher_list()

    def _refresh_teacher_list(self):
        self._clear_widgets(self._teacher_widgets)
        teachers = self.class_mgr.get_all_teachers()
        if not teachers:
            self._show_empty_label(self._teacher_scroll, self._teacher_widgets)
            return
        for t in teachers:
            row = ctk.CTkFrame(self._teacher_scroll)
            row.pack(fill="x", padx=2, pady=1)
            ctk.CTkLabel(row, text=t['name'], width=150, anchor="w").pack(side="left", padx=5)
            ctk.CTkLabel(row, text=t['teacher_code'], width=100).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=t.get('photo_path', ''), width=200, anchor="w",
                         text_color="gray").pack(side="left", padx=5)
            tid = t['id']
            ctk.CTkButton(row, text="❌", width=30, height=28, fg_color="#DC3545",
                          hover_color="#C82333",
                          command=lambda i=tid, n=t['name']: self._remove_teacher(i, n)
                          ).pack(side="right", padx=5)
            self._teacher_widgets.append(row)

    def _remove_teacher(self, tid, name):
        """[CR-5] Proper function body instead of lambda list hack."""
        def _do():
            self.class_mgr.remove_teacher(tid)
            self._refresh_teacher_list()
        self._confirm_delete(f"GV {name}", _do)

    def _show_add_teacher_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("➕ Thêm giảng viên")
        dlg.geometry("420x380")
        dlg.transient(self)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="Tên giảng viên:").pack(pady=(15, 2), padx=20, anchor="w")
        name_e = ctk.CTkEntry(dlg, placeholder_text="Tên", width=370)
        name_e.pack(padx=20)

        ctk.CTkLabel(dlg, text="Mã giảng viên:").pack(pady=(10, 2), padx=20, anchor="w")
        code_e = ctk.CTkEntry(dlg, placeholder_text="Mã GV", width=370)
        code_e.pack(padx=20)

        img = {"path": ""}
        path_lbl = ctk.CTkLabel(dlg, text="Chưa chọn ảnh", text_color="gray")
        path_lbl.pack(padx=20, pady=5)

        ctk.CTkButton(dlg, text="📷 Chọn ảnh",
                      command=lambda: self._pick_image(dlg, img, path_lbl)).pack(padx=20, pady=5)

        err = ctk.CTkLabel(dlg, text="", text_color="red")
        err.pack(padx=20)

        def submit():
            n, c = name_e.get().strip(), code_e.get().strip()
            if not n or not c:
                err.configure(text="⚠️ Vui lòng nhập tên và mã GV")
                return
            if not img["path"]:
                err.configure(text="⚠️ Vui lòng chọn ảnh chân dung")
                return
            try:
                self.class_mgr.add_teacher(n, c, img["path"])
                self._safe_close_dialog(dlg)
                self._refresh_teacher_list()
            except Exception as e:  # [F3-fix] catch all exceptions from face processing
                err.configure(text=str(e))

        bf = ctk.CTkFrame(dlg, fg_color="transparent")
        bf.pack(pady=10)
        ctk.CTkButton(bf, text="Thêm", command=submit).pack(side="left", padx=10)
        ctk.CTkButton(bf, text="Hủy", command=lambda: self._safe_close_dialog(dlg)).pack(side="right", padx=10)

    # ══════════════════════════════════════════
    # TAB 2: SINH VIÊN
    # ══════════════════════════════════════════

    def _build_student_tab(self):
        tab = self.tabview.tab("Sinh viên")
        self._student_scroll = self._make_list_frame(tab)
        self._make_button_bar(tab, "➕ Thêm SV", self._show_add_student_dialog)
        self._refresh_student_list()

    def _refresh_student_list(self):
        self._clear_widgets(self._student_widgets)
        students = self.student_mgr.get_all_students()
        if not students:
            self._show_empty_label(self._student_scroll, self._student_widgets)
            return
        for s in students:
            row = ctk.CTkFrame(self._student_scroll)
            row.pack(fill="x", padx=2, pady=1)
            ctk.CTkLabel(row, text=s['name'], width=150, anchor="w").pack(side="left", padx=5)
            ctk.CTkLabel(row, text=s['student_code'], width=100).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=s.get('photo_path', ''), width=200, anchor="w",
                         text_color="gray").pack(side="left", padx=5)
            sid = s['id']
            ctk.CTkButton(row, text="❌", width=30, height=28, fg_color="#DC3545",
                          hover_color="#C82333",
                          command=lambda i=sid, n=s['name']: self._remove_student(i, n)
                          ).pack(side="right", padx=5)
            self._student_widgets.append(row)

    def _remove_student(self, sid, name):
        """[CR-5] Proper function body instead of lambda list hack."""
        def _do():
            self.student_mgr.remove_student(sid)
            self._refresh_student_list()
        self._confirm_delete(f"SV {name}", _do)

    def _show_add_student_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("➕ Thêm sinh viên")
        dlg.geometry("420x380")
        dlg.transient(self)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="Tên sinh viên:").pack(pady=(15, 2), padx=20, anchor="w")
        name_e = ctk.CTkEntry(dlg, placeholder_text="Tên", width=370)
        name_e.pack(padx=20)

        ctk.CTkLabel(dlg, text="MSSV:").pack(pady=(10, 2), padx=20, anchor="w")
        code_e = ctk.CTkEntry(dlg, placeholder_text="MSSV", width=370)
        code_e.pack(padx=20)

        img = {"path": ""}
        path_lbl = ctk.CTkLabel(dlg, text="Chưa chọn ảnh", text_color="gray")
        path_lbl.pack(padx=20, pady=5)

        ctk.CTkButton(dlg, text="📷 Chọn ảnh",
                      command=lambda: self._pick_image(dlg, img, path_lbl)).pack(padx=20, pady=5)

        err = ctk.CTkLabel(dlg, text="", text_color="red")
        err.pack(padx=20)

        def submit():
            n, c = name_e.get().strip(), code_e.get().strip()
            if not n or not c:
                err.configure(text="⚠️ Vui lòng nhập tên và MSSV")
                return
            if not img["path"]:
                err.configure(text="⚠️ Vui lòng chọn ảnh chân dung")
                return
            try:
                self.student_mgr.add_student(n, c, img["path"])
                self._safe_close_dialog(dlg)
                self._refresh_student_list()
            except Exception as e:  # [F3-fix] catch all exceptions from face processing
                err.configure(text=str(e))

        bf = ctk.CTkFrame(dlg, fg_color="transparent")
        bf.pack(pady=10)
        ctk.CTkButton(bf, text="Thêm", command=submit).pack(side="left", padx=10)
        ctk.CTkButton(bf, text="Hủy", command=lambda: self._safe_close_dialog(dlg)).pack(side="right", padx=10)

    # ══════════════════════════════════════════
    # TAB 3: LỚP HỌC
    # ══════════════════════════════════════════

    def _build_class_tab(self):
        tab = self.tabview.tab("Lớp học")
        self._class_scroll = self._make_list_frame(tab)
        self._make_button_bar(tab, "➕ Thêm lớp", self._show_add_class_dialog)
        self._refresh_class_list()

    def _refresh_class_list(self):
        self._clear_widgets(self._class_widgets)
        teachers = {t['id']: t['name'] for t in self.class_mgr.get_all_teachers()}
        classes = self.class_mgr.get_all_classes()
        if not classes:
            self._show_empty_label(self._class_scroll, self._class_widgets)
            return
        for c in classes:
            row = ctk.CTkFrame(self._class_scroll)
            row.pack(fill="x", padx=2, pady=1)
            ctk.CTkLabel(row, text=c['class_code'], width=100, anchor="w").pack(side="left", padx=5)
            ctk.CTkLabel(row, text=c['subject'], width=150, anchor="w").pack(side="left", padx=5)
            gv = teachers.get(c.get('teacher_id'), '—')
            ctk.CTkLabel(row, text=f"GV: {gv}", width=120, anchor="w").pack(side="left", padx=5)
            # [F8-fix] Show enrolled student count
            cid = c['id']
            enrolled = self.class_mgr.get_students_in_class(cid)
            ctk.CTkLabel(row, text=f"👥 {len(enrolled)} SV", width=70,
                         text_color="gray").pack(side="left", padx=5)
            ctk.CTkButton(row, text="❌", width=30, height=28, fg_color="#DC3545",
                          hover_color="#C82333",
                          command=lambda i=cid, n=c['class_code']: self._remove_class(i, n)
                          ).pack(side="right", padx=5)
            ctk.CTkButton(row, text="👥 Gán SV", width=80, height=28,
                          command=lambda i=cid: self._show_enroll_dialog(i)
                          ).pack(side="right", padx=5)
            self._class_widgets.append(row)

    def _remove_class(self, cid, name):
        """[CR-5] Proper function body instead of lambda list hack."""
        def _do():
            self.class_mgr.delete_class(cid)
            self._refresh_class_list()
        self._confirm_delete(f"lớp {name}", _do)

    def _show_add_class_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("➕ Thêm lớp học")
        dlg.geometry("420x320")
        dlg.transient(self)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="Mã lớp:").pack(pady=(15, 2), padx=20, anchor="w")
        code_e = ctk.CTkEntry(dlg, placeholder_text="Mã lớp", width=370)
        code_e.pack(padx=20)

        ctk.CTkLabel(dlg, text="Tên môn:").pack(pady=(10, 2), padx=20, anchor="w")
        subj_e = ctk.CTkEntry(dlg, placeholder_text="Tên môn học", width=370)
        subj_e.pack(padx=20)

        teachers = self.class_mgr.get_all_teachers()
        t_map = {f"{t['name']} ({t['teacher_code']})": t['id'] for t in teachers}
        t_names = list(t_map.keys()) or ["(Chưa có GV)"]

        ctk.CTkLabel(dlg, text="Giảng viên:").pack(pady=(10, 2), padx=20, anchor="w")
        t_dd = ctk.CTkComboBox(dlg, values=t_names, width=370, state="readonly")
        t_dd.pack(padx=20)
        t_dd.set(t_names[0])

        err = ctk.CTkLabel(dlg, text="", text_color="red")
        err.pack(padx=20, pady=5)

        def submit():
            code, subj = code_e.get().strip(), subj_e.get().strip()
            if not code or not subj:
                err.configure(text="⚠️ Vui lòng nhập mã lớp và tên môn")
                return
            tid = t_map.get(t_dd.get())
            if tid is None:
                err.configure(text="⚠️ Vui lòng chọn giảng viên")
                return
            try:
                self.class_mgr.add_class(code, subj, tid)
                self._safe_close_dialog(dlg)
                self._refresh_class_list()
            except Exception as e:  # [A4-fix] Broad catch for DB errors
                err.configure(text=str(e))

        bf = ctk.CTkFrame(dlg, fg_color="transparent")
        bf.pack(pady=10)
        ctk.CTkButton(bf, text="Thêm", command=submit).pack(side="left", padx=10)
        ctk.CTkButton(bf, text="Hủy", command=lambda: self._safe_close_dialog(dlg)).pack(side="right", padx=10)

    def _show_enroll_dialog(self, class_id):
        dlg = ctk.CTkToplevel(self)
        dlg.title("👥 Quản lý sinh viên trong lớp")
        dlg.geometry("480x550")
        dlg.transient(self)
        dlg.grab_set()

        # ── Enrolled students section (with unenroll buttons) ──
        enrolled_frame = ctk.CTkFrame(dlg)
        enrolled_frame.pack(fill="x", padx=10, pady=(10, 5))
        enrolled_label = ctk.CTkLabel(enrolled_frame, text="", font=ctk.CTkFont(size=13, weight="bold"))
        enrolled_label.pack(anchor="w", padx=5, pady=2)
        enrolled_scroll = ctk.CTkScrollableFrame(enrolled_frame, height=120)
        enrolled_scroll.pack(fill="x", padx=5, pady=2)
        enrolled_widgets = []

        # ── Available students section (checkboxes to enroll) ──
        ctk.CTkLabel(dlg, text="Thêm sinh viên vào lớp:", font=ctk.CTkFont(size=13, weight="bold")).pack(
            anchor="w", padx=15, pady=(10, 2))
        avail_scroll = ctk.CTkScrollableFrame(dlg)
        avail_scroll.pack(expand=True, fill="both", padx=10, pady=5)
        checks = {}
        avail_widgets = []

        err = ctk.CTkLabel(dlg, text="", text_color="red")
        err.pack(padx=10)

        def _rebuild_lists():
            """[Q3/D4-fix] Rebuild both enrolled and available lists from live DB data."""
            # Clear enrolled section
            for w in enrolled_widgets:
                try:
                    w.destroy()
                except Exception:
                    pass
            enrolled_widgets.clear()
            # Clear available section
            for w in avail_widgets:
                try:
                    w.destroy()
                except Exception:
                    pass
            avail_widgets.clear()
            checks.clear()

            all_students = self.student_mgr.get_all_students()
            enrolled = self.class_mgr.get_students_in_class(class_id)
            enrolled_ids = {s['id'] for s in enrolled}

            # Enrolled list
            enrolled_label.configure(text=f"Đã gán ({len(enrolled)} SV):")
            if enrolled:
                for s in enrolled:
                    row = ctk.CTkFrame(enrolled_scroll)
                    row.pack(fill="x", padx=2, pady=1)
                    ctk.CTkLabel(row, text=f"{s['name']} ({s['student_code']})",
                                 anchor="w").pack(side="left", padx=5)
                    sid = s['id']
                    ctk.CTkButton(row, text="➖", width=30, height=24,
                                  fg_color="#DC3545", hover_color="#C82333",
                                  command=lambda i=sid, n=s['name']: _unenroll(i, n)
                                  ).pack(side="right", padx=5)
                    enrolled_widgets.append(row)
            else:
                lbl = ctk.CTkLabel(enrolled_scroll, text="(Chưa có SV nào)", text_color="gray")
                lbl.pack(pady=5)
                enrolled_widgets.append(lbl)

            # Available list
            available = [s for s in all_students if s['id'] not in enrolled_ids]
            if available:
                for s in available:
                    var = ctk.BooleanVar(value=False)
                    cb = ctk.CTkCheckBox(avail_scroll,
                                         text=f"{s['name']} ({s['student_code']})",
                                         variable=var)
                    cb.pack(anchor="w", padx=10, pady=2)
                    checks[s['id']] = var
                    avail_widgets.append(cb)
            else:
                lbl = ctk.CTkLabel(avail_scroll, text="Tất cả SV đã thuộc lớp này.",
                                   text_color="gray")
                lbl.pack(pady=10)
                avail_widgets.append(lbl)

        def _unenroll(sid, name):
            """[P2-fix] Unenroll student from class."""
            try:
                self.class_mgr.remove_student_from_class(class_id, sid)
            except ValueError as e:
                err.configure(text=f"⚠️ {e}")
                return
            self._refresh_class_list()
            _rebuild_lists()
            err.configure(text="")

        def submit():
            selected = [sid for sid, var in checks.items() if var.get()]
            if not selected:
                err.configure(text="⚠️ Chưa chọn sinh viên nào")
                return
            # [F6-fix] Collect and display enrollment failures
            failures = []
            for sid in selected:
                try:
                    self.class_mgr.add_student_to_class(class_id, sid)
                except ValueError as e:
                    failures.append(str(e))
                    logger.warning(f"Enroll failed for {sid}: {e}")
            # [CR-1] Always refresh class list — partial success already committed to DB
            self._refresh_class_list()
            if failures:
                err.configure(text=f"⚠️ {len(failures)} lỗi: {failures[0]}")
                # [Q3-fix] Rebuild lists so successfully enrolled students move to enrolled section
                _rebuild_lists()
            else:
                self._safe_close_dialog(dlg)

        # Initial build
        _rebuild_lists()

        bf = ctk.CTkFrame(dlg, fg_color="transparent")
        bf.pack(pady=10)
        ctk.CTkButton(bf, text="Gán", command=submit).pack(side="left", padx=10)
        ctk.CTkButton(bf, text="Đóng", command=lambda: self._safe_close_dialog(dlg)).pack(side="right", padx=10)

    # ══════════════════════════════════════════
    # TAB 4: THỜI KHÓA BIỂU
    # ══════════════════════════════════════════

    def _build_timetable_tab(self):
        tab = self.tabview.tab("Thời khóa biểu")
        self._tt_scroll = self._make_list_frame(tab)
        self._make_button_bar(tab, "➕ Thêm TKB", self._show_add_timetable_dialog)
        self._refresh_timetable_list()

    def _refresh_timetable_list(self):
        self._clear_widgets(self._tt_widgets)
        entries = self.db.get_all_timetable()
        if not entries:
            self._show_empty_label(self._tt_scroll, self._tt_widgets)
            return

        # ── Group by day_of_week (0=Mon → 6=Sun), sort by start_time ──
        from collections import defaultdict
        grouped = defaultdict(list)
        for t in entries:
            grouped[t['day_of_week']].append(t)

        # Render each day group in order (Thứ 2 → Chủ nhật)
        for day_idx in range(7):
            day_entries = grouped.get(day_idx)
            if not day_entries:
                continue
            # Sort entries within each day by start_time
            day_entries.sort(key=lambda e: e['start_time'])

            day_str = DAY_MAP.get(day_idx, str(day_idx))

            # ── Day header ──
            header = ctk.CTkFrame(self._tt_scroll, fg_color="#2B5278",
                                  corner_radius=6)
            header.pack(fill="x", padx=2, pady=(10, 3))
            ctk.CTkLabel(header, text=f"📅  {day_str}",
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color="#E0E0E0").pack(side="left", padx=10, pady=4)
            ctk.CTkLabel(header, text=f"{len(day_entries)} tiết",
                         font=ctk.CTkFont(size=12),
                         text_color="#90CAF9").pack(side="right", padx=10, pady=4)
            self._tt_widgets.append(header)

            # ── Entries under this day ──
            for t in day_entries:
                row = ctk.CTkFrame(self._tt_scroll)
                row.pack(fill="x", padx=(20, 2), pady=1)
                # [CR-7/Q4-fix] Show class_code with subject for better context
                class_label = t.get('class_code', '')
                subject = t.get('subject', '')
                display_label = f"{class_label} — {subject}" if subject else class_label
                ctk.CTkLabel(row, text=display_label, width=200, anchor="w").pack(side="left", padx=5)
                ctk.CTkLabel(row, text=f"{t['start_time']}–{t['end_time']}", width=120).pack(side="left", padx=5)
                ttid = t['id']
                ctk.CTkButton(row, text="❌", width=30, height=28, fg_color="#DC3545",
                              hover_color="#C82333",
                              command=lambda i=ttid: self._remove_timetable(i)
                              ).pack(side="right", padx=5)
                ctk.CTkButton(row, text="✏️", width=30, height=28,
                              command=lambda i=ttid, entry=t: self._show_edit_timetable_dialog(i, entry)
                              ).pack(side="right", padx=2)
                self._tt_widgets.append(row)

    def _remove_timetable(self, ttid):
        """[CR-5] Proper function body instead of lambda list hack."""
        def _do():
            self.db.delete_timetable(ttid)
            self._refresh_timetable_list()
        self._confirm_delete("TKB này", _do)

    def _show_edit_timetable_dialog(self, ttid, entry):
        """Edit an existing timetable entry — update day/start/end in-place."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("✏️ Sửa thời khóa biểu")
        dlg.geometry("420x340")
        dlg.transient(self)
        dlg.grab_set()

        class_label = entry.get('class_code', '')
        subject = entry.get('subject', '')
        display = f"{class_label} — {subject}" if subject else class_label
        ctk.CTkLabel(dlg, text=f"Lớp: {display}",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 10), padx=20)

        day_names = list(DAY_MAP.values())
        ctk.CTkLabel(dlg, text="Thứ:").pack(pady=(5, 2), padx=20, anchor="w")
        d_dd = ctk.CTkComboBox(dlg, values=day_names, width=370, state="readonly")
        d_dd.pack(padx=20)
        current_day = DAY_MAP.get(entry['day_of_week'], day_names[0])
        d_dd.set(current_day)

        ctk.CTkLabel(dlg, text="Giờ bắt đầu (HH:MM):").pack(pady=(10, 2), padx=20, anchor="w")
        start_e = ctk.CTkEntry(dlg, width=370)
        start_e.pack(padx=20)
        start_e.insert(0, entry['start_time'])

        ctk.CTkLabel(dlg, text="Giờ kết thúc (HH:MM):").pack(pady=(10, 2), padx=20, anchor="w")
        end_e = ctk.CTkEntry(dlg, width=370)
        end_e.pack(padx=20)
        end_e.insert(0, entry['end_time'])

        err = ctk.CTkLabel(dlg, text="", text_color="red")
        err.pack(padx=20, pady=5)

        def submit():
            day = DAY_REVERSE.get(d_dd.get())
            st, et = start_e.get().strip(), end_e.get().strip()
            if not st or not et:
                err.configure(text="⚠️ Vui lòng nhập giờ bắt đầu và kết thúc")
                return
            if not _TIME_RE.match(st) or not _TIME_RE.match(et):
                err.configure(text="⚠️ Giờ phải đúng định dạng HH:MM (00:00–23:59)")
                return
            if st >= et:
                err.configure(text="⚠️ Giờ bắt đầu phải trước giờ kết thúc")
                return
            try:
                self.db.update_timetable(ttid, day, st, et)
            except Exception as e:
                logger.error(f"Edit timetable failed: {e}")
                err.configure(text=f"⚠️ Lỗi sửa TKB: {e}")
                return
            self._safe_close_dialog(dlg)
            self._refresh_timetable_list()

        bf = ctk.CTkFrame(dlg, fg_color="transparent")
        bf.pack(pady=10)
        ctk.CTkButton(bf, text="Lưu", command=submit).pack(side="left", padx=10)
        ctk.CTkButton(bf, text="Hủy", command=lambda: self._safe_close_dialog(dlg)).pack(side="right", padx=10)

    def _show_add_timetable_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("➕ Thêm thời khóa biểu")
        dlg.geometry("420x380")
        dlg.transient(self)
        dlg.grab_set()

        classes = self.db.get_all_classes()
        c_map = {f"{c['class_code']} — {c['subject']}": c['id'] for c in classes}
        c_names = list(c_map.keys()) or ["(Chưa có lớp)"]

        ctk.CTkLabel(dlg, text="Lớp học:").pack(pady=(15, 2), padx=20, anchor="w")
        c_dd = ctk.CTkComboBox(dlg, values=c_names, width=370, state="readonly")
        c_dd.pack(padx=20)
        c_dd.set(c_names[0])

        day_names = list(DAY_MAP.values())
        ctk.CTkLabel(dlg, text="Thứ:").pack(pady=(10, 2), padx=20, anchor="w")
        d_dd = ctk.CTkComboBox(dlg, values=day_names, width=370, state="readonly")
        d_dd.pack(padx=20)
        d_dd.set(day_names[0])

        ctk.CTkLabel(dlg, text="Giờ bắt đầu (HH:MM):").pack(pady=(10, 2), padx=20, anchor="w")
        start_e = ctk.CTkEntry(dlg, placeholder_text="08:00", width=370)
        start_e.pack(padx=20)

        ctk.CTkLabel(dlg, text="Giờ kết thúc (HH:MM):").pack(pady=(10, 2), padx=20, anchor="w")
        end_e = ctk.CTkEntry(dlg, placeholder_text="10:00", width=370)
        end_e.pack(padx=20)

        err = ctk.CTkLabel(dlg, text="", text_color="red")
        err.pack(padx=20, pady=5)

        def submit():
            cid = c_map.get(c_dd.get())
            if cid is None:
                err.configure(text="⚠️ Vui lòng chọn lớp")
                return
            day = DAY_REVERSE.get(d_dd.get())
            st, et = start_e.get().strip(), end_e.get().strip()
            if not st or not et:
                err.configure(text="⚠️ Vui lòng nhập giờ bắt đầu và kết thúc")
                return
            # [F1-fix] Validate HH:MM format
            if not _TIME_RE.match(st) or not _TIME_RE.match(et):
                err.configure(text="⚠️ Giờ phải đúng định dạng HH:MM (00:00–23:59)")
                return
            if st >= et:
                err.configure(text="⚠️ Giờ bắt đầu phải trước giờ kết thúc")
                return
            # [CR-10] Wrap in try-except for DB operational errors
            try:
                result = self.db.add_timetable(cid, day, st, et)
            except Exception as e:
                logger.error(f"Add timetable failed: {e}")
                err.configure(text=f"⚠️ Lỗi thêm TKB: {e}")
                return
            if result is None:
                err.configure(text="⚠️ Lỗi thêm TKB vào DB")
                return
            self._safe_close_dialog(dlg)
            self._refresh_timetable_list()

        bf = ctk.CTkFrame(dlg, fg_color="transparent")
        bf.pack(pady=10)
        ctk.CTkButton(bf, text="Thêm", command=submit).pack(side="left", padx=10)
        ctk.CTkButton(bf, text="Hủy", command=lambda: self._safe_close_dialog(dlg)).pack(side="right", padx=10)

    # ══════════════════════════════════════════
    # TAB 5: LỊCH SỬ ĐIỂM DANH
    # ══════════════════════════════════════════

    def _build_history_tab(self):
        tab = self.tabview.tab("📋 Lịch sử")

        # ── Filter controls frame ──
        filter_frame = ctk.CTkFrame(tab, fg_color="transparent")
        filter_frame.pack(fill="x", padx=5, pady=(5, 2))

        # Class filter ComboBox
        ctk.CTkLabel(filter_frame, text="Lớp:", width=30).pack(side="left", padx=(0, 2))
        classes = self.db.get_all_classes() or []
        self._history_class_map = {}  # display_text → class_id
        class_values = ["Tất cả"]
        for c in classes:
            display = f"{c['class_code']} — {c['subject']}"
            class_values.append(display)
            self._history_class_map[display] = c['id']
        self._history_class_filter = ctk.CTkComboBox(
            filter_frame, values=class_values, width=200, state="readonly",
            command=self._on_history_filter_changed
        )
        self._history_class_filter.pack(side="left", padx=5)
        self._history_class_filter.set("Tất cả")

        # Date range filter
        ctk.CTkLabel(filter_frame, text="Từ:", width=25).pack(side="left", padx=(10, 2))
        self._history_from_date = ctk.CTkEntry(filter_frame, placeholder_text="YYYY-MM-DD", width=110)
        self._history_from_date.pack(side="left", padx=2)

        ctk.CTkLabel(filter_frame, text="Đến:", width=30).pack(side="left", padx=(5, 2))
        self._history_to_date = ctk.CTkEntry(filter_frame, placeholder_text="YYYY-MM-DD", width=110)
        self._history_to_date.pack(side="left", padx=2)

        ctk.CTkButton(filter_frame, text="🔍 Lọc", width=70,
                       command=self._on_history_filter_changed).pack(side="left", padx=5)

        # ── Stats summary frame ──
        stats_frame = ctk.CTkFrame(tab, fg_color="transparent")
        stats_frame.pack(fill="x", padx=5, pady=2)
        self._history_stats_label = ctk.CTkLabel(
            stats_frame, text="", font=ctk.CTkFont(size=13), text_color="gray"
        )
        self._history_stats_label.pack(anchor="w", padx=5)

        # ── Session list (scrollable) ──
        self._history_scroll = self._make_list_frame(tab)
        self._refresh_history_list()

    def _on_history_filter_changed(self, *_args):
        """Callback khi filter lớp hoặc nút Lọc được nhấn."""
        self._refresh_history_list()

    def _refresh_history_filters(self):
        """[F10-fix] Rebuild class filter ComboBox so newly-added classes appear."""
        classes = self.db.get_all_classes() or []
        self._history_class_map = {}
        class_values = ["Tất cả"]
        for c in classes:
            display = f"{c['class_code']} — {c['subject']}"
            class_values.append(display)
            self._history_class_map[display] = c['id']
        current = self._history_class_filter.get()
        self._history_class_filter.configure(values=class_values)
        # [F4-fix] Preserve current selection if still valid; log stale reset
        if current not in class_values:
            logger.info(f"History class filter reset: '{current}' no longer exists")
            self._history_class_filter.set("Tất cả")

    def _refresh_history_list(self):
        self._clear_widgets(self._history_widgets)

        # [F10-fix] Rebuild class filter to pick up new/deleted classes
        self._refresh_history_filters()

        # ── Determine class filter ──
        filter_text = self._history_class_filter.get()
        if filter_text == "Tất cả":
            sessions = self.db.get_sessions() or []
        else:
            class_id = self._history_class_map.get(filter_text)
            sessions = self.db.get_sessions(class_id=class_id) or []

        # ── Date range filter (client-side) ──
        from_date = self._history_from_date.get().strip()
        to_date = self._history_to_date.get().strip()
        # [F4-fix] Use module-level _DATE_RE instead of recompiling
        if from_date and not _DATE_RE.match(from_date):
            from_date = ""
        if to_date and not _DATE_RE.match(to_date):
            to_date = ""

        if from_date or to_date:
            filtered = []
            for s in sessions:
                if from_date and s['session_date'] < from_date:
                    continue
                if to_date and s['session_date'] > to_date:
                    continue
                filtered.append(s)
            sessions = filtered

        # ── Update stats ──
        self._update_stats(sessions)

        # ── Empty state ──
        if not sessions:
            self._show_empty_label(self._history_scroll, self._history_widgets,
                                   "(Chưa có lịch sử điểm danh)")
            return

        # ── Build session rows ──
        for s in sessions:
            row = ctk.CTkFrame(self._history_scroll)
            row.pack(fill="x", padx=2, pady=1)

            # Date
            ctk.CTkLabel(row, text=s['session_date'], width=90, anchor="w").pack(side="left", padx=5)
            # Class
            ctk.CTkLabel(row, text=s['class_code'], width=80, anchor="w").pack(side="left", padx=3)
            # Subject
            ctk.CTkLabel(row, text=s['subject'], width=130, anchor="w").pack(side="left", padx=3)
            # Teacher
            ctk.CTkLabel(row, text=s['teacher_name'], width=110, anchor="w").pack(side="left", padx=3)
            # Present/Total
            ratio = f"{s['present_count']}/{s['total_students']}"
            ctk.CTkLabel(row, text=ratio, width=60).pack(side="left", padx=3)

            # Action buttons
            sid = s['id']
            ctk.CTkButton(row, text="📊 Xuất Excel", width=95, height=26,
                           command=lambda i=sid, sess=s: self._reexport_session(i, sess)
                           ).pack(side="right", padx=3)
            ctk.CTkButton(row, text="🔍 Chi tiết", width=85, height=26,
                           command=lambda i=sid, sess=s: self._show_session_detail(i, sess)
                           ).pack(side="right", padx=3)

            self._history_widgets.append(row)

    def _update_stats(self, sessions):
        """Cập nhật thống kê tỷ lệ đi học trung bình (MVP — bỏ SV vắng nhiều nhất)."""
        if not sessions:
            self._history_stats_label.configure(text="")
            return
        total = 0
        present = 0
        for s in sessions:
            ts = s['total_students']
            pc = s['present_count']
            # [F3-fix] Log per-session corruption before clamping
            if pc > ts:
                logger.warning(f"Corrupted session {s.get('id')}: present_count ({pc}) > total_students ({ts})")
                pc = ts  # Clamp per-session
            total += ts
            present += pc
        if total > 0:
            avg_pct = present / total * 100
            self._history_stats_label.configure(
                text=f"📊 {len(sessions)} phiên | Tỷ lệ đi học trung bình: {avg_pct:.1f}%"
            )
        else:
            self._history_stats_label.configure(text=f"📊 {len(sessions)} phiên | —")

    def _show_session_detail(self, session_id, session):
        """Hiển thị chi tiết sinh viên trong một phiên điểm danh."""
        try:
            dlg = ctk.CTkToplevel(self)
            dlg.title(f"📋 Chi tiết phiên — {session.get('session_date', '')}")
            dlg.geometry("650x500")
            dlg.transient(self)
            dlg.grab_set()

            # [F10-fix] Header info — use .get() to prevent KeyError crash
            header = (
                f"Lớp: {session.get('class_code', 'N/A')} — {session.get('subject', 'N/A')}  |  "
                f"GV: {session.get('teacher_name', 'N/A')}  |  "
                f"Có mặt: {session.get('present_count', 0)}/{session.get('total_students', 0)}"
            )
            ctk.CTkLabel(dlg, text=header, font=ctk.CTkFont(size=13, weight="bold"),
                         wraplength=600).pack(pady=(10, 5), padx=10)

            # Records list
            scroll = ctk.CTkScrollableFrame(dlg)
            scroll.pack(expand=True, fill="both", padx=10, pady=5)

            records = self.db.get_session_records(session_id) or []

            if not records:
                ctk.CTkLabel(scroll, text="(Không có dữ liệu sinh viên)", text_color="gray").pack(pady=20)
            else:
                # Table header
                hdr = ctk.CTkFrame(scroll)
                hdr.pack(fill="x", padx=2, pady=(0, 3))
                ctk.CTkLabel(hdr, text="MSSV", width=90, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=3)
                ctk.CTkLabel(hdr, text="Họ tên", width=150, font=ctk.CTkFont(weight="bold"), anchor="w").pack(
                    side="left", padx=3)
                ctk.CTkLabel(hdr, text="Trạng thái", width=80, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=3)
                ctk.CTkLabel(hdr, text="Độ khớp", width=70, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=3)
                ctk.CTkLabel(hdr, text="Thời gian", width=120, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=3)

                for r in records:
                    rrow = ctk.CTkFrame(scroll)
                    rrow.pack(fill="x", padx=2, pady=1)
                    ctk.CTkLabel(rrow, text=r.get('student_code', ''), width=90).pack(side="left", padx=3)
                    ctk.CTkLabel(rrow, text=r.get('name', ''), width=150, anchor="w").pack(side="left", padx=3)
                    status = "✅ Có mặt" if r.get('is_present') else "❌ Vắng"
                    status_color = "#2ECC71" if r.get('is_present') else "#E74C3C"
                    ctk.CTkLabel(rrow, text=status, width=80, text_color=status_color).pack(side="left", padx=3)
                    conf = r.get('confidence', 0.0) or 0.0
                    conf_str = f"{conf * 100:.1f}%" if conf > 0 else "—"
                    ctk.CTkLabel(rrow, text=conf_str, width=70).pack(side="left", padx=3)
                    mark_time = r.get('mark_time', '') or '—'
                    ctk.CTkLabel(rrow, text=mark_time, width=120).pack(side="left", padx=3)

            # Close button
            bf = ctk.CTkFrame(dlg, fg_color="transparent")
            bf.pack(pady=10)
            ctk.CTkButton(bf, text="Đóng", command=lambda: self._safe_close_dialog(dlg)).pack()
        except Exception as e:  # [F5-fix] Prevent Tk event loop crash from dialog failures
            logger.error(f"Session detail dialog failed: {e}", exc_info=True)

    def _reexport_session(self, session_id, session):
        """Xuất lại Excel cho session đã chọn."""
        filepath = None
        error_msg = None
        try:
            records = self.db.get_session_records(session_id) or []
            session_result = self._reconstruct_session_result(session, records)

            # [F2-fix] Null-safe class/teacher info — use .get() to prevent KeyError
            class_info = self.db.get_class(session.get('class_id')) or {'class_code': 'N/A', 'subject': 'N/A'}
            teacher_info = self.db.get_teacher(session.get('teacher_id')) or {'name': 'N/A'}

            # Lazy import (CRITICAL: exact path)
            from src.core.excel_export import ExcelExporter
            exporter = ExcelExporter()
            filepath = exporter.export_session(session_result, class_info, teacher_info)
        except Exception as e:  # [F1-fix] Catch all to prevent Tk unhandled-exception dialog
            logger.error(f"Re-export failed: {e}", exc_info=True)
            error_msg = str(e)

        # [F6-fix] Show result dialog OUTSIDE try/except to prevent recursive dialog on Tk error
        try:
            if filepath:
                self._show_export_result(f"✅ Đã xuất Excel:\n{filepath}")
            elif error_msg:
                self._show_export_result(f"❌ Lỗi xuất Excel:\n{error_msg}")
        except Exception as e:
            logger.error(f"Export result dialog failed: {e}", exc_info=True)

    @staticmethod
    def _safe_parse_datetime(value, fallback=None):
        """[F2/F3-fix] Safely parse datetime string, returning fallback on failure."""
        if not value:
            return fallback
        from datetime import datetime as dt
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S.%f'):
            try:
                return dt.strptime(value, fmt)
            except (ValueError, TypeError):
                continue
        logger.warning(f"Cannot parse datetime: {value!r}")
        return fallback

    def _reconstruct_session_result(self, session, records):
        """Reconstruct session_result dict cho ExcelExporter."""
        from datetime import datetime as dt
        present = []
        absent = []
        for r in records:
            entry = {
                'student_code': r['student_code'],
                'name': r['name'],
                'is_present': bool(r['is_present']),
                # [F8-fix] Guard against None confidence value from DB
                'confidence': r.get('confidence', 0.0) or 0.0,
                # [F2-fix] Guard strptime against format mismatches
                'mark_time': self._safe_parse_datetime(r.get('mark_time')),
                'image_path': r.get('image_path'),
            }
            if r['is_present']:
                present.append(entry)
            else:
                absent.append(entry)
        return {
            # [F3-fix] Guard session timestamp parsing with sensible fallback
            'start_time': self._safe_parse_datetime(session.get('start_time'), dt.now()),
            'end_time': self._safe_parse_datetime(session.get('end_time'), dt.now()),
            'present': present,
            'absent': absent,
            # [F11-fix] Include class_id for dict consistency with AttendanceSession.end_session()
            'class_id': session.get('class_id'),
        }

    def _show_export_result(self, message):
        """Hiển thị kết quả xuất Excel."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("📊 Kết quả xuất Excel")
        dlg.geometry("450x150")
        dlg.transient(self)
        dlg.grab_set()
        ctk.CTkLabel(dlg, text=message, wraplength=400, justify="left").pack(
            pady=20, padx=20, expand=True)
        ctk.CTkButton(dlg, text="Đóng",
                       command=lambda: self._safe_close_dialog(dlg)).pack(pady=(0, 15))

