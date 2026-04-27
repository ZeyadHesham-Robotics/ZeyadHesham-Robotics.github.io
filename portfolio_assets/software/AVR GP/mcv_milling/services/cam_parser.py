"""Parse KRL .src files exported from EncyCAM to extract metadata."""

import re


def parse_krl_src(content):
    """
    Parse a KRL .src file. Returns dict with program_name, point_count, motion_types, is_valid.
    """
    result = {
        'program_name': None,
        'point_count': 0,
        'motion_types': {'PTP': 0, 'LIN': 0, 'CIRC': 0},
        'is_valid': False,
        'errors': [],
    }

    lines = content.split('\n')

    for line in lines:
        stripped = line.strip()
        match = re.match(r'DEF\s+(\w+)\s*\(', stripped, re.IGNORECASE)
        if match:
            result['program_name'] = match.group(1)
            break

    if not result['program_name']:
        result['errors'].append('No DEF statement found')
        return result

    motion_pattern = re.compile(r'\b(PTP|LIN|CIRC)\s+', re.IGNORECASE)
    for line in lines:
        match = motion_pattern.search(line.strip())
        if match:
            motion_type = match.group(1).upper()
            result['motion_types'][motion_type] = result['motion_types'].get(motion_type, 0) + 1
            result['point_count'] += 1

    has_end = any(line.strip().upper() == 'END' for line in lines)
    if not has_end:
        result['errors'].append('No END statement found')

    result['is_valid'] = (
        result['program_name'] is not None
        and result['point_count'] > 0
        and has_end
        and len(result['errors']) == 0
    )

    return result
