import math
import matplotlib.pyplot as plt

# Sine wave min and max values (perceptible and acceptable values)
SIN_MIN = 15 
SIN_MAX = 90

# Square wave min and max values (perceptible and acceptable values)
SQUARE_MIN = 10
SQUARE_MAX = 80

#Numbers of points for the LUT, matching the number of bits.
STEPS = 32

POWER_EXPONENT = 0.85

# Generate Weber-Fechner curve
def generate_weber(val_min, val_max, steps):
    ratio = math.pow((val_max / val_min), 1.0 / (steps - 1))
    
    table = []
    current_val = val_min
    
    for i in range(steps):
        # Round to nearest integer for the LUT
        clean_val = int(round(current_val))
        
        # Hard clamp to 100% just in case
        if clean_val > 100: clean_val = 100
        
        table.append(clean_val)
        current_val *= ratio
        
    return table

# Generate Stevens' Power Law curve
# Exponent can be from 0.8-1 depending on how high intensities are perceived
def generate_power(val_min, val_max, steps, exponent):
    """
    Generate perceptually linear LUT using Stevens' Power Law
    exponent ~0.95-1.0 for vibrotactile stimuli
    """
    table = []
    for i in range(steps):
        # Linear position in perceptual space (0 to 1)
        normalized = i / (steps - 1)
        
        # Apply inverse power law to get physical stimulus
        physical = val_min + (val_max - val_min) * (normalized ** (1/exponent))
        
        table.append(int(round(physical)))
    
    return table


def plot_lut_curves(sine_lut, square_lut, sine_min, sine_max, square_min, square_max, title="Haptic Perception Curves"):
    """
    Visualize LUT curves for sine and square waveforms
    """
    plt.figure(figsize=(10, 6))
    plt.title(title)
    plt.xlabel("Input Step (0 to 31)")
    plt.ylabel("Motor Duty Cycle (%)")
    plt.grid(True, which='both', linestyle='--', alpha=0.6)

    # Plot Sine
    plt.plot(sine_lut, marker='o', label=f'SINE (Smooth): {sine_min}% to {sine_max}%', color='green')

    # Plot Square
    plt.plot(square_lut, marker='s', label=f'SQUARE (Punchy): {square_min}% to {square_max}%', color='red')

    plt.legend()
    plt.show()


# Generate the data
sine_weber_lut = generate_weber(SIN_MIN, SIN_MAX, STEPS)
square_weber_lut = generate_weber(SQUARE_MIN, SQUARE_MAX, STEPS)

sine_power_lut = generate_power(SIN_MIN, SIN_MAX, STEPS, POWER_EXPONENT)
square_power_lut = generate_power(SQUARE_MIN, SQUARE_MAX, STEPS, POWER_EXPONENT)

# Print the tables
print("Sine Weber-Fechner LUT:", sine_weber_lut)
print("Square Weber-Fechner LUT:", square_weber_lut)
print("Sine Stevens' Power Law LUT:", sine_power_lut)
print("Square Stevens' Power Law LUT:", square_power_lut)

# Plot the curves
plot_lut_curves(sine_weber_lut, square_weber_lut, SIN_MIN, SIN_MAX, SQUARE_MIN, SQUARE_MAX, title="Haptic Perception Curves (Weber-Fechner Law)")
plot_lut_curves(sine_power_lut, square_power_lut, SIN_MIN, SIN_MAX, SQUARE_MIN, SQUARE_MAX, title="Haptic Perception Curves (Stevens' Power Law)")
