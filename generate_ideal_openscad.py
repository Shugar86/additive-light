import subprocess
import os

def render_scad(scad_code, output_stl):
    scad_file = "temp.scad"
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
        "ideal_cylinder.stl": """
            $fn = 100;
            cylinder(r=20, h=40);
        """,
        "ideal_flange.stl": """
            $fn = 100;
            difference() {
                cylinder(r=30, h=10);
                for (i = [0:3]) {
                    rotate([0, 0, i * 90])
                    translate([22, 0, -1])
                    cylinder(r=3, h=12);
                }
            }
        """,
        "ideal_stepped_shaft.stl": """
            $fn = 100;
            cylinder(r=15, h=20);
            translate([0, 0, 20])
            cylinder(r=10, h=30);
        """,
        "ideal_bracket_2.5d.stl": """
            $fn = 100;
            difference() {
                // Base
                translate([-30, -20, 0])
                cube([60, 40, 10]);
                
                // 2 corner holes
                translate([20, 10, -1])
                cylinder(r=5, h=12);
                translate([-20, -10, -1])
                cylinder(r=5, h=12);
                
                // central pocket
                translate([0, 0, 5])
                cylinder(r=15, h=6);
            }
        """,
        "ideal_helical_gear.stl": """
            $fn = 50;
            module gear_tooth() {
                linear_extrude(height=20, twist=30, slices=20)
                polygon(points=[[0,0], [8,2], [8,8], [2,8]]);
            }
            for (i = [0:11]) {
                rotate([0, 0, i * 30])
                gear_tooth();
            }
            cylinder(r=6, h=20);
        """,
        "ideal_nema17_mount.stl": """
            $fn = 60;
            difference() {
                // Main plate
                translate([-21, -21, 0])
                cube([42, 42, 5]);
                
                // Center hole for motor boss
                translate([0, 0, -1])
                cylinder(r=11.5, h=7);
                
                // 4 mounting holes
                for (x = [-15.5, 15.5]) {
                    for (y = [-15.5, 15.5]) {
                        translate([x, y, -1])
                        cylinder(r=1.75, h=7);
                    }
                }
                
                // Weight reduction slots
                for (i = [0:3]) {
                    rotate([0, 0, i * 90 + 45])
                    translate([18, 0, -1])
                    cube([10, 20, 7], center=true);
                }
            }
        """,
        "ideal_lattice_block.stl": """
            $fn = 20;
            module cell() {
                difference() {
                    cube([10, 10, 10], center=true);
                    sphere(r=6);
                }
            }
            for (x = [0, 10, 20]) {
                for (y = [0, 10, 20]) {
                    for (z = [0, 10, 20]) {
                        translate([x, y, z])
                        cell();
                    }
                }
            }
        """,
        "ideal_heat_sink.stl": """
            $fn = 40;
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
    
    print(f"\nDone! Ideal dataset generated in {output_dir}")
