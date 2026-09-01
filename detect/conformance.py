def calculate_fitness(trace):
    if trace['practiced_v'] == 0:
        return 1.0
    else:
        return 0.0
