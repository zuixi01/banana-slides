"""Compatibility normalizer for Deckforge's structured slide description contract."""
import re


def _clean_screen_lines(text):
    if not text:
        return []
    cleaned = re.sub(
        r'^\s*---\s*(页面文字|PAGE TEXT)\s*---\s*|\s*---\s*(页面文字结束|END PAGE TEXT)\s*---\s*$',
        '', str(text), flags=re.IGNORECASE | re.MULTILINE,
    )
    return [
        re.sub(r'^#{1,6}\s*', '', line.strip())
        for line in cleaned.splitlines()
        if line.strip() and line.strip() != '---'
    ]


def normalize_description(data):
    """Keep Banana's legacy fields while adding a stable, inspectable schema."""
    if not isinstance(data, dict):
        return data
    result = dict(data)
    lines = _clean_screen_lines(result.get('text'))
    extra = result.get('extra_fields') if isinstance(result.get('extra_fields'), dict) else {}

    screen = result.get('screenText') if isinstance(result.get('screenText'), dict) else {}
    screen = {
        'title': screen.get('title') or (lines[0] if lines else ''),
        'subtitle': screen.get('subtitle') or (lines[1] if len(lines) == 2 else ''),
        'body': screen.get('body') if isinstance(screen.get('body'), list) else (lines[1:] if len(lines) > 2 else []),
        'dataLabels': screen.get('dataLabels') if isinstance(screen.get('dataLabels'), list) else [],
    }
    visual_instruction = extra.get('配图与素材') or extra.get('视觉元素') or ''
    visual_assets = result.get('visualAssets')
    if not isinstance(visual_assets, list):
        visual_assets = ([{
            'type': 'diagram', 'instruction': str(visual_instruction), 'materialIds': [],
        }] if visual_instruction else [])
    layout_source = extra.get('版式与重点') or extra.get('排版布局') or ''
    layout = result.get('layout') if isinstance(result.get('layout'), dict) else {}
    layout = {
        'structure': layout.get('structure') or str(layout_source),
        'emphasis': layout.get('emphasis') or str(extra.get('视觉焦点') or ''),
        'density': layout.get('density') if layout.get('density') in {'low', 'medium', 'high'} else 'medium',
    }
    speaker_notes = result.get('speakerNotes') or extra.get('演讲者备注') or ''
    constraints = result.get('brandConstraints')
    if not isinstance(constraints, list):
        raw_constraints = extra.get('品牌约束') or extra.get('品牌规范') or ''
        constraints = [item.strip() for item in re.split(r'[；;\n]', str(raw_constraints)) if item.strip()]
    result.update({
        'schema_version': 2,
        'screenText': screen,
        'visualAssets': visual_assets,
        'layout': layout,
        'speakerNotes': str(speaker_notes),
        'brandConstraints': constraints,
    })
    return result
