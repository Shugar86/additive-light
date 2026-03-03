import subprocess
import os

def render_scad(scad_code, output_stl):
    scad_file = "temp_small.scad"
    with open(scad_file, "w") as f:
        f.write(scad_code)
    
    openscad_path = r"C:\Program Files\OpenSCAD\openscad.exe"
    try:
        subprocess.run([openscad_path, "-o", output_stl, scad_file], check=True)
        print(f"Successfully rendered: {output_stl}")
    except subprocess.CalledProcessError as e:
        print(f"Error rendering {output_stl}: {e}")
    finally:
        if os.path.exists(scad_file):
            os.remove(scad_file)

if __name__ == "__main__":
    output_dir = "benchmark_kit/ideal"
    os.makedirs(output_dir, exist_ok=True)
    
    parts = {
        "ideal_lattice_block.stl": """
            $fn = 12; // Lower res for faster rendering
            module cell() {
                difference() {
                    cube([10, 10, 10], center=true);
                    sphere(r=6);
                }
            }
            for (x = [0, 10]) { // Reduced cell count
                for (y = [0, 10]) {
                    for (z = [0, 10]) {
                        translate([x, y, z])
                        cell();
                    }
                }
            }
        """,
        "ideal_heat_sink.stl": """
            $fn = 20;
            // Base plate
            cube([50, 50, 3]);
            // Fins
            for (i = [0:9]) {
                translate([i * 5 + 1, 0, 3])
                cube([2, 50, 15]);
            }
        """
    }
    
    for filename, code in parts.items():
        render_scad(code, os.path.join(output_dir, filename))
    
    print(f"\nDone with extra parts!")
