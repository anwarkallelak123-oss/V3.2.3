"""Session settings and comparison review logic."""
import hashlib
import json
import math

import numpy as np

from engine import analyze


def field_id(*parts):
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()[:24]


class StudyFields:
    """Keep project widget values available while switching projects in a session."""

    def __init__(self, state, fingerprint):
        self.state = state
        self.prefix = f'study_field_{fingerprint}_'
        self.draft_key = f'study_draft_{fingerprint}'
        self.defaults = state.get(self.draft_key, {}).copy()

    def value(self, field, default):
        return self.state.get(self.prefix + field, self.defaults.get(field, default))

    def widget(self, widget, label, field, default, *, options=None, **kwargs):
        key = self.prefix + field
        value = self.defaults.get(field, default)
        if options is not None:
            options = list(options)
        if not self._valid(value, default, options, kwargs):
            value = default
        # The reference choices and multiselect options can change after an
        # upstream edit. Revalidate both session defaults and live widget values.
        if key in self.state and not self._valid(self.state[key], default, options, kwargs):
            previous = self.state[key]
            del self.state[key]
            if isinstance(default, list) and isinstance(previous, list):
                value = [item for item in previous if item in options]
        if isinstance(default, float):
            value = float(value)
        if options is None:
            selected = widget(label, value=value, key=key, **kwargs)
        elif isinstance(default, list):
            selected = widget(label, options, default=value, key=key, **kwargs)
        else:
            selected = widget(label, options, index=options.index(value), key=key, **kwargs)
        if self.draft_key not in self.state:
            self.state[self.draft_key] = {}
        self.state[self.draft_key][field] = selected
        return selected

    @staticmethod
    def _valid(value, default, options, kwargs):
        if isinstance(default, list):
            return isinstance(value, list) and all(item in options for item in value) and len(set(value)) == len(value)
        if isinstance(default, float):
            return (
                type(value) in (int, float)
                and abs(value) < 1e100
                and math.isfinite(value)
                and kwargs.get('min_value', -math.inf) <= value <= kwargs.get('max_value', math.inf)
            )
        return type(value) is type(default) and (options is None or value in options)

def calculate(reference, test, setting, *, equal_var=True):
    method, value, _ = setting
    if method == 'Specification width percentage':
        lsl, usl, percent = value
        if usl <= lsl:
            raise ValueError('USL must exceed LSL.')
        result = analyze(reference, test, method, (usl - lsl) * percent / 100, equal_var=equal_var)
        result.update(lsl=lsl, usl=usl, spec_percent=percent)
        return result
    return analyze(reference, test, 'Manual' if method == 'Manual' else 'Calculated', value, equal_var=equal_var)


def comparison_review(plan, parameters, normalized, results, errors, unresolved, current):
    indexed = {(meta['et'], meta['endpoint']): result for meta, result in results}
    rows = []
    for pair in plan:
        ref, test = pair['reference'], pair['test']
        for parameter in parameters or [None]:
            key = (pair['et'], parameter)
            if not pair['enabled']:
                status, reason = 'Skipped', 'Equipment pair disabled.'
            elif parameter is None:
                status, reason = 'Missing data', 'No mapped numerical parameters.'
            elif any(np.isfinite(normalized[equipment].get(parameter, [])).sum() < 2 for equipment in (ref, test)):
                unavailable = [equipment for equipment in (ref, test)
                               if np.isfinite(normalized[equipment].get(parameter, [])).sum() < 2]
                status, reason = 'Missing data', 'Fewer than two usable observations for ' + ', '.join(unavailable)
            elif parameter not in pair['parameters']:
                status, reason = 'Skipped', 'Parameter deselected for this pair.'
            elif {(ref, parameter), (test, parameter)} & unresolved:
                status, reason = 'Pending', 'Exclusion rationale required.'
            elif key in errors:
                status, reason = 'Error', errors[key]
            elif key in indexed:
                passed = indexed[key]['passed']
                status = 'Pass' if passed else 'Fail'
                reason = '' if passed else '90% CI is not strictly inside the equivalence limits.'
            else:
                status, reason = 'Pending', 'Run analysis.' if not current else 'No result returned.'
            rows.append({
                'ET': pair['et'], 'Reference': ref, 'Test': test, 'Type': pair['kind'],
                'Location': pair['location'], 'Parameter': parameter or '—',
                'Status': status, 'Reason': reason,
            })
    return rows


def exclusion_impact(results, original, settings):
    rows = []
    for meta, after in results:
        ref, test, param = meta['reference'], meta['test'], meta['endpoint']
        before_values = [original[equipment][param] for equipment in (ref, test)]
        counts = [int(np.isfinite(values).sum()) for values in before_values]
        if counts == [after['nr'], after['nt']]:
            continue
        row = {
            'ET': meta['et'], 'Parameter': param, 'Unit': meta['unit'],
            'N ref before': counts[0], 'N test before': counts[1],
            'N ref after': after['nr'], 'N test after': after['nt'],
        }
        try:
            before = calculate(*before_values, settings[param][meta["kind"]], equal_var=after["equal_var"])
        except ValueError as exc:
            before = {}
            row['Baseline note'] = str(exc)
        for label, key in [('Difference', 'diff'), ('CI low', 'ci_low'), ('CI high', 'ci_high'), ('EAC', 'margin')]:
            row[f'{label} before'] = before.get(key)
            row[f'{label} after'] = after[key]
        row['Decision before'] = ('Pass' if before['passed'] else 'Fail') if before else 'Unavailable'
        row['Decision after'] = 'Pass' if after['passed'] else 'Fail'
        rows.append(row)
    return rows
