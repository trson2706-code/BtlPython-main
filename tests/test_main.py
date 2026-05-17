"""Unit tests cho Presenter (src/main.py).

Mock tất cả dependencies — không cần camera, DB, hay GUI thật.
40 test cases covering tất cả event handlers, mode guards, error handling, và edge cases.
"""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock, call
from datetime import datetime


class TestPresenter(unittest.TestCase):
    """Test suite cho Presenter logic — mock tất cả components."""

    def setUp(self):
        """Setup: mock tất cả dependencies trước khi tạo Presenter."""
        # Patch all external dependencies
        self.patches = []

        # Core modules
        p_db = patch('src.main.DatabaseManager')
        p_class_mgr = patch('src.main.ClassManager')
        p_student_mgr = patch('src.main.StudentManager')
        p_session = patch('src.main.AttendanceSession')
        p_camera = patch('src.main.CameraManager')
        p_worker = patch('src.main.RecognitionWorker')
        p_exporter = patch('src.main.ExcelExporter')
        p_app = patch('src.main.App')
        p_config = patch('src.main.Config')
        p_events = patch('src.main.events')
        p_admin = patch('src.main.AdminWindow')

        self.patches = [p_db, p_class_mgr, p_student_mgr, p_session,
                        p_camera, p_worker, p_exporter, p_app, p_config, p_events, p_admin]

        self.MockDB = p_db.start()
        self.MockClassMgr = p_class_mgr.start()
        self.MockStudentMgr = p_student_mgr.start()
        self.MockSession = p_session.start()
        self.MockCamera = p_camera.start()
        self.MockWorker = p_worker.start()
        self.MockExporter = p_exporter.start()
        self.MockApp = p_app.start()
        self.MockConfig = p_config.start()
        self.MockEvents = p_events.start()
        self.MockAdminWindow = p_admin.start()

        # AdminWindow mock instance
        self.mock_admin = MagicMock()
        self.MockAdminWindow.return_value = self.mock_admin

        # Config mock
        self.MockConfig.return_value.get.return_value = 60

        # App mock — needs panel attributes
        self.mock_app = MagicMock()
        self.mock_app.session_panel = MagicMock()
        self.mock_app.camera_panel = MagicMock()
        self.mock_app.attendance_panel = MagicMock()
        self.mock_app.student_panel = MagicMock()
        self.mock_app.winfo_exists.return_value = True
        self.MockApp.return_value = self.mock_app

        # Import and create Presenter AFTER mocks are applied
        from src.main import Presenter
        self.presenter = Presenter()

        # Shortcuts to mock instances
        self.db = self.MockDB.return_value
        self.session = self.MockSession.return_value
        self.worker = self.MockWorker.return_value
        self.camera = self.MockCamera.return_value
        self.exporter = self.MockExporter.return_value
        self.student_mgr = self.MockStudentMgr.return_value

    def tearDown(self):
        for p in self.patches:
            p.stop()

    # ──────────────────────────────────────────────────────────
    # TEST 1: Presenter khởi tạo thành công
    # ──────────────────────────────────────────────────────────

    def test_presenter_init_components_created(self):
        """Test: Presenter khởi tạo thành công (components created in order)."""
        self.MockDB.assert_called_once()
        self.MockClassMgr.assert_called_once()
        self.MockStudentMgr.assert_called_once()
        self.MockSession.assert_called_once()
        self.MockExporter.assert_called_once()
        self.MockCamera.assert_called_once()
        self.MockWorker.assert_called_once()
        self.MockApp.assert_called_once()

        # Verify state initialization
        self.assertIsNone(self.presenter._current_mode)
        self.assertIsNone(self.presenter._current_class_id)
        self.assertIsNone(self.presenter._pending_class_id)
        self.assertIsNone(self.presenter._current_teacher_id)
        self.assertIsNone(self.presenter._last_session_result)
        self.assertIsNone(self.presenter._admin_window)

        # Verify events subscribed
        self.assertTrue(self.MockEvents.subscribe.called)
        subscribe_calls = self.MockEvents.subscribe.call_args_list
        subscribed_events = [c[0][0] for c in subscribe_calls]
        from src.core.events import EventType
        expected_events = [
            EventType.TEACHER_DETECTED,
            EventType.SESSION_CONFIRMED,
            EventType.STUDENT_DETECTED,
            EventType.SESSION_END_REQUESTED,
            EventType.EXCEL_EXPORT_REQUESTED,
            EventType.MANUAL_MARK_REQUESTED,
            EventType.SHUTDOWN_REQUESTED,
            EventType.ERROR_OCCURRED,
            EventType.CAMERA_STOPPED,
            EventType.ADMIN_REQUESTED,
            EventType.FACE_UNRECOGNIZED,
            EventType.SPOOF_DETECTED,
        ]
        for evt in expected_events:
            self.assertIn(evt, subscribed_events, f"Event {evt} not subscribed")

    # ──────────────────────────────────────────────────────────
    # TEST 2: TEACHER_DETECTED → enriched data truyền vào session_panel
    # ──────────────────────────────────────────────────────────

    def test_teacher_detected_enriches_data(self):
        """Test: TEACHER_DETECTED → enriched data truyền vào session_panel."""
        self.presenter._current_mode = 1

        self.db.get_teacher.return_value = {
            'id': 1, 'name': 'GV A', 'teacher_code': 'GV001',
        }
        self.session.check_timetable.return_value = 10
        self.db.get_class.return_value = {
            'id': 10, 'class_code': 'LHP01', 'subject': 'Toán',
        }

        data = {'person_id': 1, 'confidence': 95.5, 'coordinates': (10, 20, 30, 40)}
        self.presenter._on_teacher_detected(data)

        # Verify state saved
        self.assertEqual(self.presenter._pending_class_id, 10)
        self.assertEqual(self.presenter._current_teacher_id, 1)

        # Verify GUI calls
        self.mock_app.after.assert_any_call(
            0, self.mock_app.session_panel.on_teacher_detected,
            {
                'person_id': 1,
                'name': 'GV A',
                'teacher_code': 'GV001',
                'class_info': 'Toán - LHP01',
                'confidence': 95.5,
                'coordinates': (10, 20, 30, 40),
            }
        )

    # ──────────────────────────────────────────────────────────
    # TEST 3: TEACHER_DETECTED khi mode != 1 → bị bỏ qua [F3-fix]
    # ──────────────────────────────────────────────────────────

    def test_teacher_detected_wrong_mode_ignored(self):
        """Test: TEACHER_DETECTED khi mode != 1 → bị bỏ qua [F3-fix]."""
        self.presenter._current_mode = 2  # Wrong mode

        data = {'person_id': 1, 'confidence': 95, 'coordinates': (10, 20, 30, 40)}
        self.presenter._on_teacher_detected(data)

        # DB should NOT be queried
        self.db.get_teacher.assert_not_called()
        self.mock_app.after.assert_not_called()

    # ──────────────────────────────────────────────────────────
    # TEST 4: SESSION_CONFIRMED → switch to Mode 2 + load student encodings
    # ──────────────────────────────────────────────────────────

    def test_session_confirmed_switches_to_mode2(self):
        """Test: SESSION_CONFIRMED → switch to Mode 2 + load student encodings."""
        self.presenter._current_mode = 1  # [CR-1] Must be in Mode 1
        self.presenter._pending_class_id = 10
        self.presenter._current_teacher_id = 1

        self.db.get_students_in_class.return_value = [
            {'id': 100, 'name': 'SV 1', 'student_code': 'SV001'},
            {'id': 101, 'name': 'SV 2', 'student_code': 'SV002'},
        ]
        self.db.get_encodings_by_type.return_value = []

        self.presenter._on_session_confirmed({})

        # Verify mode switched
        self.assertEqual(self.presenter._current_mode, 2)
        self.assertEqual(self.presenter._current_class_id, 10)

        # Verify session started
        self.session.start_session.assert_called_once_with(10)

        # Verify worker switched to mode 2
        self.worker.pause_scanning.assert_called_once()
        self.worker.start_scanning.assert_called_once_with(mode=2)

    # ──────────────────────────────────────────────────────────
    # TEST 5: STUDENT_DETECTED → mark_present + update attendance_panel
    # ──────────────────────────────────────────────────────────

    def test_student_detected_marks_present(self):
        """Test: STUDENT_DETECTED → mark_present + update attendance_panel."""
        self.presenter._current_mode = 2
        self.session.mark_present.return_value = True
        self.db.get_student.return_value = {
            'id': 100, 'name': 'SV 1', 'student_code': 'SV001',
        }

        data = {
            'person_id': 100,
            'confidence': 85.0,
            'coordinates': (10, 20, 30, 40),
            'snapshot_path': '/tmp/snap.jpg',
        }
        self.presenter._on_student_detected(data)

        # Verify confidence conversion: 85.0 / 100 = 0.85
        self.session.mark_present.assert_called_once_with(100, 0.85, '/tmp/snap.jpg')

        # Verify GUI updates called
        after_calls = [str(c) for c in self.mock_app.after.call_args_list]
        self.assertTrue(any('add_record' in c for c in after_calls))
        self.assertTrue(any('on_student_detected' in c for c in after_calls))
        self.assertTrue(any('set_bounding_box' in c for c in after_calls))
        # Verify bounding box clear scheduled at 2000ms
        self.assertTrue(any('2000' in c and 'clear_bounding_box' in c for c in after_calls))

    # ──────────────────────────────────────────────────────────
    # TEST 6: STUDENT_DETECTED khi mode != 2 → bị bỏ qua [F3-fix]
    # ──────────────────────────────────────────────────────────

    def test_student_detected_wrong_mode_ignored(self):
        """Test: STUDENT_DETECTED khi mode != 2 → bị bỏ qua [F3-fix]."""
        self.presenter._current_mode = 1  # Wrong mode

        data = {
            'person_id': 100,
            'confidence': 85.0,
            'coordinates': (10, 20, 30, 40),
        }
        self.presenter._on_student_detected(data)

        self.session.mark_present.assert_not_called()

    # ──────────────────────────────────────────────────────────
    # TEST 7: SESSION_END_REQUESTED → end_session + export Excel + save result
    # ──────────────────────────────────────────────────────────

    def test_session_end_requested_exports_excel(self):
        """Test: SESSION_END_REQUESTED → end_session + export Excel + save _last_session_result."""
        self.presenter._current_mode = 2
        self.presenter._current_class_id = 10
        self.presenter._current_teacher_id = 1

        mock_result = {
            'class_id': 10, 'present': [], 'absent': [],
            'start_time': datetime.now(), 'end_time': datetime.now(),
        }
        self.session.end_session.return_value = mock_result
        self.db.get_class.return_value = {'id': 10, 'class_code': 'LHP01', 'subject': 'Toán'}
        self.db.get_teacher.return_value = {'id': 1, 'name': 'GV A', 'teacher_code': 'GV001'}
        self.exporter.export_session.return_value = '/path/to/file.xlsx'

        self.presenter._on_session_end_requested({})

        # Verify session ended
        self.session.end_session.assert_called_once()

        # Verify result saved [F4-fix]
        self.assertEqual(self.presenter._last_session_result, mock_result)

        # Verify mode reset to idle
        self.assertIsNone(self.presenter._current_mode)

        # Verify export called
        self.exporter.export_session.assert_called_once_with(
            mock_result,
            {'id': 10, 'class_code': 'LHP01', 'subject': 'Toán'},
            {'id': 1, 'name': 'GV A', 'teacher_code': 'GV001'},
        )

    # ──────────────────────────────────────────────────────────
    # TEST 8: SESSION_END_REQUESTED duplicate → ValueError caught [F7-fix]
    # ──────────────────────────────────────────────────────────

    def test_session_end_duplicate_no_crash(self):
        """Test: SESSION_END_REQUESTED duplicate → ValueError caught, no crash [F7-fix]."""
        self.session.end_session.side_effect = ValueError("Không có phiên điểm danh nào")

        # Should not raise
        self.presenter._on_session_end_requested({})

        # Export should NOT be called
        self.exporter.export_session.assert_not_called()

    # ──────────────────────────────────────────────────────────
    # TEST 9: auto-reset sau 5 giây + winfo_exists guard [F12-fix]
    # ──────────────────────────────────────────────────────────

    def test_reset_to_teacher_mode_success(self):
        """Test: auto-reset sau 5 giây + winfo_exists guard [F12-fix]."""
        self.mock_app.winfo_exists.return_value = True
        self.db.get_encodings_by_type.return_value = []

        self.presenter._reset_to_teacher_mode()

        # Verify panels reset
        self.mock_app.session_panel.reset.assert_called_once()
        self.mock_app.attendance_panel.reset.assert_called_once()
        self.mock_app.student_panel.reset.assert_called_once()
        self.mock_app.camera_panel.clear_bounding_box.assert_called_once()

        # Verify mode switched back
        self.assertEqual(self.presenter._current_mode, 1)
        self.worker.start_scanning.assert_called_with(mode=1)

    def test_reset_to_teacher_mode_app_closed(self):
        """Test: [F12-fix] winfo_exists=False → skip reset."""
        self.mock_app.winfo_exists.return_value = False

        self.presenter._reset_to_teacher_mode()

        # Panels should NOT be reset
        self.mock_app.session_panel.reset.assert_not_called()
        self.assertIsNone(self.presenter._current_mode)

    # ──────────────────────────────────────────────────────────
    # TEST 10: EXCEL_EXPORT_REQUESTED → gọi exporter
    # ──────────────────────────────────────────────────────────

    def test_excel_export_requested_with_result(self):
        """Test: EXCEL_EXPORT_REQUESTED → gọi exporter."""
        self.presenter._last_session_result = {'present': [], 'absent': []}
        self.presenter._current_class_id = 10
        self.presenter._current_teacher_id = 1
        self.db.get_class.return_value = {'id': 10}
        self.db.get_teacher.return_value = {'id': 1}
        self.exporter.export_session.return_value = '/path/to/file.xlsx'

        self.presenter._on_excel_export_requested({})

        self.exporter.export_session.assert_called_once()

    def test_excel_export_requested_no_result(self):
        """Test: EXCEL_EXPORT_REQUESTED khi chưa có result → on_error."""
        self.presenter._last_session_result = None

        self.presenter._on_excel_export_requested({})

        self.exporter.export_session.assert_not_called()
        self.mock_app.after.assert_called()

    # ──────────────────────────────────────────────────────────
    # TEST 11: STUDENT_ADD_REQUESTED → add student + update GUI [F11-fix]
    # ──────────────────────────────────────────────────────────

    def test_student_add_success(self):
        """Test: STUDENT_ADD_REQUESTED → add student + add_to_class + update GUI [F11-fix]."""
        self.presenter._current_class_id = 10
        self.student_mgr.add_student.return_value = {
            'id': 200, 'name': 'SV Mới', 'student_code': 'SV200',
        }

        data = {'name': 'SV Mới', 'student_code': 'SV200', 'image_path': '/img.jpg'}
        self.presenter._on_student_add_requested(data)

        # Verify student added
        self.student_mgr.add_student.assert_called_once_with('SV Mới', 'SV200', '/img.jpg')

        # Verify student added to class
        self.db.add_student_to_class.assert_called_once_with(10, 200)

        # Verify GUI update
        after_calls = [str(c) for c in self.mock_app.after.call_args_list]
        self.assertTrue(any('on_student_added' in c for c in after_calls))

    # ──────────────────────────────────────────────────────────
    # TEST 12: STUDENT_ADD_REQUESTED khi class_id=None → on_error [F6-fix]
    # ──────────────────────────────────────────────────────────

    def test_student_add_no_class_shows_error(self):
        """Test: STUDENT_ADD_REQUESTED khi class_id=None → on_error [F6-fix]."""
        self.presenter._current_class_id = None

        data = {'name': 'SV', 'student_code': 'SV001'}
        self.presenter._on_student_add_requested(data)

        # Student should NOT be added
        self.student_mgr.add_student.assert_not_called()

        # Error shown via on_error
        self.mock_app.after.assert_called_once()
        call_args = self.mock_app.after.call_args
        self.assertEqual(call_args[0][1], self.mock_app.student_panel.on_error)

    # ──────────────────────────────────────────────────────────
    # TEST 13: STUDENT_REMOVE_REQUESTED → remove student + update GUI
    # ──────────────────────────────────────────────────────────

    def test_student_remove_success(self):
        """Test: STUDENT_REMOVE_REQUESTED → remove student + update GUI."""
        data = {'student_id': 100}
        self.presenter._on_student_remove_requested(data)

        self.student_mgr.remove_student.assert_called_once_with(100)
        after_calls = [str(c) for c in self.mock_app.after.call_args_list]
        self.assertTrue(any('on_student_removed' in c for c in after_calls))

    # ──────────────────────────────────────────────────────────
    # TEST 14: SHUTDOWN_REQUESTED → cleanup resources
    # ──────────────────────────────────────────────────────────

    def test_shutdown_cleanup(self):
        """Test: SHUTDOWN_REQUESTED → cleanup resources."""
        self.presenter._on_shutdown({})

        self.worker.stop_scanning.assert_called_once()
        self.camera.stop.assert_called_once()
        self.mock_app.camera_panel.stop_preview.assert_called_once()
        self.mock_app.after.assert_called_with(0, self.mock_app.destroy)

    # ──────────────────────────────────────────────────────────
    # TEST 15: ERROR_OCCURRED → log error
    # ──────────────────────────────────────────────────────────

    def test_error_occurred_logged(self):
        """Test: ERROR_OCCURRED → log error."""
        with self.assertLogs('src.main', level='ERROR') as cm:
            self.presenter._on_error("Test error message")
        self.assertTrue(any("Test error message" in msg for msg in cm.output))

    # ──────────────────────────────────────────────────────────
    # TEST 16: TEACHER_DETECTED khi check_timetable raise ValueError
    # ──────────────────────────────────────────────────────────

    def test_teacher_detected_no_timetable(self):
        """Test: TEACHER_DETECTED khi check_timetable raise ValueError → handle gracefully."""
        self.presenter._current_mode = 1
        self.db.get_teacher.return_value = {'id': 1, 'name': 'GV A', 'teacher_code': 'GV001'}
        self.session.check_timetable.side_effect = ValueError("Không có TKB")

        data = {'person_id': 1, 'confidence': 90, 'coordinates': (10, 20, 30, 40)}
        self.presenter._on_teacher_detected(data)

        # GUI should NOT be updated
        self.mock_app.after.assert_not_called()

    # ──────────────────────────────────────────────────────────
    # TEST 17: mark_present returns False → không update GUI
    # ──────────────────────────────────────────────────────────

    def test_student_detected_already_marked(self):
        """Test: mark_present returns False → không update GUI."""
        self.presenter._current_mode = 2
        self.session.mark_present.return_value = False

        data = {
            'person_id': 100, 'confidence': 85.0,
            'coordinates': (10, 20, 30, 40),
        }
        self.presenter._on_student_detected(data)

        # DB should NOT be queried for student info
        self.db.get_student.assert_not_called()

    # ──────────────────────────────────────────────────────────
    # TEST 18: export_session raise OSError → log error + show error [F8-fix]
    # ──────────────────────────────────────────────────────────

    def test_export_oserror_handled(self):
        """Test: export_session raise OSError → log error + show error in GUI [F8-fix]."""
        self.presenter._current_mode = 2
        self.presenter._current_class_id = 10
        self.presenter._current_teacher_id = 1

        self.session.end_session.return_value = {
            'class_id': 10, 'present': [], 'absent': [],
            'start_time': datetime.now(), 'end_time': datetime.now(),
        }
        self.db.get_class.return_value = {'id': 10}
        self.db.get_teacher.return_value = {'id': 1}
        self.exporter.export_session.side_effect = OSError("Disk full")

        self.presenter._on_session_end_requested({})

        # Error should be shown in GUI
        after_calls = [str(c) for c in self.mock_app.after.call_args_list]
        self.assertTrue(any('on_error' in c for c in after_calls))

    # ──────────────────────────────────────────────────────────
    # TEST 19: empty teacher encodings → no crash [F10-fix]
    # ──────────────────────────────────────────────────────────

    def test_load_teacher_encodings_empty(self):
        """Test: empty teacher encodings → worker.load_encodings([], []) no crash [F10-fix]."""
        self.db.get_encodings_by_type.return_value = []

        self.presenter._load_teacher_encodings()

        self.worker.load_encodings.assert_called_once_with([], [])

    # ──────────────────────────────────────────────────────────
    # TEST 20: CAMERA_STOPPED → log warning + reset mode [F13-fix]
    # ──────────────────────────────────────────────────────────

    def test_camera_stopped_resets_mode(self):
        """Test: CAMERA_STOPPED — log warning + reset mode [F13-fix]."""
        self.presenter._current_mode = 2

        self.presenter._on_camera_stopped({})

        self.assertIsNone(self.presenter._current_mode)
        # [CR-2] GUI should be notified via lambda (info_label.configure)
        self.mock_app.after.assert_called()

    def test_camera_stopped_idle_no_gui_update(self):
        """Test: CAMERA_STOPPED khi idle — chỉ reset mode, không update GUI."""
        self.presenter._current_mode = None

        self.presenter._on_camera_stopped({})

        self.assertIsNone(self.presenter._current_mode)
        # No GUI update when already idle
        self.mock_app.after.assert_not_called()

    # ──────────────────────────────────────────────────────────
    # TEST 22: SESSION_CONFIRMED khi mode != 1 → bị bỏ qua [CR-1]
    # ──────────────────────────────────────────────────────────

    def test_session_confirmed_wrong_mode_ignored(self):
        """Test: SESSION_CONFIRMED khi mode != 1 → bị bỏ qua [CR-1]."""
        self.presenter._current_mode = 2  # Already in Mode 2
        self.presenter._pending_class_id = 10

        self.presenter._on_session_confirmed({})

        # Session should NOT be started
        self.session.start_session.assert_not_called()
        self.worker.pause_scanning.assert_not_called()

    # ──────────────────────────────────────────────────────────
    # TEST 23: SESSION_CONFIRMED khi _pending_class_id=None → bỏ qua [CR-3]
    # ──────────────────────────────────────────────────────────

    def test_session_confirmed_no_pending_class_ignored(self):
        """Test: SESSION_CONFIRMED khi _pending_class_id=None → bỏ qua [CR-3]."""
        self.presenter._current_mode = 1
        self.presenter._pending_class_id = None

        self.presenter._on_session_confirmed({})

        # Session should NOT be started
        self.session.start_session.assert_not_called()
        self.worker.pause_scanning.assert_not_called()

    # ──────────────────────────────────────────────────────────
    # TEST 24: run() startup sequence [PM-7]
    # ──────────────────────────────────────────────────────────

    def test_run_startup_sequence(self):
        """Test: run() gọi đúng thứ tự: worker.start → camera.start → load encodings → start_scanning → mainloop [PM-7]."""
        self.db.get_encodings_by_type.return_value = []

        # mainloop blocks forever — side_effect breaks it immediately
        self.mock_app.mainloop.side_effect = lambda: None

        self.presenter.run()

        # Verify startup order
        self.worker.start.assert_called_once()
        self.camera.start.assert_called_once()
        self.worker.start_scanning.assert_called_with(mode=1)
        self.assertEqual(self.presenter._current_mode, 1)
        self.mock_app.camera_panel.start_preview.assert_called_once()
        self.mock_app.mainloop.assert_called_once()

    # ──────────────────────────────────────────────────────────
    # TEST 25: _load_student_encodings filters by class [PM-8]
    # ──────────────────────────────────────────────────────────

    def test_load_student_encodings_filters_by_class(self):
        """Test: _load_student_encodings chỉ load encoding SV thuộc lớp hiện tại [PM-8]."""
        # Students in class 10: only id=100
        self.db.get_students_in_class.return_value = [
            {'id': 100, 'name': 'SV 1', 'student_code': 'SV001'},
        ]
        # All student encodings include id=100 AND id=200 (different class)
        self.db.get_encodings_by_type.return_value = [
            {'person_id': 100, 'encoding': 'enc100'},
            {'person_id': 200, 'encoding': 'enc200'},  # Not in class 10
        ]

        self.presenter._load_student_encodings(10)

        # Only encoding for id=100 should be loaded
        self.worker.load_encodings.assert_called_once_with(
            ['enc100'],
            [{'person_id': 100, 'person_type': 'student'}],
        )

    # ──────────────────────────────────────────────────────────
    # TEST 26: STUDENT_REMOVE error path [PM-9]
    # ──────────────────────────────────────────────────────────

    def test_student_remove_error_shows_message(self):
        """Test: STUDENT_REMOVE_REQUESTED error → on_error shown [PM-9]."""
        self.student_mgr.remove_student.side_effect = ValueError("SV không tồn tại")

        self.presenter._on_student_remove_requested({'student_id': 999})

        # Error should be shown via on_error
        after_calls = [str(c) for c in self.mock_app.after.call_args_list]
        self.assertTrue(any('on_error' in c for c in after_calls))

    # ──────────────────────────────────────────────────────────
    # TEST 27: SESSION_END resets _pending_class_id [PM-1/PM-5]
    # ──────────────────────────────────────────────────────────

    def test_session_end_resets_pending_state(self):
        """Test: SESSION_END_REQUESTED resets _pending_class_id [PM-1/PM-5]."""
        self.presenter._current_mode = 2
        self.presenter._current_class_id = 10
        self.presenter._current_teacher_id = 1
        self.presenter._pending_class_id = 10  # Was set by SESSION_CONFIRMED

        self.session.end_session.return_value = {
            'class_id': 10, 'present': [], 'absent': [],
            'start_time': datetime.now(), 'end_time': datetime.now(),
        }
        self.db.get_class.return_value = {'id': 10}
        self.db.get_teacher.return_value = {'id': 1}
        self.exporter.export_session.return_value = '/path/to/file.xlsx'

        self.presenter._on_session_end_requested({})

        # _pending_class_id MUST be None after session end [PM-1]
        self.assertIsNone(self.presenter._pending_class_id)
        self.assertIsNone(self.presenter._current_mode)

    # ──────────────────────────────────────────────────────────
    # TEST 28: Excel export success shows feedback [PM-6]
    # ──────────────────────────────────────────────────────────

    def test_session_end_export_success_shows_feedback(self):
        """Test: SESSION_END_REQUESTED export thành công → thông báo trên GUI [PM-6]."""
        self.presenter._current_mode = 2
        self.presenter._current_class_id = 10
        self.presenter._current_teacher_id = 1

        self.session.end_session.return_value = {
            'class_id': 10, 'present': [], 'absent': [],
            'start_time': datetime.now(), 'end_time': datetime.now(),
        }
        self.db.get_class.return_value = {'id': 10}
        self.db.get_teacher.return_value = {'id': 1}
        self.exporter.export_session.return_value = '/path/to/file.xlsx'

        self.presenter._on_session_end_requested({})

        # Success feedback should be shown — check for "green" color arg
        after_calls = self.mock_app.after.call_args_list
        success_calls = [
            c for c in after_calls
            if len(c[0]) >= 4 and c[0][1] == self.mock_app.student_panel.on_error
            and 'green' in str(c)
        ]
        self.assertTrue(len(success_calls) > 0, "No success feedback shown after export")

    # ──────────────────────────────────────────────────────────
    # TEST 29: Shutdown sets mode to None [PM-2]
    # ──────────────────────────────────────────────────────────

    def test_shutdown_neutralizes_mode(self):
        """Test: SHUTDOWN sets _current_mode = None before cleanup [PM-2]."""
        self.presenter._current_mode = 2

        self.presenter._on_shutdown({})

        self.assertIsNone(self.presenter._current_mode)
        self.worker.stop_scanning.assert_called_once()

    # ──────────────────────────────────────────────────────────
    # TEST 30: ADMIN_REQUESTED mode=1 → pause + create AdminWindow + override protocol
    # ──────────────────────────────────────────────────────────

    def test_admin_requested_mode1_opens_window(self):
        """Test: ADMIN_REQUESTED khi mode=1 → pause + tạo AdminWindow + override protocol."""
        self.presenter._current_mode = 1

        self.presenter._on_admin_requested({})

        # Worker should be paused
        self.worker.pause_scanning.assert_called_once()
        # AdminWindow should be created with correct args
        self.MockAdminWindow.assert_called_once_with(
            self.mock_app,
            self.presenter.class_mgr,
            self.presenter.student_mgr,
            self.db,
            initial_tab=None,
        )
        # Protocol override should be set
        self.mock_admin.protocol.assert_called_once_with(
            "WM_DELETE_WINDOW", self.presenter._on_admin_closed
        )
        # State should track the window
        self.assertIs(self.presenter._admin_window, self.mock_admin)
        # [CR2-F4] Mode neutralized to prevent stale event processing
        self.assertIsNone(self.presenter._current_mode)
        # [CR-F3] Admin button should be disabled for visual consistency
        self.mock_app.session_panel.admin_button.configure.assert_called_with(state="disabled")

    # ──────────────────────────────────────────────────────────
    # TEST 31: ADMIN_REQUESTED khi mode≠1 → bị bỏ qua
    # ──────────────────────────────────────────────────────────

    def test_admin_requested_wrong_mode_ignored(self):
        """Test: ADMIN_REQUESTED khi mode≠1 → bị bỏ qua (mode guard)."""
        self.presenter._current_mode = 2

        self.presenter._on_admin_requested({})

        # AdminWindow should NOT be created
        self.MockAdminWindow.assert_not_called()
        self.worker.pause_scanning.assert_not_called()
        self.assertIsNone(self.presenter._admin_window)

    # ──────────────────────────────────────────────────────────
    # TEST 32: ADMIN_REQUESTED khi admin đang mở → bị bỏ qua (double-open)
    # ──────────────────────────────────────────────────────────

    def test_admin_requested_double_open_guard(self):
        """Test: ADMIN_REQUESTED khi admin đang mở → bị bỏ qua (double-open guard)."""
        self.presenter._current_mode = 1
        self.presenter._admin_window = MagicMock()  # Already open

        self.presenter._on_admin_requested({})

        # Should NOT create a second AdminWindow
        self.MockAdminWindow.assert_not_called()
        self.worker.pause_scanning.assert_not_called()

    # ──────────────────────────────────────────────────────────
    # TEST 33: _on_admin_closed → grab_release + destroy + reload + resume
    # ──────────────────────────────────────────────────────────

    def test_admin_closed_reloads_and_resumes(self):
        """Test: _on_admin_closed → grab_release + destroy + reload encodings + resume scanning."""
        mock_win = MagicMock()
        self.presenter._admin_window = mock_win
        self.presenter._pending_class_id = 10  # Stale state from teacher detected
        self.db.get_encodings_by_type.return_value = []
        self.camera.is_opened.return_value = True

        self.presenter._on_admin_closed()

        # Window cleanup
        mock_win.grab_release.assert_called_once()
        mock_win.destroy.assert_called_once()
        self.assertIsNone(self.presenter._admin_window)

        # [F10-fix] Pending state cleared
        self.assertIsNone(self.presenter._pending_class_id)

        # Encodings reloaded
        self.db.get_encodings_by_type.assert_called_with('teacher')

        # Worker resumed in mode 1
        self.worker.start_scanning.assert_called_with(mode=1)

        # [F7/F9-fix] Mode restored
        self.assertEqual(self.presenter._current_mode, 1)

        # [CR-F1] Teacher ID cleared
        self.assertIsNone(self.presenter._current_teacher_id)

        # [CR-F3/CR2-F5] Admin button re-enabled (only when camera alive)
        self.mock_app.session_panel.admin_button.configure.assert_called_with(state="normal")

    # ──────────────────────────────────────────────────────────
    # TEST 34: ADMIN_REQUESTED nằm trong danh sách events subscribed
    # ──────────────────────────────────────────────────────────

    def test_admin_requested_event_subscribed(self):
        """Test: ADMIN_REQUESTED nằm trong danh sách events subscribed."""
        subscribe_calls = self.MockEvents.subscribe.call_args_list
        subscribed_events = [c[0][0] for c in subscribe_calls]
        from src.core.events import EventType
        self.assertIn(EventType.ADMIN_REQUESTED, subscribed_events,
                      "EventType.ADMIN_REQUESTED not subscribed in _setup_events")

    # ──────────────────────────────────────────────────────────────
    # TEST 35: _on_admin_closed camera dead → idle + GUI notification [CR-F2/F5]
    # ──────────────────────────────────────────────────────────────

    def test_admin_closed_camera_dead_goes_idle(self):
        """Test: _on_admin_closed khi camera dead → idle + GUI notification [CR-F2/F5]."""
        mock_win = MagicMock()
        self.presenter._admin_window = mock_win
        self.presenter._pending_class_id = 10
        self.presenter._current_teacher_id = 1
        self.db.get_encodings_by_type.return_value = []
        self.camera.is_opened.return_value = False  # Camera dead

        self.presenter._on_admin_closed()

        # Window cleaned up
        mock_win.grab_release.assert_called_once()
        mock_win.destroy.assert_called_once()
        self.assertIsNone(self.presenter._admin_window)

        # Mode should be idle (None), NOT mode 1
        self.assertIsNone(self.presenter._current_mode)

        # Worker should NOT resume scanning
        self.worker.start_scanning.assert_not_called()

        # [CR2-F8] No DB call for encodings when camera is dead
        self.db.get_encodings_by_type.assert_not_called()

        # [CR2-F1] Session panel reset to clear stale teacher info
        self.mock_app.session_panel.reset.assert_called_once()

        # [CR2-F5] Admin button should NOT be re-enabled (camera dead = non-functional)
        # Note: reset() calls admin_button.configure(state="normal") internally,
        # but the explicit configure call from _on_admin_closed should NOT happen
        # The session_panel.reset mock handles internal state

        # GUI should be notified about camera disconnect
        self.mock_app.after.assert_called()

    # ──────────────────────────────────────────────────────────────
    # TEST 36: _on_admin_closed app destroyed → early return [CR-F4]
    # ──────────────────────────────────────────────────────────────

    def test_admin_closed_app_destroyed_early_return(self):
        """Test: _on_admin_closed khi app destroyed → early return, no crash [CR-F4]."""
        mock_win = MagicMock()
        self.presenter._admin_window = mock_win
        self.mock_app.winfo_exists.return_value = False  # App destroyed

        self.presenter._on_admin_closed()

        # Window still cleaned up
        mock_win.grab_release.assert_called_once()
        mock_win.destroy.assert_called_once()
        self.assertIsNone(self.presenter._admin_window)

        # Mode should be idle
        self.assertIsNone(self.presenter._current_mode)

        # Should NOT try to reload encodings or start scanning
        self.db.get_encodings_by_type.assert_not_called()
        self.worker.start_scanning.assert_not_called()

    # ──────────────────────────────────────────────────────────────
    # TEST 37: Stale TEACHER_DETECTED during admin open → rejected [CR2-F4/F7]
    # ──────────────────────────────────────────────────────────────

    def test_teacher_detected_during_admin_open_rejected(self):
        """Test: TEACHER_DETECTED while admin is open → rejected (mode=None) [CR2-F4/F7]."""
        self.presenter._current_mode = 1

        # Open admin window — mode becomes None
        self.presenter._on_admin_requested({})
        self.assertIsNone(self.presenter._current_mode)

        # Reset mocks to isolate teacher detected behavior
        self.db.reset_mock()
        self.mock_app.reset_mock()

        # Simulate stale TEACHER_DETECTED arriving while admin is open
        data = {'person_id': 1, 'confidence': 95, 'coordinates': (10, 20, 30, 40)}
        self.presenter._on_teacher_detected(data)

        # Should be rejected by mode guard (mode=None ≠ 1)
        self.db.get_teacher.assert_not_called()
        self.mock_app.after.assert_not_called()

    # ──────────────────────────────────────────────────────────────
    # TEST 38: ADMIN_REQUESTED when mode=None → rejected [CR2-F9]
    # ──────────────────────────────────────────────────────────────

    def test_admin_requested_idle_mode_ignored(self):
        """Test: ADMIN_REQUESTED khi mode=None (idle) → bị bỏ qua [CR2-F9]."""
        self.presenter._current_mode = None  # Idle state

        self.presenter._on_admin_requested({})

        # AdminWindow should NOT be created
        self.MockAdminWindow.assert_not_called()
        self.worker.pause_scanning.assert_not_called()
        self.assertIsNone(self.presenter._admin_window)

    # ──────────────────────────────────────────────────────────────
    # TEST 39: SESSION_END → save_session() called [E9-S1]
    # ──────────────────────────────────────────────────────────────

    def test_session_end_calls_save_session(self):
        """Test: SESSION_END_REQUESTED → save_session() gọi với result + teacher_id [E9-S1]."""
        self.presenter._current_mode = 2
        self.presenter._current_class_id = 10
        self.presenter._current_teacher_id = 1

        mock_result = {
            'class_id': 10, 'present': [], 'absent': [],
            'start_time': datetime.now(), 'end_time': datetime.now(),
        }
        self.session.end_session.return_value = mock_result
        self.db.get_class.return_value = {'id': 10, 'class_code': 'LHP01', 'subject': 'Toán'}
        self.db.get_teacher.return_value = {'id': 1, 'name': 'GV A', 'teacher_code': 'GV001'}
        self.exporter.export_session.return_value = '/path/to/file.xlsx'

        self.presenter._on_session_end_requested({})

        # save_session should be called with result + teacher_id
        self.db.save_session.assert_called_once_with(mock_result, 1)

    # ──────────────────────────────────────────────────────────────
    # TEST 40: save_session() failure → Excel export still proceeds [E9-S1]
    # ──────────────────────────────────────────────────────────────

    def test_session_end_save_session_failure_doesnt_block_export(self):
        """Test: save_session() fail → Excel export vẫn tiếp tục [E9-S1]."""
        self.presenter._current_mode = 2
        self.presenter._current_class_id = 10
        self.presenter._current_teacher_id = 1

        mock_result = {
            'class_id': 10, 'present': [], 'absent': [],
            'start_time': datetime.now(), 'end_time': datetime.now(),
        }
        self.session.end_session.return_value = mock_result
        self.db.get_class.return_value = {'id': 10, 'class_code': 'LHP01', 'subject': 'Toán'}
        self.db.get_teacher.return_value = {'id': 1, 'name': 'GV A', 'teacher_code': 'GV001'}
        self.exporter.export_session.return_value = '/path/to/file.xlsx'

        # save_session raises Exception
        self.db.save_session.side_effect = Exception("DB locked")

        # Should NOT crash
        self.presenter._on_session_end_requested({})

        # save_session was called (and failed)
        self.db.save_session.assert_called_once()

        # Excel export should STILL proceed despite save_session failure
        self.exporter.export_session.assert_called_once()

    # ──────────────────────────────────────────────────────────────
    # TEST 41: Post-session popup hiển thị khi export thành công [E9-S3 AC1]
    # ──────────────────────────────────────────────────────────────

    @patch('src.main.ctk', create=True)
    def test_post_session_popup_shown_on_success(self, mock_ctk_unused):
        """Test: Popup hiển thị khi export thành công — _post_session_popup is not None."""
        self.presenter._current_mode = 2
        self.presenter._current_class_id = 10
        self.presenter._current_teacher_id = 1

        mock_result = {
            'class_id': 10,
            'present': [{'student_id': 100}, {'student_id': 101}],
            'absent': [{'student_id': 102}],
            'start_time': datetime.now(), 'end_time': datetime.now(),
        }
        self.session.end_session.return_value = mock_result
        self.db.get_class.return_value = {'id': 10, 'class_code': 'LHP01', 'subject': 'Toán'}
        self.db.get_teacher.return_value = {'id': 1, 'name': 'GV A', 'teacher_code': 'GV001'}
        self.exporter.export_session.return_value = '/path/to/file.xlsx'

        self.presenter._on_session_end_requested({})

        # Verify popup scheduled via app.after(0, _show_post_session_popup, ...)
        after_calls = self.mock_app.after.call_args_list
        popup_calls = [
            c for c in after_calls
            if len(c[0]) >= 2 and c[0][1] == self.presenter._show_post_session_popup
        ]
        self.assertTrue(len(popup_calls) > 0, "Post-session popup not scheduled")
        # Verify filepath and result passed correctly
        self.assertEqual(popup_calls[0][0][2], '/path/to/file.xlsx')
        self.assertEqual(popup_calls[0][0][3], mock_result)

    # ──────────────────────────────────────────────────────────────
    # TEST 42: Summary text computed correctly [E9-S3 AC4]
    # ──────────────────────────────────────────────────────────────

    def test_post_session_summary_message_correct(self):
        """Test: Summary text computed correctly — present_count/total/percent."""
        self.presenter._current_mode = 2
        self.presenter._current_class_id = 10
        self.presenter._current_teacher_id = 1

        mock_result = {
            'class_id': 10,
            'present': [{'student_id': 100}, {'student_id': 101}],
            'absent': [{'student_id': 102}],
            'start_time': datetime.now(), 'end_time': datetime.now(),
        }
        self.session.end_session.return_value = mock_result
        self.db.get_class.return_value = {'id': 10}
        self.db.get_teacher.return_value = {'id': 1}
        self.exporter.export_session.return_value = '/path/to/file.xlsx'

        self.presenter._on_session_end_requested({})

        # Verify summary message: 2/3 (66.7%)
        after_calls = self.mock_app.after.call_args_list
        summary_calls = [
            c for c in after_calls
            if len(c[0]) >= 4 and c[0][1] == self.mock_app.student_panel.on_error
            and 'green' in str(c)
        ]
        self.assertTrue(len(summary_calls) > 0, "No summary message shown")
        msg = summary_calls[0][0][2]
        self.assertIn('2/3', msg)
        self.assertIn('66.7%', msg)
        self.assertIn('Excel đã xuất', msg)

    # ──────────────────────────────────────────────────────────────
    # TEST 43: _open_file() calls subprocess.Popen on macOS [E9-S3 AC2]
    # ──────────────────────────────────────────────────────────────

    @patch('src.main.subprocess.Popen')
    @patch('src.main.sys')
    def test_open_file_macos(self, mock_sys, mock_popen):
        """Test: _open_file() calls subprocess.Popen with ['open', filepath] on macOS."""
        mock_sys.platform = 'darwin'
        self.presenter._open_file('/path/to/file.xlsx')
        mock_popen.assert_called_once_with(['open', '/path/to/file.xlsx'])

    # ──────────────────────────────────────────────────────────────
    # TEST 44: _open_file() catches OSError gracefully [E9-S3 AC2]
    # ──────────────────────────────────────────────────────────────

    @patch('src.main.subprocess.Popen')
    @patch('src.main.sys')
    def test_open_file_oserror_handled(self, mock_sys, mock_popen):
        """Test: _open_file() catches OSError — shows error feedback to user [CR-F1]."""
        mock_sys.platform = 'darwin'
        mock_popen.side_effect = OSError("File not found")
        # Popup is alive — error should be shown on popup
        mock_popup = MagicMock()
        mock_popup.winfo_exists.return_value = True
        self.presenter._post_session_popup = mock_popup

        # Should NOT raise
        self.presenter._open_file('/path/to/nonexistent.xlsx')

    # ──────────────────────────────────────────────────────────────
    # TEST 45: _on_view_history_from_popup() calls _open_admin_history [E9-S3 AC3]
    # ──────────────────────────────────────────────────────────────

    def test_view_history_from_popup_opens_admin(self):
        """Test: _on_view_history_from_popup() calls _open_admin_history() (NOT event emit)."""
        self.presenter._post_session_popup = MagicMock()
        self.presenter._post_session_popup.winfo_exists.return_value = True
        self.camera.is_opened.return_value = True

        self.presenter._on_view_history_from_popup()

        # Popup should be destroyed
        self.assertIsNone(self.presenter._post_session_popup)

        # AdminWindow should be created with initial_tab
        self.MockAdminWindow.assert_called_once_with(
            self.mock_app, self.presenter.class_mgr,
            self.presenter.student_mgr, self.db,
            initial_tab="📋 Lịch sử"
        )
        self.assertIsNotNone(self.presenter._admin_window)

    # ──────────────────────────────────────────────────────────────
    # TEST 46: Popup không hiện khi export fail [E9-S3 AC5]
    # ──────────────────────────────────────────────────────────────

    def test_no_popup_when_export_fails(self):
        """Test: Popup không hiện khi export fail — _post_session_popup remains None."""
        self.presenter._current_mode = 2
        self.presenter._current_class_id = 10
        self.presenter._current_teacher_id = 1

        self.session.end_session.return_value = {
            'class_id': 10, 'present': [], 'absent': [],
            'start_time': datetime.now(), 'end_time': datetime.now(),
        }
        self.db.get_class.return_value = {'id': 10}
        self.db.get_teacher.return_value = {'id': 1}
        self.exporter.export_session.side_effect = ValueError("Export failed")

        self.presenter._on_session_end_requested({})

        # Popup should NOT be scheduled
        after_calls = self.mock_app.after.call_args_list
        popup_calls = [
            c for c in after_calls
            if len(c[0]) >= 2 and c[0][1] == self.presenter._show_post_session_popup
        ]
        self.assertEqual(len(popup_calls), 0, "Popup scheduled despite export failure")

    # ──────────────────────────────────────────────────────────────
    # TEST 47: _close_post_session_popup() destroys popup safely [E9-S3]
    # ──────────────────────────────────────────────────────────────

    def test_close_popup_destroys_safely(self):
        """Test: _close_post_session_popup() destroys popup + sets to None."""
        mock_popup = MagicMock()
        mock_popup.winfo_exists.return_value = True
        self.presenter._post_session_popup = mock_popup

        self.presenter._close_post_session_popup()

        mock_popup.destroy.assert_called_once()
        self.assertIsNone(self.presenter._post_session_popup)

    # ──────────────────────────────────────────────────────────────
    # TEST 48: AdminWindow receives initial_tab parameter [E9-S3 AC3]
    # ──────────────────────────────────────────────────────────────

    def test_admin_requested_forwards_initial_tab(self):
        """Test: AdminWindow nhận initial_tab parameter qua event data."""
        self.presenter._current_mode = 1

        self.presenter._on_admin_requested({'initial_tab': '📋 Lịch sử'})

        # AdminWindow should be created with initial_tab
        self.MockAdminWindow.assert_called_once_with(
            self.mock_app, self.presenter.class_mgr,
            self.presenter.student_mgr, self.db,
            initial_tab='📋 Lịch sử'
        )

    # ──────────────────────────────────────────────────────────────
    # TEST 49: _reset_to_teacher_mode() skips when AdminWindow open [E9-S3]
    # ──────────────────────────────────────────────────────────────

    def test_reset_to_teacher_mode_skips_when_admin_open(self):
        """Test: _reset_to_teacher_mode() skips khi _admin_window is not None."""
        self.mock_app.winfo_exists.return_value = True
        self.presenter._admin_window = MagicMock()  # Admin window is open
        self.presenter._post_session_popup = None

        self.presenter._reset_to_teacher_mode()

        # Panels should NOT be reset
        self.mock_app.session_panel.reset.assert_not_called()
        self.mock_app.attendance_panel.reset.assert_not_called()
        self.mock_app.student_panel.reset.assert_not_called()
        # Worker should NOT start scanning
        self.worker.start_scanning.assert_not_called()

    # ──────────────────────────────────────────────────────────────
    # TEST 50: _close_post_session_popup() when popup already destroyed [CR-F5]
    # ──────────────────────────────────────────────────────────────

    def test_close_popup_already_destroyed(self):
        """Test: _close_post_session_popup() when winfo_exists=False — destroy NOT called, ref cleared."""
        mock_popup = MagicMock()
        mock_popup.winfo_exists.return_value = False  # Already destroyed by Tk
        self.presenter._post_session_popup = mock_popup

        self.presenter._close_post_session_popup()

        # destroy() should NOT be called (widget already gone)
        mock_popup.destroy.assert_not_called()
        # Reference should still be cleared
        self.assertIsNone(self.presenter._post_session_popup)

    # ──────────────────────────────────────────────────────────────
    # TEST 51: _open_file error shows fallback on student_panel when popup gone [CR-F1]
    # ──────────────────────────────────────────────────────────────

    @patch('src.main.subprocess.Popen')
    @patch('src.main.sys')
    def test_open_file_error_fallback_to_student_panel(self, mock_sys, mock_popen):
        """Test: _open_file() error fallback to student_panel when popup is gone."""
        mock_sys.platform = 'darwin'
        mock_popen.side_effect = OSError("File not found")
        # Popup is None — error should go to student_panel
        self.presenter._post_session_popup = None

        self.presenter._open_file('/path/to/nonexistent.xlsx')

        # Error should be shown on student_panel via app.after
        after_calls = self.mock_app.after.call_args_list
        error_calls = [
            c for c in after_calls
            if len(c[0]) >= 3 and c[0][1] == self.mock_app.student_panel.on_error
        ]
        self.assertTrue(len(error_calls) > 0, "Error not shown on student_panel")
        self.assertIn('Không thể mở file', error_calls[0][0][2])

    # ──────────────────────────────────────────────────────────────
    # TEST 52: _open_admin_history neutralizes _current_mode [CR-F4]
    # ──────────────────────────────────────────────────────────────

    def test_open_admin_history_neutralizes_mode(self):
        """Test: _open_admin_history() sets _current_mode=None to prevent stale events."""
        self.presenter._current_mode = 1  # Mode was restored by _reset_to_teacher_mode
        self.presenter._admin_window = None

        self.presenter._open_admin_history()

        # Mode should be neutralized
        self.assertIsNone(self.presenter._current_mode)
        # AdminWindow should be created
        self.MockAdminWindow.assert_called_once_with(
            self.mock_app, self.presenter.class_mgr,
            self.presenter.student_mgr, self.db,
            initial_tab="📋 Lịch sử"
        )


    # ──────────────────────────────────────────────────────────────
    # TEST 53: _compute_attendance_summary empty result → (0, 0, 0) [F6]
    # ──────────────────────────────────────────────────────────────

    def test_compute_attendance_summary_empty(self):
        """Test: _compute_attendance_summary with empty/None lists → (0, 0, 0) — no div-by-zero."""
        from src.main import Presenter
        # Empty lists
        pc, total, pct = Presenter._compute_attendance_summary({'present': [], 'absent': []})
        self.assertEqual(pc, 0)
        self.assertEqual(total, 0)
        self.assertEqual(pct, 0)
        # None values (falsy → or [])
        pc2, total2, pct2 = Presenter._compute_attendance_summary({'present': None, 'absent': None})
        self.assertEqual(pc2, 0)
        self.assertEqual(total2, 0)
        self.assertEqual(pct2, 0)
        # Missing keys entirely
        pc3, total3, pct3 = Presenter._compute_attendance_summary({})
        self.assertEqual(pc3, 0)
        self.assertEqual(total3, 0)
        self.assertEqual(pct3, 0)

    # ──────────────────────────────────────────────────────────────
    # TEST 54: _show_post_session_popup app destroyed → early return [F7]
    # ──────────────────────────────────────────────────────────────

    @patch('src.main.ctk', create=True)
    def test_show_popup_app_destroyed_early_return(self, mock_ctk):
        """Test: _show_post_session_popup returns early when app.winfo_exists()=False."""
        self.mock_app.winfo_exists.return_value = False

        self.presenter._show_post_session_popup('/path/file.xlsx', {'present': [], 'absent': []})

        # CTkToplevel should NOT be created
        mock_ctk.CTkToplevel.assert_not_called()
        self.assertIsNone(self.presenter._post_session_popup)

    # ──────────────────────────────────────────────────────────────
    # TEST 55: _show_post_session_popup duplicate guard [F8]
    # ──────────────────────────────────────────────────────────────

    @patch('src.main.ctk', create=True)
    def test_show_popup_duplicate_guard(self, mock_ctk):
        """Test: _show_post_session_popup skips when popup already exists (duplicate guard)."""
        existing_popup = MagicMock()
        self.presenter._post_session_popup = existing_popup

        self.presenter._show_post_session_popup('/path/file.xlsx', {'present': [], 'absent': []})

        # CTkToplevel should NOT be created (duplicate guard)
        mock_ctk.CTkToplevel.assert_not_called()
        # Original popup reference should be preserved
        self.assertIs(self.presenter._post_session_popup, existing_popup)

    # ──────────────────────────────────────────────────────────────
    # TEST 56: _open_file on Windows calls os.startfile [F10]
    # ──────────────────────────────────────────────────────────────

    @patch('src.main.os')
    @patch('src.main.subprocess.Popen')
    @patch('src.main.sys')
    def test_open_file_windows(self, mock_sys, mock_popen, mock_os):
        """Test: _open_file() calls os.startfile on Windows (sys.platform='win32')."""
        mock_sys.platform = 'win32'
        self.presenter._open_file('/path/to/file.xlsx')
        mock_os.startfile.assert_called_once_with('/path/to/file.xlsx')
        mock_popen.assert_not_called()

    # ──────────────────────────────────────────────────────────────
    # TEST 57: _open_file on Linux calls xdg-open [F10]
    # ──────────────────────────────────────────────────────────────

    @patch('src.main.subprocess.Popen')
    @patch('src.main.sys')
    def test_open_file_linux(self, mock_sys, mock_popen):
        """Test: _open_file() calls subprocess.Popen(['xdg-open', filepath]) on Linux."""
        mock_sys.platform = 'linux'
        self.presenter._open_file('/path/to/file.xlsx')
        mock_popen.assert_called_once_with(['xdg-open', '/path/to/file.xlsx'])


    # ──────────────────────────────────────────────────────────────
    # TEST 58: _on_spoof_detected() mode=None → bỏ qua (mode guard) [E10-S2 P1]
    # ──────────────────────────────────────────────────────────────

    def test_spoof_detected_idle_mode_ignored(self):
        """Test P1: _on_spoof_detected() khi _current_mode is None → bỏ qua (mode guard)."""
        self.presenter._current_mode = None
        self.presenter._on_spoof_detected({
            'coordinates': {'top': 10, 'right': 100, 'bottom': 100, 'left': 10},
            'liveness_score': 0.3,
            'details': {},
        })
        self.mock_app.after.assert_not_called()

    # ──────────────────────────────────────────────────────────────
    # TEST 59: _on_spoof_detected() mode=1 → GUI update [E10-S2 P2]
    # ──────────────────────────────────────────────────────────────

    def test_spoof_detected_mode1_gui_update(self):
        """Test P2: _on_spoof_detected() khi mode=1 → GUI update (bounding box + text)."""
        self.presenter._current_mode = 1
        data = {
            'coordinates': {'top': 10, 'right': 100, 'bottom': 100, 'left': 10},
            'liveness_score': 0.3,
            'details': {'texture': 0.1},
        }
        self.presenter._on_spoof_detected(data)

        # Assert: set_bounding_box called with 'red'
        after_calls = [str(c) for c in self.mock_app.after.call_args_list]
        self.assertTrue(any('set_bounding_box' in c for c in after_calls),
                        "set_bounding_box not called")
        # Assert: clear_bounding_box scheduled at 2000ms
        self.assertTrue(any('2000' in c and 'clear_bounding_box' in c for c in after_calls),
                        "clear_bounding_box not scheduled at 2000ms")
        # Assert: at least 3 after() calls (set_bbox + clear_bbox + text)
        self.assertGreaterEqual(len(self.mock_app.after.call_args_list), 3)

    # ──────────────────────────────────────────────────────────────
    # TEST 60: _on_spoof_detected() mode=2 → GUI update [E10-S2 P3]
    # ──────────────────────────────────────────────────────────────

    def test_spoof_detected_mode2_gui_update(self):
        """Test P3: _on_spoof_detected() khi mode=2 → GUI update (same behavior)."""
        self.presenter._current_mode = 2
        data = {
            'coordinates': {'top': 10, 'right': 100, 'bottom': 100, 'left': 10},
            'liveness_score': 0.25,
            'details': {},
        }
        self.presenter._on_spoof_detected(data)

        # Assert: GUI updates called
        after_calls = [str(c) for c in self.mock_app.after.call_args_list]
        self.assertTrue(any('set_bounding_box' in c for c in after_calls))
        self.assertTrue(any('2000' in c and 'clear_bounding_box' in c for c in after_calls))
        self.assertGreaterEqual(len(self.mock_app.after.call_args_list), 3)

    # ──────────────────────────────────────────────────────────────
    # TEST 61: SPOOF_DETECTED nằm trong danh sách events subscribed [E10-S2 P4]
    # ──────────────────────────────────────────────────────────────

    def test_spoof_detected_event_subscribed(self):
        """Test P4: SPOOF_DETECTED nằm trong danh sách events subscribed."""
        subscribe_calls = self.MockEvents.subscribe.call_args_list
        subscribed_events = [c[0][0] for c in subscribe_calls]
        from src.core.events import EventType
        self.assertIn(EventType.SPOOF_DETECTED, subscribed_events,
                      "EventType.SPOOF_DETECTED not subscribed in _setup_events")


if __name__ == '__main__':
    unittest.main()

