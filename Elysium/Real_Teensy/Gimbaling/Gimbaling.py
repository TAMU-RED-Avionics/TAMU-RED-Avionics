# Gimbaling.py — single-circle trajectory with diagonal in/out (no circle retrace)

import math
import matplotlib.pyplot as plt
import numpy as np

# =========================
# Configuration
# =========================
STEP_SIZE = 0.206   # Roll-phase angular resolution in degrees (for the circle sweep)
TARGET_ANGLE = 5.0  # Circle radius in pitch/yaw degrees
ALPHA_STEP = 0.018  # Hardware alpha quantization step in degrees

# Mechanical system parameters (all in inches)
a = 3.0
b = 17.48
c = 8.0
d = 15.4
h = 7.10
l = 4.62

# Convert to radians
target_rad = math.radians(TARGET_ANGLE)
step_rad = math.radians(STEP_SIZE)

# =========================
# Utilities
# =========================
def rad2deg(rad):
    return rad * 180.0 / math.pi

def deg2rad(deg):
    return deg * math.pi / 180.0

def round_to_step(angle_deg, step=ALPHA_STEP):
    """Round angle (deg) to nearest discrete step (deg)."""
    return round(angle_deg / step) * step

# =========================
# Linkage geometry: alpha(theta)
# =========================
def calculate_alpha(theta, a, b, c, d, h, l):
    """
    Compute linkage angle alpha for a given actuator rotation theta (radians).
    Uses xy geometry and law of cosines; returns alpha (radians).
    """
    # Planar kinematics
    x = l + d * math.cos(theta) - c * math.sin(theta)
    y = d * math.sin(theta) + c * math.cos(theta) - h
    z = math.sqrt(x**2 + y**2)

    # gamma: angle in xy-plane
    if abs(x) < 1e-12:
        gamma = math.pi/2 if y >= 0 else -math.pi/2
    else:
        gamma = math.atan2(y, x)

    # beta via law of cosines; clamp domain
    denom = 2.0 * a * z
    if abs(denom) < 1e-12:
        beta = 0.0
    else:
        arg = (b**2 - a**2 - z**2) / denom
        arg = max(-1.0, min(1.0, arg))
        beta = math.acos(arg)

    # alpha definition
    alpha = beta + gamma - math.pi/4
    return alpha

# =========================
# Inversion: theta for a target alpha (Newton–Raphson)
# =========================
def find_theta_from_alpha(target_alpha, initial_guess=0.0):
    """
    Solve f(theta) = target_alpha for theta using Newton–Raphson.
    target_alpha in radians; returns theta in radians.
    """
    theta = initial_guess
    tol = 1e-8
    max_iter = 100

    for _ in range(max_iter):
        cur = calculate_alpha(theta, a, b, c, d, h, l)
        err = cur - target_alpha
        if abs(err) < tol:
            return theta

        # Numerical derivative
        d_theta = 1e-6
        cur_plus = calculate_alpha(theta + d_theta, a, b, c, d, h, l)
        deriv = (cur_plus - cur) / d_theta

        if abs(deriv) < 1e-12:
            # Derivative too small; bail out with best-so-far
            return theta

        theta -= err / deriv

    return theta  # best effort

# =========================
# Data containers for plotting / CSV
# =========================
point_indices = []
pitch_points = []      # radians
yaw_points = []        # radians
roll_points = []       # radians
alpha_p_points = []    # deg (rounded)
alpha_y_points = []    # deg (rounded)

def record_point(traj_file, roll, pitch, yaw, index):
    """
    Store/emit one point. roll/pitch/yaw in radians.
    Alpha values are computed from pitch & yaw (rounded to ALPHA_STEP).
    """
    roll_deg  = rad2deg(roll)
    pitch_deg = rad2deg(pitch)
    yaw_deg   = rad2deg(yaw)

    # Compute alpha from pitch and yaw; quantize to hardware step
    alpha_p = calculate_alpha(pitch, a, b, c, d, h, l)
    alpha_y = calculate_alpha(yaw,   a, b, c, d, h, l)
    alpha_p_deg = round_to_step(rad2deg(alpha_p))
    alpha_y_deg = round_to_step(rad2deg(alpha_y))

    # Store for plots
    point_indices.append(index)
    roll_points.append(roll)
    pitch_points.append(pitch)
    yaw_points.append(yaw)
    alpha_p_points.append(alpha_p_deg)
    alpha_y_points.append(alpha_y_deg)

    # CSV
    traj_file.write(f"{roll_deg:.6f},{pitch_deg:.6f},{yaw_deg:.6f},{alpha_p_deg:.6f},{alpha_y_deg:.6f}\n")
    return index + 1

# =========================
# Build trajectory
# =========================
with open("Gimbal_Trajectory.csv", "w") as fcsv:
    fcsv.write("Roll(deg),Pitch(deg),Yaw(deg),Alpha_P(deg),Alpha_Y(deg)\n")

    idx = 0

    # ---- Segment 1: Diagonal approach in alpha-steps to the 45° point ----
    # Define the diagonal endpoint where pitch = yaw = target/sqrt(2)
    theta_diag = target_rad / math.sqrt(2.0)
    alpha_start = calculate_alpha(0.0,        a, b, c, d, h, l)
    alpha_end   = calculate_alpha(theta_diag, a, b, c, d, h, l)

    a_start_deg = rad2deg(alpha_start)
    a_end_deg   = rad2deg(alpha_end)
    direction   = 1 if a_end_deg > a_start_deg else -1

    alpha_steps_deg = np.arange(
        a_start_deg,
        a_end_deg + direction * ALPHA_STEP * 0.51,  # small overreach to include last step
        direction * ALPHA_STEP
    )

    current_theta_guess = 0.0
    for a_deg in alpha_steps_deg:
        a_rad = deg2rad(a_deg)
        theta_sol = find_theta_from_alpha(a_rad, current_theta_guess)
        current_theta_guess = theta_sol
        # Diagonal means pitch = yaw = theta_sol, roll = 0 here
        idx = record_point(fcsv, 0.0, theta_sol, theta_sol, idx)

    # ---- Segment 2: One full circle (returns to the same diagonal start point) ----
    # Start the circle at 45° to match the diagonal endpoint, then sweep 360°
    START_PHI_DEG = 45.0
    phi = START_PHI_DEG
    phi_end = START_PHI_DEG + 360.0 + 1e-9  # tiny epsilon to include the endpoint

    while phi <= phi_end:
        phi_rad = deg2rad(phi)
        pitch =  target_rad * math.sin(phi_rad)
        yaw   =  target_rad * math.cos(phi_rad)
        roll  =  phi_rad
        idx = record_point(fcsv, roll, pitch, yaw, idx)
        phi += STEP_SIZE

    # ---- Segment 3: Diagonal return in alpha-steps back to origin ----
    # Start near the same theta reached at the diagonal endpoint (use last diagonal theta if available)
    # We'll reuse the alpha grid in reverse to walk back to 0.
    current_theta_guess = current_theta_guess  # continue from last diagonal value
    for a_deg in alpha_steps_deg[::-1]:
        a_rad = deg2rad(a_deg)
        theta_sol = find_theta_from_alpha(a_rad, current_theta_guess)
        current_theta_guess = theta_sol
        idx = record_point(fcsv, 0.0, theta_sol, theta_sol, idx)

    # Ensure exact origin
    idx = record_point(fcsv, 0.0, 0.0, 0.0, idx)

# =========================
# Plots
# =========================
pitch_deg = [rad2deg(p) for p in pitch_points]
yaw_deg   = [rad2deg(y) for y in yaw_points]

# Time-series style plots
fig, axs = plt.subplots(3, 1, figsize=(14, 20), sharex=True)
plt.subplots_adjust(hspace=0.5)

axs[0].plot(point_indices, pitch_deg, label='Pitch')
axs[0].set_title('Pitch Angle During Gimbal Trajectory')
axs[0].set_ylabel('Angle (deg)')
axs[0].grid(True)
axs[0].legend()

axs[1].plot(point_indices, yaw_deg, label='Yaw')
axs[1].set_title('Yaw Angle During Gimbal Trajectory')
axs[1].set_ylabel('Angle (deg)')
axs[1].grid(True)
axs[1].legend()

axs[2].plot(point_indices, alpha_p_points, label='Alpha from Pitch (rounded)')
axs[2].plot(point_indices, alpha_y_points, label='Alpha from Yaw (rounded)')
axs[2].set_title('Rounded Alpha Angles During Trajectory')
axs[2].set_xlabel('Point Index')
axs[2].set_ylabel('Angle (deg)')
axs[2].grid(True)
axs[2].legend()

plt.savefig('Gimbal_Trajectory.png', dpi=300, bbox_inches='tight')
plt.show()

# Pitch vs Yaw (should trace a circle during the circle segment)
plt.figure(figsize=(10, 8))
plt.plot(pitch_deg, yaw_deg)
plt.title('Gimbal Motion Path in Pitch–Yaw Plane')
plt.xlabel('Pitch (deg)')
plt.ylabel('Yaw (deg)')
plt.grid(True)
plt.axis('equal')
plt.tight_layout()
plt.savefig('Pitch_vs_Yaw.png', dpi=300, bbox_inches='tight')
plt.show()

# Alpha comparison scatter/line
plt.figure(figsize=(10, 8))
plt.plot(alpha_p_points, alpha_y_points)
plt.title('Rounded Alpha Comparison')
plt.xlabel('Alpha from Pitch (deg)')
plt.ylabel('Alpha from Yaw (deg)')
plt.grid(True)
plt.axis('equal')
plt.tight_layout()
plt.savefig('Alpha_Comparison.png', dpi=300, bbox_inches='tight')
plt.show()
