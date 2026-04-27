import json
import logging
from django.db import models
from django.utils import timezone
import numpy as np

logger = logging.getLogger(__name__)


class BaseFrame(models.Model):
    """
    Named base frame configuration for the KUKA robot.
    Stores XYZABC, base number (1-32), and associated calibration data.
    """
    name = models.CharField(max_length=100, unique=True)
    base_number = models.IntegerField(default=1, help_text='KUKA $BASE number (1-32)')
    x = models.FloatField(default=0.0)
    y = models.FloatField(default=0.0)
    z = models.FloatField(default=0.0)
    a = models.FloatField(default=0.0)
    b = models.FloatField(default=0.0)
    c = models.FloatField(default=0.0)
    is_active = models.BooleanField(default=False)

    # Per-base calibration data
    nominal_part_tag_json = models.TextField(default='null',
        help_text='Nominal part-to-table 4x4 matrix JSON')
    hand_eye_matrix_json = models.TextField(default='null',
        help_text='Hand-eye calibration 4x4 matrix JSON')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['base_number', 'name']

    def __str__(self):
        return f"BASE[{self.base_number}] {self.name}"

    def get_xyzabc(self):
        return [self.x, self.y, self.z, self.a, self.b, self.c]

    def get_hand_eye_matrix(self):
        data = json.loads(self.hand_eye_matrix_json)
        return np.array(data, dtype=np.float64) if data else None

    def get_nominal_part_tag(self):
        data = json.loads(self.nominal_part_tag_json)
        return np.array(data, dtype=np.float64) if data else None

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'base_number': self.base_number,
            'X': self.x, 'Y': self.y, 'Z': self.z,
            'A': self.a, 'B': self.b, 'C': self.c,
            'is_active': self.is_active,
            'has_hand_eye': self.hand_eye_matrix_json not in ('null', '', None),
            'has_nominal': self.nominal_part_tag_json not in ('null', '', None),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class EventLog(models.Model):
    """System-wide event log for tracking actions, errors, and status changes."""
    LEVEL_CHOICES = [
        ('info', 'Info'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ]
    CATEGORY_CHOICES = [
        ('robot', 'Robot'),
        ('calibration', 'Calibration'),
        ('camera', 'Camera'),
        ('job', 'Job'),
        ('settings', 'Settings'),
        ('system', 'System'),
    ]

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='info')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='system')
    message = models.CharField(max_length=500)
    details_json = models.TextField(default='{}', blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'category']),
        ]

    def __str__(self):
        return f"[{self.level.upper()}] {self.category}: {self.message}"

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'level': self.level,
            'category': self.category,
            'message': self.message,
            'details': json.loads(self.details_json) if self.details_json else {},
        }


def log_event(category, message, level='info', details=None):
    """Helper to create an EventLog entry and also log via Python logger."""
    details_json = json.dumps(details) if details else '{}'
    try:
        EventLog.objects.create(
            category=category,
            message=message[:500],
            level=level,
            details_json=details_json,
        )
    except Exception as e:
        logger.error(f"Failed to write EventLog: {e}")

    log_fn = getattr(logger, level if level != 'success' else 'info')
    log_fn(f"[{category}] {message}")


class SystemSettings(models.Model):
    """Singleton settings. Always use get_settings()."""
    # Robot connection
    robot_ip = models.GenericIPAddressField(default='192.168.1.120')
    robot_port = models.IntegerField(default=54610)

    # Camera
    camera_index = models.IntegerField(default=0)
    camera_width = models.IntegerField(default=1280)
    camera_height = models.IntegerField(default=720)
    camera_fps = models.IntegerField(default=30)
    camera_fx = models.FloatField(default=900.0)
    camera_fy = models.FloatField(default=900.0)
    camera_cx = models.FloatField(default=640.0)
    camera_cy = models.FloatField(default=360.0)
    dist_coeffs_json = models.TextField(default='[0,0,0,0,0]')

    # ArUco tags
    ARUCO_DICT_CHOICES = [
        ('DICT_4X4_50', '4x4 (50)'),
        ('DICT_4X4_100', '4x4 (100)'),
        ('DICT_4X4_250', '4x4 (250)'),
        ('DICT_4X4_1000', '4x4 (1000)'),
        ('DICT_5X5_50', '5x5 (50)'),
        ('DICT_5X5_100', '5x5 (100)'),
        ('DICT_5X5_250', '5x5 (250)'),
        ('DICT_5X5_1000', '5x5 (1000)'),
        ('DICT_6X6_50', '6x6 (50)'),
        ('DICT_6X6_100', '6x6 (100)'),
        ('DICT_6X6_250', '6x6 (250)'),
        ('DICT_6X6_1000', '6x6 (1000)'),
        ('DICT_7X7_50', '7x7 (50)'),
        ('DICT_7X7_100', '7x7 (100)'),
        ('DICT_7X7_250', '7x7 (250)'),
        ('DICT_7X7_1000', '7x7 (1000)'),
    ]
    aruco_dict_type = models.CharField(
        max_length=20, choices=ARUCO_DICT_CHOICES, default='DICT_6X6_250'
    )
    table_tag_id = models.IntegerField(default=0)
    part_tag_id = models.IntegerField(default=1)
    tag_size_mm = models.FloatField(default=100.0)

    # Capture position (6 robot + 6 external axes)
    capture_joint_pos_json = models.TextField(
        default='[0, -90, 90, 0, 0, 0, 0, 0, 0, 0, 0, 0]'
    )

    # Nominal base frame
    nominal_base_x = models.FloatField(default=0.0)
    nominal_base_y = models.FloatField(default=0.0)
    nominal_base_z = models.FloatField(default=0.0)
    nominal_base_a = models.FloatField(default=0.0)
    nominal_base_b = models.FloatField(default=0.0)
    nominal_base_c = models.FloatField(default=0.0)

    # Nominal part tag pose relative to table tag (4x4 JSON)
    nominal_part_tag_json = models.TextField(default='null')

    # Hand-eye calibration matrix (4x4 JSON)
    hand_eye_matrix_json = models.TextField(default='null')

    # HSV color segmentation thresholds
    hsv_lower_json = models.TextField(default='[0, 0, 0]', help_text='Lower HSV bounds')
    hsv_upper_json = models.TextField(default='[180, 255, 255]', help_text='Upper HSV bounds')

    # Dry run mode (Phase 4)
    dry_run_mode = models.BooleanField(default=False,
        help_text='When true, calibration computes but does not send $BASE to robot')

    # Active base frame reference
    active_base_frame = models.ForeignKey(
        BaseFrame, null=True, blank=True, on_delete=models.SET_NULL,
        help_text='Currently active base frame configuration'
    )

    # Safety limits
    max_correction_mm = models.FloatField(default=50.0)
    max_correction_deg = models.FloatField(default=5.0)
    override_percent = models.IntegerField(default=10)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'System Settings'
        verbose_name_plural = 'System Settings'

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def get_camera_matrix(self):
        return np.array([
            [self.camera_fx, 0, self.camera_cx],
            [0, self.camera_fy, self.camera_cy],
            [0, 0, 1]
        ], dtype=np.float64)

    def get_dist_coeffs(self):
        return np.array(json.loads(self.dist_coeffs_json), dtype=np.float64)

    def get_capture_joint_pos(self):
        return json.loads(self.capture_joint_pos_json)

    def get_nominal_base(self):
        return [self.nominal_base_x, self.nominal_base_y, self.nominal_base_z,
                self.nominal_base_a, self.nominal_base_b, self.nominal_base_c]

    def get_hand_eye_matrix(self):
        data = json.loads(self.hand_eye_matrix_json)
        return np.array(data, dtype=np.float64) if data else None

    def get_nominal_part_tag(self):
        data = json.loads(self.nominal_part_tag_json)
        return np.array(data, dtype=np.float64) if data else None


class CameraCalibration(models.Model):
    """Stores camera calibration results from chessboard wizard."""
    fx = models.FloatField()
    fy = models.FloatField()
    cx = models.FloatField()
    cy = models.FloatField()
    dist_coeffs_json = models.TextField(help_text='Distortion coefficients JSON array')
    rms_error = models.FloatField(help_text='RMS reprojection error')
    num_poses = models.IntegerField(help_text='Number of calibration images used')
    board_rows = models.IntegerField(default=9)
    board_cols = models.IntegerField(default=6)
    square_size_mm = models.FloatField(default=25.0)
    is_applied = models.BooleanField(default=False,
        help_text='Whether this calibration has been applied to SystemSettings')
    calibrated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-calibrated_at']

    def __str__(self):
        return f"CamCal {self.calibrated_at:%Y-%m-%d %H:%M} (RMS={self.rms_error:.4f})"

    def to_dict(self):
        return {
            'id': self.id,
            'fx': self.fx, 'fy': self.fy, 'cx': self.cx, 'cy': self.cy,
            'dist_coeffs': json.loads(self.dist_coeffs_json),
            'rms_error': self.rms_error,
            'num_poses': self.num_poses,
            'board_rows': self.board_rows, 'board_cols': self.board_cols,
            'square_size_mm': self.square_size_mm,
            'is_applied': self.is_applied,
            'calibrated_at': self.calibrated_at.isoformat() if self.calibrated_at else None,
        }


class CapturePosition(models.Model):
    """Named capture position for the robot (joint angles for calibration view)."""
    name = models.CharField(max_length=100)
    joint_pos_json = models.TextField(
        default='[0, -90, 90, 0, 0, 0, 0, 0, 0, 0, 0, 0]',
        help_text='12 joint values: 6 robot axes + 6 external axes'
    )
    is_default = models.BooleanField(default=False)
    base_frame = models.ForeignKey(
        BaseFrame, null=True, blank=True, on_delete=models.CASCADE,
        related_name='capture_positions'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"CapturePos: {self.name}"

    def get_joint_pos(self):
        return json.loads(self.joint_pos_json)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'joint_pos': self.get_joint_pos(),
            'is_default': self.is_default,
            'base_frame_id': self.base_frame_id,
            'base_frame_name': self.base_frame.name if self.base_frame else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class KRLProgram(models.Model):
    name = models.CharField(max_length=100, unique=True)
    src_file = models.FileField(upload_to='krl_programs/')
    dat_file = models.FileField(upload_to='krl_programs/', blank=True, null=True)
    description = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    point_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.name


class CalibrationRecord(models.Model):
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('rejected', 'Rejected'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    table_tag_pose_json = models.TextField(blank=True, default='')
    part_tag_pose_json = models.TextField(blank=True, default='')
    robot_pos_json = models.TextField(blank=True, default='')

    correction_x = models.FloatField(null=True)
    correction_y = models.FloatField(null=True)
    correction_z = models.FloatField(null=True)
    correction_a = models.FloatField(null=True)
    correction_b = models.FloatField(null=True)
    correction_c = models.FloatField(null=True)

    corrected_base_x = models.FloatField(null=True)
    corrected_base_y = models.FloatField(null=True)
    corrected_base_z = models.FloatField(null=True)
    corrected_base_a = models.FloatField(null=True)
    corrected_base_b = models.FloatField(null=True)
    corrected_base_c = models.FloatField(null=True)

    translation_mag = models.FloatField(null=True)
    rotation_mag = models.FloatField(null=True)

    error_message = models.TextField(blank=True, default='')
    is_dry_run = models.BooleanField(default=False)

    krl_program = models.ForeignKey(KRLProgram, null=True, blank=True,
                                     on_delete=models.SET_NULL)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Cal {self.timestamp:%Y-%m-%d %H:%M} - {self.status}"


class JobCycle(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('calibrated', 'Calibrated'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('aborted', 'Aborted'),
        ('error', 'Error'),
    ]

    cycle_number = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    calibration = models.OneToOneField(CalibrationRecord, null=True, blank=True,
                                       on_delete=models.SET_NULL)
    krl_program = models.ForeignKey(KRLProgram, null=True, blank=True,
                                     on_delete=models.SET_NULL)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Cycle #{self.cycle_number} - {self.status}"
