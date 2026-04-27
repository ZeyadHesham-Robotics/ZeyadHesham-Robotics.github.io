from django.urls import path
from . import views

urlpatterns = [
    # Pages
    path('', views.dashboard, name='dashboard'),
    path('calibration/', views.calibration_page, name='calibration'),
    path('jobs/', views.jobs_page, name='jobs'),
    path('settings/', views.settings_page, name='settings'),
    path('camera-calibration/', views.camera_calibration_page, name='camera_calibration'),

    # Robot API
    path('api/robot/connect/', views.api_robot_connect, name='api_robot_connect'),
    path('api/robot/disconnect/', views.api_robot_disconnect, name='api_robot_disconnect'),
    path('api/robot/status/', views.api_robot_status, name='api_robot_status'),
    path('api/robot/move-to-capture/', views.api_move_to_capture, name='api_move_to_capture'),
    path('api/robot/jog/', views.api_robot_jog, name='api_robot_jog'),
    path('api/robot/set-speed/', views.api_robot_set_speed, name='api_robot_set_speed'),
    path('api/robot/position/', views.api_robot_position, name='api_robot_position'),
    path('api/robot/teach-capture/', views.api_teach_capture, name='api_teach_capture'),

    # Capture Position API
    path('api/capture-positions/', views.api_capture_positions, name='api_capture_positions'),
    path('api/capture-positions/<int:pk>/', views.api_capture_position_detail, name='api_capture_position_detail'),
    path('api/capture-positions/<int:pk>/activate/', views.api_activate_capture_position, name='api_activate_capture_position'),

    # Calibration API
    path('api/calibration/detect/', views.api_detect_tags, name='api_detect_tags'),
    path('api/calibration/scan-tags/', views.api_scan_all_tags, name='api_scan_all_tags'),
    path('api/calibration/assign-tags/', views.api_assign_tags, name='api_assign_tags'),
    path('api/calibration/teach-nominal/', views.api_teach_nominal, name='api_teach_nominal'),

    # Camera Calibration Wizard
    path('api/camera-cal/detect-board/', views.api_cam_cal_detect_board, name='api_cam_cal_detect_board'),
    path('api/camera-cal/capture/', views.api_cam_cal_capture, name='api_cam_cal_capture'),
    path('api/camera-cal/compute/', views.api_cam_cal_compute, name='api_cam_cal_compute'),
    path('api/camera-cal/<int:pk>/apply/', views.api_cam_cal_apply, name='api_cam_cal_apply'),
    path('api/camera-cal/history/', views.api_cam_cal_history, name='api_cam_cal_history'),

    # Hand-Eye Calibration Wizard
    path('api/hand-eye/capture/', views.api_hand_eye_capture, name='api_hand_eye_capture'),
    path('api/hand-eye/compute/', views.api_hand_eye_compute, name='api_hand_eye_compute'),
    path('api/hand-eye/apply/', views.api_hand_eye_apply, name='api_hand_eye_apply'),
    path('api/hand-eye/reset/', views.api_hand_eye_reset, name='api_hand_eye_reset'),
    path('api/hand-eye/status/', views.api_hand_eye_status, name='api_hand_eye_status'),

    # HSV Tuner
    path('api/vision/hsv-preview/', views.api_hsv_preview, name='api_hsv_preview'),
    path('api/vision/hsv-save/', views.api_hsv_save, name='api_hsv_save'),
    path('api/calibration/full-cycle/', views.api_full_cycle, name='api_full_cycle'),
    path('api/calibration/auto-cycle/', views.api_auto_calibration, name='api_auto_calibration'),
    path('api/calibration/repeatability-test/', views.api_repeatability_test, name='api_repeatability_test'),
    path('api/calibration/toggle-dry-run/', views.api_toggle_dry_run, name='api_toggle_dry_run'),
    path('api/calibration/history/', views.api_calibration_history, name='api_calibration_history'),

    # Jobs API
    path('api/jobs/upload/', views.api_upload_krl, name='api_upload_krl'),
    path('api/jobs/', views.api_list_jobs, name='api_list_jobs'),
    path('api/jobs/<int:pk>/activate/', views.api_activate_job, name='api_activate_job'),
    path('api/jobs/<int:pk>/delete/', views.api_delete_job, name='api_delete_job'),
    path('api/jobs/<int:pk>/source/', views.api_job_source, name='api_job_source'),
    path('api/jobs/<int:pk>/statistics/', views.api_job_statistics, name='api_job_statistics'),
    path('api/jobs/execute-cycle/', views.api_execute_cycle, name='api_execute_cycle'),

    # Settings API
    path('api/settings/', views.api_settings, name='api_settings'),

    # Base Frame API
    path('api/base-frames/', views.api_base_frames, name='api_base_frames'),
    path('api/base-frames/<int:pk>/', views.api_base_frame_detail, name='api_base_frame_detail'),
    path('api/base-frames/<int:pk>/activate/', views.api_activate_base_frame, name='api_activate_base_frame'),

    # Event Log API
    path('api/events/', views.api_events, name='api_events'),

    # Camera API
    path('api/camera/open/', views.api_camera_open, name='api_camera_open'),
    path('api/camera/close/', views.api_camera_close, name='api_camera_close'),
    path('api/camera/status/', views.api_camera_status, name='api_camera_status'),

    # Export API
    path('api/calibration/export/csv/', views.api_export_csv, name='api_export_csv'),
    path('api/calibration/export/xlsx/', views.api_export_xlsx, name='api_export_xlsx'),

    # Backup / Restore API
    path('api/settings/backup/', views.api_backup_settings, name='api_backup_settings'),
    path('api/settings/restore/', views.api_restore_settings, name='api_restore_settings'),

    # Authentication
    path('login/', views.login_page, name='login'),
    path('api/auth/login/', views.api_login, name='api_login'),
    path('api/auth/logout/', views.api_logout, name='api_logout'),
    path('api/auth/user/', views.api_user_info, name='api_user_info'),

    # Diagnostics & Visualization
    path('api/calibration/segmentation/', views.api_segmentation_view, name='api_segmentation_view'),
    path('api/calibration/workspace/', views.api_workspace_data, name='api_workspace_data'),
]
