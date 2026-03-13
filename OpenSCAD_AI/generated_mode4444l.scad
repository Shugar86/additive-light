// PARAMETERS
square_size = 22;             // Size of one chess square (suitable for miniatures)
border_width = 12;            // Width of the border for notation
box_height = 35;              // Total height of the external box
wall_thickness = 3;           // Thickness of the outer walls
corner_radius = 3;            // Radius for vertical corners
drawer_clearance = 0.6;       // Gap between drawer and box for smooth sliding
text_depth = 0.8;             // Depth of engraved notation
font_size = 6;                // Size of letters/numbers
handle_depth = 15;            // How much the handle sticks out
handle_width = 40;            // Width of the drawer handle

// RENDER CONTROL
// Change this to select which part to render/export
// "assembly" = view both (drawer slightly open)
// "box" = only the outer shell (for STL export)
// "drawer" = only the inner drawer (for STL export)
part_to_show = "assembly"; 

$fn_val = 60;
$fn = $fn_val;

// DERIVED DIMENSIONS
board_active_width = square_size * 8;
total_width = board_active_width + (border_width * 2); // X axis
total_depth = board_active_width + (border_width * 2); // Y axis

// HELPER: Rounded profile for hulling
module rounded_slice(w, d, r, z) {
    translate([0, 0, z])
    hull() {
        translate([r, r, 0]) circle(r=r);
        translate([w-r, r, 0]) circle(r=r);
        translate([w-r, d-r, 0]) circle(r=r);
        translate([r, d-r, 0]) circle(r=r);
    }
}

// 1. MAIN BOX SHELL
module box_shell() {
    difference() {
        union() {
            // Main Body
            linear_extrude(box_height)
                rounded_slice(total_width, total_depth, corner_radius, 0);
            
            // Raised Dark Squares (0.6mm height)
            translate([border_width, border_width, box_height])
            for (x = [0:7]) {
                for (y = [0:7]) {
                    if ((x + y) % 2 == 1) { // Dark squares
                        translate([x*square_size, y*square_size, 0])
                        cube([square_size, square_size, 0.6]);
                    }
                }
            }
        }

        // Cutout for Drawer (Front opening is at Y=0)
        // We leave wall_thickness at the back (Y=total_depth)
        translate([wall_thickness, -1, wall_thickness])
        cube([
            total_width - (wall_thickness*2), 
            total_depth - wall_thickness + 1, // +1 to ensure cut through front face
            box_height - (wall_thickness*2)
        ]);

        // Engraving Notation
        translate([0, 0, box_height]) notation_engraving();
    }
}

// 2. NOTATION MODULE
module notation_engraving() {
    // Font settings
    font_style = "Liberation Sans:style=Bold";
    
    // Letters a-h (Bottom edge / Front)
    for (i = [0:7]) {
        translate([border_width + (i * square_size) + (square_size/2), border_width/2, -text_depth])
        linear_extrude(text_depth * 2)
        text(chr(97 + i), size=font_size, halign="center", valign="center", font=font_style);
    }

    // Letters a-h (Top edge / Back - rotated for opponent)
    for (i = [0:7]) {
        translate([border_width + (i * square_size) + (square_size/2), total_depth - border_width/2, -text_depth])
        linear_extrude(text_depth * 2)
        rotate([0,0,180])
        text(chr(97 + i), size=font_size, halign="center", valign="center", font=font_style);
    }

    // Numbers 1-8 (Left edge)
    for (i = [0:7]) {
        translate([border_width/2, border_width + (i * square_size) + (square_size/2), -text_depth])
        linear_extrude(text_depth * 2)
        text(str(i + 1), size=font_size, halign="center", valign="center", font=font_style);
    }

    // Numbers 1-8 (Right edge - rotated)
    for (i = [0:7]) {
        translate([total_width - border_width/2, border_width + (i * square_size) + (square_size/2), -text_depth])
        linear_extrude(text_depth * 2)
        rotate([0,0,180])
        text(str(i + 1), size=font_size, halign="center", valign="center", font=font_style);
    }
}

// 3. DRAWER MODULE
module drawer() {
    // Calculate available space based on shell and clearance
    dr_w = total_width - (wall_thickness*2) - (drawer_clearance*2);
    // Depth is slightly less to sit lush
    dr_d = total_depth - wall_thickness - drawer_clearance; 
    dr_h = box_height - (wall_thickness*2) - (drawer_clearance*2);
    
    union() {
        // Actual Drawer Bin
        difference() {
            // Outer shape of drawer
            translate([0, 0, 0])
            cube([dr_w, dr_d, dr_h]);
            
            // Hollow interior
            translate([wall_thickness, wall_thickness, wall_thickness])
            cube([dr_w - (wall_thickness*2), dr_d - wall_thickness + 1, dr_h]); // Open top logic implies walls
        }
        
        // Front Plate (Slightly larger to cover the gap)
        translate([-drawer_clearance, -wall_thickness, -drawer_clearance])
        cube([dr_w + (drawer_clearance*2), wall_thickness, dr_h + (drawer_clearance*2)]);
        
        // Handle (Trapezoidal profile via hull)
        translate([dr_w/2, -wall_thickness, dr_h/2])
        rotate([90, 0, 0]) // Rotate so we build out from front face
        hull() {
            // Base of handle at drawer face
            translate([-handle_width/2, -dr_h/4, 0])
            cube([handle_width, dr_h/2, 0.1]);
            
            // Tip of handle
            translate([-handle_width/2 + 5, -dr_h/4 + 2, handle_depth])
            cube([handle_width - 10, dr_h/2 - 4, 0.1]);
        }
    }
}

// LOGIC TO DISPLAY PARTS
if (part_to_show == "box") {
    box_shell();
} 
else if (part_to_show == "drawer") {
    drawer();
} 
else {
    // Assembly View
    box_shell();
    
    // Position drawer slightly open
    color("Teal")
    translate([wall_thickness + drawer_clearance, -15, wall_thickness + drawer_clearance])
    drawer();
}