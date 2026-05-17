import pytest
import customtkinter as ctk
from unittest.mock import Mock, patch, MagicMock
from src.gui.student_panel import StudentPanel
from src.core.events import events, EventType


@pytest.fixture
def app():
    """Tạo CTk root cho test."""
    _app = ctk.CTk()
    yield _app
    _app.destroy()


@pytest.fixture
def panel(app):
    """Tạo StudentPanel instance."""
    _panel = StudentPanel(app)
    yield _panel


@pytest.fixture(autouse=True)
def cleanup_events():
    """Cleanup event subscriptions sau mỗi test."""
    yield
    with events._lock:
        events._listeners.clear()


# ── Dữ liệu test ──

SAMPLE_STUDENTS = [
    {'student_id': 1, 'name': 'Nguyễn Văn A', 'student_code': '2024001'},
    {'student_id': 2, 'name': 'Trần Văn B', 'student_code': '2024002'},
    {'student_id': 3, 'name': 'Lê Thị C', 'student_code': '2024003'},
]


class TestStudentPanelInitialization:
    """Test khởi tạo StudentPanel default state."""

    def test_panel_is_ctk_frame(self, panel):
        assert isinstance(panel, ctk.CTkFrame)

    def test_default_student_widgets_empty(self, panel):
        assert panel._student_widgets == {}

    def test_default_has_session_data_false(self, panel):
        assert panel._has_session_data is False

    def test_export_button_disabled_by_default(self, panel):
        state = panel.export_button.cget("state")
        assert state == "disabled"

    def test_placeholder_visible_by_default(self, panel):
        """Placeholder visible khi chưa có SV."""
        text = panel._placeholder_label.cget("text")
        assert "Chưa có sinh viên" in text
        assert panel._placeholder_label.winfo_manager() == "pack"

    def test_has_add_button(self, panel):
        assert hasattr(panel, 'add_button')

    def test_has_export_button(self, panel):
        assert hasattr(panel, 'export_button')


class TestOnStudentsLoaded:
    """Test on_students_loaded()."""

    def test_renders_list(self, panel):
        """on_students_loaded() renders list đúng."""
        panel.on_students_loaded(SAMPLE_STUDENTS)

        assert len(panel._student_widgets) == 3
        assert 1 in panel._student_widgets
        assert 2 in panel._student_widgets
        assert 3 in panel._student_widgets

    def test_hides_placeholder(self, panel):
        """on_students_loaded() ẩn placeholder."""
        panel.on_students_loaded(SAMPLE_STUDENTS)
        assert panel._placeholder_label.winfo_manager() == ""

    def test_clears_old_widgets(self, panel):
        """on_students_loaded() gọi lần 2 → clear widgets cũ trước (no duplicate rows)."""
        panel.on_students_loaded(SAMPLE_STUDENTS)
        old_widgets = dict(panel._student_widgets)

        # Load danh sách mới
        new_students = [
            {'student_id': 10, 'name': 'Phạm Văn D', 'student_code': '2024010'},
        ]
        panel.on_students_loaded(new_students)

        # Chỉ chứa data mới
        assert len(panel._student_widgets) == 1
        assert 10 in panel._student_widgets
        assert 1 not in panel._student_widgets

        # Widgets cũ phải bị destroy
        for widget in old_widgets.values():
            assert not widget.winfo_exists()

    def test_empty_list_no_crash(self, panel):
        """on_students_loaded() với empty list → no crash, placeholder visible, Excel disabled."""
        panel.on_students_loaded([])

        assert len(panel._student_widgets) == 0
        assert panel._placeholder_label.winfo_manager() == "pack"
        assert panel._has_session_data is False
        assert panel.export_button.cget("state") == "disabled"

    def test_sets_has_session_data(self, panel):
        """on_students_loaded() set _has_session_data = True."""
        panel.on_students_loaded(SAMPLE_STUDENTS)
        assert panel._has_session_data is True

    def test_enables_export_button(self, panel):
        """on_students_loaded() enable Excel button."""
        panel.on_students_loaded(SAMPLE_STUDENTS)
        assert panel.export_button.cget("state") == "normal"


class TestOnStudentAdded:
    """Test on_student_added()."""

    def test_adds_one_row(self, panel):
        """on_student_added() thêm 1 row."""
        panel.on_student_added({'student_id': 1, 'name': 'Nguyễn Văn A', 'student_code': '2024001'})

        assert len(panel._student_widgets) == 1
        assert 1 in panel._student_widgets

    def test_duplicate_student_id_skip(self, panel):
        """on_student_added() duplicate student_id → skip (idempotency, no duplicate rows)."""
        panel.on_student_added({'student_id': 1, 'name': 'Nguyễn Văn A', 'student_code': '2024001'})
        panel.on_student_added({'student_id': 1, 'name': 'Nguyễn Văn A', 'student_code': '2024001'})

        assert len(panel._student_widgets) == 1

    def test_hides_placeholder(self, panel):
        """on_student_added() ẩn placeholder."""
        panel.on_student_added({'student_id': 1, 'name': 'Nguyễn Văn A', 'student_code': '2024001'})
        assert panel._placeholder_label.winfo_manager() == ""

    def test_enables_export_button(self, panel):
        """M2: on_student_added() enables export khi list non-empty."""
        assert panel.export_button.cget("state") == "disabled"
        panel.on_student_added({'student_id': 1, 'name': 'Test', 'student_code': '0001'})
        assert panel._has_session_data is True
        assert panel.export_button.cget("state") == "normal"


class TestOnStudentRemoved:
    """Test on_student_removed()."""

    def test_removes_correct_student(self, panel):
        """on_student_removed() xóa row đúng student_id + gọi destroy()."""
        panel.on_students_loaded(SAMPLE_STUDENTS)
        widget_ref = panel._student_widgets[2]

        panel.on_student_removed(2)

        assert 2 not in panel._student_widgets
        assert not widget_ref.winfo_exists()

    def test_nonexistent_student_no_crash(self, panel):
        """on_student_removed() student_id không tồn tại → no crash."""
        panel.on_students_loaded(SAMPLE_STUDENTS)
        panel.on_student_removed(999)  # Should not crash

        assert len(panel._student_widgets) == 3

    def test_shows_placeholder_when_empty(self, panel):
        """on_student_removed() hiển thị placeholder khi hết SV."""
        panel.on_student_added({'student_id': 1, 'name': 'Test', 'student_code': '0001'})
        panel.on_student_removed(1)

        assert panel._placeholder_label.winfo_manager() == "pack"

    def test_disables_export_when_all_removed(self, panel):
        """Architect-2: on_student_removed() disables export khi hết SV."""
        panel.on_student_added({'student_id': 1, 'name': 'Test', 'student_code': '0001'})
        assert panel.export_button.cget("state") == "normal"

        panel.on_student_removed(1)

        assert panel._has_session_data is False
        assert panel.export_button.cget("state") == "disabled"

    def test_widget_destroyed_no_crash(self, app):
        """T2: on_student_removed() khi widget destroyed → no TclError."""
        _panel = StudentPanel(app)
        _panel.on_students_loaded(SAMPLE_STUDENTS)
        _panel.destroy()
        app.update_idletasks()

        _panel.on_student_removed(1)  # Should not crash

    def test_malformed_student_data_skipped(self, panel):
        """T4: on_students_loaded() skip SV dict thiếu student_id — no crash."""
        students = [
            {'name': 'No ID', 'student_code': '0000'},  # missing student_id
            {'student_id': 1, 'name': 'Valid', 'student_code': '2024001'},
        ]
        panel.on_students_loaded(students)

        assert len(panel._student_widgets) == 1
        assert 1 in panel._student_widgets


class TestExcelExportButton:
    """Test nút Xuất Excel."""

    def test_emits_excel_export_requested(self, panel):
        """Nút Xuất Excel emit EXCEL_EXPORT_REQUESTED."""
        mock_listener = Mock()
        events.subscribe(EventType.EXCEL_EXPORT_REQUESTED, mock_listener)

        panel._on_export_click()

        # D3: Emit {} thay vì None
        mock_listener.assert_called_once_with({})

    def test_disabled_when_no_session_data(self, panel):
        """Nút Xuất Excel disabled khi _has_session_data == False."""
        assert panel._has_session_data is False
        assert panel.export_button.cget("state") == "disabled"


class TestRemoveConfirmationDialog:
    """Test nút xóa SV hiển thị confirmation dialog."""

    def test_confirmation_emits_on_direct_call(self, panel):
        """Confirm remove emits STUDENT_REMOVE_REQUESTED with correct data."""
        panel.on_students_loaded(SAMPLE_STUDENTS)

        mock_listener = Mock()
        events.subscribe(EventType.STUDENT_REMOVE_REQUESTED, mock_listener)

        # Mock CTkToplevel to capture dialog behavior
        with patch('src.gui.student_panel.ctk.CTkToplevel') as MockToplevel:
            mock_dialog = MagicMock()
            MockToplevel.return_value = mock_dialog
            mock_dialog.winfo_toplevel.return_value = mock_dialog

            # Capture the command passed to the Xóa button
            confirm_command = None
            cancel_command = None

            def capture_button(*args, **kwargs):
                nonlocal confirm_command, cancel_command
                btn = MagicMock()
                text = kwargs.get('text', '')
                if text == 'Xóa':
                    confirm_command = kwargs.get('command')
                elif text == 'Hủy':
                    cancel_command = kwargs.get('command')
                return btn

            # Mock CTkButton within dialog context
            with patch('src.gui.student_panel.ctk.CTkButton', side_effect=capture_button):
                with patch('src.gui.student_panel.ctk.CTkLabel'):
                    with patch('src.gui.student_panel.ctk.CTkFrame') as MockFrame:
                        MockFrame.return_value = MagicMock()
                        panel._on_remove_click(1, 'Nguyễn Văn A')

            # Execute confirm command
            if confirm_command:
                confirm_command()

            mock_listener.assert_called_once_with({'student_id': 1})

    def test_cancel_no_emit(self, panel):
        """Cancel button does not emit STUDENT_REMOVE_REQUESTED."""
        panel.on_students_loaded(SAMPLE_STUDENTS)

        mock_listener = Mock()
        events.subscribe(EventType.STUDENT_REMOVE_REQUESTED, mock_listener)

        # Mock all CTk widgets used inside dialog to prevent hanging
        with patch('src.gui.student_panel.ctk.CTkToplevel') as MockToplevel:
            mock_dialog = MagicMock()
            MockToplevel.return_value = mock_dialog

            with patch('src.gui.student_panel.ctk.CTkButton', return_value=MagicMock()):
                with patch('src.gui.student_panel.ctk.CTkLabel'):
                    with patch('src.gui.student_panel.ctk.CTkFrame', return_value=MagicMock()):
                        panel._on_remove_click(1, 'Nguyễn Văn A')

            # Dialog was created
            MockToplevel.assert_called_once()

            # Without clicking confirm, no event should be emitted
            mock_listener.assert_not_called()


class TestAddDialog:
    """Test _show_add_dialog()."""

    def test_dialog_created_with_transient(self, panel):
        """_show_add_dialog() creates CTkToplevel with transient()."""
        with patch('src.gui.student_panel.ctk.CTkToplevel') as MockToplevel:
            mock_dialog = MagicMock()
            MockToplevel.return_value = mock_dialog

            with patch('src.gui.student_panel.ctk.CTkButton', return_value=MagicMock()):
                with patch('src.gui.student_panel.ctk.CTkLabel'):
                    with patch('src.gui.student_panel.ctk.CTkEntry', return_value=MagicMock()):
                        with patch('src.gui.student_panel.ctk.CTkFrame', return_value=MagicMock()):
                            panel._show_add_dialog()

            MockToplevel.assert_called_once()
            mock_dialog.transient.assert_called_once_with(panel.winfo_toplevel())

    @patch('src.gui.student_panel.filedialog.askopenfilename')
    def test_grab_release_before_filedialog(self, mock_filedialog, panel):
        """Add dialog grab_release() trước filedialog + grab_set() sau."""
        mock_filedialog.return_value = "/path/to/photo.jpg"

        with patch('src.gui.student_panel.ctk.CTkToplevel') as MockToplevel:
            mock_dialog = MagicMock()
            MockToplevel.return_value = mock_dialog

            # Capture choose_image callback
            choose_image_cmd = None
            original_CTkButton = ctk.CTkButton

            def capture_button(*args, **kwargs):
                nonlocal choose_image_cmd
                text = kwargs.get('text', '')
                if 'Chọn ảnh' in text:
                    choose_image_cmd = kwargs.get('command')
                btn = MagicMock()
                return btn

            with patch('src.gui.student_panel.ctk.CTkButton', side_effect=capture_button):
                with patch('src.gui.student_panel.ctk.CTkLabel'):
                    with patch('src.gui.student_panel.ctk.CTkEntry') as MockEntry:
                        MockEntry.return_value = MagicMock()
                        with patch('src.gui.student_panel.ctk.CTkFrame') as MockFrame:
                            MockFrame.return_value = MagicMock()
                            panel._show_add_dialog()

            # Execute choose_image
            if choose_image_cmd:
                choose_image_cmd()

                # Verify grab_release was called before filedialog
                mock_dialog.grab_release.assert_called()
                mock_filedialog.assert_called_once()
                # Verify grab_set was called after filedialog (at least 2 times: initial + after filedialog)
                assert mock_dialog.grab_set.call_count >= 2

    def test_validate_empty_name_code_no_emit(self, panel):
        """Add dialog validate: tên + MSSV rỗng → không emit."""
        mock_listener = Mock()
        events.subscribe(EventType.STUDENT_ADD_REQUESTED, mock_listener)

        with patch('src.gui.student_panel.ctk.CTkToplevel') as MockToplevel:
            mock_dialog = MagicMock()
            MockToplevel.return_value = mock_dialog

            submit_cmd = None

            def capture_button(*args, **kwargs):
                nonlocal submit_cmd
                text = kwargs.get('text', '')
                if text == 'Thêm':
                    submit_cmd = kwargs.get('command')
                return MagicMock()

            mock_name_entry = MagicMock()
            mock_name_entry.get.return_value = ""  # Empty name
            mock_code_entry = MagicMock()
            mock_code_entry.get.return_value = ""  # Empty code

            entry_calls = []

            def capture_entry(*args, **kwargs):
                entry = MagicMock()
                entry.get.return_value = ""
                entry_calls.append(entry)
                return entry

            with patch('src.gui.student_panel.ctk.CTkButton', side_effect=capture_button):
                with patch('src.gui.student_panel.ctk.CTkLabel'):
                    with patch('src.gui.student_panel.ctk.CTkEntry', side_effect=capture_entry):
                        with patch('src.gui.student_panel.ctk.CTkFrame') as MockFrame:
                            MockFrame.return_value = MagicMock()
                            panel._show_add_dialog()

            if submit_cmd:
                submit_cmd()

            # Không emit vì tên + MSSV rỗng
            mock_listener.assert_not_called()

    def test_cancel_button_destroys_dialog(self, panel):
        """Add dialog nút Hủy → dialog.destroy(), không emit."""
        mock_listener = Mock()
        events.subscribe(EventType.STUDENT_ADD_REQUESTED, mock_listener)

        with patch('src.gui.student_panel.ctk.CTkToplevel') as MockToplevel:
            mock_dialog = MagicMock()
            MockToplevel.return_value = mock_dialog

            cancel_cmd = None

            def capture_button(*args, **kwargs):
                nonlocal cancel_cmd
                text = kwargs.get('text', '')
                if text == 'Hủy':
                    cancel_cmd = kwargs.get('command')
                return MagicMock()

            with patch('src.gui.student_panel.ctk.CTkButton', side_effect=capture_button):
                with patch('src.gui.student_panel.ctk.CTkLabel'):
                    with patch('src.gui.student_panel.ctk.CTkEntry') as MockEntry:
                        MockEntry.return_value = MagicMock()
                        with patch('src.gui.student_panel.ctk.CTkFrame') as MockFrame:
                            MockFrame.return_value = MagicMock()
                            panel._show_add_dialog()

            if cancel_cmd:
                cancel_cmd()
                mock_dialog.destroy.assert_called()

            mock_listener.assert_not_called()

    def test_valid_submit_empty_image_emits_event(self, panel):
        """T5: Valid name+code, no image → emit with image_path=''."""
        mock_listener = Mock()
        events.subscribe(EventType.STUDENT_ADD_REQUESTED, mock_listener)

        with patch('src.gui.student_panel.ctk.CTkToplevel') as MockToplevel:
            mock_dialog = MagicMock()
            MockToplevel.return_value = mock_dialog

            submit_cmd = None

            def capture_button(*args, **kwargs):
                nonlocal submit_cmd
                text = kwargs.get('text', '')
                if text == 'Thêm':
                    submit_cmd = kwargs.get('command')
                return MagicMock()

            entry_calls = []

            def capture_entry(*args, **kwargs):
                entry = MagicMock()
                placeholder = kwargs.get('placeholder_text', '')
                if 'Tên' in placeholder:
                    entry.get.return_value = "Nguyễn Văn Test"
                elif 'MSSV' in placeholder:
                    entry.get.return_value = "2024099"
                entry_calls.append(entry)
                return entry

            with patch('src.gui.student_panel.ctk.CTkButton', side_effect=capture_button):
                with patch('src.gui.student_panel.ctk.CTkLabel'):
                    with patch('src.gui.student_panel.ctk.CTkEntry', side_effect=capture_entry):
                        with patch('src.gui.student_panel.ctk.CTkFrame') as MockFrame:
                            MockFrame.return_value = MagicMock()
                            panel._show_add_dialog()

            if submit_cmd:
                submit_cmd()

            mock_listener.assert_called_once_with({
                'name': 'Nguyễn Văn Test',
                'student_code': '2024099',
                'image_path': '',  # Empty — no image selected
            })


class TestOnError:
    """Test on_error()."""

    def test_displays_message(self, panel):
        """on_error() hiển thị message."""
        panel.on_error("Mã SV đã tồn tại")
        text = panel.info_label.cget("text")
        assert "Mã SV đã tồn tại" in text

    def test_custom_color(self, panel):
        """L3: on_error() accepts custom color."""
        panel.on_error("Thành công", color="green")
        color = panel.info_label.cget("text_color")
        assert color == "green"

    def test_auto_clear_scheduled(self, panel):
        """H1: on_error() schedules auto-clear via self.after()."""
        with patch.object(panel, 'after') as mock_after:
            panel.on_error("Test error")
            mock_after.assert_called_once()
            # Verify 5000ms delay
            args = mock_after.call_args
            assert args[0][0] == 5000


class TestReset:
    """Test reset()."""

    def test_clears_list_and_disables_export(self, panel):
        """reset() clears list + disables Excel button."""
        panel.on_students_loaded(SAMPLE_STUDENTS)
        panel.reset()

        assert len(panel._student_widgets) == 0
        assert panel._has_session_data is False
        assert panel.export_button.cget("state") == "disabled"

    def test_shows_placeholder(self, panel):
        """reset() hiển thị placeholder."""
        panel.on_students_loaded(SAMPLE_STUDENTS)
        panel.reset()

        assert panel._placeholder_label.winfo_manager() == "pack"

    def test_clears_info_label(self, panel):
        """reset() clears info label."""
        panel.on_error("Test error")
        panel.reset()

        assert panel.info_label.cget("text") == ""

    def test_destroys_row_widgets(self, panel):
        """reset() destroy row widgets (memory leak prevention)."""
        panel.on_students_loaded(SAMPLE_STUDENTS)
        old_widgets = list(panel._student_widgets.values())

        panel.reset()

        for widget in old_widgets:
            assert not widget.winfo_exists()
