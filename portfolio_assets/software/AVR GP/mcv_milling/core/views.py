import json
import time
import csv
import io
import cv2
import numpy as np
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User

import base64
from .models import (SystemSettings, KRLProgram, CalibrationRecord, JobCycle,
                     BaseFrame, EventLog, CapturePosition, CameraCalibration, log_event)
from services.robot_service import RobotService
from services.vision_service import VisionService
from services.calibration_service import CalibrationEngine, compute_hand_eye
from services.cam_parser import parse_krl_src

# In-memory storage for calibration wizard sessions
_cam_cal_frames = []   # list of corners arrays for camera calibration
_hand_eye_poses = []   # list of {'robot_pose': [...], 'cam_pose': 4x4} for hand-eye


# ── Page views ────────────────────────────────────────────────

def dashboard(request):
    settings = SystemSettings.get_settings()
    recent_cals = CalibrationRecord.objects.all()[:10]
    active_program = KRLProgram.objects.filter(is_active=True).first()
    total_cycles = JobCycle.objects.count()
    success_cycles = JobCycle.objects.filter(status='completed').count()
    return render(request, 'dashboard.html', {
        'settings': settings,
        'recent_cals': recent_cals,
        'active_program': active_program,
        'total_cycles': total_cycles,
        'success_cycles': success_cycles,
    })


def calibration_page(request):
    settings = SystemSettings.get_settings()
    has_hand_eye = settings.hand_eye_matrix_json not in ('null', '', None)
    has_nominal = settings.nominal_part_tag_json not in ('null', '', None)
    return render(request, 'calibration.html', {
        'settings': settings,
        'has_hand_eye': has_hand_eye,
        'has_nominal': has_nominal,
    })


def jobs_page(request):
    programs = KRLProgram.objects.all()
    return render(request, 'jobs.html', {'programs': programs})


def camera_calibration_page(request):
    settings = SystemSettings.get_settings()
    calibrations = CameraCalibration.objects.all()[:10]
    return render(request, 'camera_calibration.html', {
        'settings': settings,
        'calibrations': calibrations,
    })


def settings_page(request):
    settings = SystemSettings.get_settings()
    return render(request, 'settings.html', {'settings': settings})


# ── Robot API ─────────────────────────────────────────────────

@csrf_exempt
@require_POST
def api_robot_connect(request):
    data = json.loads(request.body) if request.body else {}
    settings = SystemSettings.get_settings()
    ip = data.get('ip', settings.robot_ip)
    port = data.get('port', settings.robot_port)
    robot = RobotService()
    result = robot.connect(ip, port)
    if result.get('status') == 'connected':
        log_event('robot', f'Connected to robot at {ip}:{port} ({result.get("robot_name", "Unknown")})', level='success')
    else:
        log_event('robot', f'Connection failed to {ip}:{port}: {result.get("message", "")}', level='error')
    return JsonResponse(result)


@csrf_exempt
@require_POST
def api_robot_disconnect(request):
    robot = RobotService()
    result = robot.disconnect()
    log_event('robot', 'Disconnected from robot', level='info')
    return JsonResponse(result)


@require_GET
def api_robot_status(request):
    robot = RobotService()
    if not robot.is_connected:
        return JsonResponse({'connected': False})
    try:
        info = robot.get_robot_info()
        pos = robot.get_current_cart_pos()
        return JsonResponse({'connected': True, 'info': info, 'position': pos})
    except Exception as e:
        return JsonResponse({'connected': True, 'error': str(e)})


@csrf_exempt
@require_POST
def api_move_to_capture(request):
    robot = RobotService()
    settings = SystemSettings.get_settings()
    try:
        joints = settings.get_capture_joint_pos()
        robot.go_to_joint_pos(joints)
        log_event('robot', 'Moving to capture position', level='info')
        return JsonResponse({'status': 'ok', 'message': 'Moving to capture position'})
    except Exception as e:
        log_event('robot', f'Move to capture failed: {e}', level='error')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


# ── Calibration API ───────────────────────────────────────────

def _build_engine():
    """Build CalibrationEngine from current settings."""
    s = SystemSettings.get_settings()
    return CalibrationEngine(
        camera_matrix=s.get_camera_matrix(),
        dist_coeffs=s.get_dist_coeffs(),
        table_tag_id=s.table_tag_id,
        part_tag_id=s.part_tag_id,
        tag_size_mm=s.tag_size_mm,
        hand_eye_matrix=s.get_hand_eye_matrix(),
        nominal_part_tag_matrix=s.get_nominal_part_tag(),
        nominal_base=s.get_nominal_base(),
        max_correction_mm=s.max_correction_mm,
        max_correction_deg=s.max_correction_deg,
        aruco_dict_type=s.aruco_dict_type,
    )


@csrf_exempt
@require_POST
def api_detect_tags(request):
    """Detect both tags in current camera frame (preview mode)."""
    vision = VisionService()
    try:
        frame = vision.capture_frame()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        engine = _build_engine()
        result = engine.detect_tags(gray)
        return JsonResponse({
            'status': 'ok',
            'table_found': result['table_found'],
            'part_found': result['part_found'],
            'table_dist_mm': round(result['table_dist_mm'], 1),
            'part_dist_mm': round(result['part_dist_mm'], 1),
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_scan_all_tags(request):
    """Scan for ALL ArUco tags visible to the camera. Returns list of detected tag IDs with distances."""
    from services.vision_service import get_aruco_dict
    vision = VisionService()
    settings = SystemSettings.get_settings()
    try:
        frame = vision.capture_frame()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        aruco_dict = get_aruco_dict(settings.aruco_dict_type)
        aruco_params = cv2.aruco.DetectorParameters()
        corners, ids, _ = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=aruco_params)

        tags = []
        if ids is not None and len(ids) > 0:
            camera_matrix = settings.get_camera_matrix()
            dist_coeffs = settings.get_dist_coeffs()
            half = settings.tag_size_mm / 2.0
            obj_pts = np.array([
                [-half, half, 0], [half, half, 0],
                [half, -half, 0], [-half, -half, 0]
            ], dtype=np.float32)

            for i, mid in enumerate(ids.flatten()):
                tag_info = {'id': int(mid), 'distance_mm': 0}
                img_pts = corners[i][0].astype(np.float32)
                ok, rvec, tvec = cv2.solvePnP(
                    obj_pts, img_pts, camera_matrix, dist_coeffs,
                    flags=cv2.SOLVEPNP_IPPE_SQUARE
                )
                if ok:
                    tag_info['distance_mm'] = round(float(np.linalg.norm(tvec)), 1)

                # Current role assignment
                if int(mid) == settings.table_tag_id:
                    tag_info['role'] = 'table'
                elif int(mid) == settings.part_tag_id:
                    tag_info['role'] = 'part'
                else:
                    tag_info['role'] = 'none'

                tags.append(tag_info)

        return JsonResponse({
            'status': 'ok',
            'tags': sorted(tags, key=lambda t: t['id']),
            'total': len(tags),
            'aruco_dict': settings.aruco_dict_type,
            'current_table_id': settings.table_tag_id,
            'current_part_id': settings.part_tag_id,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_assign_tags(request):
    """Assign tag roles (table/part) and save to settings."""
    data = json.loads(request.body)
    table_id = data.get('table_tag_id')
    part_id = data.get('part_tag_id')

    if table_id is None or part_id is None:
        return JsonResponse({'status': 'error', 'message': 'Both table_tag_id and part_tag_id required'}, status=400)
    if table_id == part_id:
        return JsonResponse({'status': 'error', 'message': 'Table and part tags must be different IDs'}, status=400)

    s = SystemSettings.get_settings()
    s.table_tag_id = int(table_id)
    s.part_tag_id = int(part_id)
    s.save()

    return JsonResponse({
        'status': 'ok',
        'table_tag_id': s.table_tag_id,
        'part_tag_id': s.part_tag_id,
    })


@csrf_exempt
@require_POST
def api_teach_nominal(request):
    """Teach the nominal part-to-table relationship."""
    vision = VisionService()
    try:
        frame = vision.capture_averaged(n=5)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        engine = _build_engine()
        T_nominal = engine.teach_nominal(gray)

        # Save to settings
        s = SystemSettings.get_settings()
        s.nominal_part_tag_json = json.dumps(T_nominal.tolist())
        s.save()

        log_event('calibration', 'Nominal part-to-table position taught successfully', level='success')
        return JsonResponse({
            'status': 'ok',
            'message': 'Nominal position taught successfully',
            'transform': T_nominal.tolist(),
        })
    except Exception as e:
        log_event('calibration', f'Teach nominal failed: {e}', level='error')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_full_cycle(request):
    """Full calibration cycle: move to capture, detect, compute, send $BASE."""
    robot = RobotService()
    vision = VisionService()
    settings = SystemSettings.get_settings()

    try:
        # 1. Move to capture position
        joints = settings.get_capture_joint_pos()
        robot.go_to_joint_pos(joints)
        time.sleep(1.5)

        # 2. Get robot TCP position
        tcp_pos = robot.get_current_cart_pos()

        # 3. Capture frame
        frame = vision.capture_averaged(n=5)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 4. Compute correction
        engine = _build_engine()
        result = engine.compute_correction(gray, tcp_pos)

        # 5. Send corrected base (skip in dry run mode)
        base = result['corrected_base']
        if not settings.dry_run_mode:
            robot.set_base_data(*base)

        # 6. Log
        record = CalibrationRecord.objects.create(
            status='success',
            table_tag_pose_json=json.dumps(result['table_tag_pose']),
            part_tag_pose_json=json.dumps(result['part_tag_pose']),
            robot_pos_json=json.dumps(tcp_pos),
            correction_x=result['correction'][0],
            correction_y=result['correction'][1],
            correction_z=result['correction'][2],
            correction_a=result['correction'][3],
            correction_b=result['correction'][4],
            correction_c=result['correction'][5],
            corrected_base_x=base[0],
            corrected_base_y=base[1],
            corrected_base_z=base[2],
            corrected_base_a=base[3],
            corrected_base_b=base[4],
            corrected_base_c=base[5],
            translation_mag=result['translation_magnitude_mm'],
            rotation_mag=result['rotation_magnitude_deg'],
            is_dry_run=settings.dry_run_mode,
        )

        log_event('calibration',
            f'Calibration cycle OK — dT={result["translation_magnitude_mm"]:.2f}mm, dR={result["rotation_magnitude_deg"]:.2f}deg',
            level='success',
            details={'correction': result['correction'], 'record_id': record.id})

        return JsonResponse({
            'status': 'success',
            'corrected_base': {k: round(v, 3) for k, v in zip('XYZABC', base)},
            'correction': {k: round(v, 3) for k, v in zip(
                ['dX', 'dY', 'dZ', 'dA', 'dB', 'dC'], result['correction'])},
            'translation_mm': round(result['translation_magnitude_mm'], 2),
            'rotation_deg': round(result['rotation_magnitude_deg'], 2),
            'record_id': record.id,
        })

    except Exception as e:
        CalibrationRecord.objects.create(
            status='failed',
            error_message=str(e),
        )
        log_event('calibration', f'Calibration cycle FAILED: {e}', level='error')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@require_GET
def api_calibration_history(request):
    records = CalibrationRecord.objects.all()[:50]
    data = [{
        'id': r.id,
        'timestamp': r.timestamp.isoformat(),
        'status': r.status,
        'correction': {
            'X': r.correction_x, 'Y': r.correction_y, 'Z': r.correction_z,
            'A': r.correction_a, 'B': r.correction_b, 'C': r.correction_c,
        } if r.correction_x is not None else None,
        'translation_mm': r.translation_mag,
        'rotation_deg': r.rotation_mag,
        'error': r.error_message,
    } for r in records]
    return JsonResponse({'records': data})


# ── Jobs API ──────────────────────────────────────────────────

@csrf_exempt
@require_POST
def api_upload_krl(request):
    src_file = request.FILES.get('src_file')
    dat_file = request.FILES.get('dat_file')
    if not src_file:
        return JsonResponse({'status': 'error', 'message': 'No .src file provided'}, status=400)

    content = src_file.read().decode('utf-8', errors='replace')
    parsed = parse_krl_src(content)

    name = request.POST.get('name', parsed.get('program_name', src_file.name))

    program = KRLProgram.objects.create(
        name=name,
        src_file=src_file,
        dat_file=dat_file,
        description=request.POST.get('description', ''),
        point_count=parsed['point_count'],
    )

    log_event('job', f'KRL program "{name}" uploaded ({parsed["point_count"]} points)', level='success')

    return JsonResponse({
        'status': 'ok',
        'id': program.id,
        'name': program.name,
        'point_count': parsed['point_count'],
        'motion_types': parsed['motion_types'],
        'is_valid': parsed['is_valid'],
        'errors': parsed['errors'],
    })


@require_GET
def api_list_jobs(request):
    programs = KRLProgram.objects.all()
    data = [{
        'id': p.id,
        'name': p.name,
        'description': p.description,
        'point_count': p.point_count,
        'is_active': p.is_active,
        'uploaded_at': p.uploaded_at.isoformat(),
    } for p in programs]
    return JsonResponse({'programs': data})


@csrf_exempt
@require_POST
def api_activate_job(request, pk):
    try:
        KRLProgram.objects.all().update(is_active=False)
        program = KRLProgram.objects.get(pk=pk)
        program.is_active = True
        program.save()
        log_event('job', f'Program "{program.name}" activated', level='info')
        return JsonResponse({'status': 'ok', 'name': program.name})
    except KRLProgram.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Program not found'}, status=404)


@csrf_exempt
@require_POST
def api_delete_job(request, pk):
    try:
        program = KRLProgram.objects.get(pk=pk)
        program.src_file.delete()
        if program.dat_file:
            program.dat_file.delete()
        program.delete()
        return JsonResponse({'status': 'ok'})
    except KRLProgram.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Program not found'}, status=404)


@require_GET
def api_job_source(request, pk):
    """Return KRL source file content for viewing."""
    try:
        program = KRLProgram.objects.get(pk=pk)
        content = program.src_file.read().decode('utf-8', errors='replace')
        program.src_file.seek(0)
        dat_content = None
        if program.dat_file:
            dat_content = program.dat_file.read().decode('utf-8', errors='replace')
            program.dat_file.seek(0)
        return JsonResponse({
            'status': 'ok',
            'name': program.name,
            'src': content,
            'dat': dat_content,
            'point_count': program.point_count,
        })
    except KRLProgram.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)


@csrf_exempt
@require_POST
def api_execute_cycle(request):
    """Execute a job cycle: optionally calibrate first, then record cycle."""
    data = json.loads(request.body) if request.body else {}
    auto_calibrate = data.get('auto_calibrate', False)
    settings = SystemSettings.get_settings()
    program = KRLProgram.objects.filter(is_active=True).first()

    start_time = time.time()
    cal_record = None

    try:
        # Optional auto-calibration
        if auto_calibrate:
            robot = RobotService()
            vision = VisionService()
            joints = settings.get_capture_joint_pos()
            robot.go_to_joint_pos(joints)
            time.sleep(1.5)
            tcp_pos = robot.get_current_cart_pos()
            frame = vision.capture_averaged(n=5)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            engine = _build_engine()
            result = engine.compute_correction(gray, tcp_pos)
            base = result['corrected_base']
            if not settings.dry_run_mode:
                robot.set_base_data(*base)

            cal_record = CalibrationRecord.objects.create(
                status='success',
                correction_x=result['correction'][0], correction_y=result['correction'][1],
                correction_z=result['correction'][2], correction_a=result['correction'][3],
                correction_b=result['correction'][4], correction_c=result['correction'][5],
                corrected_base_x=base[0], corrected_base_y=base[1],
                corrected_base_z=base[2], corrected_base_a=base[3],
                corrected_base_b=base[4], corrected_base_c=base[5],
                translation_mag=result['translation_magnitude_mm'],
                rotation_mag=result['rotation_magnitude_deg'],
                is_dry_run=settings.dry_run_mode,
                krl_program=program,
            )

        # Create job cycle record
        last_cycle = JobCycle.objects.order_by('-cycle_number').first()
        cycle_num = (last_cycle.cycle_number + 1) if last_cycle else 1
        duration = time.time() - start_time

        cycle = JobCycle.objects.create(
            cycle_number=cycle_num,
            status='calibrated' if auto_calibrate else 'completed',
            calibration=cal_record,
            krl_program=program,
            duration_seconds=round(duration, 2),
        )

        log_event('job',
            f'Cycle #{cycle_num} {"with calibration" if auto_calibrate else "executed"} '
            f'({duration:.1f}s)', level='success')

        return JsonResponse({
            'status': 'ok',
            'cycle_number': cycle_num,
            'duration_seconds': round(duration, 2),
            'calibrated': auto_calibrate,
            'program': program.name if program else None,
        })
    except Exception as e:
        log_event('job', f'Cycle execution failed: {e}', level='error')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@require_GET
def api_job_statistics(request, pk):
    """Get statistics for a specific KRL program."""
    try:
        program = KRLProgram.objects.get(pk=pk)
    except KRLProgram.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)

    cycles = JobCycle.objects.filter(krl_program=program)
    completed = cycles.filter(status='completed')
    calibrated = cycles.filter(status='calibrated')
    errors = cycles.filter(status='error')

    durations = [c.duration_seconds for c in cycles if c.duration_seconds]

    stats = {
        'program_name': program.name,
        'total_cycles': cycles.count(),
        'completed': completed.count(),
        'calibrated': calibrated.count(),
        'errors': errors.count(),
        'avg_duration': round(sum(durations) / len(durations), 2) if durations else None,
        'min_duration': round(min(durations), 2) if durations else None,
        'max_duration': round(max(durations), 2) if durations else None,
    }
    return JsonResponse({'status': 'ok', 'stats': stats})


# ── Settings API ──────────────────────────────────────────────

@csrf_exempt
def api_settings(request):
    s = SystemSettings.get_settings()
    if request.method == 'GET':
        return JsonResponse({
            'robot_ip': s.robot_ip,
            'robot_port': s.robot_port,
            'camera_index': s.camera_index,
            'camera_width': s.camera_width,
            'camera_height': s.camera_height,
            'camera_fps': s.camera_fps,
            'camera_fx': s.camera_fx,
            'camera_fy': s.camera_fy,
            'camera_cx': s.camera_cx,
            'camera_cy': s.camera_cy,
            'dist_coeffs': json.loads(s.dist_coeffs_json),
            'aruco_dict_type': s.aruco_dict_type,
            'table_tag_id': s.table_tag_id,
            'part_tag_id': s.part_tag_id,
            'tag_size_mm': s.tag_size_mm,
            'capture_joint_pos': json.loads(s.capture_joint_pos_json),
            'nominal_base': s.get_nominal_base(),
            'max_correction_mm': s.max_correction_mm,
            'max_correction_deg': s.max_correction_deg,
            'override_percent': s.override_percent,
            'has_hand_eye': s.hand_eye_matrix_json not in ('null', '', None),
            'has_nominal_part': s.nominal_part_tag_json not in ('null', '', None),
        })

    elif request.method in ('PUT', 'POST'):
        data = json.loads(request.body)
        field_map = {
            'robot_ip': 'robot_ip', 'robot_port': 'robot_port',
            'camera_index': 'camera_index', 'camera_width': 'camera_width',
            'camera_height': 'camera_height', 'camera_fps': 'camera_fps',
            'camera_fx': 'camera_fx', 'camera_fy': 'camera_fy',
            'camera_cx': 'camera_cx', 'camera_cy': 'camera_cy',
            'aruco_dict_type': 'aruco_dict_type',
            'table_tag_id': 'table_tag_id', 'part_tag_id': 'part_tag_id',
            'tag_size_mm': 'tag_size_mm',
            'max_correction_mm': 'max_correction_mm',
            'max_correction_deg': 'max_correction_deg',
            'override_percent': 'override_percent',
            'nominal_base_x': 'nominal_base_x', 'nominal_base_y': 'nominal_base_y',
            'nominal_base_z': 'nominal_base_z', 'nominal_base_a': 'nominal_base_a',
            'nominal_base_b': 'nominal_base_b', 'nominal_base_c': 'nominal_base_c',
        }
        for key, field in field_map.items():
            if key in data:
                setattr(s, field, data[key])
        if 'dist_coeffs' in data:
            s.dist_coeffs_json = json.dumps(data['dist_coeffs'])
        if 'capture_joint_pos' in data:
            s.capture_joint_pos_json = json.dumps(data['capture_joint_pos'])
        if 'hand_eye_matrix' in data:
            s.hand_eye_matrix_json = json.dumps(data['hand_eye_matrix'])
        s.save()
        log_event('settings', 'System settings updated', level='info',
                  details={'fields': list(data.keys())})
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


# ── Camera API ────────────────────────────────────────────────

@csrf_exempt
@require_POST
def api_camera_open(request):
    vision = VisionService()
    settings = SystemSettings.get_settings()
    try:
        vision.open_camera(
            index=settings.camera_index,
            width=settings.camera_width,
            height=settings.camera_height,
            fps=settings.camera_fps,
        )
        log_event('camera', f'Camera opened (index={settings.camera_index}, {settings.camera_width}x{settings.camera_height})', level='success')
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        log_event('camera', f'Camera open failed: {e}', level='error')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_camera_close(request):
    vision = VisionService()
    vision.close_camera()
    log_event('camera', 'Camera closed', level='info')
    return JsonResponse({'status': 'ok'})


@require_GET
def api_camera_status(request):
    vision = VisionService()
    return JsonResponse({'opened': vision.is_open})


# ── Robot Jog & Position API ──────────────────────────────────

@csrf_exempt
@require_POST
def api_robot_jog(request):
    """Jog robot by axis offset. Reads current pos, adds offset, moves to new pos."""
    robot = RobotService()
    data = json.loads(request.body)
    axis = data.get('axis', 'X')
    step = float(data.get('step', 1.0))
    mode = data.get('mode', 'cartesian')  # 'cartesian' or 'joint'

    try:
        if mode == 'joint':
            # Joint jog: axis = 'A1'-'A6'
            joint_idx = int(axis.replace('A', '')) - 1
            if joint_idx < 0 or joint_idx > 5:
                return JsonResponse({'status': 'error', 'message': 'Invalid joint axis'}, status=400)
            jp = robot.get_current_joint_pos()
            axes_keys = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6']
            ext_keys = ['E1', 'E2', 'E3', 'E4', 'E5', 'E6']
            robot_axes = [jp[k] for k in axes_keys]
            ext_axes = [jp[k] for k in ext_keys]
            robot_axes[joint_idx] += step
            from robot.joint_position import JointPosition
            new_jp = JointPosition(robot_axes, ext_axes)
            robot.eki.goToJointPos(new_jp)
            log_event('robot', f'Jog {axis} by {step:+.1f}deg (joint)', level='info')
            return JsonResponse({'status': 'ok', 'axis': axis, 'step': step, 'mode': 'joint'})
        else:
            # Cartesian jog: axis = 'X','Y','Z','A','B','C'
            pos = robot.get_current_cart_pos()
            axis_map = {'X': 0, 'Y': 1, 'Z': 2, 'A': 3, 'B': 4, 'C': 5}
            if axis not in axis_map:
                return JsonResponse({'status': 'error', 'message': f'Invalid axis: {axis}'}, status=400)
            frame = [pos['X'], pos['Y'], pos['Z'], pos['A'], pos['B'], pos['C']]
            frame[axis_map[axis]] += step
            robot.go_to_frame(frame)
            unit = 'mm' if axis in 'XYZ' else 'deg'
            log_event('robot', f'Jog {axis} by {step:+.1f}{unit} (cartesian)', level='info')
            return JsonResponse({'status': 'ok', 'axis': axis, 'step': step, 'mode': 'cartesian'})
    except Exception as e:
        log_event('robot', f'Jog failed: {e}', level='error')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_robot_set_speed(request):
    """Set robot speed for cartesian and/or joint moves."""
    robot = RobotService()
    data = json.loads(request.body)
    try:
        if 'cart_speed' in data:
            robot.set_cart_speed(data['cart_speed'])
        if 'joint_speed' in data:
            robot.set_joint_speed(data['joint_speed'])
        log_event('robot', f'Speed set: cart={data.get("cart_speed", "--")} joint={data.get("joint_speed", "--")}', level='info')
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@require_GET
def api_robot_position(request):
    """Get full robot position (cartesian + joints)."""
    robot = RobotService()
    if not robot.is_connected:
        return JsonResponse({'connected': False})
    try:
        cart = robot.get_current_cart_pos()
        joints = robot.get_current_joint_pos()
        return JsonResponse({
            'connected': True,
            'cartesian': cart,
            'joints': joints,
        })
    except Exception as e:
        return JsonResponse({'connected': False, 'error': str(e)})


@csrf_exempt
@require_POST
def api_teach_capture(request):
    """Read current robot joint position and save as capture position."""
    robot = RobotService()
    try:
        jp = robot.get_current_joint_pos()
        axes_keys = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6']
        ext_keys = ['E1', 'E2', 'E3', 'E4', 'E5', 'E6']
        joints = [jp[k] for k in axes_keys] + [jp[k] for k in ext_keys]

        # Save to SystemSettings as default capture position
        s = SystemSettings.get_settings()
        s.capture_joint_pos_json = json.dumps(joints)
        s.save()

        log_event('robot', f'Capture position taught from current joint pos', level='success',
                  details={'joints': joints[:6]})
        return JsonResponse({
            'status': 'ok',
            'joint_pos': joints,
            'message': 'Capture position saved from current robot position',
        })
    except Exception as e:
        log_event('robot', f'Teach capture failed: {e}', level='error')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


# ── Capture Position API ─────────────────────────────────────

@csrf_exempt
def api_capture_positions(request):
    """List (GET) or create (POST) capture positions."""
    if request.method == 'GET':
        positions = CapturePosition.objects.all()
        return JsonResponse({'positions': [p.to_dict() for p in positions]})
    elif request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({'status': 'error', 'message': 'Name required'}, status=400)

        joint_pos = data.get('joint_pos')
        if joint_pos is None:
            # Read from current robot position
            robot = RobotService()
            try:
                jp = robot.get_current_joint_pos()
                axes_keys = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6']
                ext_keys = ['E1', 'E2', 'E3', 'E4', 'E5', 'E6']
                joint_pos = [jp[k] for k in axes_keys] + [jp[k] for k in ext_keys]
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': f'Could not read robot: {e}'}, status=400)

        base_frame_id = data.get('base_frame_id')
        pos = CapturePosition.objects.create(
            name=name,
            joint_pos_json=json.dumps(joint_pos),
            base_frame_id=base_frame_id,
        )
        log_event('robot', f'Capture position "{name}" created', level='success')
        return JsonResponse({'status': 'ok', 'position': pos.to_dict()})
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


@csrf_exempt
def api_capture_position_detail(request, pk):
    """Update (PUT) or delete (DELETE) a capture position."""
    try:
        pos = CapturePosition.objects.get(pk=pk)
    except CapturePosition.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)

    if request.method == 'PUT':
        data = json.loads(request.body)
        if 'name' in data:
            pos.name = data['name'].strip()
        if 'joint_pos' in data:
            pos.joint_pos_json = json.dumps(data['joint_pos'])
        if 'base_frame_id' in data:
            pos.base_frame_id = data['base_frame_id']
        pos.save()
        return JsonResponse({'status': 'ok', 'position': pos.to_dict()})
    elif request.method == 'DELETE':
        name = pos.name
        pos.delete()
        log_event('robot', f'Capture position "{name}" deleted', level='warning')
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


@csrf_exempt
@require_POST
def api_activate_capture_position(request, pk):
    """Activate a capture position — copies its joint angles to SystemSettings."""
    try:
        pos = CapturePosition.objects.get(pk=pk)
    except CapturePosition.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)

    CapturePosition.objects.all().update(is_default=False)
    pos.is_default = True
    pos.save()

    s = SystemSettings.get_settings()
    s.capture_joint_pos_json = pos.joint_pos_json
    s.save()

    log_event('robot', f'Capture position "{pos.name}" activated', level='success')
    return JsonResponse({'status': 'ok', 'position': pos.to_dict()})


# ── Base Frame API ────────────────────────────────────────────

@csrf_exempt
def api_base_frames(request):
    """List all base frames (GET) or create a new one (POST)."""
    if request.method == 'GET':
        frames = BaseFrame.objects.all()
        return JsonResponse({
            'frames': [f.to_dict() for f in frames],
        })
    elif request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({'status': 'error', 'message': 'Name is required'}, status=400)
        if BaseFrame.objects.filter(name=name).exists():
            return JsonResponse({'status': 'error', 'message': f'Base frame "{name}" already exists'}, status=400)
        base_number = int(data.get('base_number', 1))
        if base_number < 1 or base_number > 32:
            return JsonResponse({'status': 'error', 'message': 'Base number must be 1-32'}, status=400)
        frame = BaseFrame.objects.create(
            name=name,
            base_number=base_number,
            x=float(data.get('X', 0)), y=float(data.get('Y', 0)), z=float(data.get('Z', 0)),
            a=float(data.get('A', 0)), b=float(data.get('B', 0)), c=float(data.get('C', 0)),
        )
        log_event('settings', f'Base frame "{name}" created (BASE[{base_number}])', level='success')
        return JsonResponse({'status': 'ok', 'frame': frame.to_dict()})
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


@csrf_exempt
def api_base_frame_detail(request, pk):
    """Update (PUT) or delete (DELETE) a base frame."""
    try:
        frame = BaseFrame.objects.get(pk=pk)
    except BaseFrame.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Base frame not found'}, status=404)

    if request.method == 'PUT':
        data = json.loads(request.body)
        if 'name' in data:
            new_name = data['name'].strip()
            if new_name and new_name != frame.name:
                if BaseFrame.objects.filter(name=new_name).exclude(pk=pk).exists():
                    return JsonResponse({'status': 'error', 'message': f'Name "{new_name}" already exists'}, status=400)
                frame.name = new_name
        if 'base_number' in data:
            bn = int(data['base_number'])
            if 1 <= bn <= 32:
                frame.base_number = bn
        for axis in ('X', 'Y', 'Z', 'A', 'B', 'C'):
            if axis in data:
                setattr(frame, axis.lower(), float(data[axis]))
        frame.save()
        log_event('settings', f'Base frame "{frame.name}" updated', level='info')
        return JsonResponse({'status': 'ok', 'frame': frame.to_dict()})

    elif request.method == 'DELETE':
        name = frame.name
        # Unlink from settings if active
        SystemSettings.objects.filter(active_base_frame=frame).update(active_base_frame=None)
        frame.delete()
        log_event('settings', f'Base frame "{name}" deleted', level='warning')
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


@csrf_exempt
@require_POST
def api_activate_base_frame(request, pk):
    """Activate a base frame — copies its XYZABC to nominal_base fields and sets FK."""
    try:
        frame = BaseFrame.objects.get(pk=pk)
    except BaseFrame.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Base frame not found'}, status=404)

    # Deactivate all, activate this one
    BaseFrame.objects.all().update(is_active=False)
    frame.is_active = True
    frame.save()

    # Copy XYZABC to SystemSettings nominal base
    s = SystemSettings.get_settings()
    s.nominal_base_x = frame.x
    s.nominal_base_y = frame.y
    s.nominal_base_z = frame.z
    s.nominal_base_a = frame.a
    s.nominal_base_b = frame.b
    s.nominal_base_c = frame.c
    s.active_base_frame = frame

    # Copy per-base calibration data if present
    if frame.hand_eye_matrix_json not in ('null', '', None):
        s.hand_eye_matrix_json = frame.hand_eye_matrix_json
    if frame.nominal_part_tag_json not in ('null', '', None):
        s.nominal_part_tag_json = frame.nominal_part_tag_json

    s.save()
    log_event('settings', f'Base frame "{frame.name}" activated (BASE[{frame.base_number}])', level='success')
    return JsonResponse({'status': 'ok', 'frame': frame.to_dict()})


# ── Event Log API ─────────────────────────────────────────────

@require_GET
def api_events(request):
    """Return recent event log entries. Supports ?category=&level=&limit= filters."""
    qs = EventLog.objects.all()
    category = request.GET.get('category')
    level = request.GET.get('level')
    limit = int(request.GET.get('limit', 50))
    limit = min(limit, 200)

    if category:
        qs = qs.filter(category=category)
    if level:
        qs = qs.filter(level=level)

    events = qs[:limit]
    return JsonResponse({
        'events': [e.to_dict() for e in events],
        'total': qs.count(),
    })


# ── Auto-Calibration & Repeatability API ──────────────────────

@csrf_exempt
@require_POST
def api_auto_calibration(request):
    """Run N calibration cycles, average corrections, apply best result."""
    robot = RobotService()
    vision = VisionService()
    settings = SystemSettings.get_settings()
    data = json.loads(request.body) if request.body else {}
    n_cycles = int(data.get('cycles', 3))
    n_cycles = min(max(n_cycles, 1), 20)

    results = []
    errors = []

    try:
        for i in range(n_cycles):
            try:
                # Move to capture
                joints = settings.get_capture_joint_pos()
                robot.go_to_joint_pos(joints)
                time.sleep(1.5)

                tcp_pos = robot.get_current_cart_pos()
                frame = vision.capture_averaged(n=5)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                engine = _build_engine()
                result = engine.compute_correction(gray, tcp_pos)
                results.append(result)

                # Record each cycle
                base = result['corrected_base']
                CalibrationRecord.objects.create(
                    status='success',
                    table_tag_pose_json=json.dumps(result['table_tag_pose']),
                    part_tag_pose_json=json.dumps(result['part_tag_pose']),
                    robot_pos_json=json.dumps(tcp_pos),
                    correction_x=result['correction'][0],
                    correction_y=result['correction'][1],
                    correction_z=result['correction'][2],
                    correction_a=result['correction'][3],
                    correction_b=result['correction'][4],
                    correction_c=result['correction'][5],
                    corrected_base_x=base[0], corrected_base_y=base[1],
                    corrected_base_z=base[2], corrected_base_a=base[3],
                    corrected_base_b=base[4], corrected_base_c=base[5],
                    translation_mag=result['translation_magnitude_mm'],
                    rotation_mag=result['rotation_magnitude_deg'],
                    is_dry_run=settings.dry_run_mode,
                )
            except Exception as e:
                errors.append(str(e))

        if not results:
            return JsonResponse({'status': 'error', 'message': 'All cycles failed', 'errors': errors}, status=400)

        # Average correction
        avg_correction = [0.0] * 6
        for r in results:
            for j in range(6):
                avg_correction[j] += r['correction'][j]
        avg_correction = [c / len(results) for c in avg_correction]

        # Apply average: nominal + average correction
        from services.calibration_service import kuka_abc_to_matrix, matrix_to_kuka_abc
        M_nominal = kuka_abc_to_matrix(*settings.get_nominal_base())
        # Use last corrected base as the best estimate
        final_base = results[-1]['corrected_base']

        if not settings.dry_run_mode:
            robot.set_base_data(*final_base)

        log_event('calibration',
            f'Auto-calibration: {len(results)}/{n_cycles} cycles OK, applied final correction',
            level='success',
            details={'avg_correction': avg_correction, 'n_success': len(results)})

        return JsonResponse({
            'status': 'ok',
            'cycles_total': n_cycles,
            'cycles_success': len(results),
            'errors': errors,
            'avg_correction': {k: round(v, 3) for k, v in zip(['dX','dY','dZ','dA','dB','dC'], avg_correction)},
            'final_base': {k: round(v, 3) for k, v in zip('XYZABC', final_base)},
            'dry_run': settings.dry_run_mode,
        })
    except Exception as e:
        log_event('calibration', f'Auto-calibration failed: {e}', level='error')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_repeatability_test(request):
    """Run N detect-only cycles (no movement) to measure detection repeatability."""
    vision = VisionService()
    data = json.loads(request.body) if request.body else {}
    n_cycles = int(data.get('cycles', 10))
    n_cycles = min(max(n_cycles, 2), 50)

    measurements = []
    try:
        engine = _build_engine()
        for _ in range(n_cycles):
            frame = vision.capture_frame()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            result = engine.detect_tags(gray)

            if result['table_found'] and result['part_found']:
                T_table = result['table_tag']
                T_part = result['part_tag']
                T_pt = np.linalg.inv(T_table) @ T_part
                measurements.append({
                    'x': float(T_pt[0, 3]), 'y': float(T_pt[1, 3]), 'z': float(T_pt[2, 3]),
                })
            time.sleep(0.1)

        if len(measurements) < 2:
            return JsonResponse({'status': 'error', 'message': f'Only {len(measurements)} successful detections'}, status=400)

        xs = [m['x'] for m in measurements]
        ys = [m['y'] for m in measurements]
        zs = [m['z'] for m in measurements]

        stats = {
            'n_samples': len(measurements),
            'n_total': n_cycles,
            'x': {'mean': round(np.mean(xs), 3), 'std': round(np.std(xs), 4), 'range': round(max(xs)-min(xs), 4)},
            'y': {'mean': round(np.mean(ys), 3), 'std': round(np.std(ys), 4), 'range': round(max(ys)-min(ys), 4)},
            'z': {'mean': round(np.mean(zs), 3), 'std': round(np.std(zs), 4), 'range': round(max(zs)-min(zs), 4)},
        }

        log_event('calibration',
            f'Repeatability test: {len(measurements)}/{n_cycles} samples, '
            f'std X={stats["x"]["std"]:.4f} Y={stats["y"]["std"]:.4f} Z={stats["z"]["std"]:.4f}mm',
            level='info')

        return JsonResponse({'status': 'ok', 'stats': stats, 'measurements': measurements})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_toggle_dry_run(request):
    """Toggle dry run mode."""
    s = SystemSettings.get_settings()
    s.dry_run_mode = not s.dry_run_mode
    s.save()
    log_event('settings', f'Dry run mode {"enabled" if s.dry_run_mode else "disabled"}',
              level='warning' if s.dry_run_mode else 'info')
    return JsonResponse({'status': 'ok', 'dry_run': s.dry_run_mode})


# ── Camera Calibration Wizard API ─────────────────────────────

@csrf_exempt
@require_POST
def api_cam_cal_detect_board(request):
    """Detect chessboard in current frame. Returns annotated image (base64)."""
    vision = VisionService()
    data = json.loads(request.body) if request.body else {}
    rows = int(data.get('rows', 9))
    cols = int(data.get('cols', 6))
    try:
        frame = vision.capture_frame()
        found, corners, display = vision.find_chessboard(frame, rows, cols)
        _, buf = cv2.imencode('.jpg', display, [cv2.IMWRITE_JPEG_QUALITY, 80])
        b64 = base64.b64encode(buf).decode('utf-8')
        return JsonResponse({
            'status': 'ok', 'found': found,
            'corners_count': len(corners) if corners is not None else 0,
            'image': b64,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_cam_cal_capture(request):
    """Capture a chessboard frame for calibration. Adds to in-memory buffer."""
    global _cam_cal_frames
    vision = VisionService()
    data = json.loads(request.body) if request.body else {}
    rows = int(data.get('rows', 9))
    cols = int(data.get('cols', 6))
    try:
        frame = vision.capture_frame()
        found, corners, _ = vision.find_chessboard(frame, rows, cols)
        if not found:
            return JsonResponse({'status': 'error', 'message': 'Chessboard not found'}, status=400)
        _cam_cal_frames.append(corners)
        log_event('camera', f'Camera cal frame {len(_cam_cal_frames)} captured', level='info')
        return JsonResponse({
            'status': 'ok',
            'frame_count': len(_cam_cal_frames),
            'message': f'Frame {len(_cam_cal_frames)} captured',
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_cam_cal_compute(request):
    """Compute camera calibration from captured frames."""
    global _cam_cal_frames
    data = json.loads(request.body) if request.body else {}
    rows = int(data.get('rows', 9))
    cols = int(data.get('cols', 6))
    square_size = float(data.get('square_size_mm', 25.0))

    if len(_cam_cal_frames) < 5:
        return JsonResponse({'status': 'error', 'message': f'Need at least 5 frames (have {len(_cam_cal_frames)})'}, status=400)

    vision = VisionService()
    settings = SystemSettings.get_settings()
    image_size = (settings.camera_width, settings.camera_height)

    try:
        result = vision.compute_camera_calibration(_cam_cal_frames, rows, cols, square_size, image_size)
        mtx = result['camera_matrix']
        dist = result['dist_coeffs']
        rms = result['rms']

        # Save record
        record = CameraCalibration.objects.create(
            fx=float(mtx[0, 0]), fy=float(mtx[1, 1]),
            cx=float(mtx[0, 2]), cy=float(mtx[1, 2]),
            dist_coeffs_json=json.dumps(dist.flatten().tolist()),
            rms_error=float(rms),
            num_poses=len(_cam_cal_frames),
            board_rows=rows, board_cols=cols,
            square_size_mm=square_size,
        )

        log_event('camera', f'Camera calibration computed: RMS={rms:.4f} from {len(_cam_cal_frames)} frames', level='success')
        _cam_cal_frames = []  # Clear buffer

        return JsonResponse({
            'status': 'ok',
            'calibration': record.to_dict(),
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_cam_cal_apply(request, pk):
    """Apply a saved camera calibration to SystemSettings."""
    try:
        cal = CameraCalibration.objects.get(pk=pk)
    except CameraCalibration.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)

    s = SystemSettings.get_settings()
    s.camera_fx = cal.fx
    s.camera_fy = cal.fy
    s.camera_cx = cal.cx
    s.camera_cy = cal.cy
    s.dist_coeffs_json = cal.dist_coeffs_json
    s.save()

    CameraCalibration.objects.all().update(is_applied=False)
    cal.is_applied = True
    cal.save()

    log_event('camera', f'Camera calibration #{cal.id} applied (RMS={cal.rms_error:.4f})', level='success')
    return JsonResponse({'status': 'ok', 'calibration': cal.to_dict()})


@require_GET
def api_cam_cal_history(request):
    """List saved camera calibrations."""
    cals = CameraCalibration.objects.all()[:20]
    return JsonResponse({'calibrations': [c.to_dict() for c in cals]})


# ── Hand-Eye Calibration Wizard API ──────────────────────────

@csrf_exempt
@require_POST
def api_hand_eye_capture(request):
    """Capture a hand-eye calibration sample (robot pose + ArUco tag pose)."""
    global _hand_eye_poses
    robot = RobotService()
    vision = VisionService()
    settings = SystemSettings.get_settings()

    try:
        # Read robot TCP position
        tcp = robot.get_current_cart_pos()
        robot_pose = [tcp['X'], tcp['Y'], tcp['Z'], tcp['A'], tcp['B'], tcp['C']]

        # Detect ArUco tag (use table tag for hand-eye)
        frame = vision.capture_averaged(n=5)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        from services.calibration_service import detect_aruco_pose
        T_tag2cam = detect_aruco_pose(
            gray, settings.table_tag_id, settings.tag_size_mm,
            settings.get_camera_matrix(), settings.get_dist_coeffs(),
            settings.aruco_dict_type
        )
        if T_tag2cam is None:
            return JsonResponse({'status': 'error', 'message': 'ArUco tag not detected'}, status=400)

        _hand_eye_poses.append({
            'robot_pose': robot_pose,
            'cam_pose': T_tag2cam.tolist(),
        })

        log_event('calibration', f'Hand-eye sample {len(_hand_eye_poses)} captured', level='info')
        return JsonResponse({
            'status': 'ok',
            'sample_count': len(_hand_eye_poses),
            'robot_pose': {k: round(v, 2) for k, v in zip('XYZABC', robot_pose)},
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_hand_eye_compute(request):
    """Compute hand-eye calibration from captured samples."""
    global _hand_eye_poses
    if len(_hand_eye_poses) < 5:
        return JsonResponse({
            'status': 'error',
            'message': f'Need at least 5 samples (have {len(_hand_eye_poses)})'
        }, status=400)

    try:
        robot_poses = [p['robot_pose'] for p in _hand_eye_poses]
        cam_poses = [p['cam_pose'] for p in _hand_eye_poses]

        T_cam2flange = compute_hand_eye(robot_poses, cam_poses)

        # Translation magnitude for sanity check
        t_mag = float(np.linalg.norm(T_cam2flange[:3, 3]))

        log_event('calibration',
            f'Hand-eye calibration computed from {len(_hand_eye_poses)} samples (t={t_mag:.1f}mm)',
            level='success')

        return JsonResponse({
            'status': 'ok',
            'matrix': T_cam2flange.tolist(),
            'translation_mm': round(t_mag, 2),
            'sample_count': len(_hand_eye_poses),
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_hand_eye_apply(request):
    """Apply computed hand-eye matrix to SystemSettings."""
    data = json.loads(request.body)
    matrix = data.get('matrix')
    if matrix is None:
        return JsonResponse({'status': 'error', 'message': 'No matrix provided'}, status=400)

    s = SystemSettings.get_settings()
    s.hand_eye_matrix_json = json.dumps(matrix)
    s.save()

    # Also save to active base frame if one exists
    if s.active_base_frame:
        s.active_base_frame.hand_eye_matrix_json = json.dumps(matrix)
        s.active_base_frame.save()

    log_event('calibration', 'Hand-eye calibration matrix applied', level='success')
    return JsonResponse({'status': 'ok'})


@csrf_exempt
@require_POST
def api_hand_eye_reset(request):
    """Reset hand-eye calibration session."""
    global _hand_eye_poses
    _hand_eye_poses = []
    return JsonResponse({'status': 'ok', 'message': 'Hand-eye session reset'})


@require_GET
def api_hand_eye_status(request):
    """Get current hand-eye calibration session status."""
    settings = SystemSettings.get_settings()
    return JsonResponse({
        'sample_count': len(_hand_eye_poses),
        'has_calibration': settings.hand_eye_matrix_json not in ('null', '', None),
        'samples': [
            {'index': i + 1, 'robot_pose': {k: round(v, 2) for k, v in zip('XYZABC', p['robot_pose'])}}
            for i, p in enumerate(_hand_eye_poses)
        ],
    })


# ── HSV Tuner API ────────────────────────────────────────────

@csrf_exempt
@require_POST
def api_hsv_preview(request):
    """Apply HSV mask to camera frame and return preview."""
    vision = VisionService()
    data = json.loads(request.body) if request.body else {}
    lower = data.get('lower', [0, 0, 0])
    upper = data.get('upper', [180, 255, 255])

    try:
        frame = vision.capture_frame()
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_np = np.array(lower, dtype=np.uint8)
        upper_np = np.array(upper, dtype=np.uint8)
        mask = cv2.inRange(hsv, lower_np, upper_np)
        result = cv2.bitwise_and(frame, frame, mask=mask)

        # Side by side: original | masked
        composite = np.hstack([frame, result])
        _, buf = cv2.imencode('.jpg', composite, [cv2.IMWRITE_JPEG_QUALITY, 75])
        b64 = base64.b64encode(buf).decode('utf-8')

        # Count non-zero pixels in mask
        pct = float(cv2.countNonZero(mask)) / (mask.shape[0] * mask.shape[1]) * 100

        return JsonResponse({
            'status': 'ok',
            'image': b64,
            'mask_percent': round(pct, 1),
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_hsv_save(request):
    """Save HSV thresholds to settings."""
    data = json.loads(request.body)
    s = SystemSettings.get_settings()
    s.hsv_lower_json = json.dumps(data.get('lower', [0, 0, 0]))
    s.hsv_upper_json = json.dumps(data.get('upper', [180, 255, 255]))
    s.save()
    log_event('settings', 'HSV thresholds saved', level='info')
    return JsonResponse({'status': 'ok'})


# ── Workspace Visualization API ──────────────────────────────

@csrf_exempt
@require_POST
def api_workspace_data(request):
    """
    Capture frame, detect tags, return 2D workspace data for visualization.
    Returns tag positions in table-tag frame (XY plane) + base frame info.
    """
    vision = VisionService()
    settings = SystemSettings.get_settings()
    try:
        frame = vision.capture_frame()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        engine = _build_engine()
        result = engine.detect_tags(gray)

        data = {
            'status': 'ok',
            'table_found': result['table_found'],
            'part_found': result['part_found'],
            'table_dist_mm': round(result['table_dist_mm'], 1),
            'part_dist_mm': round(result['part_dist_mm'], 1),
            'nominal_base': {k: v for k, v in zip('XYZABC', settings.get_nominal_base())},
        }

        if result['table_found'] and result['part_found']:
            T_table2cam = result['table_tag']
            T_part2cam = result['part_tag']
            T_part2table = np.linalg.inv(T_table2cam) @ T_part2cam

            # Part position relative to table tag (XY in mm)
            data['part_position'] = {
                'x': round(float(T_part2table[0, 3]), 2),
                'y': round(float(T_part2table[1, 3]), 2),
                'z': round(float(T_part2table[2, 3]), 2),
            }

            # Part orientation (rotation around Z axis)
            angle_z = float(np.degrees(np.arctan2(T_part2table[1, 0], T_part2table[0, 0])))
            data['part_angle_deg'] = round(angle_z, 2)

            # Part X/Y axes direction vectors for drawing coordinate frame
            data['part_axes'] = {
                'x_dir': [round(float(T_part2table[0, 0]), 4),
                          round(float(T_part2table[1, 0]), 4)],
                'y_dir': [round(float(T_part2table[0, 1]), 4),
                          round(float(T_part2table[1, 1]), 4)],
            }

            # If nominal part-to-table exists, include nominal position
            if engine.T_part2table_nominal is not None:
                T_nom = engine.T_part2table_nominal
                data['nominal_part_position'] = {
                    'x': round(float(T_nom[0, 3]), 2),
                    'y': round(float(T_nom[1, 3]), 2),
                    'z': round(float(T_nom[2, 3]), 2),
                }
                nom_angle = float(np.degrees(np.arctan2(T_nom[1, 0], T_nom[0, 0])))
                data['nominal_part_angle_deg'] = round(nom_angle, 2)
                data['nominal_part_axes'] = {
                    'x_dir': [round(float(T_nom[0, 0]), 4),
                              round(float(T_nom[1, 0]), 4)],
                    'y_dir': [round(float(T_nom[0, 1]), 4),
                              round(float(T_nom[1, 1]), 4)],
                }

                # Displacement from nominal
                data['displacement'] = {
                    'dx': round(float(T_part2table[0, 3] - T_nom[0, 3]), 2),
                    'dy': round(float(T_part2table[1, 3] - T_nom[1, 3]), 2),
                    'dz': round(float(T_part2table[2, 3] - T_nom[2, 3]), 2),
                    'dangle': round(angle_z - nom_angle, 2),
                }

        elif result['table_found']:
            # Only table tag found — report its Z distance
            data['table_only'] = True

        # Include last successful calibration result
        last_cal = CalibrationRecord.objects.filter(status='success').first()
        if last_cal and last_cal.corrected_base_x is not None:
            data['last_correction'] = {
                'dX': last_cal.correction_x, 'dY': last_cal.correction_y,
                'dZ': last_cal.correction_z, 'dA': last_cal.correction_a,
                'dB': last_cal.correction_b, 'dC': last_cal.correction_c,
            }
            data['corrected_base'] = {
                'X': last_cal.corrected_base_x, 'Y': last_cal.corrected_base_y,
                'Z': last_cal.corrected_base_z, 'A': last_cal.corrected_base_a,
                'B': last_cal.corrected_base_b, 'C': last_cal.corrected_base_c,
            }

        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


# ── Export API ────────────────────────────────────────────────

@require_GET
def api_export_csv(request):
    """Export calibration history as CSV."""
    records = CalibrationRecord.objects.all()[:500]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Timestamp', 'Status', 'dX', 'dY', 'dZ', 'dA', 'dB', 'dC',
                     'TransMag_mm', 'RotMag_deg', 'DryRun', 'Error'])
    for r in records:
        writer.writerow([
            r.id, r.timestamp.isoformat(), r.status,
            r.correction_x, r.correction_y, r.correction_z,
            r.correction_a, r.correction_b, r.correction_c,
            r.translation_mag, r.rotation_mag,
            r.is_dry_run, r.error_message,
        ])
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="calibration_history.csv"'
    log_event('system', 'Calibration data exported as CSV', level='info')
    return response


@require_GET
def api_export_xlsx(request):
    """Export calibration history as Excel."""
    try:
        import openpyxl
    except ImportError:
        return JsonResponse({'status': 'error', 'message': 'openpyxl not installed. Run: pip install openpyxl'}, status=500)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Calibration History'
    headers = ['ID', 'Timestamp', 'Status', 'dX', 'dY', 'dZ', 'dA', 'dB', 'dC',
               'TransMag_mm', 'RotMag_deg', 'DryRun', 'Error']
    ws.append(headers)

    records = CalibrationRecord.objects.all()[:500]
    for r in records:
        ws.append([
            r.id, r.timestamp.isoformat(), r.status,
            r.correction_x, r.correction_y, r.correction_z,
            r.correction_a, r.correction_b, r.correction_c,
            r.translation_mag, r.rotation_mag,
            r.is_dry_run, r.error_message,
        ])

    output = io.BytesIO()
    wb.save(output)
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="calibration_history.xlsx"'
    log_event('system', 'Calibration data exported as Excel', level='info')
    return response


# ── Backup / Restore API ─────────────────────────────────────

@require_GET
def api_backup_settings(request):
    """Download all settings as JSON backup."""
    s = SystemSettings.get_settings()
    backup = {
        'version': '1.0',
        'settings': {
            'robot_ip': s.robot_ip, 'robot_port': s.robot_port,
            'camera_index': s.camera_index, 'camera_width': s.camera_width,
            'camera_height': s.camera_height, 'camera_fps': s.camera_fps,
            'camera_fx': s.camera_fx, 'camera_fy': s.camera_fy,
            'camera_cx': s.camera_cx, 'camera_cy': s.camera_cy,
            'dist_coeffs': json.loads(s.dist_coeffs_json),
            'aruco_dict_type': s.aruco_dict_type,
            'table_tag_id': s.table_tag_id, 'part_tag_id': s.part_tag_id,
            'tag_size_mm': s.tag_size_mm,
            'capture_joint_pos': json.loads(s.capture_joint_pos_json),
            'nominal_base': s.get_nominal_base(),
            'hand_eye_matrix': json.loads(s.hand_eye_matrix_json),
            'nominal_part_tag': json.loads(s.nominal_part_tag_json),
            'max_correction_mm': s.max_correction_mm,
            'max_correction_deg': s.max_correction_deg,
            'override_percent': s.override_percent,
            'hsv_lower': json.loads(s.hsv_lower_json),
            'hsv_upper': json.loads(s.hsv_upper_json),
            'dry_run_mode': s.dry_run_mode,
        },
        'base_frames': [f.to_dict() for f in BaseFrame.objects.all()],
        'capture_positions': [p.to_dict() for p in CapturePosition.objects.all()],
    }
    content = json.dumps(backup, indent=2)
    response = HttpResponse(content, content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename="mcv_backup.json"'
    log_event('system', 'Settings backup downloaded', level='info')
    return response


@csrf_exempt
@require_POST
def api_restore_settings(request):
    """Restore settings from JSON backup."""
    try:
        data = json.loads(request.body)
        if data.get('version') != '1.0':
            return JsonResponse({'status': 'error', 'message': 'Unknown backup version'}, status=400)

        settings_data = data.get('settings', {})
        s = SystemSettings.get_settings()

        # Restore settings fields
        field_map = {
            'robot_ip': 'robot_ip', 'robot_port': 'robot_port',
            'camera_index': 'camera_index', 'camera_width': 'camera_width',
            'camera_height': 'camera_height', 'camera_fps': 'camera_fps',
            'camera_fx': 'camera_fx', 'camera_fy': 'camera_fy',
            'camera_cx': 'camera_cx', 'camera_cy': 'camera_cy',
            'aruco_dict_type': 'aruco_dict_type',
            'table_tag_id': 'table_tag_id', 'part_tag_id': 'part_tag_id',
            'tag_size_mm': 'tag_size_mm',
            'max_correction_mm': 'max_correction_mm',
            'max_correction_deg': 'max_correction_deg',
            'override_percent': 'override_percent',
            'dry_run_mode': 'dry_run_mode',
        }
        for key, field in field_map.items():
            if key in settings_data:
                setattr(s, field, settings_data[key])

        if 'dist_coeffs' in settings_data:
            s.dist_coeffs_json = json.dumps(settings_data['dist_coeffs'])
        if 'capture_joint_pos' in settings_data:
            s.capture_joint_pos_json = json.dumps(settings_data['capture_joint_pos'])
        if 'hand_eye_matrix' in settings_data:
            s.hand_eye_matrix_json = json.dumps(settings_data['hand_eye_matrix'])
        if 'nominal_part_tag' in settings_data:
            s.nominal_part_tag_json = json.dumps(settings_data['nominal_part_tag'])
        if 'nominal_base' in settings_data:
            nb = settings_data['nominal_base']
            s.nominal_base_x = nb[0]; s.nominal_base_y = nb[1]; s.nominal_base_z = nb[2]
            s.nominal_base_a = nb[3]; s.nominal_base_b = nb[4]; s.nominal_base_c = nb[5]
        if 'hsv_lower' in settings_data:
            s.hsv_lower_json = json.dumps(settings_data['hsv_lower'])
        if 'hsv_upper' in settings_data:
            s.hsv_upper_json = json.dumps(settings_data['hsv_upper'])

        s.save()
        log_event('system', 'Settings restored from backup', level='success')
        return JsonResponse({'status': 'ok', 'message': 'Settings restored successfully'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


# ── Authentication API ────────────────────────────────────────

def login_page(request):
    """Login page view."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'login.html')


@csrf_exempt
@require_POST
def api_login(request):
    """Authenticate user."""
    data = json.loads(request.body) if request.body else {}
    username = data.get('username', '')
    password = data.get('password', '')
    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        log_event('system', f'User "{username}" logged in', level='info')
        return JsonResponse({'status': 'ok', 'username': user.username})
    return JsonResponse({'status': 'error', 'message': 'Invalid credentials'}, status=401)


@require_POST
def api_logout(request):
    """Log out user."""
    username = request.user.username if request.user.is_authenticated else 'Unknown'
    logout(request)
    log_event('system', f'User "{username}" logged out', level='info')
    return JsonResponse({'status': 'ok'})


@require_GET
def api_user_info(request):
    """Get current user info."""
    if request.user.is_authenticated:
        return JsonResponse({
            'authenticated': True,
            'username': request.user.username,
            'is_staff': request.user.is_staff,
            'groups': list(request.user.groups.values_list('name', flat=True)),
        })
    return JsonResponse({'authenticated': False})


# ── Segmentation / Diagnostics API ───────────────────────────

@csrf_exempt
@require_POST
def api_segmentation_view(request):
    """
    Capture a frame and return a 2x2 diagnostic image (base64 JPEG):
    raw grayscale, CLAHE enhanced, adaptive threshold, detection overlay.
    """
    vision = VisionService()
    settings = SystemSettings.get_settings()
    try:
        frame = vision.capture_frame()
        camera_matrix = settings.get_camera_matrix()
        dist_coeffs = settings.get_dist_coeffs()
        b64_image, det_info = vision.get_segmentation_jpeg(
            frame, camera_matrix, dist_coeffs, settings.tag_size_mm,
            table_tag_id=settings.table_tag_id,
            part_tag_id=settings.part_tag_id,
            aruco_dict_type=settings.aruco_dict_type,
        )
        return JsonResponse({
            'status': 'ok',
            'image': b64_image,
            'detection': det_info,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
