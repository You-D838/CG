import pygame
import sys

pygame.init()

# Window setup
WIDTH, HEIGHT = 900, 700
TOOLBAR_HEIGHT = 100
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Paint App with Shapes, Tools, Zoom, and Pan")

# Colors and constants
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
COLORS = [BLACK, (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 165, 0), (128, 0, 128)]
FPS = 60
font = pygame.font.SysFont(None, 20)

# Drawing settings
current_color = BLACK
brush_size = 5
current_tool = "pen"  # pen, brush, marker, rectangle, square, circle, ellipse, triangle, select, text
fill_shape = False

# Zoom and pan
zoom = 1.0
offset = pygame.Vector2(0, 0)
panning = False
pan_start = pygame.Vector2(0, 0)

# Layers
canvas_surface = pygame.Surface((WIDTH, HEIGHT - TOOLBAR_HEIGHT), pygame.SRCALPHA)
canvas_surface.fill(WHITE)
text_layer = pygame.Surface((WIDTH, HEIGHT - TOOLBAR_HEIGHT), pygame.SRCALPHA)

# Undo/Redo stacks
undo_stack = []
redo_stack = []

# Shapes
shapes = []
selected_shape = None
moving_shape = False
move_offset = pygame.Vector2(0, 0)

# Text input
placing_text = False
text_input = ""
text_pos = (0, 0)

# Drawing state
drawing = False
start_pos = None
last_pos = None

# Store freehand strokes separately to preserve them on canvas during shape move
freehand_strokes = []  # Each entry: (tool, color, brush_size, list of points)

class Shape:
    def __init__(self, shape_type, pos, size, color, filled):
        self.shape_type = shape_type
        self.pos = pygame.Vector2(pos)
        self.size = size if isinstance(size, tuple) else (size, size)
        self.color = color
        self.filled = filled

    def draw(self, surface, brush_size):
        rect = pygame.Rect(self.pos.x, self.pos.y, self.size[0], self.size[1])
        if self.shape_type == "rectangle":
            pygame.draw.rect(surface, self.color, rect, 0 if self.filled else brush_size)
        elif self.shape_type == "square":
            side = max(self.size)
            rect.width = rect.height = side
            pygame.draw.rect(surface, self.color, rect, 0 if self.filled else brush_size)
        elif self.shape_type == "ellipse":
            pygame.draw.ellipse(surface, self.color, rect, 0 if self.filled else brush_size)
        elif self.shape_type == "circle":
            radius = max(self.size)//2
            center = self.pos + pygame.Vector2(radius, radius)
            pygame.draw.circle(surface, self.color, center, radius, 0 if self.filled else brush_size)
        elif self.shape_type == "triangle":
            x, y = self.pos
            w, h = self.size
            points = [(x, y + h), (x + w / 2, y), (x + w, y + h)]
            pygame.draw.polygon(surface, self.color, points, 0 if self.filled else brush_size)

    def is_clicked(self, mouse_pos):
        x, y = self.pos
        mx, my = mouse_pos
        if self.shape_type in ["rectangle", "square", "ellipse"]:
            w, h = self.size
            return x <= mx <= x + w and y <= my <= y + h
        elif self.shape_type == "circle":
            radius = max(self.size)//2
            center = self.pos + pygame.Vector2(radius, radius)
            return (mx - center.x) ** 2 + (my - center.y) ** 2 <= radius ** 2
        elif self.shape_type == "triangle":
            # Approximate bounding box check
            w, h = self.size
            return x <= mx <= x + w and y <= my <= y + h
        return False

class Button:
    def __init__(self, x, y, w, h, color, text, action):
        self.rect = pygame.Rect(x, y, w, h)
        self.color = color
        self.text = text
        self.action = action

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect)
        pygame.draw.rect(surface, BLACK, self.rect, 2)
        if self.text:
            text_surf = font.render(self.text, True, BLACK)
            text_rect = text_surf.get_rect(center=self.rect.center)
            surface.blit(text_surf, text_rect)

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)

def set_tool(tool):
    global current_tool, placing_text, selected_shape, moving_shape
    current_tool = tool
    placing_text = False
    selected_shape = None
    moving_shape = False

def set_color(color):
    global current_color
    current_color = color

def toggle_fill():
    global fill_shape
    fill_shape = not fill_shape

def undo():
    if undo_stack:
        redo_stack.append(canvas_surface.copy())
        canvas_surface.blit(undo_stack.pop(), (0, 0))
        # Redraw shapes on canvas after undo to keep them
        for shape in shapes:
            shape.draw(canvas_surface, brush_size)
        # Redraw freehand strokes on canvas after undo
        redraw_freehand_strokes()

def redo():
    if redo_stack:
        undo_stack.append(canvas_surface.copy())
        canvas_surface.blit(redo_stack.pop(), (0, 0))
        # Redraw shapes on canvas after redo to keep them
        for shape in shapes:
            shape.draw(canvas_surface, brush_size)
        redraw_freehand_strokes()

def clear_canvas():
    global shapes, freehand_strokes
    canvas_surface.fill(WHITE)
    shapes.clear()
    freehand_strokes.clear()

def save_canvas():
    final_surface = canvas_surface.copy()
    final_surface.blit(text_layer, (0, 0))
    pygame.image.save(final_surface, "drawing_output.png")

def load_canvas():
    try:
        img = pygame.image.load("drawing_output.png")
        canvas_surface.blit(img, (0, 0))
    except:
        print("No saved file found.")

def redraw_freehand_strokes():
    # Draw all saved freehand strokes on canvas_surface
    for tool, color, size, points in freehand_strokes:
        if len(points) < 2:
            continue
        for i in range(len(points)-1):
            p1 = points[i]
            p2 = points[i+1]
            if tool == "pen":
                pygame.draw.line(canvas_surface, color, p1, p2, 1)
            elif tool == "brush":
                pygame.draw.circle(canvas_surface, color, (int(p2[0]), int(p2[1])), size)
            elif tool == "marker":
                marker_color = (*color[:3], 80)
                marker_surf = pygame.Surface((size*4, size*4), pygame.SRCALPHA)
                pygame.draw.circle(marker_surf, marker_color, (size*2, size*2), size*2)
                canvas_surface.blit(marker_surf, (p2[0] - size*2, p2[1] - size*2))

# Create buttons
buttons = []

for i, color in enumerate(COLORS):
    buttons.append(Button(10 + i * 45, 10, 40, 30, color, "", lambda c=color: set_color(c)))

shape_buttons = [
    ("Rectangle", "rectangle"),
    ("Square", "square"),
    ("Circle", "circle"),
    ("Ellipse", "ellipse"),
    ("Triangle", "triangle"),
]

for idx, (text, tool_name) in enumerate(shape_buttons):
    buttons.append(Button(300 + idx * 80, 10, 75, 30, (180, 180, 180), text, lambda t=tool_name: set_tool(t)))

buttons.extend([
    Button(10, 50, 60, 30, (180,180,180), "Pen", lambda: set_tool("pen")),
    Button(80, 50, 60, 30, (180,180,180), "Brush", lambda: set_tool("brush")),
    Button(150, 50, 60, 30, (180,180,180), "Marker", lambda: set_tool("marker")),
    Button(220, 50, 100, 30, (180,180,180), "Select Shape", lambda: toggle_select_tool()),
    Button(340, 50, 60, 30, (180,180,180), "Undo", undo),
    Button(410, 50, 60, 30, (180,180,180), "Redo", redo),
    Button(480, 50, 60, 30, (180,180,180), "Clear", clear_canvas),
    Button(550, 50, 60, 30, (180,180,180), "Save", save_canvas),
    Button(620, 50, 80, 30, (180,180,180), "Fill: Off", toggle_fill)
])

select_tool_active = False
def toggle_select_tool():
    global select_tool_active
    select_tool_active = not select_tool_active
    if select_tool_active:
        set_tool("select")
    else:
        set_tool("pen")

def draw_toolbar():
    pygame.draw.rect(screen, (200, 200, 200), (0, 0, WIDTH, TOOLBAR_HEIGHT))
    for btn in buttons:
        btn.draw(screen)

def draw_shape_preview(surface, shape_type, start, end):
    x1, y1 = start
    x2, y2 = end
    width = x2 - x1
    height = y2 - y1
    rect_pos = (x1, y1)
    rect_size = (width, height)
    if shape_type == "rectangle":
        pygame.draw.rect(surface, current_color, pygame.Rect(rect_pos, rect_size), 0 if fill_shape else brush_size)
    elif shape_type == "square":
        side = max(abs(width), abs(height))
        rect_size = (side if width >= 0 else -side, side if height >= 0 else -side)
        pygame.draw.rect(surface, current_color, pygame.Rect(rect_pos, rect_size), 0 if fill_shape else brush_size)
    elif shape_type == "circle":
        radius = int(((width)**2 + (height)**2)**0.5)
        pygame.draw.circle(surface, current_color, start, radius, 0 if fill_shape else brush_size)
    elif shape_type == "ellipse":
        pygame.draw.ellipse(surface, current_color, pygame.Rect(rect_pos, rect_size), 0 if fill_shape else brush_size)
    elif shape_type == "triangle":
        points = [
            (x1, y2),
            (x1 + width / 2, y1),
            (x2, y2)
        ]
        pygame.draw.polygon(surface, current_color, points, 0 if fill_shape else brush_size)

def screen_to_canvas(pos):
    """Convert screen coordinates to canvas coordinates considering zoom and offset."""
    x = (pos[0] - offset.x)
    y = (pos[1] - offset.y - TOOLBAR_HEIGHT)
    return (x / zoom, y / zoom)

def main():
    global brush_size
    global drawing, start_pos, last_pos, selected_shape, moving_shape, move_offset, zoom, offset, placing_text, text_input, text_pos

    running = True
    while running:
        clock.tick(FPS)
        screen.fill((220, 220, 220))
        mouse_pos = pygame.mouse.get_pos()
        rel_mouse = screen_to_canvas(mouse_pos)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if mouse_pos[1] <= TOOLBAR_HEIGHT:
                        for btn in buttons:
                            if btn.is_clicked(mouse_pos):
                                btn.action()
                                break
                    else:
                        if select_tool_active:
                            # Try select shape
                            for shape in reversed(shapes):
                                if shape.is_clicked(rel_mouse):
                                    selected_shape = shape
                                    moving_shape = True
                                    move_offset = pygame.Vector2(rel_mouse) - selected_shape.pos
                                    break
                        else:
                            drawing = True
                            start_pos = rel_mouse
                            last_pos = rel_mouse
                            undo_stack.append(canvas_surface.copy())
                            redo_stack.clear()
                            if current_tool in ["pen", "brush", "marker"]:
                                # Start new freehand stroke
                                freehand_strokes.append((current_tool, current_color, brush_size, [rel_mouse]))

                elif event.button == 3:
                    # Right click drag = pan
                    global panning, pan_start
                    panning = True
                    pan_start = pygame.Vector2(mouse_pos)

                elif event.button == 4:
                    # Scroll up = zoom in
                    global zoom
                    zoom = min(4, zoom * 1.1)
                elif event.button == 5:
                    # Scroll down = zoom out
                    zoom = max(0.2, zoom / 1.1)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    if moving_shape:
                        moving_shape = False
                    elif drawing:
                        end_pos = rel_mouse
                        if current_tool in ["rectangle", "square", "circle", "ellipse", "triangle"]:
                            size = (end_pos[0] - start_pos[0], end_pos[1] - start_pos[1])
                            shapes.append(Shape(current_tool, start_pos, size, current_color, fill_shape))
                            shapes[-1].draw(canvas_surface, brush_size)
                        elif current_tool in ["pen", "brush", "marker"]:
                            pass  # freehand strokes already added continuously
                        drawing = False
                        start_pos = None
                        last_pos = None
                    selected_shape = None
                elif event.button == 3:
                    panning = False

            elif event.type == pygame.MOUSEMOTION:
                if panning:
                    rel = event.rel
                    offset.x += rel[0]
                    offset.y += rel[1]
                if moving_shape and selected_shape:
                    mouse_world = screen_to_canvas(mouse_pos)
                    selected_shape.pos = mouse_world - move_offset
                    # Redraw canvas: clear, draw shapes, redraw freehand strokes
                    canvas_surface.fill(WHITE)
                    for shape in shapes:
                        shape.draw(canvas_surface, brush_size)
                    redraw_freehand_strokes()

                elif drawing and current_tool in ["pen", "brush", "marker"]:
                    pos = rel_mouse
                    if current_tool == "pen":
                        pygame.draw.line(canvas_surface, current_color, last_pos, pos, 1)
                    elif current_tool == "brush":
                        pygame.draw.circle(canvas_surface, current_color, (int(pos[0]), int(pos[1])), brush_size)
                    elif current_tool == "marker":
                        marker_color = (*current_color[:3], 80)
                        marker_surf = pygame.Surface((brush_size * 4, brush_size * 4), pygame.SRCALPHA)
                        pygame.draw.circle(marker_surf, marker_color, (brush_size * 2, brush_size * 2), brush_size * 2)
                        canvas_surface.blit(marker_surf, (pos[0] - brush_size * 2, pos[1] - brush_size * 2))
                    last_pos = pos
                    # Append point to last freehand stroke
                    if freehand_strokes:
                        freehand_strokes[-1][3].append(pos)

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    brush_size = min(100, brush_size + 1)
                elif event.key == pygame.K_DOWN:
                    brush_size = max(1, brush_size - 1)

        # Draw the toolbar background
        draw_toolbar()

        # Draw canvas with zoom and pan
        transformed_canvas = pygame.transform.rotozoom(canvas_surface, 0, zoom)
        screen.blit(transformed_canvas, (offset.x, offset.y + TOOLBAR_HEIGHT))

        # Draw shape preview if drawing shape
        if drawing and current_tool in ["rectangle", "square", "circle", "ellipse", "triangle"] and start_pos:
            mouse_world = screen_to_canvas(mouse_pos)
            preview_surface = pygame.Surface((WIDTH, HEIGHT - TOOLBAR_HEIGHT), pygame.SRCALPHA)
            draw_shape_preview(preview_surface, current_tool, start_pos, mouse_world)
            transformed_preview = pygame.transform.rotozoom(preview_surface, 0, zoom)
            screen.blit(transformed_preview, (offset.x, offset.y + TOOLBAR_HEIGHT))

        # Draw text layer
        transformed_text = pygame.transform.rotozoom(text_layer, 0, zoom)
        screen.blit(transformed_text, (offset.x, offset.y + TOOLBAR_HEIGHT))

        # Draw brush size indicator circle at cursor if pen/brush/marker selected and not drawing shapes or selecting
        if current_tool in ["pen", "brush", "marker"] and not drawing and not moving_shape:
            cursor_pos = mouse_pos
            if current_tool == "pen":
                pygame.draw.circle(screen, current_color, cursor_pos, 2, 1)
            elif current_tool == "brush":
                pygame.draw.circle(screen, current_color, cursor_pos, brush_size, 1)
            elif current_tool == "marker":
                marker_color = (*current_color[:3], 80)
                s = pygame.Surface((brush_size * 4, brush_size * 4), pygame.SRCALPHA)
                pygame.draw.circle(s, marker_color, (brush_size * 2, brush_size * 2), brush_size * 2)
                screen.blit(s, (cursor_pos[0] - brush_size * 2, cursor_pos[1] - brush_size * 2))

        # Update fill toggle button text
        for btn in buttons:
            if btn.text.startswith("Fill"):
                btn.text = f"Fill: {'On' if fill_shape else 'Off'}"

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    clock = pygame.time.Clock()
    main()