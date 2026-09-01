def make_prose(attr, op, val, action_t, action_f):
    op_map = {
        '<=': 'less than or equal to',
        '>=': 'greater than or equal to',
        '<': 'strictly less than',
        '>': 'strictly greater than',
        '==': 'exactly'
    }
    op_str = op_map.get(op, op)
    return f"If {attr} is {op_str} {val}, then the action must be {action_t}. Otherwise, if it does not meet this condition, the action must be {action_f}."

def render_constraint(constraint_str, action_t, action_f):
    parts = constraint_str.split(' ')
    attr = parts[0]
    op = parts[1]
    val = parts[2].strip("'")
    return make_prose(attr, op, val, action_t, action_f)
