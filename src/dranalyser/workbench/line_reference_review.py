"""Bind an explicitly chosen published reference to unchanged draft constants."""
import math

from .line_references import get_line_reference


def clean_reference_review(raw, review):
    """Keep legacy manual reviews unchanged; reject misleading reference labels."""
    reference_id = raw.get('reference_id', '')
    reviewed = raw.get('reference_reviewed', False)
    if not isinstance(reference_id, str) or len(reference_id) > 120:
        raise ValueError('Line reference ID must be text of at most 120 characters.')
    if type(reviewed) is not bool:
        raise ValueError('Reference applicability review must be an explicit boolean.')
    if not reference_id:
        if reviewed:
            raise ValueError('Choose a published reference before confirming its applicability.')
        return {}
    reference = get_line_reference(reference_id)
    if reference is None:
        raise ValueError('Published line reference is unavailable; enter approved values manually.')
    expected = dict(kv=reference['kv'], basis=reference['basis'],
                    **{key: reference['parameters'][key] for key in ('r1', 'x1')})
    if review['sections'] or any(
            review.get(key) != value if isinstance(value, str) else
            review.get(key) is None or not math.isclose(review[key], value, rel_tol=0, abs_tol=1e-12)
            for key, value in expected.items()):
        raise ValueError('Published reference constants changed or conflict with sections; use manual entry without a reference label.')
    return dict(reference_id=reference_id, reference_reviewed=reviewed)


def reference_provenance(review):
    """Freeze positive-sequence provenance without asserting physical measurement."""
    reference = get_line_reference(review.get('reference_id'))
    if reference is None:
        return None
    reference.update(applicability_reviewed=review.get('reference_reviewed') is True,
                     applied_parameters=['kv', 'basis', 'r1', 'x1'])
    return reference
