import os
import math
import colorsys

def write_cube(filename, size, transform_func):
    with open(filename, 'w') as f:
        f.write(f'TITLE "{os.path.basename(filename).replace(".cube", "")}"\n')
        f.write(f'LUT_3D_SIZE {size}\n')
        
        for b in range(size):
            for g in range(size):
                for r in range(size):
                    r_norm = r / (size - 1)
                    g_norm = g / (size - 1)
                    b_norm = b / (size - 1)
                    
                    r_out, g_out, b_out = transform_func(r_norm, g_norm, b_norm)
                    
                    # Clamp to 0..1
                    r_out = max(0.0, min(1.0, r_out))
                    g_out = max(0.0, min(1.0, g_out))
                    b_out = max(0.0, min(1.0, b_out))
                    
                    f.write(f"{r_out:.6f} {g_out:.6f} {b_out:.6f}\n")

# 1. Cinematic Teal & Orange
def transform_teal_orange(r, g, b):
    # Base contrast S-curve
    def s_curve(v):
        val = v * 2 - 1
        curved = val * 1.15 / (1 + 0.15 * abs(val))
        return (curved + 1) / 2
        
    r = s_curve(r)
    g = s_curve(g)
    b = s_curve(b)
    
    # Split toning
    r_out = r + (0.1 * math.sin(r * math.pi))  if r > 0.5 else r - (0.1 * math.sin(r * math.pi))
    g_out = g + (0.05 * math.sin(g * math.pi)) if g < 0.5 else g + (0.02 * math.sin(g * math.pi))
    b_out = b + (0.15 * math.sin(b * math.pi)) if b < 0.5 else b - (0.1 * math.sin(b * math.pi))
    
    return r_out, g_out, b_out

# 2. Vibrant Pop
def transform_vibrant_pop(r, g, b):
    def s_curve(v):
        val = v * 2 - 1
        curved = val * 1.25 / (1 + 0.25 * abs(val))
        return (curved + 1) / 2
        
    r = s_curve(r)
    g = s_curve(g)
    b = s_curve(b)
    
    # Increase saturation
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    s = min(1.0, s * 1.4)
    r_out, g_out, b_out = colorsys.hsv_to_rgb(h, s, v)
    
    return r_out, g_out, b_out

# 3. High Contrast B&W (just for fun, another preset)
def transform_bw(r, g, b):
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    val = lum * 2 - 1
    curved = val * 1.5 / (1 + 0.5 * abs(val))
    lum = (curved + 1) / 2
    return lum, lum, lum

if __name__ == "__main__":
    out_dir = r"D:\Python_Projects\captions\project\assets\luts"
    write_cube(os.path.join(out_dir, "Cinematic_Teal_Orange.cube"), 17, transform_teal_orange)
    write_cube(os.path.join(out_dir, "Vibrant_Pop.cube"), 17, transform_vibrant_pop)
    write_cube(os.path.join(out_dir, "Moody_BW.cube"), 17, transform_bw)
    print("LUTs generated successfully!")
