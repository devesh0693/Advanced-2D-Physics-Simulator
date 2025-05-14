import customtkinter as ctk
import pygame
import pymunk
import pymunk.pygame_util
import os
import random
import math
import csv # For data logging
from datetime import datetime
import numpy as np
from PIL import Image, ImageTk

# --- Constants ---
SCREEN_WIDTH = 1000 # Increased screen width
SCREEN_HEIGHT = 600 # Physics area height
FPS = 60
TIME_STEP = 1.0 / FPS

# Collision Types
COLLISION_TYPE_PLAYER = 1
COLLISION_TYPE_COIN = 2
COLLISION_TYPE_BOUNCER = 3
COLLISION_TYPE_BOX = 4
COLLISION_TYPE_BALL = 5 # Generic ball

# --- Asset Loading ---
IMAGE_CACHE = {}
def load_image(name, scale_factor=1.0):
    if (name, scale_factor) in IMAGE_CACHE:
        return IMAGE_CACHE[(name, scale_factor)]

    fullname = os.path.join("assets", name)
    try:
        image = pygame.image.load(fullname)
    except pygame.error as message:
        print(f"Cannot load image: {name}")
        # Fallback to a default surface if image not found
        fallback_surface = pygame.Surface((50, 50))
        fallback_surface.fill((200, 200, 200))
        pygame.draw.circle(fallback_surface, (255,0,0), (25,25), 20) # Draw a red circle as placeholder
        IMAGE_CACHE[(name, scale_factor)] = (fallback_surface, fallback_surface.get_rect())
        print(f"Using fallback for {name}")
        return fallback_surface, fallback_surface.get_rect()

    if scale_factor != 1.0:
        size = image.get_size()
        new_size = (max(1, int(size[0] * scale_factor)), max(1, int(size[1] * scale_factor)))
        image = pygame.transform.scale(image, new_size)

    original_image = image.convert_alpha() if image.get_alpha() else image.convert()
    IMAGE_CACHE[(name, scale_factor)] = (original_image, original_image.get_rect())
    return original_image, original_image.get_rect()

class Camera:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.offset_x = 0
        self.offset_y = 0
        self.zoom = 1.0
        self.zoom_speed = 0.05
        self.min_zoom = 0.2
        self.max_zoom = 3.0
        self.pan_speed = 15

    def apply(self, target_pos):
        """Converts world coordinates to screen coordinates."""
        # Apply zoom first around the center of the view
        zoomed_x = target_pos[0] * self.zoom
        zoomed_y = target_pos[1] * self.zoom

        # Then apply panning offset
        screen_x = zoomed_x - self.offset_x * self.zoom + self.width / 2 * (1 - self.zoom)
        screen_y = zoomed_y - self.offset_y * self.zoom + self.height / 2 * (1 - self.zoom)
        return int(screen_x), int(screen_y)

    def apply_rect(self, target_rect):
        """Applies camera transform to a pygame.Rect."""
        # Get world position of the rect's center
        world_center_x = target_rect.centerx
        world_center_y = target_rect.centery

        # Transform center
        screen_center_x, screen_center_y = self.apply((world_center_x, world_center_y))

        # Scale width and height
        scaled_width = int(target_rect.width * self.zoom)
        scaled_height = int(target_rect.height * self.zoom)

        new_rect = pygame.Rect(0,0, scaled_width, scaled_height)
        new_rect.center = (screen_center_x, screen_center_y)
        return new_rect

    def screen_to_world(self, screen_pos):
        """Converts screen coordinates to world coordinates."""
        # Reverse panning
        world_x_no_zoom = (screen_pos[0] - self.width / 2 * (1-self.zoom) + self.offset_x * self.zoom)
        world_y_no_zoom = (screen_pos[1] - self.height / 2 * (1-self.zoom) + self.offset_y * self.zoom)

        # Reverse zoom
        world_x = world_x_no_zoom / self.zoom
        world_y = world_y_no_zoom / self.zoom
        return world_x, world_y

    def zoom_in(self):
        self.zoom = min(self.max_zoom, self.zoom + self.zoom_speed)

    def zoom_out(self):
        self.zoom = max(self.min_zoom, self.zoom - self.zoom_speed)

    def pan(self, dx, dy):
        self.offset_x += dx / self.zoom # Pan less when zoomed out
        self.offset_y += dy / self.zoom

# --- Base Entity Class ---
class Entity(pygame.sprite.Sprite):
    def __init__(self, pos, space, image_path, mass=10, radius=20, scale=0.1,
                 friction=0.7, elasticity=0.8, is_static=False, collision_type=0, body_type=pymunk.Body.DYNAMIC):
        super().__init__()
        self.space = space
        self.original_image_pristine, _ = load_image(image_path, scale) # Keep pristine for re-rotation
        self.image = self.original_image_pristine
        self.rect = self.image.get_rect(center=pos)
        self.collision_type = collision_type
        self.marked_for_removal = False

        if is_static:
            body_type = pymunk.Body.STATIC
            mass = float('inf') # Static bodies have infinite mass
            moment = float('inf')
        else:
            moment = pymunk.moment_for_circle(mass, 0, radius) # Default to circle, override in subclass if needed

        self.body = pymunk.Body(mass, moment, body_type=body_type)
        self.body.position = pos
        self.shape = pymunk.Circle(self.body, radius) # Default shape
        self.shape.mass = mass
        self.shape.friction = friction
        self.shape.elasticity = elasticity
        self.shape.collision_type = collision_type
        self.shape.parent_sprite = self

        if body_type != pymunk.Body.STATIC:
            self.space.add(self.body, self.shape)
        else:
             # For separate static bodies, add both
             self.space.add(self.body, self.shape)

    def update(self):
        if self.marked_for_removal:
            self.kill_entity()
            return

        if self.body.body_type == pymunk.Body.DYNAMIC: # Only update dynamic bodies
            self.rect.center = self.body.position # Pymunk position is world position
            # Rotate the image
            self.image = pygame.transform.rotate(self.original_image_pristine, -math.degrees(self.body.angle))
            self.rect = self.image.get_rect(center=self.rect.center)

    def draw(self, surface, camera):
        """Draws the entity transformed by the camera."""
        if not self.alive(): return # Pygame sprite group method

        # Create a new rect for camera transformation
        # self.rect.center is already in world coordinates from Pymunk body
        camera_rect = camera.apply_rect(self.rect)

        # Scale the image according to zoom and apply rotation
        scaled_width = int(self.original_image_pristine.get_width() * camera.zoom)
        scaled_height = int(self.original_image_pristine.get_height() * camera.zoom)

        if scaled_width <= 0 or scaled_height <= 0: return # Don't draw if too small

        # Scale the pristine image first, then rotate
        scaled_image = pygame.transform.scale(self.original_image_pristine, (scaled_width, scaled_height))
        rotated_image = pygame.transform.rotate(scaled_image, -math.degrees(self.body.angle))

        # Update the rect for blitting based on the rotated and scaled image
        final_rect = rotated_image.get_rect(center=camera_rect.center)
        surface.blit(rotated_image, final_rect)

    def kill_entity(self):
        if self.body in self.space.bodies:
            self.space.remove(self.body)
        if self.shape in self.space.shapes:
            self.space.remove(self.shape)
        self.kill() # Pygame sprite kill

# --- Specific Entity Classes ---
class ControllableEntity(Entity):
    def __init__(self, pos, space, image_path="ball.png", scale=0.1, mass=5, radius=15):
        super().__init__(pos, space, image_path, mass=mass, radius=radius, scale=scale,
                         collision_type=COLLISION_TYPE_PLAYER)
        self.force_magnitude = 20000

    def apply_force(self, direction_vector):
        force_x = direction_vector[0] * self.force_magnitude
        force_y = direction_vector[1] * self.force_magnitude
        self.body.apply_force_at_local_point((force_x, force_y), (0, 0))

class BoxEntity(Entity):
    def __init__(self, pos, space, image_path="box.png", scale=0.15, mass=20,
                 friction=0.8, elasticity=0.4, is_static=False):
        # For boxes, radius is not used for moment calculation directly
        super().__init__(pos, space, image_path, mass=mass, radius=1, # Placeholder radius
                         scale=scale, friction=friction, elasticity=elasticity,
                         is_static=is_static, collision_type=COLLISION_TYPE_BOX)

        # Override shape for box
        self.space.remove(self.shape) # Remove default circle shape
        actual_size = (self.original_image_pristine.get_width(), self.original_image_pristine.get_height())
        moment = pymunk.moment_for_box(mass, actual_size) if not is_static else float('inf')
        self.body.moment = moment # Update moment for box
        self.shape = pymunk.Poly.create_box(self.body, actual_size)
        self.shape.mass = mass
        self.shape.friction = friction
        self.shape.elasticity = elasticity
        self.shape.collision_type = COLLISION_TYPE_BOX # Ensure it's set
        self.shape.parent_sprite = self
        self.space.add(self.shape)

class BouncerEntity(Entity):
    def __init__(self, pos, space, image_path="bouncer.png", scale=0.2, radius=25, is_static=True):
        super().__init__(pos, space, image_path, mass=float('inf'), radius=radius, scale=scale,
                         friction=0.5, elasticity=2.0, # High elasticity
                         is_static=is_static, collision_type=COLLISION_TYPE_BOUNCER)
        self.bounce_force = 500000

    def on_collision(self, arbiter, other_shape):
        """Applies an impulse to the other object."""
        if other_shape.body.body_type == pymunk.Body.DYNAMIC:
            # Calculate impulse direction away from the bouncer
            direction = (other_shape.body.position - self.body.position).normalized()
            other_shape.body.apply_impulse_at_local_point(direction * self.bounce_force * TIME_STEP, (0,0))
            print(f"Bouncer applied impulse to {other_shape.parent_sprite.__class__.__name__}")

class CoinEntity(Entity):
    def __init__(self, pos, space, image_path="coin.png", scale=0.07, radius=10):
        super().__init__(pos, space, image_path, mass=1, radius=radius, scale=scale,
                         friction=1.0, elasticity=0.1, collision_type=COLLISION_TYPE_COIN)
        self.value = 10 # Example score value

    def on_collected(self, app_instance):
        print(f"Coin collected! Value: {self.value}")
        app_instance.score += self.value
        app_instance.log_event(f"Collected Coin: +{self.value} score")
        self.marked_for_removal = True # Mark for removal in next update cycle


class SimulationApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Advanced 2D Physics Simulator")
        self.geometry(f"{SCREEN_WIDTH}x{SCREEN_HEIGHT+150}") # Extra space for controls
        
        # Create assets directory if it doesn't exist
        if not os.path.exists("assets"):
            os.makedirs("assets")
            print("Created 'assets' directory. Please add: ball.png, box.png, bouncer.png, coin.png")

        # Initialize Pygame
        pygame.init()
        pygame.font.init()
        pygame.display.set_mode((1,1))  # Set minimal video mode to allow image loading
        
        # Data log and score initialization
        self.data_log = []
        self.score = 0
        
        # --- Create Pygame Surface for Rendering ---
        self.pygame_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.screen_font = pygame.font.SysFont("Arial", 18)
        self.clock = pygame.time.Clock()
        
        # --- Create CustomTkinter Frame for the Pygame Surface ---
        self.pygame_frame = ctk.CTkFrame(self, width=SCREEN_WIDTH, height=SCREEN_HEIGHT)
        self.pygame_frame.pack(pady=10, padx=10, fill="x")
        
        # Create Tkinter Canvas to display the Pygame Surface
        self.canvas = ctk.CTkCanvas(self.pygame_frame, width=SCREEN_WIDTH, height=SCREEN_HEIGHT, 
                                   bg="black", highlightthickness=0)
        self.canvas.pack()
        
        # --- Camera ---
        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT)
        
        # --- Pymunk Setup ---
        self.space = pymunk.Space()
        self.space.gravity = (0, 900)
        self.draw_options = pymunk.pygame_util.DrawOptions(self.pygame_surface)
        self.debug_draw_pymunk = False
        
        # --- Simulation Objects ---
        self.all_sprites = pygame.sprite.Group()
        self.entities = []
        self.controllable_object = None
        self._add_boundaries()
        
        # --- Dragging ---
        self.selected_shape_drag = None
        self.mouse_joint = None
        self.mouse_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        
        # --- Setup mouse and keyboard events ---
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)
        self.canvas.bind("<ButtonPress-3>", self.on_right_click)
        self.canvas.bind("<Motion>", self.on_mouse_motion)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)  # Windows and macOS
        self.canvas.bind("<Button-4>", lambda e: self.on_mouse_wheel(e, 1))  # Linux scroll up
        self.canvas.bind("<Button-5>", lambda e: self.on_mouse_wheel(e, -1))  # Linux scroll down
        
        # Keyboard focus
        self.canvas.focus_set()
        self.bind("<Key>", self.on_key_press)
        self.bind("<KeyRelease>", self.on_key_release)
        
        # Track pressed keys
        self.pressed_keys = set()
        
        # --- Collision Handlers Setup ---
        self._setup_collision_handlers()
        
        # --- GUI Controls Frame ---
        self.controls_frame = ctk.CTkFrame(self)
        self.controls_frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        # Left Controls (Adding Objects, Reset)
        self.left_controls_frame = ctk.CTkFrame(self.controls_frame)
        self.left_controls_frame.pack(side="left", padx=10, pady=5, fill="y")
        
        ctk.CTkLabel(self.left_controls_frame, text="Add Objects:").pack(pady=2, anchor="w")
        self.add_player_button = ctk.CTkButton(self.left_controls_frame, text="Add Player Ball", 
                                              command=self.add_player_gui)
        self.add_player_button.pack(pady=3, fill="x")
        self.add_box_button = ctk.CTkButton(self.left_controls_frame, text="Add Box", 
                                           command=lambda: self.add_object_at_mouse_center("box"))
        self.add_box_button.pack(pady=3, fill="x")
        self.add_bouncer_button = ctk.CTkButton(self.left_controls_frame, text="Add Bouncer", 
                                              command=lambda: self.add_object_at_mouse_center("bouncer"))
        self.add_bouncer_button.pack(pady=3, fill="x")
        self.add_coin_button = ctk.CTkButton(self.left_controls_frame, text="Add Coin", 
                                            command=lambda: self.add_object_at_mouse_center("coin"))
        self.add_coin_button.pack(pady=3, fill="x")
        
        ctk.CTkLabel(self.left_controls_frame, text="Actions:").pack(pady=(10,2), anchor="w")
        self.reset_button = ctk.CTkButton(self.left_controls_frame, text="Reset Simulation", 
                                         command=self.reset_simulation)
        self.reset_button.pack(pady=3, fill="x")
        self.debug_draw_button = ctk.CTkButton(self.left_controls_frame, text="Toggle Pymunk Debug Draw", 
                                              command=self.toggle_debug_draw)
        self.debug_draw_button.pack(pady=3, fill="x")
        
        # Right Controls (Sliders and Info)
        self.right_controls_frame = ctk.CTkFrame(self.controls_frame)
        self.right_controls_frame.pack(side="right", padx=10, pady=5, fill="both", expand=True)
        
        ctk.CTkLabel(self.right_controls_frame, text="Simulation Parameters:").pack(pady=2, anchor="w")
        
        # Gravity X
        ctk.CTkLabel(self.right_controls_frame, text="Gravity X:").pack(anchor="w", padx=5)
        self.gravity_x_slider = ctk.CTkSlider(self.right_controls_frame, from_=-1000, to=1000, 
                                            command=self.update_gravity_x)
        self.gravity_x_slider.set(self.space.gravity[0])
        self.gravity_x_slider.pack(fill="x", padx=5)
        
        # Gravity Y
        ctk.CTkLabel(self.right_controls_frame, text="Gravity Y:").pack(anchor="w", padx=5, pady=(5,0))
        self.gravity_y_slider = ctk.CTkSlider(self.right_controls_frame, from_=-1000, to=2000, 
                                            command=self.update_gravity_y)
        self.gravity_y_slider.set(self.space.gravity[1])
        self.gravity_y_slider.pack(fill="x", padx=5)
        
        # Info Labels
        ctk.CTkLabel(self.right_controls_frame, text="Info:").pack(pady=(10,2), anchor="w")
        self.fps_label = ctk.CTkLabel(self.right_controls_frame, text="FPS: 0")
        self.fps_label.pack(anchor="w", padx=5)
        self.obj_count_label = ctk.CTkLabel(self.right_controls_frame, text="Objects: 0")
        self.obj_count_label.pack(anchor="w", padx=5)
        self.score_label = ctk.CTkLabel(self.right_controls_frame, text="Score: 0")
        self.score_label.pack(anchor="w", padx=5)
        self.zoom_label = ctk.CTkLabel(self.right_controls_frame, text=f"Zoom: {self.camera.zoom:.2f}")
        self.zoom_label.pack(anchor="w", padx=5)
        self.pan_label = ctk.CTkLabel(self.right_controls_frame, text=f"Pan: ({self.camera.offset_x:.0f}, {self.camera.offset_y:.0f})")
        self.pan_label.pack(anchor="w", padx=5)
        
        # --- Simulation Loop ---
        self.running = True
        self.log_event("Simulation Started")
        self.after(50, self.update_simulation)  # Start the simulation loop
    
    def _add_boundaries(self):
        static_body = self.space.static_body # Use the space's built-in static body
        thickness = 50 # Make boundaries thicker and outside typical view
        # Adjusted for potential panning/zooming, make them large
        world_boundaries = [
            pymunk.Segment(static_body, (-5000, SCREEN_HEIGHT + thickness), 
                          (SCREEN_WIDTH + 5000, SCREEN_HEIGHT + thickness), thickness), # Bottom
            pymunk.Segment(static_body, (-thickness, -5000), 
                          (-thickness, SCREEN_HEIGHT + 5000), thickness),               # Left
            pymunk.Segment(static_body, (SCREEN_WIDTH + thickness, -5000), 
                          (SCREEN_WIDTH + thickness, SCREEN_HEIGHT + 5000), thickness), # Right
            pymunk.Segment(static_body, (-5000, -thickness), 
                          (SCREEN_WIDTH + 5000, -thickness), thickness)  # Top
        ]
        for bound in world_boundaries:
            bound.elasticity = 0.7
            bound.friction = 0.9
            bound.collision_type = 0 # So they don't trigger specific game logic
        self.space.add(*world_boundaries)
    
    def _setup_collision_handlers(self):
        # Player collects Coin
        h_player_coin = self.space.add_collision_handler(COLLISION_TYPE_PLAYER, COLLISION_TYPE_COIN)
        def player_collect_coin_begin(arbiter, space, data):
            player_shape, coin_shape = arbiter.shapes
            if hasattr(coin_shape, 'parent_sprite') and isinstance(coin_shape.parent_sprite, CoinEntity):
                coin_shape.parent_sprite.on_collected(self) # Pass app instance
            return True # Process collision normally (though coin will be removed)
        h_player_coin.begin = player_collect_coin_begin
        
        # Anything hits Bouncer
        h_bouncer = self.space.add_wildcard_collision_handler(COLLISION_TYPE_BOUNCER)
        def bouncer_interaction_begin(arbiter, space, data):
            bouncer_shape, other_shape = arbiter.shapes
            # Ensure bouncer_shape is the one with COLLISION_TYPE_BOUNCER
            if bouncer_shape.collision_type != COLLISION_TYPE_BOUNCER:
                bouncer_shape, other_shape = other_shape, bouncer_shape # Swap
                
            if hasattr(bouncer_shape, 'parent_sprite') and isinstance(bouncer_shape.parent_sprite, BouncerEntity):
                bouncer_shape.parent_sprite.on_collision(arbiter, other_shape)
            return True # Allow normal physical response too
        h_bouncer.begin = bouncer_interaction_begin
    
    # --- Mouse and Keyboard Event Handlers ---
    def on_mouse_press(self, event):
        if not self.running:
            return
        
        # Convert to world coordinates
        world_pos = self.camera.screen_to_world((event.x, event.y))
        
        # Query for shapes at the click point
        point_query = self.space.point_query_nearest(world_pos, 0, pymunk.ShapeFilter())
        if point_query and point_query.shape and point_query.shape.body and point_query.shape.body.body_type == pymunk.Body.DYNAMIC:
            self.selected_shape_drag = point_query.shape
            # Create a pivot joint for dragging
            pivot = pymunk.PivotJoint(self.mouse_body, self.selected_shape_drag.body,
                                      (0,0), self.selected_shape_drag.body.world_to_local(world_pos))
            pivot.max_force = 700000 * self.camera.zoom # Stronger joint
            pivot.error_bias = (1.0 - 0.15) ** 60.0
            self.space.add(pivot)
            self.mouse_joint = pivot
    
    def on_mouse_release(self, event):
        if not self.running or not self.mouse_joint:
            return
        
        if self.mouse_joint in self.space.constraints:
            self.space.remove(self.mouse_joint)
            self.mouse_joint = None
            self.selected_shape_drag = None
    
    def on_right_click(self, event):
        if not self.running:
            return
        
        # Add a ball at the click position
        self.add_object_at_click((event.x, event.y), "ball")
    
    def on_mouse_motion(self, event):
        if not self.running:
            return
        
        world_pos = self.camera.screen_to_world((event.x, event.y))
        self.mouse_body.position = world_pos
    
    def on_mouse_wheel(self, event, direction=None):
        if not self.running:
            return
        
        if direction is None:  # Windows/macOS
            if event.delta > 0:
                self.camera.zoom_in()
            else:
                self.camera.zoom_out()
        else:  # Linux
            if direction > 0:
                self.camera.zoom_in()
            else:
                self.camera.zoom_out()
    
    def on_key_press(self, event):
        self.pressed_keys.add(event.keysym.lower())
    
    def on_key_release(self, event):
        try:
            self.pressed_keys.remove(event.keysym.lower())
        except KeyError:
            pass
    
    # --- Game Functions ---
    def add_player_gui(self):
        # Adds player at current camera center
        world_pos = self.camera.screen_to_world((SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2))
        
        if self.controllable_object and self.controllable_object.alive():
            self.controllable_object.kill_entity() # Remove old one
            self.entities.remove(self.controllable_object)
            
        obj = ControllableEntity(world_pos, self.space)
        self.all_sprites.add(obj)
        self.entities.append(obj)
        self.controllable_object = obj
        self.log_event(f"Added Player at {world_pos}")
    
    def add_object_at_mouse_center(self, entity_type_str):
        # Adds object at the center of the current camera view
        world_pos = self.camera.screen_to_world((SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2))
        self._add_object_at_pos(world_pos, entity_type_str)
    
    def add_object_at_click(self, screen_pos, entity_type_str):
        world_pos = self.camera.screen_to_world(screen_pos)
        self._add_object_at_pos(world_pos, entity_type_str)
    
    def _add_object_at_pos(self, world_pos, entity_type_str):
        obj = None
        if entity_type_str == "ball":
            obj = Entity(world_pos, self.space, image_path="ball.png", scale=0.08, radius=12, 
                        collision_type=COLLISION_TYPE_BALL)
        elif entity_type_str == "box":
            obj = BoxEntity(world_pos, self.space, image_path="box.png", scale=0.1)
        elif entity_type_str == "bouncer":
            obj = BouncerEntity(world_pos, self.space, is_static=True) # Bouncers usually static
        elif entity_type_str == "coin":
            obj = CoinEntity(world_pos, self.space)
        else:
            return
            
        if obj:
            self.all_sprites.add(obj)
            self.entities.append(obj)
            self.log_event(f"Added {entity_type_str} at {world_pos}")
    
    def reset_simulation(self):
        self.log_event("Resetting simulation...")
        # Remove all dynamic objects
        for entity in list(self.entities): # Iterate over a copy
            entity.kill_entity()
            
        self.entities.clear()
        self.controllable_object = None
        self.score = 0
        self.camera.offset_x = 0
        self.camera.offset_y = 0
        self.camera.zoom = 1.0
        self.log_event("Simulation reset.")
    
    def update_gravity_x(self, value):
        self.space.gravity = (float(value), self.space.gravity[1])
        
    def update_gravity_y(self, value):
        self.space.gravity = (self.space.gravity[0], float(value))
        
    def toggle_debug_draw(self):
        self.debug_draw_pymunk = not self.debug_draw_pymunk
    
    def handle_keyboard_input(self):
        # Camera Pan
        pan_dx, pan_dy = 0, 0
        if 'left' in self.pressed_keys: pan_dx -= self.camera.pan_speed
        if 'right' in self.pressed_keys: pan_dx += self.camera.pan_speed
        if 'up' in self.pressed_keys: pan_dy -= self.camera.pan_speed
        if 'down' in self.pressed_keys: pan_dy += self.camera.pan_speed
        if pan_dx != 0 or pan_dy != 0:
            self.camera.pan(pan_dx, pan_dy)

    def update_simulation(self):
        """Main simulation loop that updates physics and rendering"""
        if not self.running:
            return

        # Process physics
        self.space.step(TIME_STEP)

        # Handle keyboard input
        self.handle_keyboard_input()

        # Move controllable object with WASD
        if self.controllable_object and self.controllable_object.alive():
            force_dir = [0, 0]
            if 'w' in self.pressed_keys: force_dir[1] -= 1
            if 's' in self.pressed_keys: force_dir[1] += 1
            if 'a' in self.pressed_keys: force_dir[0] -= 1
            if 'd' in self.pressed_keys: force_dir[0] += 1
            
            # Normalize force vector if needed
            if force_dir[0] != 0 or force_dir[1] != 0:
                length = math.sqrt(force_dir[0]**2 + force_dir[1]**2)
                force_dir[0] /= length
                force_dir[1] /= length
                self.controllable_object.apply_force(force_dir)

        # Update all sprites
        for entity in list(self.entities):  # Use a copy to allow removal during iteration
            entity.update()
            if entity.marked_for_removal and entity in self.entities:
                self.entities.remove(entity)

        # Clear the pygame surface
        self.pygame_surface.fill((30, 30, 40))  # Dark background

        # Draw grid for better spatial reference
        self._draw_grid()

        # Draw all sprites
        for entity in self.entities:
            entity.draw(self.pygame_surface, self.camera)

        # Draw debug info if enabled
        if self.debug_draw_pymunk:
            self.space.debug_draw(self.draw_options)

        # Draw HUD information
        self._draw_hud()

        # Convert pygame surface to a PhotoImage and display on canvas
        self._update_canvas()

        # Update info labels
        self.fps_label.configure(text=f"FPS: {self.clock.get_fps():.1f}")
        self.obj_count_label.configure(text=f"Objects: {len(self.entities)}")
        self.score_label.configure(text=f"Score: {self.score}")
        self.zoom_label.configure(text=f"Zoom: {self.camera.zoom:.2f}x")
        self.pan_label.configure(text=f"Pan: ({self.camera.offset_x:.0f}, {self.camera.offset_y:.0f})")

        # Tick the clock
        self.clock.tick(FPS)

        # Schedule next update
        self.after(10, self.update_simulation)

    def _draw_grid(self):
        """Draw a reference grid on the background"""
        # Base grid size
        grid_size = 100
        # Apply camera zoom
        visible_grid_size = int(grid_size * self.camera.zoom)
        
        if visible_grid_size < 20:  # Skip if grid is too small
            return
            
        # Calculate grid offset based on camera position
        offset_x = int(self.camera.offset_x * self.camera.zoom) % visible_grid_size
        offset_y = int(self.camera.offset_y * self.camera.zoom) % visible_grid_size
        
        # Draw vertical lines
        for x in range(-offset_x, SCREEN_WIDTH, visible_grid_size):
            alpha = 40  # Transparency
            pygame.draw.line(self.pygame_surface, (255, 255, 255, alpha), 
                            (x, 0), (x, SCREEN_HEIGHT), 1)
                            
        # Draw horizontal lines
        for y in range(-offset_y, SCREEN_HEIGHT, visible_grid_size):
            pygame.draw.line(self.pygame_surface, (255, 255, 255, 40), 
                            (0, y), (SCREEN_WIDTH, y), 1)

    def _draw_hud(self):
        """Draw heads-up display with game information"""
        # Draw FPS
        fps_text = self.screen_font.render(f"FPS: {self.clock.get_fps():.1f}", True, (255, 255, 255))
        self.pygame_surface.blit(fps_text, (10, 10))
        
        # Draw object count
        obj_text = self.screen_font.render(f"Objects: {len(self.entities)}", True, (255, 255, 255))
        self.pygame_surface.blit(obj_text, (10, 40))
        
        # Draw score
        score_text = self.screen_font.render(f"Score: {self.score}", True, (255, 255, 255))
        self.pygame_surface.blit(score_text, (10, 70))
        
        # Draw zoom level
        zoom_text = self.screen_font.render(f"Zoom: {self.camera.zoom:.2f}x", True, (255, 255, 255))
        self.pygame_surface.blit(zoom_text, (10, 100))
        
        # Draw controls help
        controls_text = self.screen_font.render("WASD: Move player | Arrow keys: Pan camera | Mouse wheel: Zoom", 
                                              True, (200, 200, 200))
        self.pygame_surface.blit(controls_text, (SCREEN_WIDTH - controls_text.get_width() - 10, 10))

    def _update_canvas(self):
        """Convert pygame surface to a format Tkinter can display"""
        # Convert pygame surface to a string buffer
        pygame_img_str = pygame.image.tostring(self.pygame_surface, 'RGB')
        
        # Create PIL Image from the string buffer
        pil_img = Image.frombytes('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), pygame_img_str)
        
        # Convert PIL image to a PhotoImage that Tkinter can display
        tk_img = ImageTk.PhotoImage(image=pil_img)
        
        # Save reference to prevent garbage collection
        self.tk_img = tk_img
        
        # Update canvas with the new image
        self.canvas.create_image(0, 0, image=tk_img, anchor="nw")

    def log_event(self, message):
        """Log an event with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        self.data_log.append(log_entry)
        
        # Optional: Write to CSV file
        with open('simulation_log.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([timestamp, message])

# --- Main Program ---
if __name__ == "__main__":
    app = SimulationApp()
    app.mainloop()