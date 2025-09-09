def generate_pulse_pattern(devices, duty=8, freq=3, pulse_duration=500, pause_duration=500, num_pulses=3):
    commands = []
    
    for pulse_num in range(num_pulses):
        # Calculate timing for this pulse
        pulse_start_time = pulse_num * (pulse_duration + pause_duration)
        pulse_stop_time = pulse_start_time + pulse_duration
        
        # Start all devices for this pulse
        for addr in devices:
            commands.append({
                "addr": addr,
                "duty": duty,
                "freq": freq,
                "start_or_stop": 1,
                "delay_ms": pulse_start_time
            })
        
        # Stop all devices after pulse duration
        for addr in devices:
            commands.append({
                "addr": addr,
                "duty": 0,
                "freq": 0,
                "start_or_stop": 0,
                "delay_ms": pulse_stop_time
            })
    
    return commands





def generate_static_pattern(devices, duty=8, freq=3, duration=2000):
    commands = []
    
    # Start all devices immediately
    for addr in devices:
        commands.append({
            "addr": addr,
            "duty": duty,
            "freq": freq,
            "start_or_stop": 1,
            "delay_ms": 0
        })
    
    # Stop all devices after duration
    for addr in devices:
        commands.append({
            "addr": addr,
            "duty": 0,
            "freq": 0,
            "start_or_stop": 0,
            "delay_ms": duration
        })
    
    return commands