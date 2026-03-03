// Dimensions of the plate
plate_width = 10;
plate_length = 30;
plate_thickness = 2;

// Hole parameters
hole_diameter = 2;
hole_spacing = 4; // Distance between centers of holes
hole_margin_min = 1.5; // Minimum distance from the edge

// Resolution
$fn_val = 60;

module perforated_plate() {
    // Calculate number of holes that fit
    // Available space = dimension - 2 * margin
    // Num holes = floor(available / spacing) + 1 roughly, but safer to loop
    
    // Calculate actual counts to center them
    count_x = floor((plate_width - 2 * hole_margin_min + hole_spacing) / hole_spacing) - 1;
    // Calculation adjustment for fencepost error logic:
    // fit_width = (n-1)*spacing.  fit_width <= width - 2*margin.
    // (n-1) <= (width - 2*margin)/spacing
    // n <= (width - 2*margin)/spacing + 1
    
    cx = floor((plate_width - 2 * hole_margin_min) / hole_spacing);
    num_x = (cx * hole_spacing + hole_diameter <= plate_width) ? cx + 1 : cx;
    
    // Simplified centering logic:
    real_count_x = floor((plate_width - 2 * hole_margin_min) / hole_spacing) + 1;
    real_count_y = floor((plate_length - 2 * hole_margin_min) / hole_spacing) + 1;

    // Check bounds so we don't overhang (sanity check)
    nx = ((real_count_x - 1) * hole_spacing > plate_width - 2*hole_margin_min) ? real_count_x -1 : real_count_x;
    ny = ((real_count_y - 1) * hole_spacing > plate_length - 2*hole_margin_min) ? real_count_y -1 : real_count_y;

    // Calculate offsets to center the pattern
    offset_x = (plate_width - (nx - 1) * hole_spacing) / 2;
    offset_y = (plate_length - (ny - 1) * hole_spacing) / 2;

    difference() {
        // Base Plate
        translate([0, 0, plate_thickness / 2])
        cube([plate_width, plate_length, plate_thickness], center = false);

        // Holes
        for (ix = [0 : max(0, nx - 1)]) {
            for (iy = [0 : max(0, ny - 1)]) {
                translate([
                    offset_x + ix * hole_spacing, 
                    offset_y + iy * hole_spacing, 
                    -1 // Start below to cut through cleanly
                ])
                cylinder(h = plate_thickness + 2, d = hole_diameter, $fn = $fn_val);
            }
        }
    }
}

// Render
perforated_plate();