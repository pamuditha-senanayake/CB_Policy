def calculate_fitness(trace, policy_doc):
    events = trace.get('events', [])
    if not events:
        return None
        
    matches = 0
    constraint = policy_doc['constraint']
    action_true = policy_doc['action_true']
    action_false = policy_doc['action_false']
    
    for event in events:
        attrs = event.get('attrs', {})
        decision = event.get('decision')
        
        # Evaluate constraint
        # constraint looks like "days_since_purchase <= 30" or "tier == 'gold'"
        # We can construct a simple env
        env = dict(attrs)
        try:
            expected_bool = eval(constraint, {"__builtins__": {}}, env)
            expected_decision = action_true if expected_bool else action_false
            if decision == expected_decision:
                matches += 1
        except Exception as e:
            pass # default to no match if eval fails
            
    return float(matches) / len(events)
